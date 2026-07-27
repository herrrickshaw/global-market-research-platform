#!/usr/bin/env python3
"""
wise.py — a Wisesheets-style representation layer for the analysis.

Wisesheets pulls any metric for any ticker with one formula (=WISE("AAPL","Revenue","TTM"))
and ships watchlist/dashboard templates. This gives our multi-market analysis the same shape:

  wise("7203.T", "pe")            -> 12.4          # any metric for any ticker
  wise("7203.T", "verdict")       -> "UNDERPRICED"
  wise("JP", "strategy")          -> "value-reversion, long cheap-vs-market (+6.6%/6M, t4.84)"
  wise("KR", "pe")                -> DataFrame of every Korean name's PE
  python wise.py --workbook       -> analysis_dashboard.xlsx (summary + a sheet per market)

Metrics: close, eps, pe, pb, roe, mcap, earnings_yield (from all_ratios) ·
         valuation_z, verdict (peer-cluster) · strategy, character, edge (per market) ·
         signal (watchlist zone). Numbers come from the data — never invented.
"""
from __future__ import annotations
import sys, glob
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
REP = HERE / "reports"
NORM = {"india": "IN", "us": "US", "korea": "KR", "japan": "JP", "europe": "EU", "china": "CN",
        "in": "IN", "kr": "KR", "jp": "JP", "eu": "EU", "cn": "CN"}
MKTS = ["IN", "US", "KR", "JP", "EU", "CN"]

# per-market strategy verdicts (this session's backtests — stable)
STRAT = {
 "IN": ("momentum/trend", "long-only", "trend + sector-relative value", "+5.3%/6M, t2.5 · DSR0.994"),
 "US": ("mixed/light", "long-tilt", "short-horizon cheap-vs-market", "+1.72%/3M, t2.32"),
 "KR": ("mean-reversion", "full long/short", "cheap∩hi-ROE − expensive∩lo-ROE", "+4.83%/6M, t4.17"),
 "JP": ("value-reversion", "long cheap-vs-market", "cheap-vs-market (deep EDINET)", "+6.6%/6M, t4.84"),
 "EU": ("momentum (bull)", "directional", "12-month momentum", "DSR0.985 · value underpowered"),
 "CN": ("momentum/retail", "—", "value tested & FAILS", "cheap−rich ≈0%, t0.04 (powered null)"),
}


def _mk(s: str) -> str | None:
    return NORM.get(str(s).strip().lower())


def _ratios() -> pd.DataFrame:
    d = pd.read_csv(REP / "all_ratios.csv")
    d["mk"] = d.market.astype(str).str.lower().map(NORM).fillna(d.market.astype(str).str.upper())
    return d


def _clusters() -> pd.DataFrame:
    if not (REP / "valuation_clusters.csv").exists():
        return pd.DataFrame()
    d = pd.read_csv(REP / "valuation_clusters.csv")
    d["mk"] = d.market.astype(str).str.lower().map(NORM).fillna(d.market.astype(str).str.upper())
    return d


def _watch() -> pd.DataFrame:
    p = HERE / "watchlist.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


RATIO_COLS = {"close": "close", "eps": "eps", "pe": "pe", "pb": "pb", "roe": "roe",
              "mcap": "mcap_local", "earnings_yield": "earnings_yield"}


def _pnl() -> pd.DataFrame:
    """the strategy's own income statement per geography (paper-trade ledger)."""
    p = REP / "income_statement_by_geo.csv"
    return pd.read_csv(p).set_index("market") if p.exists() else pd.DataFrame()


def _bench() -> pd.DataFrame:
    p = REP / "strategy_vs_benchmark.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


# the strategy treated as a firm: which per-market P&L metrics wise() can return
PNL_COLS = {"net_income": "net_income", "roic": "ROIC_%", "eva": "economic_profit_eva",
            "hit_rate": "hit_rate", "capital": "capital_deployed", "ebit": "operating_income_ebit",
            "revenue": "revenue_gross_gains", "cost_of_capital": "cost_of_capital_%"}


def performance_insight() -> pd.DataFrame:
    """Does the strategy create value? Per geography: net income, ROIC vs its cost of
    capital, economic profit (EVA), and alpha over the benchmark — with a plain read."""
    pnl = _pnl(); bench = _bench()
    rows = []
    for mk in [m for m in MKTS if m in pnl.index]:
        r = pnl.loc[mk]
        alpha = bench[bench.market == mk]["excess"].mean() if len(bench) else float("nan")
        roic, coc = float(r["ROIC_%"]) * 100, float(r["cost_of_capital_%"]) * 100
        ni = float(r.net_income); eva = float(r.economic_profit_eva)
        read = ("✅ profitable + beats benchmark" if ni > 0 and alpha > 0 else
                "🟡 profitable, lags benchmark" if ni > 0 else
                "🔴 loss-making (paper-track)")
        rows.append({"market": mk, "trades": int(r.trades), "hit_rate": f"{float(r.hit_rate)*100:.0f}%",
                     "net_income": round(ni), "ROIC_%": round(roic, 2), "cost_of_capital_%": round(coc, 1),
                     "creates_value(EVA)": "yes" if eva > 0 else "no", "alpha_vs_bench": f"{alpha*100:+.2f}%" if alpha == alpha else "—",
                     "read": read})
    return pd.DataFrame(rows)


