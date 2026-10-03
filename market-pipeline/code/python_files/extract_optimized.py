#!/usr/bin/env python3
"""
Optimized stock data extraction for memory-constrained environments.
Streams data chunk-by-chunk to DuckDB instead of loading entire markets into RAM.

Key strategies:
  - Process 50 stocks at a time (tunable)
  - Write directly to parquet/DuckDB after each batch
  - Rate-limit API calls (1 call/50ms = 20/sec)
  - Use polars for faster ingestion where available
  - Support resume (skip already-extracted batches)

Usage:
    python extract_optimized.py --market india --batch-size 50
    python extract_optimized.py --market us --with-fundamentals
    python extract_optimized.py --all-markets
"""

import argparse
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator, Optional
import warnings

warnings.filterwarnings("ignore")

import duckdb
import pandas as pd
import requests

# Try polars first (faster), fall back to pandas
try:
    import polars as pl
    HAS_POLARS = True
except ImportError:
    HAS_POLARS = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("extract_optimized.log"),
    ],
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────

OUTPUT_DIR = Path(__file__).parent / "../../../data"
OUTPUT_DIR.mkdir(exist_ok=True)

DB_PATH = OUTPUT_DIR / "market_data.duckdb"

MARKETS = {
    'india': {
        'suffix': '.NS',
        'source': 'nse_equity_list.csv',
        'chunk_size': 50,
        'api_delay_ms': 50,  # 20 req/sec
    },
    'us': {
        'suffix': '',
        'source': 'us_list.csv',
        'chunk_size': 75,
        'api_delay_ms': 35,  # 28 req/sec
    },
    'europe': {
        'suffix': '',
        'source': 'market_data.duckdb:europe_all_list',
        'chunk_size': 50,
        'api_delay_ms': 50,
    },
    'japan': {
        'suffix': '',
        'source': 'japan_list.csv',
        'chunk_size': 40,
        'api_delay_ms': 60,  # 17 req/sec
    },
    'korea': {
        'suffix': '',
        'source': 'korea_list.csv',
        'chunk_size': 40,
        'api_delay_ms': 60,
    },
}


# ── Ticker loader ─────────────────────────────────────────────────────────

def load_tickers_from_csv(csv_path: Path) -> list[str]:
    """Load ticker list from CSV (first column assumed to be ticker)."""
    try:
        df = pd.read_csv(csv_path, usecols=[0], nrows=10000)
        return df.iloc[:, 0].dropna().unique().tolist()
    except Exception as e:
        logger.error(f"Failed to load {csv_path}: {e}")
        return []


def load_tickers_from_duckdb(table: str, market: str) -> list[str]:
    """Load ticker list from DuckDB table."""
    try:
        con = duckdb.connect(str(DB_PATH))
        # Assume table has 'yf_ticker' or 'symbol' column
        col = 'yf_ticker' if market == 'india' else 'symbol'
        result = con.execute(
            f"SELECT {col} FROM {table} WHERE market = '{market}' LIMIT 10000"
        ).fetchall()
        con.close()
        return [r[0] for r in result if r[0]]
    except Exception as e:
        logger.error(f"Failed to load {table} from DuckDB: {e}")
        return []


def load_tickers(market: str) -> list[str]:
    """Load ticker list for market using configured source."""
    cfg = MARKETS.get(market, {})
    source = cfg.get('source', '')

    if ':' in source:
        # DuckDB table reference
        table, tbl_name = source.split(':')
        return load_tickers_from_duckdb(tbl_name, market)
    else:
        # CSV file reference
        csv_path = OUTPUT_DIR / source
        return load_tickers_from_csv(csv_path)


# ── Batch streamer ───────────────────────────────────────────────────────

def batch_iterator(items: list, batch_size: int) -> Generator:
    """Yield items in batches."""
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


# ── Data fetchers ─────────────────────────────────────────────────────────

