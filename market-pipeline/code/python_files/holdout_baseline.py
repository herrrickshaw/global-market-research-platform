#!/usr/bin/env python3
"""
holdout_baseline.py — a permanently frozen control strategy.

WHY THIS FILE EXISTS
────────────────────
Every screener, zone rule and eviction threshold in this repo has been revised
repeatedly, each change justified on its own terms, and none of it measured
against a control. So the one question that matters — "is the strategy actually
better than it was six months ago, or has it just been *changed* six months
worth?" — has never had an answer available.

A holdout answers it. Freeze one version of the strategy permanently, run it on
the same scans every day, and compare. The failure it detects is the one that is
invisible from inside: twenty individually-defensible "+0.5%" changes that
compound to zero, or to less than zero, because each was fitted to the window it
was made in.

THE DUPLICATION BELOW IS THE MECHANISM, NOT AN ACCIDENT
───────────────────────────────────────────────────────
FROZEN_FILTERS is a byte-for-byte copy of filter_watchlists.FILTERS as of the
freeze date, with its own copies of the pass functions and its own copies of
EVICT/PURGE. It must NEVER be refactored to import from filter_watchlists — an
import is precisely what would let a change to the live strategy silently move
the control, at which point the comparison measures nothing. If a linter or a
future cleanup pass flags the duplication, the answer is no.

What it DOES share with the live path is bookkeeping only: scan loading and
update_membership(), the pure add/evict/purge state machine. Those are
mechanism, not strategy. The boundary is: anything that decides WHICH NAMES
PASS is frozen here; anything that merely records what passed is shared.

The frozen logic is hashed (BASELINE_HASH) so an accidental edit is loud, the
same way eval_contract.py guards the evaluation gate.

Run: python3 holdout_baseline.py            # record today's baseline picks
     python3 holdout_baseline.py --compare  # live vs baseline divergence
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

# Bookkeeping only — see the boundary note above. NOT the strategy.
from filter_watchlists import (
    PRICE_COLS,
    SYM_COLS,
    _latest_scan,
    update_membership,
)

HERE = Path(__file__).resolve().parent
OUT = HERE / "holdout_watchlist.csv"
LIVE = HERE / "filter_watchlist.csv"

FREEZE_DATE = "2026-08-27"

COLS = ["symbol", "market", "filter", "status", "entry_date", "entry_price",
        "last_pass_date", "miss_count", "evicted_date", "last_price"]

# ══════════════════════════════════════════════════════════════════════════════
# FROZEN STRATEGY — do not edit, do not refactor, do not import from live.
# Copied from filter_watchlists.py at FREEZE_DATE.
# ══════════════════════════════════════════════════════════════════════════════

FROZEN_EVICT_SESSIONS = 5
FROZEN_PURGE_SESSIONS = 15


def _frozen_darvas_pass(s: pd.DataFrame) -> pd.Series:
    return s.get("Darvas_Signal", pd.Series("", index=s.index)) == "BREAKOUT_BUY"


def _frozen_ema_pass(s: pd.DataFrame) -> pd.Series:
    return (s.get("Above_EMA50", pd.Series(0, index=s.index)).fillna(0).astype(bool)
            & s.get("EMA50_Rising", pd.Series(0, index=s.index)).fillna(0).astype(bool))


def _frozen_piotroski_pass(s: pd.DataFrame) -> pd.Series:
    return pd.to_numeric(s.get("Piotroski_Score", pd.Series(np.nan, index=s.index)),
                         errors="coerce") >= 7


def _frozen_golden_cross_pass(s: pd.DataFrame) -> pd.Series:
    return s.get("GC_Signal", pd.Series("", index=s.index)) == "GOLDEN_CROSS"


FROZEN_FILTERS = {
    "darvas":       {"markets": ["IN", "US", "KR", "JP", "EU"], "pass_fn": _frozen_darvas_pass},
    "ema":          {"markets": ["US", "KR", "JP", "EU"],       "pass_fn": _frozen_ema_pass},
    "piotroski":    {"markets": ["IN"],                         "pass_fn": _frozen_piotroski_pass},
    "golden_cross": {"markets": ["IN", "US", "KR", "JP", "EU"], "pass_fn": _frozen_golden_cross_pass},
}

BASELINE_HASH = "3b72ddfc51da6ac2"

# ══════════════════════════════════════════════════════════════════════════════


class BaselineDrift(RuntimeError):
    """The frozen control was edited — every comparison after this is void."""


def baseline_digest() -> str:
    """Digest over the frozen pass-function SOURCE plus the filter/market map
    and the eviction constants — i.e. everything that decides which names pass."""
    parts = [inspect.getsource(f) for f in (
        _frozen_darvas_pass, _frozen_ema_pass,
        _frozen_piotroski_pass, _frozen_golden_cross_pass)]
    parts.append(repr({k: v["markets"] for k, v in sorted(FROZEN_FILTERS.items())}))
    parts.append(f"{FROZEN_EVICT_SESSIONS}/{FROZEN_PURGE_SESSIONS}")
    return hashlib.sha256("".join(parts).encode()).hexdigest()[:16]


def verify_frozen() -> None:
    actual = baseline_digest()
    if actual != BASELINE_HASH:
        raise BaselineDrift(
            f"holdout baseline changed: recorded {BASELINE_HASH}, computed "
            f"{actual}.\nThe control is supposed to be frozen — a comparison "
            f"against an edited baseline measures nothing. Revert the edit. "
            f"Starting a NEW baseline is a deliberate act: bump FREEZE_DATE, "
            f"move holdout_watchlist.csv aside, and rehash."
        )


def _load(path: Path) -> pd.DataFrame:
    if path.exists():
        d = pd.read_csv(path)
        for c in ("entry_date", "last_pass_date", "evicted_date"):
            if c in d.columns:
                d[c] = pd.to_datetime(d[c], errors="coerce")
        return d
    return pd.DataFrame(columns=COLS)


def record() -> int:
    """Run the FROZEN strategy over today's scans and update the baseline book."""
    verify_frozen()
    wl = _load(OUT)
    today = pd.Timestamp(date.today())
    scans: dict[str, pd.DataFrame | None] = {}
    totals = {"added": 0, "revived": 0, "still_passing": 0, "missed": 0,
              "evicted": 0, "purged": 0}
    skipped = []

    for filt, cfg in FROZEN_FILTERS.items():
        for mkt in cfg["markets"]:
            if mkt not in scans:
                scans[mkt] = _latest_scan(mkt)
            s = scans[mkt]
            if s is None:
                skipped.append(f"{filt}x{mkt}: no scan file")
                continue
            sym_col, price_col = SYM_COLS[mkt], PRICE_COLS[mkt]
            if sym_col not in s.columns:
                skipped.append(f"{filt}x{mkt}: missing {sym_col}")
                continue
            try:
                mask = cfg["pass_fn"](s)
            except Exception as e:                       # noqa: BLE001
                skipped.append(f"{filt}x{mkt}: pass_fn error: {e}")
                continue
            passing = set(s.loc[mask.fillna(False), sym_col].astype(str).str.upper())
            prices = dict(zip(s[sym_col].astype(str).str.upper(),
                              pd.to_numeric(s.get(price_col), errors="coerce")))
            wl, stats = update_membership(
                wl, filt, mkt, passing, prices, today,
                evict_sessions=FROZEN_EVICT_SESSIONS,
                purge_sessions=FROZEN_PURGE_SESSIONS)
            for k in totals:
                totals[k] += stats.get(k, 0)

    wl.to_csv(OUT, index=False)
    print(f"[holdout {BASELINE_HASH}] frozen {FREEZE_DATE} -> {OUT.name}: "
          + " ".join(f"{k}={v}" for k, v in totals.items() if v))
    for s in skipped:
        print(f"  skipped {s}")
    return 0


