#!/usr/bin/env python3
"""
Complete India + US fundamentals in Cassandra from LOCAL sources only.

India (3,480 symbols), precedence:
  A. IN_screener_only_backup.parquet — 1,487 tickers, annual FY, values in
     ₹ crores with RAW share counts (scale crores x 1e7 for per-share math).
     Gives roe/opm/roce/d-e/interest_cov/asset_turnover/eps/dividend_yield/
     growth + price-based pe/pb/market_cap.
  B. nse_xbrl/pit_quarterly.parquet — 2,364 NSE tickers, quarterly PIT
     results. TTM (last 4 quarters) eps/opm/interest_cov/revenue growth for
     tickers screener doesn't cover.

US (9,278 symbols):
  Postgres global_fundamentals latest FY (sec_edgar) + US_shares_supplement
  (463 tickers) + '.'<->'-' ticker aliasing (BRK.B vs BRK-B). ETFs and
  non-EDGAR OTC names have no local statement source and are left to
  quality_score.

Prices: Postgres ohlcv_history latest close (INR / USD).
"""

import math
import subprocess
import sys
import csv
from collections import defaultdict
from pathlib import Path

import pandas as pd
import psycopg2

SCREENER = '/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history/IN_screener_only_backup.parquet'
PIT_Q = '/Users/umashankar/market-pipeline/market_cache/nse_xbrl/pit_quarterly.parquet'
US_SUPP = '/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history/US_shares_supplement.parquet'
SCRATCH = Path('/private/tmp/claude-501/-Users-umashankar/fce772c6-1b5d-436e-a845-f7e0585e07e4/scratchpad')
CR = 1e7  # crores -> units


