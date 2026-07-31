#!/usr/bin/env python3
"""
Bridge: Postgres market_data.global_fundamentals + ohlcv_history
        -> Cassandra herrrickshaw.stock_quotes

Uses the EXISTING warehouse (237k statement rows; sec_edgar US, dart/kr KR,
jp_master JP, eastmoney/baostock CN, screener_in IN, eu_union EU, yfinance
CA/AU/TW/HK/DE/FI/DK) instead of re-collecting via APIs.

- Latest FY per (market,ticker), src_priority breaks ties; prior FY for growth.
- Prices: latest close per ticker from ohlcv_history (local currency), used
  for pe / pb / market_cap. eps falls back to net_income/shares.
- Sanity ranges guard against unit mismatches (e.g. screener.in crores):
  implausible values are skipped, never written.
"""

import subprocess
import sys
import csv
import math
from collections import defaultdict
from pathlib import Path

import psycopg2

SCRATCH = Path('/private/tmp/claude-501/-Users-umashankar/fce772c6-1b5d-436e-a845-f7e0585e07e4/scratchpad')
SCRATCH.mkdir(parents=True, exist_ok=True)

# global_fundamentals.market -> cassandra market (order = priority on collisions)
PG_TO_CASS_MARKET = [
    ('US', 'us'), ('IN', 'india'), ('JP', 'japan'), ('KR', 'korea'),
    ('CN', 'china'), ('EU', 'europe'), ('CA', 'canada'), ('AU', 'australia'),
    ('TW', 'taiwan'), ('HK', 'hongkong'),
    ('DE', 'europe'), ('FI', 'europe'), ('DK', 'europe'),
]
# Cassandra tickers carry suffixes these Postgres tables lack
STRIP_SUFFIX_MARKETS = {'korea', 'china'}
# ohlcv_history market_name -> cassandra market
PRICE_MARKET_MAP = {'usa': 'us', 'india': 'india', 'japan': 'japan',
                    'korea': 'korea', 'europe': 'europe', 'china': 'china'}


