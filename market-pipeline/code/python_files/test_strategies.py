#!/usr/bin/env python3
"""
test_strategies.py — offline checks for strategies/ screening defects fixed 2026-09-15.

Each check reproduces a case that screened wrongly before the fix. Same harness
as test_pipeline_invariants.py: hermetic (synthetic StockData, no network, no
warehouse), and a module that cannot be imported SKIPS with a stated reason.

    test_strategies.py          # run everything
    test_strategies.py -v       # show each check
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

PASS, FAIL, SKIP = [], [], []
VERBOSE = "-v" in sys.argv


def check(name):
    def deco(fn):
        try:
            fn()
        except _Skip as s:
            SKIP.append((name, str(s)))
            if VERBOSE:
                print(f"  —  {name}: skipped ({s})")
        except Exception as e:
            FAIL.append((name, f"{type(e).__name__}: {e}", traceback.format_exc()))
            print(f"  ❌ {name}: {type(e).__name__}: {e}")
        else:
            PASS.append(name)
            if VERBOSE:
                print(f"  ✅ {name}")
        return fn
    return deco


class _Skip(Exception):
    pass


from strategies.base import StockData, first_present  # noqa: E402


def stock(**fundamentals) -> StockData:
    return StockData(symbol="TEST", market="IN", fundamentals=fundamentals)


# ── fallback between fields must keep a real zero ─────────────────────────────
@check("base: first_present keeps 0.0 instead of falling through")
def _():
    assert first_present(0.0, 25.0) == 0.0
    assert first_present(None, 25.0) == 25.0
    assert first_present(None, None) is None


@check("garp: zero EPS growth is not replaced by earnings_growth")
def _():
    from strategies import garp
    r = garp.screen(stock(eps_growth=0.0, earnings_growth=40.0, pe=10.0))
    assert r is not None and not r.passed, r
    assert r.metrics["EPS_Growth%"] == 0.0, r.metrics


@check("magic_formula: zero ROC is not replaced by ROCE")
def _():
    from strategies import magic_formula
    r = magic_formula.screen(stock(roc=0.0, roce=40.0, earnings_yield=20.0))
    assert r is not None and not r.passed, r
    assert r.metrics["ROC%"] == 0.0, r.metrics


@check("bluest_blue_chips: zero profit growth is not replaced by EPS growth")
def _():
    from strategies import bluest_blue_chips
    r = bluest_blue_chips.screen(stock(market_cap_cr=50_000, roe=22.0, profit_growth=0.0,
                                       eps_growth=30.0, pe=15.0, industry_pe=25.0))
    assert r is not None and not r.passed, r
    assert r.metrics["ProfitGrowth>=10"] == 0, r.metrics


# ── coffee can: multi-year ROE consistency gates the pass ─────────────────────
_CC = dict(revenue=200.0, revenue_5y_ago=100.0, debt_to_equity=0.4)   # 14.9% CAGR


@check("coffee_can: one weak ROE year in history fails the screen")
def _():
    from strategies import coffee_can
    r = coffee_can.screen(stock(roe=20.0, roe_history=[20.0, 8.0, 18.0], **_CC))
    assert r is not None and not r.passed, r
    assert r.metrics["ROE_consistent"] == 0, r.metrics


@check("coffee_can: no ROE history passes but is marked unverified")
def _():
    from strategies import coffee_can
    r = coffee_can.screen(stock(roe=20.0, **_CC))
    assert r is not None and r.passed, r
    assert r.metrics["ROE_consistent"] is None and "unverified" in r.note, (r.metrics, r.note)


@check("coffee_can: history-only stock uses the newest year as current ROE")
def _():
    from strategies import coffee_can
    r = coffee_can.screen(stock(roe_history=[18.0, 17.0, 16.0], **_CC))
    assert r is not None and r.passed, r
    assert r.metrics["ROE"] == 18.0 and r.metrics["ROE_consistent"] == 1, r.metrics


# ── cash conversion cycle: a missing leg is unknown, not zero days ────────────
@check("cash_conversion_cycle: missing payables yields no result, not DIO+DSO")
def _():
    from strategies import cash_conversion_cycle as ccc
    r = ccc.screen(stock(inventory=10.0, receivables=10.0, cogs=100.0, revenue=100.0))
    assert r is None, r.row() if r else r
    full = ccc.screen(stock(inventory=10.0, receivables=10.0, payables=20.0,
                            cogs=100.0, revenue=100.0))
    assert full is not None and abs(full.metrics["CCC_days"] - 0.0) < 1e-9, full.metrics


@check("custom_screener: _ccc needs every leg")
def _():
    try:
        import custom_screener
    except Exception as e:
        raise _Skip(f"module unavailable ({type(e).__name__})")
    f = dict(inventory=10.0, receivables=10.0, cogs=100.0, revenue=100.0)
    assert custom_screener._ccc(f) is None
    assert custom_screener._ccc({**f, "ccc": 12.0}) == 12.0
    assert abs(custom_screener._ccc({**f, "payables": 20.0}) - 0.0) < 1e-9


# ── loss to profit: the sign flip must be against the previous quarter ───────
@check("loss_to_profit: an old loss followed by steady profits is not a turnaround")
def _():
    from strategies import loss_to_profit
    r = loss_to_profit.screen(stock(quarterly_net_income=[5.0, 3.0, -1.0, 4.0]))
    assert r is not None and not r.passed, r.metrics
    r2 = loss_to_profit.screen(stock(quarterly_net_income=[5.0, -2.0, 3.0]))
    assert r2 is not None and r2.passed, r2.metrics


# ── darvas: delegated to scan_core ────────────────────────────────────────────
def _box_frame():
    import pandas as pd
    rows = [(100 + i * 0.5, 95.0, 98.0) for i in range(20)]      # rising highs
    rows += [(110.0, 96.0, 105.0)]                               # box top at bar 20
    rows += [(105.0, 97.0, 102.0)] * 8                           # consolidation
    rows += [(113.0, 104.0, 112.0)]                              # current: breakout
    return pd.DataFrame(rows, columns=["High", "Low", "Close"])


@check("darvas: synthetic breakout is BREAKOUT_BUY")
def _():
    try:
        from strategies import darvas
    except Exception as e:
        raise _Skip(f"module unavailable ({type(e).__name__})")
    r = darvas.screen(StockData("TEST", ohlcv=_box_frame()))
    assert r is not None and r.note == "BREAKOUT_BUY", (r.note if r else r)
    assert r.metrics["Box_Top"] == 110.0 and r.metrics["Box_Bottom"] == 96.0, r.metrics


@check("darvas: an 'Adj Close' column ahead of 'Close' is not used as the close")
def _():
    try:
        from strategies import darvas
    except Exception as e:
        raise _Skip(f"module unavailable ({type(e).__name__})")
    df = _box_frame()
    df.insert(0, "Adj Close", 50.0)
    r = darvas.screen(StockData("TEST", ohlcv=df))
    assert r is not None and r.note == "BREAKOUT_BUY", (r.note if r else r)
    assert r.metrics["LTP"] == 112.0, r.metrics


@check("darvas: a trailing NaN close bar is dropped, not read as price 0")
def _():
    import pandas as pd
    try:
        from strategies import darvas
    except Exception as e:
        raise _Skip(f"module unavailable ({type(e).__name__})")
    df = pd.concat([_box_frame(),
                    pd.DataFrame([(float("nan"),) * 3], columns=["High", "Low", "Close"])],
                   ignore_index=True)
    r = darvas.screen(StockData("TEST", ohlcv=df))
    assert r is not None and r.note == "BREAKOUT_BUY", (r.note if r else r)
    assert r.metrics["LTP"] == 112.0, r.metrics


def main() -> int:
    print("=== strategy checks ===")
    n = len(PASS) + len(FAIL) + len(SKIP)
    print(f"\n  {len(PASS)} passed · {len(FAIL)} failed · {len(SKIP)} skipped ({n} checks)")
    for name, reason in SKIP:
        print(f"    — skipped: {name} ({reason})")
    for name, msg, tb in FAIL:
        print(f"\n  ❌ {name}\n{tb}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