def fnum(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def in_range(v, lo, hi):
    return v is not None and lo <= v <= hi


def load_prices(conn, market_name):
    cur = conn.cursor()
    if market_name == 'india':
        # ohlcv_history's india partition is contaminated with USD ADR series
        # (e.g. INFY at $11.49) — bhavcopy.cleaned_ohlcv is the clean source
        cur.execute("""
            SELECT c.symbol, c.close
            FROM bhavcopy.cleaned_ohlcv c
            JOIN (SELECT symbol, MAX(trade_date) d FROM bhavcopy.cleaned_ohlcv
                  GROUP BY symbol) mx
                 ON mx.symbol = c.symbol AND mx.d = c.trade_date
        """)
    else:
        cur.execute("""
            SELECT st.ticker, o.close_price
            FROM ohlcv_history o
            JOIN stocks st ON st.stock_id = o.stock_id
            JOIN markets m ON st.market_id = m.market_id
            JOIN (SELECT stock_id, MAX(date) d FROM ohlcv_history GROUP BY stock_id) mx
                 ON mx.stock_id = o.stock_id AND mx.d = o.date
            WHERE m.market_name = %s
        """, (market_name,))
    return {t.strip(): fnum(c) for t, c in cur.fetchall() if fnum(c) and fnum(c) > 0}


def load_cassandra_symbols(market):
    out = SCRATCH / 'cass_symbols.csv'
    syms = []
    with open(out) as f:
        for row in csv.DictReader(f):
            if row['market'] == market:
                syms.append(row['yf_ticker'])
    return syms


# ---------------- India ----------------

IN_YF = '/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history/IN_yfinance.parquet'
IN_MERGED = '/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history/IN.parquet'


def india_shares_map():
    """Raw share counts from yfinance-sourced parquets (screener 'shares' is
    null for ~2/3 of tickers). Share counts are safe here — the known
    quarterly-as-annual yfinance bug only corrupts EPS/income, not shares."""
    shares = {}
    for path in (IN_MERGED, IN_YF):  # IN_yfinance wins (loaded last)
        df = pd.read_parquet(path)
        lat = df.sort_values('fy_end').groupby('ticker').tail(1)
        for t, s in zip(lat['ticker'], lat['shares']):
            v = fnum(s)
            if v and v > 1e5:
                shares[t] = v
    return shares


def india_from_screener(prices, shares_map):
    df = pd.read_parquet(SCREENER)
    df = df.sort_values('fy_end')
    out = {}
    for ticker, g in df.groupby('ticker'):
        rows = g.tail(3).to_dict('records')
        lat = rows[-1]
        pri = rows[-2] if len(rows) >= 2 else None

        rev, ni, ebit = fnum(lat.get('revenue')), fnum(lat.get('net_income')), fnum(lat.get('ebit'))
        eq_cap, res = fnum(lat.get('equity_capital')), fnum(lat.get('reserves'))
        borrow, other_liab = fnum(lat.get('borrowings')), fnum(lat.get('other_liab'))
        interest, shares = fnum(lat.get('interest')), fnum(lat.get('shares'))
        if not (shares and shares > 1e5):
            shares = shares_map.get(ticker)
        roce, div_amt = fnum(lat.get('roce')), fnum(lat.get('dividend_amount'))
        equity = (eq_cap or 0) + (res or 0) if (eq_cap is not None or res is not None) else None

        m = {}
        if ni is not None and equity and equity > 0:
            v = ni / equity * 100
            if in_range(v, -500, 500):
                m['roe'] = v
        if rev and rev > 0 and ebit is not None:
            v = ebit / rev * 100
            if in_range(v, -300, 100):
                m['opm'] = v
        if equity and equity > 0 and borrow is not None:
            v = borrow / equity
            if in_range(v, 0, 50):
                m['debt_to_equity'] = v
        if interest and interest > 0 and ebit is not None:
            v = ebit / interest
            if in_range(v, -1000, 10000):
                m['interest_cov'] = v
        if roce is not None and in_range(roce * 100, -300, 300):
            m['roce'] = roce * 100
        total_assets = (equity or 0) + (borrow or 0) + (other_liab or 0)
        if rev and rev > 0 and total_assets > 0:
            v = rev / total_assets
            if in_range(v, 0, 20):
                m['asset_turnover'] = v

        eps = None
        if ni is not None and shares and shares > 1e5:
            eps = ni * CR / shares
            if in_range(abs(eps), 0.01, 1e6):
                m['eps'] = eps
            else:
                eps = None

        if pri is not None:
            p_rev, p_ni, p_sh = fnum(pri.get('revenue')), fnum(pri.get('net_income')), fnum(pri.get('shares'))
            if not (p_sh and p_sh > 1e5):
                p_sh = shares_map.get(ticker)
            if rev is not None and p_rev and p_rev > 0:
                v = (rev / p_rev - 1) * 100
                if in_range(v, -95, 1000):
                    m['revenue_growth'] = v
            if eps and p_ni is not None and p_sh and p_sh > 1e5:
                p_eps = p_ni * CR / p_sh
                if p_eps > 0.01 and eps > 0.01:
                    v = (eps / p_eps - 1) * 100
                    if in_range(v, -95, 1000):
                        m['eps_growth'] = v

        price = prices.get(ticker)
        if price:
            if eps and eps > 0.01:
                v = price / eps
                if in_range(v, 0.5, 2000):
                    m['pe'] = v
            if equity and equity > 0 and shares and shares > 1e5:
                bvps = equity * CR / shares
                if bvps > 0:
                    v = price / bvps
                    if in_range(v, 0.05, 200):
                        m['pb'] = v
                mc = price * shares
                if in_range(mc, 1e6, 1e16):
                    m['market_cap'] = mc
            if div_amt is not None and div_amt >= 0 and shares and shares > 1e5:
                dps = div_amt * CR / shares
                v = dps / price * 100
                if in_range(v, 0, 50):
                    m['dividend_yield'] = v

        if m:
            out[ticker] = m
    return out


def india_from_xbrl(prices):
    df = pd.read_parquet(PIT_Q)
    # prefer consolidated rows when both exist for a period
    df = df.sort_values(['symbol', 'period_end', 'consolidated'])
    df = df.drop_duplicates(subset=['symbol', 'period_end'], keep='last')
    df = df.sort_values(['symbol', 'period_end'])
    out = {}
    for sym, g in df.groupby('symbol'):
        rows = g.tail(8).to_dict('records')
        if len(rows) < 4:
            continue
        ttm = rows[-4:]
        span = (pd.Timestamp(ttm[-1]['period_end']) - pd.Timestamp(ttm[0]['period_end'])).days
        if not 250 <= span <= 300:  # 3 quarter-gaps ~ 273 days
            continue

        def s(rows_, col):
            vals = [fnum(r.get(col)) for r in rows_]
            return sum(v for v in vals if v is not None) if any(v is not None for v in vals) else None

        rev, pat, fc = s(ttm, 'revenue'), s(ttm, 'pat'), s(ttm, 'finance_costs')
        pbt = s(ttm, 'pbt')
        eps_vals = [fnum(r.get('eps_basic')) for r in ttm]
        eps_ttm = sum(eps_vals) if all(v is not None for v in eps_vals) else None

        m = {}
        ebit = None
        if pbt is not None:
            ebit = pbt + (fc or 0)
        if rev and rev > 0 and ebit is not None:
            v = ebit / rev * 100
            if in_range(v, -300, 100):
                m['opm'] = v
        if fc and fc > 0 and ebit is not None:
            v = ebit / fc
            if in_range(v, -1000, 10000):
                m['interest_cov'] = v
        if len(rows) == 8:
            prior = rows[:4]
            p_span = (pd.Timestamp(prior[-1]['period_end']) - pd.Timestamp(prior[0]['period_end'])).days
            if 250 <= p_span <= 300:
                p_rev = s(prior, 'revenue')
                if rev is not None and p_rev and p_rev > 0:
                    v = (rev / p_rev - 1) * 100
                    if in_range(v, -95, 1000):
                        m['revenue_growth'] = v
                p_eps_vals = [fnum(r.get('eps_basic')) for r in prior]
                if eps_ttm and all(v is not None for v in p_eps_vals):
                    p_eps = sum(p_eps_vals)
                    if p_eps > 0.01 and eps_ttm > 0.01:
                        v = (eps_ttm / p_eps - 1) * 100
                        if in_range(v, -95, 1000):
                            m['eps_growth'] = v

        if eps_ttm is not None and in_range(abs(eps_ttm), 0.01, 1e6):
            m['eps'] = eps_ttm
            price = prices.get(sym)
            if price and eps_ttm > 0.01:
                v = price / eps_ttm
                if in_range(v, 0.5, 2000):
                    m['pe'] = v
        if m:
            out[sym] = m
    return out


# ---------------- US ----------------

def us_from_warehouse(conn, prices, cass_symbols):
    cur = conn.cursor()
    cur.execute("""
        WITH r AS (
          SELECT *, ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fy_end DESC, src_priority DESC) rn
          FROM global_fundamentals WHERE market='US' AND fy_end IS NOT NULL
        )
        SELECT ticker, revenue, ebit, net_income, equity, total_assets,
               total_liabilities, current_assets, current_liabilities, shares
        FROM r WHERE rn = 1
    """)
    latest = {r[0]: r[1:] for r in cur.fetchall()}
    cur.execute("""
        WITH r AS (
          SELECT *, ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fy_end DESC, src_priority DESC) rn
          FROM global_fundamentals WHERE market='US' AND fy_end IS NOT NULL
        )
        SELECT ticker, revenue, net_income, shares FROM r WHERE rn = 2
    """)
    prior = {r[0]: r[1:] for r in cur.fetchall()}

    supp = pd.read_parquet(US_SUPP).set_index('ticker')

    cass_set = set(cass_symbols)
    alias = {}
    for t in latest:
        if t not in cass_set:
            for cand in (t.replace('.', '-'), t.replace('-', '.')):
                if cand in cass_set:
                    alias[t] = cand
                    break

    out = {}
    for ticker, row in latest.items():
        yf_t = ticker if ticker in cass_set else alias.get(ticker)
        if yf_t is None:
            continue
        revenue, ebit, ni, equity, ta, tl, ca, cl, shares = [fnum(x) for x in row]
        if (shares is None or equity is None) and ticker in supp.index:
            s = supp.loc[ticker]
            if shares is None:
                shares = fnum(s.get('shares'))
            if equity is None:
                equity = fnum(s.get('equity'))

        m = {}
        if ni is not None and equity and equity > 0:
            v = ni / equity * 100
            if in_range(v, -500, 500):
                m['roe'] = v
        if revenue and revenue > 0:
            if ebit is not None:
                v = ebit / revenue * 100
                if in_range(v, -300, 100):
                    m['opm'] = v
            if ta and ta > 0:
                v = revenue / ta
                if in_range(v, 0, 20):
                    m['asset_turnover'] = v
        if equity and equity > 0 and tl is not None:
            v = tl / equity
            if in_range(v, 0, 50):
                m['debt_to_equity'] = v
        if cl and cl > 0 and ca is not None:
            v = ca / cl
            if in_range(v, 0, 100):
                m['current_ratio'] = v
        if ebit is not None and ta and cl is not None and (ta - cl) > 0:
            v = ebit / (ta - cl) * 100
            if in_range(v, -300, 300):
                m['roce'] = v

        eps = None
        if ni is not None and shares and shares > 1e5:
            eps = ni / shares
            if in_range(abs(eps), 0.01, 1e6):
                m['eps'] = eps
            else:
                eps = None

        p = prior.get(ticker)
        if p:
            p_rev, p_ni, p_sh = fnum(p[0]), fnum(p[1]), fnum(p[2])
            if revenue is not None and p_rev and p_rev > 0:
                v = (revenue / p_rev - 1) * 100
                if in_range(v, -95, 1000):
                    m['revenue_growth'] = v
            if eps and p_ni is not None and p_sh and p_sh > 1e5:
                p_eps = p_ni / p_sh
                if p_eps > 0.01 and eps > 0.01:
                    v = (eps / p_eps - 1) * 100
                    if in_range(v, -95, 1000):
                        m['eps_growth'] = v

        price = prices.get(yf_t) or prices.get(ticker)
        if price:
            if eps and eps > 0.01:
                v = price / eps
                if in_range(v, 0.5, 2000):
                    m['pe'] = v
            if equity and equity > 0 and shares and shares > 1e5:
                bvps = equity / shares
                if bvps > 0:
                    v = price / bvps
                    if in_range(v, 0.05, 200):
                        m['pb'] = v
                mc = price * shares
                if in_range(mc, 1e6, 1e16):
                    m['market_cap'] = mc
        if m:
            out[yf_t] = m
    return out


def emit_cql(f, market, per_ticker, counts):
    n = 0
    for ticker, m in per_ticker.items():
        sets = ', '.join(f"{c} = {v:.6f}" for c, v in m.items())
        for c in m:
            counts[c] += 1
        safe = ticker.replace("'", "''")
        f.write(f"UPDATE herrrickshaw.stock_quotes SET {sets} "
                f"WHERE market = '{market}' AND yf_ticker = '{safe}';\n")
        n += 1
    return n


def main():
    conn = psycopg2.connect(dbname='market_data')

    print("Prices...")
    in_prices = load_prices(conn, 'india')
    us_prices = load_prices(conn, 'usa')
    print(f"  india {len(in_prices)}, us {len(us_prices)}")

    in_cass = set(load_cassandra_symbols('india'))
    us_cass = load_cassandra_symbols('us')
    print(f"  cassandra: india {len(in_cass)}, us {len(us_cass)}")

    shares_map = india_shares_map()
    print(f"India shares map: {len(shares_map)} tickers")
    print("India A: screener annual...")
    scr = india_from_screener(in_prices, shares_map)
    print(f"  {len(scr)} tickers")
    print("India B: NSE XBRL quarterly TTM...")
    xbrl = india_from_xbrl(in_prices)
    print(f"  {len(xbrl)} tickers")

    # merge: screener wins; xbrl fills missing tickers AND missing columns
    india = {}
    for t, m in scr.items():
        if t in in_cass:
            india[t] = dict(m)
    for t, m in xbrl.items():
        if t not in in_cass:
            continue
        if t in india:
            for c, v in m.items():
                india[t].setdefault(c, v)
        else:
            india[t] = dict(m)
    # market_cap for XBRL-only tickers with known shares + price
    for t, m in india.items():
        if 'market_cap' not in m:
            sh, price = shares_map.get(t), in_prices.get(t)
            if sh and price:
                mc = price * sh
                if in_range(mc, 1e6, 1e16):
                    m['market_cap'] = mc
    print(f"India combined: {len(india)} of {len(in_cass)} Cassandra symbols")

    print("US: warehouse + shares supplement + dot-dash alias...")
    us = us_from_warehouse(conn, us_prices, us_cass)
    print(f"US: {len(us)} of {len(us_cass)} Cassandra symbols")
    conn.close()

    out = Path('/Users/umashankar/market-pipeline/reports_local/FUNDAMENTALS_INDIA_US_COMPLETE.cql')
    counts = defaultdict(int)
    with open(out, 'w') as f:
        f.write("-- India (screener annual + NSE XBRL TTM) + US (sec_edgar + supplement)\n")
        n_in = emit_cql(f, 'india', india, counts)
        n_us = emit_cql(f, 'us', us, counts)
    print(f"\nCQL: {out} ({n_in} india + {n_us} us)")
    print("Column fill counts:")
    for c, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {c:16} {n}")


if __name__ == '__main__':
    main()