def fnum(v):
    if v is None:
        return None
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def load_postgres_statements(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT market, ticker, fy_end, src_priority,
               revenue, ebit, net_income, equity, total_assets,
               total_liabilities, current_assets, current_liabilities,
               shares, eps, fiscal_period
        FROM global_fundamentals
        WHERE fy_end IS NOT NULL
    """)
    rows_by_key = defaultdict(list)
    for r in cur.fetchall():
        rows_by_key[(r[0], r[1])].append(r)

    def find_by_offset(rows, lat_end, lat_fp, years):
        want_fp = None
        if lat_fp.startswith('FY') and len(lat_fp) >= 6 and lat_fp[2:6].isdigit():
            want_fp = f"FY{int(lat_fp[2:6]) - years}{lat_fp[6:]}"
        for r in rows[1:]:
            if want_fp and (r[14] or '') == want_fp:
                return r
        lo, hi = 365 * years - 65, 365 * years + 65
        for r in rows[1:]:
            if lo <= (lat_end - r[2]).days <= hi:
                return r
        return None

    latest, prior, prior2 = {}, {}, {}
    for key, rows in rows_by_key.items():
        rows.sort(key=lambda r: (r[2], r[3]), reverse=True)
        latest[key] = rows[0]
        lat_end, lat_fp = rows[0][2], rows[0][14] or ''
        p1 = find_by_offset(rows, lat_end, lat_fp, 1)
        p2 = find_by_offset(rows, lat_end, lat_fp, 2)
        if p1 is not None:
            prior[key] = p1
        if p2 is not None:
            prior2[key] = p2
    return latest, prior, prior2


def load_prices(conn):
    """Latest close per (cassandra_market, bare_ticker) from ohlcv_history."""
    cur = conn.cursor()
    cur.execute("""
        SELECT m.market_name, st.ticker, o.close_price
        FROM ohlcv_history o
        JOIN stocks st ON st.stock_id = o.stock_id
        JOIN markets m ON st.market_id = m.market_id
        JOIN (SELECT stock_id, MAX(date) AS d FROM ohlcv_history GROUP BY stock_id) mx
             ON mx.stock_id = o.stock_id AND mx.d = o.date
    """)
    prices = {}
    for market_name, ticker, close in cur.fetchall():
        cass_mkt = PRICE_MARKET_MAP.get(market_name)
        c = fnum(close)
        if cass_mkt and c and c > 0:
            prices[(cass_mkt, ticker.strip())] = c
    return prices


def load_cassandra_symbols():
    out = SCRATCH / 'cass_symbols.csv'
    if not out.exists():
        cmd = f"COPY herrrickshaw.stock_quotes (market, yf_ticker, cmp) TO '{out}' WITH HEADER=true;"
        res = subprocess.run(['cqlsh', 'localhost', '-e', cmd], capture_output=True, text=True, timeout=300)
        if not out.exists():
            print(f"cqlsh COPY failed: {res.stderr[:500]}", file=sys.stderr)
            sys.exit(1)
    symbols = []
    with open(out) as f:
        for row in csv.DictReader(f):
            symbols.append((row['market'], row['yf_ticker']))
    return symbols


def in_range(v, lo, hi):
    return v is not None and lo <= v <= hi


def compute_metrics(lat, pri, pri2, price):
    (_, _, _, _, revenue, ebit, net_income, equity, total_assets,
     total_liabilities, current_assets, current_liabilities, shares, eps, _fp) = lat
    revenue, ebit, net_income = fnum(revenue), fnum(ebit), fnum(net_income)
    equity, total_assets = fnum(equity), fnum(total_assets)
    total_liabilities = fnum(total_liabilities)
    current_assets, current_liabilities = fnum(current_assets), fnum(current_liabilities)
    shares, eps = fnum(shares), fnum(eps)

    if eps is None and net_income is not None and shares and shares > 1e5:
        eps = net_income / shares

    m = {}
    if net_income is not None and equity and equity > 0:
        roe = net_income / equity * 100
        if in_range(roe, -500, 500):
            m['roe'] = roe

    if revenue and revenue > 0:
        if ebit is not None:
            opm = ebit / revenue * 100
            if in_range(opm, -300, 100):
                m['opm'] = opm
        if total_assets and total_assets > 0:
            at = revenue / total_assets
            if in_range(at, 0, 20):
                m['asset_turnover'] = at

    if equity and equity > 0 and total_liabilities is not None:
        de = total_liabilities / equity
        if in_range(de, 0, 50):
            m['debt_to_equity'] = de

    if current_liabilities and current_liabilities > 0 and current_assets is not None:
        cr = current_assets / current_liabilities
        if in_range(cr, 0, 100):
            m['current_ratio'] = cr

    if ebit is not None and total_assets and current_liabilities is not None:
        cap = total_assets - current_liabilities
        if cap > 0:
            roce = ebit / cap * 100
            if in_range(roce, -300, 300):
                m['roce'] = roce

    # |eps| < 0.01 in local currency signals a unit mismatch (e.g. crores
    # net income against raw share count) — skip rather than write garbage
    if eps is not None and in_range(abs(eps), 0.01, 1e6):
        m['eps'] = eps

    if pri is not None:
        p_revenue = fnum(pri[4])
        p_eps = fnum(pri[13])
        if p_eps is None:
            p_ni, p_sh = fnum(pri[6]), fnum(pri[12])
            if p_ni is not None and p_sh and p_sh > 1e5:
                p_eps = p_ni / p_sh
        if revenue is not None and p_revenue and p_revenue > 0:
            rg = (revenue / p_revenue - 1) * 100
            # cross-check extreme 1y growth against the annualized 2y rate;
            # a big disagreement means the prior row is likely an interim
            # stored as annual — trust the 2y rate instead
            if abs(rg) > 50 and pri2 is not None:
                p2_revenue = fnum(pri2[4])
                if p2_revenue and p2_revenue > 0:
                    ratio2 = revenue / p2_revenue
                    if ratio2 > 0:
                        rg2 = (math.sqrt(ratio2) - 1) * 100
                        if abs(rg - rg2) > 40:
                            rg = rg2
            if in_range(rg, -95, 1000):
                m['revenue_growth'] = rg
        if eps is not None and eps > 0.01 and p_eps and p_eps > 0.01:
            eg = (eps / p_eps - 1) * 100
            if in_range(eg, -95, 1000):
                m['eps_growth'] = eg

    if price and price > 0:
        if eps and eps > 0.01:
            pe = price / eps
            if in_range(pe, 0.5, 2000):
                m['pe'] = pe
        if equity and equity > 0 and shares and shares > 1e5:
            bvps = equity / shares
            if bvps > 0:
                pb = price / bvps
                if in_range(pb, 0.05, 200):
                    m['pb'] = pb
            mc = price * shares
            if in_range(mc, 1e6, 1e16):
                m['market_cap'] = mc

    return m


def main():
    conn = psycopg2.connect(dbname='market_data')

    print("Loading statements (latest + prior FY per ticker)...")
    latest, prior, prior2 = load_postgres_statements(conn)
    print(f"  {len(latest)} (market,ticker) pairs")

    print("Loading latest close prices from ohlcv_history...")
    prices = load_prices(conn)
    conn.close()
    print(f"  {len(prices)} tickers with a latest close")

    print("Loading Cassandra symbol universe...")
    cass = load_cassandra_symbols()
    print(f"  {len(cass)} Cassandra symbols")

    # statement index by (cass_market, ticker); first mapping wins (priority order)
    pg_index = {}
    for pg_mkt, cass_mkt in PG_TO_CASS_MARKET:
        for (m, ticker), row in latest.items():
            if m == pg_mkt and (cass_mkt, ticker) not in pg_index:
                pg_index[(cass_mkt, ticker)] = ((m, ticker), row)
    # europe fallback: unique base symbol
    eu_base = defaultdict(list)
    for (cass_mkt, ticker) in pg_index:
        if cass_mkt == 'europe':
            eu_base[ticker.rsplit('.', 1)[0]].append(ticker)

    out_dir = Path('/Users/umashankar/market-pipeline/reports_local')
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / 'FUNDAMENTALS_PG_BRIDGE.cql'

    matched = defaultdict(int)
    col_counts = defaultdict(int)
    written = 0
    with open(out_file, 'w') as f:
        f.write("-- Bridge: Postgres global_fundamentals + ohlcv_history -> Cassandra stock_quotes\n")
        for cass_mkt, yf_ticker in cass:
            bare = yf_ticker.rsplit('.', 1)[0] if '.' in yf_ticker else yf_ticker
            key = None
            if cass_mkt in STRIP_SUFFIX_MARKETS:
                if (cass_mkt, bare) in pg_index:
                    key = (cass_mkt, bare)
            elif (cass_mkt, yf_ticker) in pg_index:
                key = (cass_mkt, yf_ticker)
            elif cass_mkt == 'japan' and (cass_mkt, bare + '.T') in pg_index:
                key = (cass_mkt, bare + '.T')
            elif cass_mkt == 'europe':
                cands = eu_base.get(bare, [])
                if len(cands) == 1:
                    key = (cass_mkt, cands[0])
            if key is None:
                continue

            pg_key, lat = pg_index[key]
            pri = prior.get(pg_key)
            pri2 = prior2.get(pg_key)
            # price lookup: ohlcv stocks tickers are bare for japan/korea/china
            price = (prices.get((cass_mkt, yf_ticker))
                     or prices.get((cass_mkt, bare)))
            metrics = compute_metrics(lat, pri, pri2, price)
            if not metrics:
                continue
            matched[cass_mkt] += 1
            for c in metrics:
                col_counts[c] += 1
            sets = ', '.join(f"{c} = {v:.6f}" for c, v in metrics.items())
            safe = yf_ticker.replace("'", "''")
            f.write(f"UPDATE herrrickshaw.stock_quotes SET {sets} "
                    f"WHERE market = '{cass_mkt}' AND yf_ticker = '{safe}';\n")
            written += 1

    print(f"\nMatched by market: {dict(sorted(matched.items()))}")
    print(f"Total UPDATE statements: {written}")
    print("Column fill counts:")
    for c, n in sorted(col_counts.items(), key=lambda x: -x[1]):
        print(f"  {c:16} {n}")
    print(f"\nCQL file: {out_file}")


if __name__ == '__main__':
    main()