def _active_returns(d: pd.DataFrame) -> pd.DataFrame:
    a = d[d["status"] == "active"].copy()
    if a.empty:
        return a
    ep = pd.to_numeric(a["entry_price"], errors="coerce")
    lp = pd.to_numeric(a["last_price"], errors="coerce")
    a["ret"] = np.where((ep > 0) & lp.notna(), lp / ep - 1.0, np.nan)
    return a


def compare() -> int:
    """Live vs frozen baseline — the whole point of the exercise."""
    verify_frozen()
    live, base = _load(LIVE), _load(OUT)
    if base.empty:
        print("holdout book is empty — run `python3 holdout_baseline.py` first, "
              "then give it time. A control is only worth reading once it has "
              "accumulated history.")
        return 0

    L, B = _active_returns(live), _active_returns(base)
    print(f"holdout comparison   live vs baseline frozen {FREEZE_DATE} "
          f"[{BASELINE_HASH}]")
    print(f"  active names       live {len(L):>5}   baseline {len(B):>5}")

    lset = set(zip(L["filter"], L["market"], L["symbol"]))
    bset = set(zip(B["filter"], B["market"], B["symbol"]))
    both = lset & bset
    print(f"  overlap            {len(both)} shared · "
          f"{len(lset - bset)} live-only · {len(bset - lset)} baseline-only")

    lr, br = L["ret"].dropna(), B["ret"].dropna()
    if len(lr) and len(br):
        print(f"  mean return        live {lr.mean():+7.2%}   "
              f"baseline {br.mean():+7.2%}   delta {lr.mean()-br.mean():+7.2%}")
        print(f"  median return      live {lr.median():+7.2%}   "
              f"baseline {br.median():+7.2%}")
        print(f"  priced names       live {len(lr)}/{len(L)}   "
              f"baseline {len(br)}/{len(B)}")
    else:
        print("  returns            not enough priced rows on one side yet")

    print("\n  per filter x market (mean return, active count):")
    print(f"    {'filter':<14}{'mkt':<5}{'live':>16}{'baseline':>16}{'delta':>10}")
    keys = sorted(set(zip(L['filter'], L['market'])) | set(zip(B['filter'], B['market'])))
    for f, m in keys:
        ls = L[(L["filter"] == f) & (L["market"] == m)]["ret"].dropna()
        bs = B[(B["filter"] == f) & (B["market"] == m)]["ret"].dropna()
        lv = f"{ls.mean():+.2%} ({len(ls)})" if len(ls) else "—"
        bv = f"{bs.mean():+.2%} ({len(bs)})" if len(bs) else "—"
        dl = f"{ls.mean()-bs.mean():+.2%}" if len(ls) and len(bs) else "—"
        print(f"    {f:<14}{m:<5}{lv:>16}{bv:>16}{dl:>10}")

    # The honest caveat, printed every time so it cannot be forgotten in a
    # screenshot: this is a difference in realised means, not a significance
    # test. It becomes evidence only under the same gate everything else faces.
    from eval_contract import MIN_NONOVERLAP_OBS
    print(f"\n  ⚠️  descriptive only — a divergence is not an edge until it "
          f"clears the evaluation contract\n      (>= {MIN_NONOVERLAP_OBS} "
          f"non-overlapping observations, |t| >= 2). Do not act on this table.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="frozen holdout control strategy")
    ap.add_argument("--compare", action="store_true",
                    help="report live vs baseline divergence")
    ap.add_argument("--rehash", action="store_true",
                    help="print the digest (only when deliberately re-freezing)")
    a = ap.parse_args()
    if a.rehash:
        print(f'BASELINE_HASH = "{baseline_digest()}"')
        return 0
    return compare() if a.compare else record()


if __name__ == "__main__":
    sys.exit(main())
