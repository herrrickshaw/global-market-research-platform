#!/usr/bin/env python3
"""
build_business_valuation_report.py — reporting template for actual
strategy-implementation earnings + a business valuation of the research/
trading operation, structured like CFI's standard corporate-finance
templates (Income Statement / Ratios / DCF) the user supplied as a model.

NOT a new copy of those CFI files — those are commercial/licensed
products; this borrows their professional STRUCTURE (statement -> ratios
-> DCF) and populates it with this platform's own real, already-computed
numbers, in a fresh workbook.

DATA INTEGRITY NOTE (read before trusting any number downstream)
------------------------------------------------------------------
watchlist_pnl.py's "sold" rows compare entry_price to the CURRENT market
price, not the actual exit/sale price (no exit price is tracked anywhere
in this pipeline). Several show implausible -90%+ "returns" (WKHS, AMC,
BLNK) that are the underlying stock crashing AFTER the position closed —
not the user's real trading loss. This report therefore treats ONLY
"held" positions as actual, defensible P&L (real cost basis vs current
mark, capital genuinely at risk right now) and reports "sold" separately,
explicitly labeled as post-exit price drift, not realized P&L.

    build_business_valuation_report.py     # writes the .xlsx
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import watchlist_pnl as WP

OUT = Path(__file__).parent / "reports" / "business_valuation" / \
    f"strategy_earnings_and_valuation_{dt.date.today():%Y-%m-%d}.xlsx"

NAVY = "0B2F4A"
TEAL = "1F7A7A"
LIGHT = "EEF4F6"
WARN = "8A6D3B"
WARN_BG = "F4F0E8"

HEAD_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
HEAD_FILL = PatternFill("solid", fgColor=NAVY)
SUBHEAD_FONT = Font(name="Calibri", size=10, bold=True, color=NAVY)
TITLE_FONT = Font(name="Calibri", size=16, bold=True, color=NAVY)
NOTE_FONT = Font(name="Calibri", size=9, italic=True, color="666666")
WARN_FONT = Font(name="Calibri", size=9, bold=True, color=WARN)
THIN = Side(style="thin", color="D8D2C2")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _style_header_row(ws, row, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = HEAD_FONT
        cell.fill = HEAD_FILL
        cell.border = BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _autofit(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _write_df(ws, df, start_row, start_col=1, pct_cols=(), money_cols=()):
    ncols = len(df.columns)
    for j, col in enumerate(df.columns):
        ws.cell(row=start_row, column=start_col + j, value=str(col))
    _style_header_row(ws, start_row, start_col + ncols - 1)
    for i, (_, r) in enumerate(df.iterrows()):
        for j, col in enumerate(df.columns):
            cell = ws.cell(row=start_row + 1 + i, column=start_col + j, value=r[col])
            cell.border = BORDER
            if col in pct_cols:
                cell.number_format = "+0.0%;-0.0%"
            elif col in money_cols:
                cell.number_format = "#,##0.00"
    return start_row + 1 + len(df)


def _title(ws, text, row=1, col=1, size=16):
    cell = ws.cell(row=row, column=col, value=text)
    cell.font = Font(name="Calibri", size=size, bold=True, color=NAVY)
    return row + 1


def _note(ws, text, row, col=1, span=8, font=NOTE_FONT):
    cell = ws.cell(row=row, column=col, value=text)
    cell.font = font
    cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=row, start_column=col, end_row=row, end_column=col + span - 1)
    ws.row_dimensions[row].height = 15 * (1 + len(text) // 110)
    return row + 1


# ── data ─────────────────────────────────────────────────────────────────────

def load_pnl():
    df = WP.build(market=None, status=None)
    d = df.dropna(subset=["pct_since"]).copy()
    d["pct_since"] = d["pct_since"] / 100.0
    held = d[d["status"] == "held"].sort_values("pct_since", ascending=False)
    sold = d[d["status"] == "sold"].sort_values("pct_since", ascending=False)
    return d, held, sold


# ── sheets ───────────────────────────────────────────────────────────────────

def sheet_cover(wb, held, sold, d):
    ws = wb.active
    ws.title = "Cover & Methodology"
    r = _title(ws, "Strategy Implementation — Actual Earnings & Business Valuation")
    ws.cell(row=r, column=1, value=f"Generated {dt.date.today():%Y-%m-%d} from live watchlist_pnl.py + "
                                    "fact_screener_signal + cost_vs_edge.py outputs").font = NOTE_FONT
    r += 2
    r = _note(ws, "STRUCTURE: modeled on the CFI Financial Projection / DCF / Three-Statement "
                  "templates supplied as reference (statement → ratios → DCF), rebuilt fresh with "
                  "this platform's own real numbers rather than edited into those licensed files.", r)
    r += 1
    r = _note(ws, "⚠ DATA INTEGRITY — READ BEFORE TRUSTING ANY NUMBER IN THIS WORKBOOK: "
                  "the 'sold' status in watchlist.csv has NO tracked exit price — watchlist_pnl.py "
                  "compares entry cost to the CURRENT market price even for closed positions. "
                  "Several show -90%+ 'returns' (e.g. WKHS, AMC, BLNK) that are the stock crashing "
                  "AFTER the position was closed, not the user's real trading loss. This report "
                  "therefore treats ONLY 'held' positions (real cost basis vs current mark, capital "
                  "genuinely at risk today) as actual P&L. 'Sold' is reported separately and labeled "
                  "as post-exit price drift, never as realized P&L.", r, font=WARN_FONT)
    r += 1
    r = _note(ws, "⚠ NOT INVESTMENT ADVICE. This is a mechanical accounting/valuation exercise on "
                  "this platform's own historical data — it values the RESEARCH OPERATION as a "
                  "business, it does not recommend any security. Backtest statistics quoted here "
                  "(Sheet 3) are historical, not a forecast; several already-published caveats from "
                  "this pipeline's own prior work are carried through unchanged (see Sheet 3 notes).", r)
    r += 2

    ws.cell(row=r, column=1, value="Snapshot").font = SUBHEAD_FONT
    r += 1
    stats = [
        ("Total watchlist positions (with computable P&L)", len(d)),
        ("Held positions (actual capital at risk)", len(held)),
        ("Held — mean return", f"{held['pct_since'].mean():+.1%}"),
        ("Held — median return", f"{held['pct_since'].median():+.1%}"),
        ("Held — win rate", f"{(held['pct_since'] > 0).mean():.1%}"),
        ("Closed ('sold') positions — count only, see caveat above", len(sold)),
    ]
    for label, val in stats:
        ws.cell(row=r, column=1, value=label)
        ws.cell(row=r, column=3, value=val).font = Font(bold=True)
        r += 1
    _autofit(ws, [46, 4, 20, 4, 4, 4, 4, 4])
    return ws


def sheet_actual_pnl(wb, held, sold, d):
    ws = wb.create_sheet("Actual P&L (Held)")
    r = _title(ws, "Actual Earnings — Held Positions (Real Cost Basis vs Current Mark)")
    r = _note(ws, "This is the closest thing this platform has to a real income statement: "
                  "entry_price is the ACTUAL cost basis on file, ltp is the current market price, "
                  "pct_since is the live mark-to-market gain/loss on capital currently deployed.", r)
    r += 1

    by_mkt = held.groupby("market")["pct_since"].agg(["count", "mean", "median"]).round(4)
    by_mkt.columns = ["n", "mean_return", "median_return"]
    by_mkt = by_mkt.reset_index()
    ws.cell(row=r, column=1, value="By market").font = SUBHEAD_FONT
    r += 1
    r = _write_df(ws, by_mkt, r, pct_cols=("mean_return", "median_return")) + 2

    ws.cell(row=r, column=1, value="Full held-position detail, sorted by return").font = SUBHEAD_FONT
    r += 1
    detail = held[["symbol", "market", "entry_price", "ltp", "pct_since"]].rename(
        columns={"entry_price": "cost_basis", "ltp": "current_price", "pct_since": "unrealized_return"})
    r = _write_df(ws, detail, r, pct_cols=("unrealized_return",), money_cols=("cost_basis", "current_price")) + 2

    ws.cell(row=r, column=1, value="Closed positions — NOT realized P&L, see Cover sheet caveat"
            ).font = WARN_FONT
    r += 1
    sold_detail = sold[["symbol", "market", "entry_price", "ltp", "pct_since"]].rename(
        columns={"entry_price": "cost_basis", "ltp": "price_now", "pct_since": "price_drift_since_close"})
    _write_df(ws, sold_detail, r, pct_cols=("price_drift_since_close",), money_cols=("cost_basis", "price_now"))

    _autofit(ws, [12, 8, 12, 12, 14])
    return ws


def sheet_signal_quality(wb):
    ws = wb.create_sheet("Strategy Signal Quality")
    r = _title(ws, "Backtest Evidence — Screener/Signal Performance (Large-Sample)")
    r = _note(ws, "From fact_screener_signal (4.98M rows, 37 screeners × 8 markets, 2009-2026) — "
                  "reverified 2026-07-31 against the FULL history, not a sample. Historical, not a "
                  "forecast. This is the evidence base for the DCF sheet's 'edge' assumption.", r)
    r += 1
    rows = [
        ("Golden Cross", "India", 35376, 0.3115, "252d"),
        ("Darvas", "India", 63164, 0.2914, "252d"),
        ("Golden Cross", "USA", 29941, -0.0766, "252d"),
        ("Piotroski", "USA", 2937, -0.0082, "252d"),
    ]
    df = pd.DataFrame(rows, columns=["screener", "market", "n", "mean_252d_excess_return", "horizon"])
    r = _write_df(ws, df, r, pct_cols=("mean_252d_excess_return",)) + 2
    r = _note(ws, "India momentum screens (Golden Cross/Darvas) show large, statistically substantial "
                  "positive excess return over this history. US Golden Cross and Piotroski show FLAT "
                  "TO NEGATIVE excess return over the same horizon — do not extrapolate the India "
                  "result to other markets or other screens.", r)
    r += 1
    r = _note(ws, "⚠ Separately, this pipeline's own re-entry signal (a different, related feature) "
                  "was explicitly re-tested and found to have NO measured forward edge "
                  "(India 63d excess return: -2.01% median, t=0.06) — that finding is NOT reversed "
                  "by the numbers above, which are a different signal on a different, larger dataset.", r, font=WARN_FONT)
    _autofit(ws, [16, 10, 10, 20, 10])
    return ws


def sheet_capacity(wb):
    ws = wb.create_sheet("Capacity & Cost Model")
    r = _title(ws, "Execution Capacity — Where the Edge Dies to Market Impact")
    r = _note(ws, "From cost_vs_edge.py / reports/execution_capacity.csv — Almgren-Chriss square-root "
                  "impact model, 15%-ADV participation cap, Corwin-Schultz spread estimate. "
                  "net_edge_bps = gross excess return minus round-trip execution cost at that AUM.", r)
    r += 1

    csv_path = Path(__file__).parent / "reports" / "execution_capacity.csv"
    cap_df = pd.read_csv(csv_path)
    r = _write_df(ws, cap_df, r) + 2

    ws.cell(row=r, column=1, value="Capacity ceiling per desk (AUM $M where net edge → 0)").font = SUBHEAD_FONT
    r += 1
    ceiling = pd.DataFrame([
        ("IN", 44, "~1"), ("US", 21, "~1"), ("JP", 15, "~0 (already dead at $1M)"),
        ("KR", 66, "~1"), ("EU", 15, "~5"),
    ], columns=["desk", "gross_edge_bps_2wk", "capacity_$M_AUM"])
    r = _write_df(ws, ceiling, r) + 1
    _note(ws, "This is the hard constraint on the DCF sheet's scale assumption — the edge is a "
              "small-money edge, not something that scales to institutional AUM.", r, font=WARN_FONT)
    _autofit(ws, [10, 10, 10, 10, 12, 12, 14, 14])
    return ws


def sheet_dcf(wb, held):
    ws = wb.create_sheet("DCF — Operation Valuation")
    r = _title(ws, "DCF — Illustrative Valuation of the Research/Trading Operation")
    r = _note(ws, "Values the OPERATION as a business (a research capability that could size capital "
                  "up to its measured capacity ceiling), NOT any individual security. Every yellow "
                  "cell below is an assumption you can change — the NPV recalculates live.", r)
    r += 1
    r = _note(ws, "⚠ Illustrative only. Discount rate reflects a solo, key-person-dependent, "
                  "small-cap/illiquid strategy — genuinely high risk, not a diversified fund's cost "
                  "of capital. Capacity and edge figures are this pipeline's own historical measurements "
                  "(Sheets 3-4), not guaranteed future performance.", r, font=WARN_FONT)
    r += 1

    ASSUME_FILL = PatternFill("solid", fgColor="FFF6D8")

    def assume(row, label, value, fmt=None):
        ws.cell(row=row, column=1, value=label)
        cell = ws.cell(row=row, column=3, value=value)
        cell.fill = ASSUME_FILL
        cell.border = BORDER
        if fmt:
            cell.number_format = fmt
        return row + 1

    ws.cell(row=r, column=1, value="Assumptions (editable)").font = SUBHEAD_FONT
    r += 1
    r0 = r
    r = assume(r, "Deployable capital at capacity ceiling ($, blended IN/US/KR desk)", 1_000_000, "#,##0")
    r_cap = r0
    r = assume(r, "Blended gross edge captured (annualized, bps)", 0.02, "0.0%")
    r_edge = r0 + 1
    r = assume(r, "Operating cost ratio (data/compute/infra, % of capital)", 0.005, "0.0%")
    r_cost = r0 + 2
    r = assume(r, "Discount rate (reflects key-person/illiquidity risk)", 0.25, "0.0%")
    r_disc = r0 + 3
    r = assume(r, "Projection years", 5, "0")
    r_years = r0 + 4
    r = assume(r, "Terminal growth rate", 0.02, "0.0%")
    r_term = r0 + 5
    r += 1

    ws.cell(row=r, column=1, value="Projected annual free cash flow").font = SUBHEAD_FONT
    r += 1
    fcf_row = r
    ws.cell(row=r, column=1, value="Annual FCF = capital × (edge − cost ratio)")
    fcf_cell = ws.cell(row=r, column=3,
                        value=f"=C{r_cap}*(C{r_edge}-C{r_cost})")
    fcf_cell.number_format = "#,##0"
    fcf_cell.border = BORDER
    r += 2

    ws.cell(row=r, column=1, value="5-year DCF").font = SUBHEAD_FONT
    r += 1
    yr_row = r
    ws.cell(row=r, column=1, value="Year")
    for y in range(1, 6):
        ws.cell(row=r, column=1 + y, value=y)
    _style_header_row(ws, r, 6)
    r += 1
    fcf_line = r
    ws.cell(row=r, column=1, value="FCF")
    for y in range(1, 6):
        c = ws.cell(row=r, column=1 + y, value=f"=$C${fcf_row}")
        c.number_format = "#,##0"
    r += 1
    dcf_line = r
    ws.cell(row=r, column=1, value="PV of FCF")
    for y in range(1, 6):
        col = get_column_letter(1 + y)
        c = ws.cell(row=r, column=1 + y, value=f"={col}{fcf_line}/(1+$C${r_disc})^{y}")
        c.number_format = "#,##0"
    r += 2

    ws.cell(row=r, column=1, value="Terminal value (Gordon growth, at year 5)")
    tv_row = r
    tv_cell = ws.cell(row=r, column=3,
                       value=f"=({get_column_letter(6)}{fcf_line}*(1+C{r_term}))/(C{r_disc}-C{r_term})")
    tv_cell.number_format = "#,##0"
    tv_cell.border = BORDER
    r += 1
    ws.cell(row=r, column=1, value="PV of terminal value")
    pv_tv_row = r
    pv_tv_cell = ws.cell(row=r, column=3, value=f"=C{tv_row}/(1+C{r_disc})^C{r_years}")
    pv_tv_cell.number_format = "#,##0"
    pv_tv_cell.border = BORDER
    r += 2

    ws.cell(row=r, column=1, value="Estimated operation value (NPV)").font = Font(bold=True, size=12, color=NAVY)
    npv_cell = ws.cell(row=r, column=3,
                        value=f"=SUM({get_column_letter(2)}{dcf_line}:{get_column_letter(6)}{dcf_line})+C{pv_tv_row}")
    npv_cell.number_format = "#,##0"
    npv_cell.font = Font(bold=True, size=12, color=NAVY)
    npv_cell.border = BORDER
    r += 2

    r = _note(ws, "Sensitivity: halving the discount rate assumption roughly doubles this NPV; "
                  "the capacity ceiling (Sheet 4) is the actual binding constraint on the capital-at-"
                  "capacity input above — raising it past the desk's measured ceiling overstates the "
                  "edge, since net_edge_bps goes negative beyond that AUM.", r)

    _autofit(ws, [50, 10, 16, 12, 12, 12, 12])
    return ws


def build():
    wb = Workbook()
    d, held, sold = load_pnl()
    sheet_cover(wb, held, sold, d)
    sheet_actual_pnl(wb, held, sold, d)
    sheet_signal_quality(wb)
    sheet_capacity(wb)
    sheet_dcf(wb, held)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"wrote {OUT}")
    return OUT


if __name__ == "__main__":
    build()
