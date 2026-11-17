#!/usr/bin/env python3
"""
edinet_bench_extract.py — turn the Sakana EDINET-Bench HF parquets into a deep JP
fundamentals panel (NO EDINET API key needed). Each annual securities report carries a
5-year Summary-of-Business-Results block, so filings across 2014–2024 stitch into ~10y of
Sales / net-income / equity / total-assets / EPS per company. Maps 証券コード → ticker.

Input: the downloaded EDINET-Bench parquets (earnings_forecast + fraud_detection).
Output: JP_edinet.parquet (ticker, fy_end, revenue, net_income, equity, total_assets, eps).
"""
from __future__ import annotations
import glob, json
from pathlib import Path
import pandas as pd, numpy as np

SP = "/private/tmp/claude-501/-Users-umashankar/38173149-3030-43dc-97c5-a0ced49bd927/scratchpad"
OUT = Path("/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history/JP_edinet.parquet")
# JP summary element → our schema
MAP = {"revenue": "売上高", "net_income": "親会社株主に帰属する当期純利益",
       "equity": "純資産額", "total_assets": "総資産額", "eps": "１株当たり当期純利益又は当期純損失"}
OFF = {"Prior4Year": 4, "Prior3Year": 3, "Prior2Year": 2, "Prior1Year": 1, "CurrentYear": 0}


def num(x):
    try:
        return float(str(x).replace(",", ""))
    except Exception:
        return np.nan


def main() -> int:
    files = glob.glob(f"{SP}/edinet_earnings_forecast_*.parquet") + glob.glob(f"{SP}/edinet_fraud_detection_*.parquet")
    rows = []
    for f in files:
        d = pd.read_parquet(f)
        for _, r in d.iterrows():
            try:
                meta = json.loads(r["meta"]); summ = json.loads(r["summary"])
            except Exception:
                continue
            sec = str(meta.get("証券コード", "")).strip()
            if not sec or sec == "－" or not sec[:4].isdigit():
                continue
            ticker = f"{sec[:4]}.T"
            cur_end = pd.to_datetime(meta.get("当事業年度終了日"), errors="coerce")
            if pd.isna(cur_end):
                continue
            for rel, off in OFF.items():
                fy_end = (cur_end - pd.DateOffset(years=off)).date().isoformat()
                rec = {"ticker": ticker, "fy_end": fy_end}
                has = False
                for col, jp in MAP.items():
                    v = num(summ.get(jp, {}).get(rel)) if isinstance(summ.get(jp), dict) else np.nan
                    rec[col] = v
                    has = has or np.isfinite(v)
                if has:
                    rows.append(rec)
    df = pd.DataFrame(rows)
    # dedup: same (ticker, fy_end) appears across filings — keep the row with most non-nulls
    df["_n"] = df[list(MAP)].notna().sum(axis=1)
    df = df.sort_values("_n", ascending=False).drop_duplicates(["ticker", "fy_end"]).drop(columns="_n")
    df.to_parquet(OUT, index=False)
    y = pd.to_datetime(df.fy_end, errors="coerce").dt.year
    print(f"JP_edinet: {len(df)} rows, {df.ticker.nunique()} tickers, {int(y.min())}-{int(y.max())}")
    print(f"  per-ticker years: median {int(df.groupby('ticker').size().median())} | "
          f"eps nn {df.eps.notna().mean():.0%} | revenue nn {df.revenue.notna().mean():.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