def wise(entity: str, metric: str, period: str = "LY"):
    """The =WISE() analog. entity = ticker or market; metric = any of the above."""
    metric = metric.lower()
    mk = _mk(entity)
    # ---- market-level metrics ----
    if mk and metric in ("strategy", "character", "edge", "book", "verdict_market"):
        ch, book, edge, ev = STRAT[mk]
        return {"strategy": f"{ch}, {book} — {edge} ({ev})", "character": ch,
                "edge": f"{edge} ({ev})", "book": book, "verdict_market": ev}[metric]
    if mk:                                          # market + ratio/analysis → column across names
        if metric in RATIO_COLS:
            r = _ratios(); return r[r.mk == mk][["ticker", RATIO_COLS[metric]]].reset_index(drop=True)
        if metric in ("valuation_z", "verdict"):
            c = _clusters(); col = "valuation_z" if metric == "valuation_z" else "verdict"
            return c[c.mk == mk][["name", col]].reset_index(drop=True) if len(c) else "no clusters"
    # ---- ticker-level metrics ----
    if mk and metric in PNL_COLS:                   # the strategy's own P&L per market
        pnl = _pnl()
        return float(pnl.loc[mk, PNL_COLS[metric]]) if mk in pnl.index else None
    tk = str(entity)
    if metric in RATIO_COLS:
        r = _ratios(); row = r[r.ticker.astype(str) == tk]
        return float(row.iloc[0][RATIO_COLS[metric]]) if len(row) else None
    if metric in ("valuation_z", "verdict"):
        c = _clusters()
        row = c[c.get("ticker", pd.Series(dtype=str)).astype(str) == tk] if "ticker" in c.columns else pd.DataFrame()
        if len(row):
            return row.iloc[0]["valuation_z" if metric == "valuation_z" else "verdict"]
        return None
    if metric == "signal":
        w = _watch(); row = w[w.symbol.astype(str) == tk] if "symbol" in w.columns else pd.DataFrame()
        return row.iloc[0]["status"] if len(row) else "not on watchlist"
    return f"unknown metric '{metric}'"


def sheet(mk: str) -> pd.DataFrame:
    """A Wisesheets-style watchlist/dashboard table for one market."""
    r = _ratios(); r = r[r.mk == mk][["ticker", "close", "pe", "pb", "roe", "earnings_yield"]].copy()
    c = _clusters()
    if len(c):
        cc = c[c.mk == mk][["ticker", "valuation_z", "verdict"]] if "ticker" in c.columns else pd.DataFrame()
        if len(cc):
            r = r.merge(cc, on="ticker", how="left")
    w = _watch()
    if len(w):
        r = r.merge(w[w.market == mk][["symbol", "status"]].rename(columns={"symbol": "ticker", "status": "signal"}),
                    on="ticker", how="left")
    return r.sort_values("valuation_z" if "valuation_z" in r.columns else "pe").reset_index(drop=True)


def workbook(path: str = "reports/analysis_dashboard.xlsx"):
    """Export a multi-sheet Excel dashboard: Strategy Summary + one sheet per market."""
    out = HERE / path
    with pd.ExcelWriter(out, engine="openpyxl") as xl:
        summ = pd.DataFrame([{"market": m, "character": STRAT[m][0], "book": STRAT[m][1],
                              "winning edge": STRAT[m][2], "backtest": STRAT[m][3]} for m in MKTS])
        summ.to_excel(xl, sheet_name="Strategy Summary", index=False)
        # ---- the strategy AS A FIRM: performance, income statement, balance sheet ----
        ins = performance_insight()
        if len(ins):
            ins.to_excel(xl, sheet_name="Performance Insight", index=False)
        for name, p in [("Income Statement", "income_statement_by_geo.csv"),
                        ("Balance Sheet", "balance_sheet_by_geo.csv"),
                        ("vs Benchmark", "strategy_vs_benchmark.csv")]:
            fp = REP / p
            if fp.exists():
                pd.read_csv(fp).to_excel(xl, sheet_name=name, index=False)
        for m in MKTS:
            try:
                s = sheet(m)
                if len(s):
                    s.head(500).to_excel(xl, sheet_name=m, index=False)
            except Exception:
                pass
    print(f"wrote {out}")
    return str(out)


def main() -> int:
    a = sys.argv[1:]
    if not a:
        print(__doc__); return 0
    if a[0] == "--workbook":
        workbook(); return 0
    if a[0] == "--insight":
        print("# Strategy performance — the paper-track as a firm\n")
        print(performance_insight().to_markdown(index=False))
        print("\n> ROIC is the period return on capital deployed; the cost-of-capital hurdle is "
              "annual, so EVA is a conservative (stringent) read. Alpha = mean return over the "
              "market benchmark. Paper-track only — no capital deployed. Not investment advice.")
        return 0
    if a[0] == "--sheet" and len(a) > 1:
        print(sheet(_mk(a[1]) or a[1].upper()).to_markdown(index=False)); return 0
    entity, metric = a[0], (a[1] if len(a) > 1 else "pe")
    res = wise(entity, metric, a[2] if len(a) > 2 else "LY")
    print(res.to_markdown(index=False) if isinstance(res, pd.DataFrame) else res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
