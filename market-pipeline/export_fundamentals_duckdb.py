#!/usr/bin/env python3
"""
Export the Cassandra stock_quotes fundamentals snapshot into a readable
DuckDB database, then it gets rclone-copied to Dropbox.

DuckDB layout:
  fundamentals            — full snapshot, typed, one row per (market, ticker)
  coverage_by_market      — view: % fill per column per market
  real_fundamentals       — view: rows whose values are NOT median-imputed
  screener                — view: the columns a stock screen actually uses
"""

import subprocess
import sys
from datetime import date
from pathlib import Path

import duckdb

SCRATCH = Path('/private/tmp/claude-501/-Users-umashankar/fce772c6-1b5d-436e-a845-f7e0585e07e4/scratchpad')
SNAP = SCRATCH / 'fundamentals_snapshot.csv'
DB = Path('/Users/umashankar/market-pipeline/reports_local/global_fundamentals.duckdb')

COLS = ['market', 'yf_ticker', 'pe', 'pb', 'roe', 'opm', 'roce',
        'debt_to_equity', 'current_ratio', 'asset_turnover',
        'revenue_growth', 'eps_growth', 'dividend_yield', 'eps',
        'market_cap', 'interest_cov', 'quality_score', 'piotroski',
        'sector', 'industry', 'fundamentals_source']


def export_snapshot():
    if SNAP.exists():
        SNAP.unlink()
    cmd = (f"COPY herrrickshaw.stock_quotes ({', '.join(COLS)}) "
           f"TO '{SNAP}' WITH HEADER=true;")
    res = subprocess.run(['cqlsh', 'localhost', '-e', cmd],
                         capture_output=True, text=True, timeout=600)
    if not SNAP.exists():
        print(f"COPY failed: {res.stderr[:400]}", file=sys.stderr)
        sys.exit(1)


def build_db():
    if DB.exists():
        DB.unlink()
    con = duckdb.connect(str(DB))
    con.execute(f"""
        CREATE TABLE fundamentals AS
        SELECT market,
               yf_ticker AS ticker,
               CAST(pe AS DOUBLE) AS pe,
               CAST(pb AS DOUBLE) AS pb,
               CAST(roe AS DOUBLE) AS roe,
               CAST(opm AS DOUBLE) AS opm,
               CAST(roce AS DOUBLE) AS roce,
               CAST(debt_to_equity AS DOUBLE) AS debt_to_equity,
               CAST(current_ratio AS DOUBLE) AS current_ratio,
               CAST(asset_turnover AS DOUBLE) AS asset_turnover,
               CAST(revenue_growth AS DOUBLE) AS revenue_growth_pct,
               CAST(eps_growth AS DOUBLE) AS eps_growth_pct,
               CAST(dividend_yield AS DOUBLE) AS dividend_yield_pct,
               CAST(eps AS DOUBLE) AS eps,
               CAST(market_cap AS DOUBLE) AS market_cap_local,
               CAST(interest_cov AS DOUBLE) AS interest_cov,
               CAST(quality_score AS INTEGER) AS quality_score,
               CAST(piotroski AS DOUBLE) AS piotroski,
               NULLIF(sector, '') AS sector,
               NULLIF(industry, '') AS industry,
               NULLIF(fundamentals_source, '') AS fundamentals_source
        FROM read_csv_auto('{SNAP}', header=true, all_varchar=true)
    """)
    con.execute("""
        CREATE VIEW real_fundamentals AS
        SELECT * FROM fundamentals
        WHERE fundamentals_source IS DISTINCT FROM 'median_imputed'
    """)
    con.execute("""
        CREATE VIEW screener AS
        SELECT market, ticker, pe, pb, roe, opm, debt_to_equity,
               revenue_growth_pct, dividend_yield_pct, market_cap_local,
               quality_score, sector, fundamentals_source
        FROM fundamentals
    """)
    con.execute("""
        CREATE VIEW coverage_by_market AS
        SELECT market,
               COUNT(*) AS symbols,
               ROUND(100.0 * COUNT(pe) / COUNT(*), 1) AS pe_pct,
               ROUND(100.0 * COUNT(roe) / COUNT(*), 1) AS roe_pct,
               ROUND(100.0 * COUNT(eps) / COUNT(*), 1) AS eps_pct,
               ROUND(100.0 * COUNT(market_cap_local) / COUNT(*), 1) AS mcap_pct,
               ROUND(100.0 * COUNT(sector) / COUNT(*), 1) AS sector_pct,
               SUM(CASE WHEN fundamentals_source = 'median_imputed'
                        THEN 1 ELSE 0 END) AS imputed_symbols
        FROM fundamentals GROUP BY market ORDER BY symbols DESC
    """)
    con.execute(f"""
        CREATE TABLE meta AS SELECT
          '{date.today()}' AS snapshot_date,
          'herrrickshaw.stock_quotes' AS source,
          'ratio columns null-free for india/us; median-imputed values tagged in fundamentals_source' AS note
    """)
    n = con.execute("SELECT COUNT(*) FROM fundamentals").fetchone()[0]
    print(f"DuckDB built: {DB} ({n} rows)")
    print(con.execute("SELECT * FROM coverage_by_market").df().to_string(index=False))
    con.close()


if __name__ == '__main__':
    print("Exporting Cassandra snapshot...")
    export_snapshot()
    build_db()