def fetch_ohlcv_batch(
    tickers: list[str],
    suffix: str,
    api_delay_ms: float = 50,
) -> list[dict]:
    """
    Fetch OHLCV for a batch via yfinance (or fallback provider).
    Returns list of dicts with columns: ticker, date, open, high, low, close, volume.
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed; skipping batch")
        return []

    yf_tickers = [f"{t}{suffix}" if suffix and not str(t).endswith(suffix) else t
                  for t in tickers]

    # Build yfinance query string
    ticker_str = ' '.join(yf_tickers)

    logger.info(f"Fetching OHLCV for {len(tickers)} tickers (batch)")

    try:
        # 1-year history
        data = yf.download(
            ticker_str,
            start=datetime.now() - timedelta(days=365),
            end=datetime.now(),
            progress=False,
            threads=True,
        )

        # Flatten multi-index columns (ticker, OHLCV)
        rows = []
        if len(tickers) == 1:
            # Single ticker: columns are [Open, High, Low, Close, Volume]
            data.index.name = 'date'
            data['ticker'] = tickers[0]
            for idx, row in data.iterrows():
                rows.append({
                    'ticker': tickers[0],
                    'date': idx.strftime('%Y-%m-%d'),
                    'open': float(row['Open']) if pd.notna(row['Open']) else None,
                    'high': float(row['High']) if pd.notna(row['High']) else None,
                    'low': float(row['Low']) if pd.notna(row['Low']) else None,
                    'close': float(row['Close']) if pd.notna(row['Close']) else None,
                    'volume': int(row['Volume']) if pd.notna(row['Volume']) else 0,
                })
        else:
            # Multiple tickers: multi-index columns
            for ticker_col in data.columns.levels[0]:
                ticker_data = data[ticker_col].copy()
                ticker_data.index.name = 'date'
                for idx, row in ticker_data.iterrows():
                    rows.append({
                        'ticker': str(ticker_col),
                        'date': idx.strftime('%Y-%m-%d'),
                        'open': float(row.get('Open', None)) if pd.notna(row.get('Open')) else None,
                        'high': float(row.get('High', None)) if pd.notna(row.get('High')) else None,
                        'low': float(row.get('Low', None)) if pd.notna(row.get('Low')) else None,
                        'close': float(row.get('Close', None)) if pd.notna(row.get('Close')) else None,
                        'volume': int(row.get('Volume', 0)) if pd.notna(row.get('Volume')) else 0,
                    })

        logger.info(f"✓ Fetched {len(rows)} rows for {len(tickers)} tickers")
        return rows

    except Exception as e:
        logger.error(f"Batch fetch failed: {e}")
        return []


# ── DuckDB writer ────────────────────────────────────────────────────────

def append_ohlcv_batch_to_db(
    market: str,
    batch_rows: list[dict],
    table_name: str = 'price_history_streaming',
) -> int:
    """Append batch of OHLCV rows to DuckDB table. Returns row count written."""
    if not batch_rows:
        return 0

    try:
        con = duckdb.connect(str(DB_PATH))

        # Create table if not exists
        con.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                market VARCHAR,
                ticker VARCHAR,
                date DATE,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert batch (DuckDB is fast at this)
        df = pd.DataFrame(batch_rows)
        df['market'] = market
        df['date'] = pd.to_datetime(df['date'])

        con.execute(f"INSERT INTO {table_name} SELECT * FROM df")
        con.commit()
        con.close()

        logger.info(f"✓ Wrote {len(batch_rows)} rows to {table_name}")
        return len(batch_rows)

    except Exception as e:
        logger.error(f"Failed to append batch to DB: {e}")
        return 0


# ── Resume tracking ──────────────────────────────────────────────────────

def load_progress(market: str, out_file: Optional[Path] = None) -> dict:
    """Load extraction progress (which batches already done)."""
    if out_file is None:
        out_file = OUTPUT_DIR / f".extract_progress_{market}.json"

    if out_file.exists():
        try:
            with open(out_file) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load progress: {e}")

    return {'market': market, 'batches_done': 0, 'total_rows': 0, 'started_at': datetime.now().isoformat()}


def save_progress(market: str, progress: dict, out_file: Optional[Path] = None):
    """Save extraction progress."""
    if out_file is None:
        out_file = OUTPUT_DIR / f".extract_progress_{market}.json"

    progress['updated_at'] = datetime.now().isoformat()
    try:
        with open(out_file, 'w') as f:
            json.dump(progress, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save progress: {e}")


# ── Main extraction loop ──────────────────────────────────────────────────

def extract_market(
    market: str,
    with_fundamentals: bool = False,
    resume: bool = True,
):
    """Extract OHLCV for a market in streaming batches."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Extracting {market.upper()} OHLCV (streaming mode)")
    logger.info(f"{'='*60}\n")

    cfg = MARKETS.get(market)
    if not cfg:
        logger.error(f"Market {market} not configured")
        return

    # Load progress
    progress = load_progress(market) if resume else {'market': market, 'batches_done': 0, 'total_rows': 0}

    # Load tickers
    tickers = load_tickers(market)
    if not tickers:
        logger.error(f"No tickers found for {market}")
        return

    logger.info(f"Loaded {len(tickers)} tickers for {market}")

    chunk_size = cfg['chunk_size']
    api_delay_ms = cfg['api_delay_ms']
    suffix = cfg['suffix']

    total_written = 0
    started = time.time()

    # Stream batches
    for batch_idx, batch in enumerate(batch_iterator(tickers, chunk_size)):
        if resume and batch_idx < progress['batches_done']:
            logger.info(f"Skipping batch {batch_idx} (already done)")
            continue

        logger.info(f"\n[Batch {batch_idx}] {len(batch)} tickers")

        # Fetch
        batch_rows = fetch_ohlcv_batch(batch, suffix, api_delay_ms)

        # Write
        written = append_ohlcv_batch_to_db(market, batch_rows)
        total_written += written

        # Update progress
        progress['batches_done'] = batch_idx + 1
        progress['total_rows'] = total_written
        save_progress(market, progress)

        # Rate limit
        time.sleep(api_delay_ms / 1000.0)

    elapsed = time.time() - started
    logger.info(f"\n✓ {market.upper()} extraction complete")
    logger.info(f"  Total rows written: {total_written}")
    logger.info(f"  Elapsed: {elapsed:.1f}s ({total_written/elapsed:.0f} rows/sec)")
    logger.info(f"  Output: {DB_PATH}")


# ── CLI ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Optimized memory-efficient stock data extraction"
    )
    parser.add_argument(
        '--market',
        choices=list(MARKETS.keys()) + ['all'],
        default='india',
        help='Market to extract (default: india)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        help='Override market default batch size'
    )
    parser.add_argument(
        '--with-fundamentals',
        action='store_true',
        help='Also fetch fundamentals (Phase 2, slower)'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        default=True,
        help='Resume from last checkpoint (default: on)'
    )
    parser.add_argument(
        '--no-resume',
        dest='resume',
        action='store_false',
        help='Start fresh (ignore checkpoints)'
    )

    args = parser.parse_args()

    markets = list(MARKETS.keys()) if args.market == 'all' else [args.market]

    for mkt in markets:
        cfg = MARKETS[mkt]
        if args.batch_size:
            cfg['chunk_size'] = args.batch_size

        extract_market(mkt, with_fundamentals=args.with_fundamentals, resume=args.resume)


if __name__ == '__main__':
    main()
