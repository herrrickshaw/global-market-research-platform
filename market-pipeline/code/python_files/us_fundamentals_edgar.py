#!/usr/bin/env python3
"""
us_fundamentals_edgar.py — fill the US fundamentals store off-hours from SEC
EDGAR companyfacts, into the same shape as the India store, so US screeners and
ratios stop depending on throttled per-ticker yfinance calls.

WHY EDGAR AND NOT YFINANCE
--------------------------
The India store (fundamentals_offhours.py) uses yfinance because India has no
free official filings API. The US does: data.sec.gov serves every XBRL fact a
company ever filed, keyed by CIK, with FILING DATES — official, dated, and
rate-limited at a documented 10 req/s rather than an opaque throttle that
truncates alphabetically. One pass over ~7k tickers takes ~35 min at the polite
default rate; after that a run only refetches names >FRESH_DAYS stale.

STORE SHAPE = IN_current.parquet EXACTLY (ticker, fy_end, source, <fields>,
collected_at) so every consumer that reads the India store can read
US_current.parquet unchanged. Values are as-filed USD; India's are INR — the
ratio layer (financial_ratios.py) never mixes currencies across markets.

WHAT IS DELIBERATELY NOT HERE
-----------------------------
* No fuzzy tag matching. Each field lists exact us-gaap tags in priority order
  (first present wins, same discipline as YF_MAP). A company using none of the
  listed tags gets NaN — visible in coverage — rather than a silently wrong row.
* Quarterly/TTM: companyfacts carries it, but the India quarterly store is
  revenue+NI only and nothing consumes a US quarterly yet. Scaffold later if a
  screener needs it.

Usage:
    us_fundamentals_edgar.py                  # full universe, skip fresh names
    us_fundamentals_edgar.py --limit 300      # bounded slice (one off-hours session)
    us_fundamentals_edgar.py --max-age-days 7 # re-collect only names >7d stale
    us_fundamentals_edgar.py --self-test      # offline; verify parsing logic
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent

try:
    import data_registry as _R
    FUND_DIR = _R.FUND_DIR
    BHAV_CACHE = Path(_R.BHAV_CACHE) if hasattr(_R, "BHAV_CACHE") else \
        Path("/Users/umashankar/market-pipeline/data/bhavcopy_cache")
except Exception:
    FUND_DIR = HERE / "cache_seed" / "fundamentals_current"
    BHAV_CACHE = Path("/Users/umashankar/market-pipeline/data/bhavcopy_cache")

STORE = FUND_DIR / "US_current.parquet"
CIK_CACHE = FUND_DIR / "company_tickers.json"

# 🔴 2026-08-19: the universe used to come from `ohlcv_US.parquet` — an ORPHAN
# panel no scheduled job refreshes, sitting at the 14 Aug session while the store
# the US scan actually reads held 17 Aug. Drawing the fundamentals universe from
# a dead file means every newly-listed ticker is invisible to this collector for
# as long as that file stays dead, which is indefinitely.
#
# The live store is the per-ticker OHLC tree the scan itself writes. The dead
# parquet is kept only as a last-resort fallback, and says so when it is used.
try:
    OHLC_DIR = _R.OHLC_DIR
except Exception:
    OHLC_DIR = Path("/Users/umashankar/market-pipeline/market_cache/ohlc")
UNIVERSE_PARQUET = BHAV_CACHE / "ohlcv_US.parquet"     # fallback only

# SEC asks for a descriptive UA with contact; anonymous UAs get 403'd.
UA = {"User-Agent": "umashankar market-pipeline umashankartd1991@gmail.com"}
RATE = 0.25           # seconds between requests — well under SEC's 10 req/s cap
CHECKPOINT_EVERY = 50
FRESH_DAYS = 30
N_YEARS = 5           # match the India store: last 5 fiscal years per ticker

# field -> us-gaap tags, priority order, first present wins. Field names are the
# India store's, verbatim — that equality is the whole point of this file.
GAAP_MAP = {
    "net_income":          ["NetIncomeLoss", "ProfitLoss"],
    "revenue":             ["Revenues",
                            "RevenueFromContractWithCustomerExcludingAssessedTax",
                            "RevenueFromContractWithCustomerIncludingAssessedTax",
                            "SalesRevenueNet"],
    "cfo":                 ["NetCashProvidedByUsedInOperatingActivities",
                            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "total_assets":        ["Assets"],
    "long_term_debt":      ["LongTermDebtNoncurrent", "LongTermDebt"],
    "current_assets":      ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "gross_profit":        ["GrossProfit"],
    "stockholders_equity": ["StockholdersEquity",
                            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "ebit":                ["OperatingIncomeLoss"],
    "capex":               ["PaymentsToAcquirePropertyPlantAndEquipment",
                            "PaymentsToAcquireProductiveAssets"],
    "total_debt":          ["DebtLongtermAndShorttermCombinedAmount",
                            "LongTermDebt", "LongTermDebtNoncurrent"],
    "cash":                ["CashAndCashEquivalentsAtCarryingValue",
                            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    # ── cash conversion cycle inputs (added 2026-08-21) ──────────────────────
    # CCC = DSO + DIO - DPO, so it needs receivables, inventory, payables and
    # COGS. Collected here so the cycle can be COMPUTED from filings instead of
    # scraped: screener.in was the only source for it, and a single 25s timeout
    # to that host took out the whole step twice in three days.
    #
    # Tags genuinely vary by filer — verified 2026-08-21: AAPL uses
    # AccountsReceivableNetCurrent + CostOfGoodsAndServicesSold, WMT uses
    # ReceivablesNetCurrent + CostOfRevenue, XOM uses
    # AccountsPayableAndAccruedLiabilitiesCurrent and reports NO COGS tag at
    # all. The last case is why CCC must be allowed to come out NaN: an oil
    # major has no cost-of-goods line, and inventing one from total expenses
    # would produce a confident number with no meaning.
    "receivables":         ["AccountsReceivableNetCurrent",
                            "ReceivablesNetCurrent",
                            "AccountsNotesAndLoansReceivableNetCurrent"],
    "inventory":           ["InventoryNet", "InventoryGross"],
    "payables":            ["AccountsPayableCurrent",
                            "AccountsPayableTradeCurrent",
                            "AccountsPayableAndAccruedLiabilitiesCurrent"],
    "cost_of_revenue":     ["CostOfRevenue", "CostOfGoodsAndServicesSold",
                            "CostOfGoodsSold"],
}
# FOREIGN PRIVATE ISSUERS FILE IFRS, NOT US-GAAP (added 2026-08-19).
# `_annual_series` already accepted 20-F and 40-F forms, but `parse_companyfacts`
# only ever looked in the `us-gaap` namespace — so every IFRS filer parsed to
# zero rows and silently vanished from the store. Measured against the 19 Aug US
# scan, that was TSM, SHEL, BP, AZN, NVO, SPOT, NU, CP, CCJ and ~200 more ADRs:
# real companies, real SEC filings, no fundamentals.
#
# Same discipline as GAAP_MAP — exact tags in priority order, first present wins,
# no fuzzy matching. Tag names verified live against TSM (334 ifrs tags) and SHEL
# (333) on 2026-08-19; where one of them lacks a tag the field is simply absent
# for that filer rather than being approximated from a near-neighbour.
IFRS_MAP = {
    "net_income":          ["ProfitLoss", "ProfitLossAttributableToOwnersOfParent"],
    "revenue":             ["Revenue", "RevenueFromContractsWithCustomers"],
    "cfo":                 ["CashFlowsFromUsedInOperatingActivities"],
    "total_assets":        ["Assets"],
    "long_term_debt":      ["LongtermBorrowings",
                            "NoncurrentPortionOfNoncurrentLoansAndBorrowings"],
    "current_assets":      ["CurrentAssets"],
    "current_liabilities": ["CurrentLiabilities"],
    "gross_profit":        ["GrossProfit"],
    "stockholders_equity": ["EquityAttributableToOwnersOfParent", "Equity"],
    "ebit":                ["ProfitLossFromOperatingActivities"],
    "capex":               ["PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"],
    "total_debt":          ["LongtermBorrowings"],
    "cash":                ["CashAndCashEquivalents"],
    # CCC inputs, IFRS side. Tag names verified against the ifrs-full
    # taxonomy; a filer missing any of them yields NaN for that field
    # rather than an approximation.
    "receivables":         ["TradeAndOtherCurrentReceivables",
                            "CurrentTradeReceivables"],
    "inventory":           ["Inventories"],
    "payables":            ["TradeAndOtherCurrentPayables",
                            "CurrentTradePayables"],
    "cost_of_revenue":     ["CostOfSales"],
}

# balance-sheet tags are instants (end only); flows must span ~a fiscal year,
# or the comparative quarterly rows inside a 10-K leak in as annual figures.
# Balance-sheet tags are INSTANTS (a point-in-time stock); flows must span a
# fiscal year. receivables/inventory/payables are stocks, cost_of_revenue is a
# flow — getting this wrong lets a comparative quarterly figure inside a 10-K
# through as an annual one.
INSTANT = {"total_assets", "long_term_debt", "current_assets",
           "current_liabilities", "stockholders_equity", "total_debt", "cash",
           "receivables", "inventory", "payables"}
ANNUAL_DAYS = (330, 380)

# IFRS reporters state amounts in their own presentation currency. USD is kept
# alongside the reporting unit so a TWD or EUR filer is not dropped for having
# no USD facts — but the unit is RECORDED on the row, because a ratio layer that
# divides a USD price by a TWD earnings figure is worse than a missing value.
_CURRENCY_UNITS = ("USD", "EUR", "GBP", "TWD", "JPY", "CHF", "SEK", "NOK",
                   "DKK", "CAD", "AUD", "BRL", "INR", "KRW", "CNY", "HKD",
                   "ILS", "MXN", "ZAR", "SGD")


def _hash_order(syms):
    """Same rationale as the India collector: a run killed early must leave a
    representative sample, not an alphabetical prefix."""
    return sorted(set(syms), key=lambda s: hashlib.md5(str(s).encode()).hexdigest())


# ── ticker -> CIK ─────────────────────────────────────────────────────────────
def load_cik_map(refresh_days: int = 7) -> dict:
    """company_tickers.json, cached; SEC regenerates it daily."""
    if CIK_CACHE.exists():
        age = (time.time() - CIK_CACHE.stat().st_mtime) / 86400
        if age < refresh_days:
            raw = json.loads(CIK_CACHE.read_text())
            return {v["ticker"].upper(): int(v["cik_str"]) for v in raw.values()}
    r = requests.get("https://www.sec.gov/files/company_tickers.json",
                     headers=UA, timeout=30)
    r.raise_for_status()
    CIK_CACHE.parent.mkdir(parents=True, exist_ok=True)
    CIK_CACHE.write_text(r.text)
    raw = r.json()
    return {v["ticker"].upper(): int(v["cik_str"]) for v in raw.values()}


# ── companyfacts parsing ──────────────────────────────────────────────────────
def _annual_series(fact_units: dict, instant: bool) -> tuple[dict, str | None]:
    """({fy_end_date: value}, unit) from one tag's unit list, FY figures only,
    deduped by period end keeping the LATEST filing (10-Ks restate prior
    years as comparatives; the most recent filing is the corrected one).

    Returns the unit alongside the series so an IFRS filer reporting in TWD or
    EUR is kept AND labelled, rather than silently dropped for having no USD
    facts or silently mixed into a USD store.
    """
    rows = []
    unit_seen = None
    for unit, entries in fact_units.items():
        if unit not in _CURRENCY_UNITS and unit != "shares":
            continue
        if unit != "shares":
            # Prefer USD when a filer reports both; otherwise take what there is.
            if unit_seen == "USD" and unit != "USD":
                continue
            if unit == "USD" and unit_seen not in (None, "USD"):
                rows, unit_seen = [], None      # restart, USD wins
            unit_seen = unit
        for e in entries:
            form = e.get("form", "")
            if not (form.startswith("10-K") or form.startswith("20-F")
                    or form.startswith("40-F")):
                continue
            end = e.get("end")
            if not end:
                continue
            if not instant:
                start = e.get("start")
                if not start:
                    continue
                span = (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days
                if not (ANNUAL_DAYS[0] <= span <= ANNUAL_DAYS[1]):
                    continue
            rows.append((end, e.get("filed", ""), e.get("val")))
    out = {}
    for end, filed, val in sorted(rows, key=lambda r: (r[0], r[1])):
        out[end] = val          # later (higher `filed`) overwrites earlier
    return out, unit_seen


def _filed_dates(doc: dict) -> dict[str, str]:
    """{fy_end: EARLIEST filing date carrying that fiscal year}.

    🔴 WITHOUT THIS THERE IS NO POINT-IN-TIME. `_annual_series` already reads
    `filed` — it uses it to prefer the latest restatement — and then discards
    it, so the store knew only `fy_end`. A backtest that ranks on a fiscal year
    from the day it ENDED is look-ahead: the 10-K lands weeks to months later,
    and until it does nobody could have traded on the number.
    METHODOLOGY.md assumption 1 allows FYE+90d as a fallback, but EDGAR gives
    the real date for free and a fixed 90 days is wrong in both directions —
    large accelerated filers have 60, and a late filer can take far longer.

    EARLIEST, not latest: the question is when the figure first became public,
    not when it was last restated. Using the restatement date would push the
    signal forward and understate the edge.
    """
    out: dict[str, str] = {}
    for ns in ("us-gaap", "ifrs-full"):
        for tag in doc.get("facts", {}).get(ns, {}).values():
            for entries in tag.get("units", {}).values():
                for e in entries:
                    if not str(e.get("form", "")).startswith(("10-K", "20-F", "40-F")):
                        continue
                    end, filed = e.get("end"), e.get("filed")
                    if end and filed and (end not in out or filed < out[end]):
                        out[end] = filed
    return out


def parse_companyfacts(doc: dict) -> list[dict]:
    """companyfacts JSON -> list of per-FY rows in the India-store shape.

    Tries us-gaap first, then ifrs-full. Whichever namespace yields more fields
    wins outright rather than the two being merged: a filer's statements are
    internally consistent within one framework, and cherry-picking Revenue from
    IFRS while taking Assets from a stray us-gaap tag produces a row that
    reconciles to nothing.
    """
    facts = doc.get("facts", {})
    dei = facts.get("dei", {})
    filed_by_fy = _filed_dates(doc)

    def harvest(ns: str, mapping: dict) -> tuple[dict, str | None]:
        """Merge tags PER FISCAL YEAR, in priority order — not first-tag-wins.

        🔴 2026-08-19. This loop used to stop at the first tag holding any data
        at all. Visa reports revenue under `Revenues` for FY2018-2020 and under
        `RevenueFromContractWithCustomerExcludingAssessedTax` for FY2023-2025 —
        the ASC 606 transition, which nearly every US filer went through. The
        old loop matched `Revenues`, found data (2018-2020), broke, and never
        looked at the newer tag; the store keeps the last 5 fiscal years, so
        Visa's revenue came out NaN in every one of them.

        Merging per-year keeps the exact-tag discipline that makes this file
        trustworthy — for a given year the first tag in priority order still
        wins, and an unmapped tag still yields NaN rather than a guess — while
        letting a field span a tag migration, which is a change in how the
        filing is written, not in what the company earned.
        """
        space = facts.get(ns, {})
        got: dict[str, dict] = {}
        unit = None
        for field, tags in mapping.items():
            merged: dict[str, float] = {}
            for tag in tags:
                if tag not in space:
                    continue
                s, u = _annual_series(space[tag]["units"], field in INSTANT)
                if not s:
                    continue
                unit = unit or u
                for end, val in s.items():
                    merged.setdefault(end, val)   # earlier tag wins that year
            if merged:
                got[field] = merged
        return got, unit

    gaap_fields, gaap_unit = harvest("us-gaap", GAAP_MAP)
    ifrs_fields, ifrs_unit = harvest("ifrs-full", IFRS_MAP)
    if len(ifrs_fields) > len(gaap_fields):
        per_field, framework, unit = ifrs_fields, "ifrs", ifrs_unit
    else:
        per_field, framework, unit = gaap_fields, "us-gaap", gaap_unit
    # ── share count ───────────────────────────────────────────────────────────
    # 🔴 2026-08-19. This used to read ONLY the dei cover-page tag
    # `EntityCommonStockSharesOutstanding` and attach the value NEAREST each
    # fiscal year end, with no bound on how near. Two ways that goes wrong, both
    # measured:
    #   * Visa has two such entries in total, none after 2024. FY2025 therefore
    #     matched a years-old count of ~469M against a real ~1.9bn, and the store
    #     reported EPS 42.74 where Visa's is ~10. A wrong EPS is strictly worse
    #     than a missing one — it prices a mega-cap at a quarter of its multiple.
    #   * Alphabet does not publish the tag at all, so shares came out None.
    #
    # EPS is defined on WEIGHTED-AVERAGE DILUTED shares, and that is a us-gaap
    # annual duration filed with the income statement — same period, same filing,
    # populated where the cover-page tag is not (GOOGL 12.23bn, XOM 4.305bn). So
    # prefer it, per fiscal year, and keep the cover-page count only as a bounded
    # fallback. A year with neither gets None, which is the honest answer.
    # Ordered best-to-worst as an EPS denominator. `shares_basis` records WHICH
    # one supplied the figure, because they are not interchangeable: EPS is
    # defined on a WEIGHTED AVERAGE, so a period-end count is an approximation,
    # and a basic count is a different statistic from a diluted one. Without the
    # basis on the row, a cross-sectional PE screen silently compares a diluted
    # multiple for one company against a basic one for the next.
    SHARE_TAGS = [("WeightedAverageNumberOfDilutedSharesOutstanding", "diluted"),
                  ("WeightedAverageNumberOfSharesOutstandingBasic", "basic"),
                  ("CommonStockSharesOutstanding", "period_end"),
                  ("CommonStockSharesIssued", "issued")]

    # EPS = (net income − PREFERRED DIVIDENDS) / weighted-average shares. The
    # subtraction was missing, which overstates earnings available to common for
    # every issuer with preferred stock — banks, insurers and REITs routinely —
    # and an overstated EPS understates PE, making such a name look cheaper than
    # it is. Stored as its own field plus a derived `net_income_to_common` so a
    # consumer can see the adjustment rather than inherit it silently.
    PREF_TAGS = ["PreferredStockDividendsAndOtherAdjustments",
                 "PreferredStockDividendsIncomeStatementImpact",
                 "DividendsPreferredStock"]
    gaap_space = facts.get("us-gaap", {})
    shares_by_fy: dict[str, float] = {}
    basis_by_fy: dict[str, str] = {}
    for tag, basis in SHARE_TAGS:
        if tag not in gaap_space:
            continue
        instant = tag.startswith("CommonStock")
        ser, _ = _annual_series(gaap_space[tag]["units"], instant)
        for end, val in ser.items():
            if end not in shares_by_fy:
                shares_by_fy[end] = val
                basis_by_fy[end] = basis

    pref_by_fy: dict[str, float] = {}
    for tag in PREF_TAGS:
        if tag not in gaap_space:
            continue
        ser, _ = _annual_series(gaap_space[tag]["units"], False)
        for end, val in ser.items():
            pref_by_fy.setdefault(end, val)

    # dei cover-page count: a point-in-time figure filed WITH the 10-K, so it is
    # only meaningful within about a year of the period it accompanies.
    SHARES_MAX_GAP_DAYS = 400
    shares_series = {}
    for tag in ("EntityCommonStockSharesOutstanding",):
        if tag in dei:
            for e in dei[tag]["units"].get("shares", []):
                if e.get("end"):
                    shares_series[e["end"]] = e.get("val")

    # Future-dated instants are debt MATURITY schedules, not fiscal years —
    # PMTV reported LongTermDebt repayments due 2026-2029 as instants with
    # future `end` dates, which minted phantom FY rows. A fiscal year that
    # hasn't ended yet cannot have been filed.
    today = dt.date.today().isoformat()
    ends = sorted({e for s in per_field.values() for e in s if e <= today})[-N_YEARS:]
    rows = []
    for end in ends:
        # `framework` and `unit` are recorded, not inferred downstream. A row
        # whose figures are TWD must be distinguishable from a USD row before
        # anything divides a price by it.
        row = {"fy_end": end, "source": "edgar",
               "framework": framework, "currency": unit,
               # the date this fiscal year first became public — the only
               # honest timestamp to lag a backtest signal to
               "filed": filed_by_fy.get(end)}
        for field in GAAP_MAP:                # union key set — IFRS_MAP matches it
            row[field] = per_field.get(field, {}).get(end)
        # capex is reported as cash PAID (positive); store it negative to match
        # the yfinance convention the India store uses, and derive FCF the same
        # way the scan would: cfo + capex.
        if row.get("capex") is not None:
            row["capex"] = -abs(row["capex"])
        cfo, capex = row.get("cfo"), row.get("capex")
        row["free_cash_flow"] = (cfo + capex) if (cfo is not None and capex is not None) else None
        # weighted-average diluted for this exact FY, else a cover-page count
        # filed close enough to it to be about the same company.
        shares = shares_by_fy.get(end)
        if shares is None and shares_series:
            near = min(shares_series, key=lambda d: abs(
                dt.date.fromisoformat(d) - dt.date.fromisoformat(end)))
            gap = abs((dt.date.fromisoformat(near) - dt.date.fromisoformat(end)).days)
            shares = shares_series[near] if gap <= SHARES_MAX_GAP_DAYS else None
        row["shares"] = shares
        row["shares_basis"] = basis_by_fy.get(end) if shares is not None else None
        pref = pref_by_fy.get(end)
        row["preferred_dividends"] = pref
        ni_row = row.get("net_income")
        # Absent a preferred-dividend tag the adjustment is zero, which is the
        # right default: the vast majority of filers have no preferred stock,
        # and treating "not reported" as "unknown" would null out earnings for
        # all of them.
        row["net_income_to_common"] = (
            (ni_row - (pref or 0.0)) if ni_row is not None else None)
        rows.append(row)
    return rows


# ── transient-failure retry ───────────────────────────────────────────────────
# A full pass is ~7,670 requests over ~2h, so a per-request failure rate that
# looks negligible still loses names: the 2026-08-20 backfill ended
# "7,669 fetched, 1 failed" — one ticker with no fundamentals for a week until
# FRESH_DAYS expires and it gets another try.
#
# Retried on transport errors AND on 429/5xx, which for SEC means "slow down" or
# "try later" rather than an answer. 404 is NOT retried — for a fund or an ADR
# with no XBRL it is the correct, final reply, and the caller already treats it
# as one. Backoff starts at 1s and caps at 20s, comfortably inside SEC's
# documented 10 req/s while still riding out a rate-limit burst.
def _sec_retryable(exc: Exception) -> bool:
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


try:
    from tenacity import retry as _tretry, retry_if_exception, stop_after_attempt, wait_exponential

    def _log_sec_retry(state):
        print(f"    sec: {type(state.outcome.exception()).__name__} — "
              f"retry {state.attempt_number}/4 in {state.next_action.sleep:.0f}s")

    _retry_sec = _tretry(
        retry=retry_if_exception(_sec_retryable),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        stop=stop_after_attempt(4),
        before_sleep=_log_sec_retry,
        reraise=True,
    )
except ImportError:                      # tenacity absent → previous behaviour
    def _retry_sec(fn):
        return fn


@_retry_sec
def fetch_companyfacts(cik: int, session: requests.Session) -> dict | None:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
    r = session.get(url, headers=UA, timeout=30)
    if r.status_code == 404:        # no XBRL facts (funds, some ADRs) — real answer
        return None
    r.raise_for_status()
    return r.json()


# ── successor-CIK resolution ──────────────────────────────────────────────────
# 🔴 2026-08-19. `company_tickers.json` maps XOM to CIK 2115436 — an entity also
# named "Exxon Mobil Corporation", 78 KB of companyfacts, ZERO parseable annual
# rows. Exxon's actual filing history (3.1 MB, revenue $332bn, equity $259bn) is
# under the legacy CIK 34088. When a company re-registers, SEC's ticker map
# follows the new registrant while the history stays behind, and the collector
# fetched the empty one, parsed 0 rows, and dropped the ticker silently.
#
# So a mapped CIK that yields zero rows is treated as a RESOLUTION FAILURE, not
# as an absence, and retried against the name→CIK index — which is keyed by
# company name and therefore still points at the entity holding the filings.
# Genuinely factless tickers (ETFs, trusts) resolve to nothing here too and are
# reported as such, so the two cases stay distinguishable.
CIK_LOOKUP_CACHE = FUND_DIR / "cik_lookup_by_name.json"
_LOOKUP_URL = "https://www.sec.gov/Archives/edgar/cik-lookup-data.txt"


def load_name_index(session: requests.Session, refresh_days: int = 30) -> dict:
    """{UPPERCASE COMPANY NAME: [cik, ...]} from SEC's cik-lookup-data.txt."""
    if CIK_LOOKUP_CACHE.exists():
        age = (time.time() - CIK_LOOKUP_CACHE.stat().st_mtime) / 86400
        if age < refresh_days:
            try:
                return json.loads(CIK_LOOKUP_CACHE.read_text())
            except Exception:
                pass
    idx: dict[str, list] = {}
    r = session.get(_LOOKUP_URL, headers=UA, timeout=180, stream=True)
    r.raise_for_status()
    for raw in r.iter_lines():
        if not raw:
            continue
        s = raw.decode("latin-1", "replace").rstrip(":")
        name, _, cik = s.rpartition(":")
        if name and cik.isdigit():
            idx.setdefault(name.strip().upper(), []).append(int(cik))
    CIK_LOOKUP_CACHE.parent.mkdir(parents=True, exist_ok=True)
    CIK_LOOKUP_CACHE.write_text(json.dumps(idx))
    return idx


def _name_variants(entity: str):
    """SEC's name index uses abbreviated legal suffixes ('CORP' not
    'Corporation'), so try the filed name and its common abbreviations."""
    n = " ".join(entity.upper().replace(",", " ").replace(".", " ").split())
    seen, out = set(), []
    for v in (n,
              n.replace(" CORPORATION", " CORP"),
              n.replace(" INCORPORATED", " INC"),
              n.replace(" COMPANY", " CO"),
              n.replace(" LIMITED", " LTD"),
              n.replace(" CORPORATION", " CORP").replace(" /DE/", ""),
              n.rsplit(" ", 1)[0] if " " in n else n):
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def resolve_by_name(doc: dict, session: requests.Session,
                    name_idx: dict, tried: int) -> tuple[dict | None, int | None]:
    """Given an empty-but-present companyfacts doc, find the CIK that has the
    filings. Returns (better_doc, better_cik) or (None, None)."""
    entity = (doc or {}).get("entityName") or ""
    if not entity:
        return None, None
    # Only OPERATING COMPANIES get the retry. A re-registered filer still carries
    # its accounting namespace (XOM's empty successor doc has `us-gaap`); an ETF,
    # trust or shell has `dei` alone and never will. Without this discriminator
    # the fallback fires on every fund in a 7,699-name universe, spending four
    # extra requests each to confirm a real absence — measured at ~0.6 tickers/s
    # against the 4/s the rate limit allows.
    ns = set((doc.get("facts") or {}).keys())
    if not (ns & {"us-gaap", "ifrs-full"}):
        return None, None
    for variant in _name_variants(entity):
        for cik in name_idx.get(variant, [])[:4]:
            if cik == tried:
                continue
            time.sleep(RATE)
            try:
                alt = fetch_companyfacts(cik, session)
            except Exception:
                continue
            if alt and parse_companyfacts(alt):
                return alt, cik
    return None, None


# ── store I/O (same atomic pattern as the India collector) ────────────────────
def load_store() -> pd.DataFrame:
    return pd.read_parquet(STORE) if STORE.exists() else pd.DataFrame()


def _store_lock(name: str = "us_fundamentals_edgar"):
    """Exclusive lock around a store's read-modify-write.

    `name` picks the lock file, so sibling collectors that write their own
    parquet (collect_us_sic) serialise against themselves without blocking an
    unrelated fundamentals run.

    🔴 2026-08-21: two full collections ran CONCURRENTLY against this store —
    one launched here, one from a terminal — and nothing prevented it. The write
    is atomic (tmp + replace), which protects a READER from a half-file, but
    does nothing for two WRITERS: each holds its own in-memory `store`, drops
    the tickers it refetched, concatenates its own rows and replaces the file,
    so whichever finishes second silently discards everything the first added.

    That run happened to come out coherent because the two passes covered the
    same tickers in the same hash order, which is luck of timing, not design.
    It is the same lost-update shape `refresh_panels._panel_lock` was added for
    the day before; this file simply had not been given the same treatment.
    """
    try:
        from filelock import FileLock

        return FileLock(f"/tmp/{name}.lock", timeout=3600)
    except ImportError:
        import contextlib

        print("  ⚠ filelock absent — a concurrent collection can silently lose rows")
        return contextlib.nullcontext()


def save_store(store: pd.DataFrame, new_rows: list, collected_at: str) -> pd.DataFrame:
    if not new_rows:
        return store
    nd = pd.DataFrame(new_rows)
    nd["collected_at"] = collected_at
    with _store_lock():
        # Re-read INSIDE the lock rather than merging into the caller's copy.
        # The in-memory `store` was loaded at startup and is stale by exactly
        # whatever another process committed since — merging into it is what
        # discards their rows. Re-reading makes this a genuine read-modify-write.
        on_disk = pd.read_parquet(STORE) if STORE.exists() else store
        if not on_disk.empty:
            on_disk = on_disk[~on_disk["ticker"].astype(str).str.upper().isin(
                nd["ticker"].astype(str).str.upper())]
        merged = pd.concat([on_disk, nd], ignore_index=True)
        STORE.parent.mkdir(parents=True, exist_ok=True)
        if STORE.exists():
            shutil.copy2(STORE, STORE.with_suffix(".parquet.bak"))
        tmp = STORE.with_suffix(".parquet.tmp")
        merged.to_parquet(tmp, index=False)
        tmp.replace(STORE)
    return merged


def universe() -> list[str]:
    """Live US symbol universe: the per-ticker OHLC tree the scan writes.

    Filenames are the symbols, so this needs no parquet read at all — one
    directory listing, and it tracks the scan exactly.
    """
    if OHLC_DIR.exists():
        syms = sorted(p.stem for p in OHLC_DIR.glob("*.parquet") if p.stem)
        if len(syms) > 1000:            # a plausible US universe, not a stub
            return syms
        print(f"  ! {OHLC_DIR} holds only {len(syms)} symbols — falling back")
    import duckdb  # only needed here; the venv runner may lack it — fall back
    try:
        con = duckdb.connect()
        syms = [r[0] for r in con.execute(
            f"SELECT DISTINCT Symbol FROM read_parquet('{UNIVERSE_PARQUET}')").fetchall()]
        print(f"  ! universe from STALE fallback {UNIVERSE_PARQUET.name} "
              f"({len(syms)} symbols) — no job refreshes this file")
        return [s for s in syms if s]
    except Exception:
        pass
    return []


def _universe_fallback() -> list[str]:
    """pandas fallback when duckdb isn't importable in this interpreter."""
    df = pd.read_parquet(UNIVERSE_PARQUET, columns=["Symbol"])
    return sorted(df["Symbol"].dropna().unique().tolist())


def coverage(store: pd.DataFrame) -> None:
    if store.empty:
        print("  store empty"); return
    import collections
    usable = store.dropna(subset=["cfo", "total_assets"])
    tick = sorted(usable["ticker"].astype(str).str.upper().unique())
    c = collections.Counter(t[0] for t in tick if t)
    a_share = c.get("A", 0) / len(tick) * 100 if tick else 0
    print(f"  usable tickers (cfo+total_assets): {len(tick)}")
    print(f"  A-share: {a_share:.1f}%  letters: {dict(sorted(c.items()))}")


# ── self test (offline) ───────────────────────────────────────────────────────
def self_test() -> int:
    doc = {"facts": {"us-gaap": {
        "NetIncomeLoss": {"units": {"USD": [
            # comparative restated year: later filing must win
            {"start": "2023-01-01", "end": "2023-12-31", "val": 100, "form": "10-K", "filed": "2024-02-01"},
            {"start": "2023-01-01", "end": "2023-12-31", "val": 101, "form": "10-K", "filed": "2025-02-01"},
            {"start": "2024-01-01", "end": "2024-12-31", "val": 200, "form": "10-K", "filed": "2025-02-01"},
            # quarterly row inside the 10-K: must be excluded by span filter
            {"start": "2024-10-01", "end": "2024-12-31", "val": 999, "form": "10-K", "filed": "2025-02-01"},
        ]}},
        "Assets": {"units": {"USD": [
            {"end": "2023-12-31", "val": 1000, "form": "10-K", "filed": "2024-02-01"},
            {"end": "2024-12-31", "val": 1100, "form": "10-K", "filed": "2025-02-01"},
        ]}},
        # debt maturity schedule: future-dated instants must NOT mint FY rows
        "LongTermDebtNoncurrent": {"units": {"USD": [
            {"end": "2029-12-31", "val": 555, "form": "10-K", "filed": "2025-02-01"},
        ]}},
        "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [
            {"start": "2024-01-01", "end": "2024-12-31", "val": 300, "form": "10-K", "filed": "2025-02-01"},
        ]}},
        "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [
            {"start": "2024-01-01", "end": "2024-12-31", "val": 50, "form": "10-K", "filed": "2025-02-01"},
        ]}},
    }, "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [
        {"end": "2025-01-15", "val": 10}]}}}}}
    rows = parse_companyfacts(doc)
    by_end = {r["fy_end"]: r for r in rows}
    assert by_end["2023-12-31"]["net_income"] == 101, "latest filing must win restatements"
    assert by_end["2024-12-31"]["net_income"] == 200
    assert all(r["net_income"] != 999 for r in rows), "quarterly span must be excluded"
    assert by_end["2024-12-31"]["capex"] == -50, "capex stored negative (yfinance convention)"
    assert by_end["2024-12-31"]["free_cash_flow"] == 250
    assert by_end["2024-12-31"]["shares"] == 10
    assert by_end["2024-12-31"]["total_assets"] == 1100
    assert "2029-12-31" not in by_end, "future maturity dates must not mint FY rows"
    print("self-test OK")
    return 0


# ── main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="max tickers this run (0 = all)")
    ap.add_argument("--rate", type=float, default=RATE)
    ap.add_argument("--max-age-days", type=int, default=FRESH_DAYS)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--no-cik-fallback", action="store_true",
                    help="skip successor-CIK resolution (faster, loses XOM-class names)")
    ap.add_argument("--only", nargs="*", help="restrict to these tickers (testing)")
    a = ap.parse_args()
    if a.self_test:
        return self_test()

    try:
        syms = universe() or _universe_fallback()
    except Exception as e:
        print(f"cannot load universe from {UNIVERSE_PARQUET}: {e}")
        return 1
    cik_map = load_cik_map()
    store = load_store()

    fresh: set[str] = set()
    if not store.empty and "collected_at" in store.columns:
        cutoff = (dt.datetime.now(dt.timezone.utc)
                  - dt.timedelta(days=a.max_age_days)).isoformat()
        fresh = set(store.loc[store["collected_at"] >= cutoff, "ticker"]
                    .astype(str).str.upper())

    todo = [s for s in _hash_order(syms)
            if s.upper() in cik_map and s.upper() not in fresh]
    no_cik = sum(1 for s in syms if s.upper() not in cik_map)
    if a.only:
        want = {s.upper() for s in a.only}
        todo = [s for s in syms if s.upper() in want and s.upper() in cik_map]
        fresh = set()
    if a.limit:
        todo = todo[: a.limit]
    print(f"universe {len(syms)} | no CIK {no_cik} | fresh-skip {len(fresh)} | fetching {len(todo)}")

    sess = requests.Session()
    name_idx = {}
    if not a.no_cik_fallback:
        try:
            name_idx = load_name_index(sess)
            print(f"name index: {len(name_idx):,} names (successor-CIK fallback armed)")
        except Exception as e:
            print(f"  ! name index unavailable, fallback disabled: {str(e)[:70]}")

    collected_at = dt.datetime.now(dt.timezone.utc).isoformat()
    pending: list[dict] = []
    done = failed = 0
    empty: list[str] = []          # doc present, zero rows, unresolved
    recovered: list[str] = []      # rescued via successor-CIK fallback
    for i, sym in enumerate(todo, 1):
        try:
            doc = fetch_companyfacts(cik_map[sym.upper()], sess)
            rows = parse_companyfacts(doc) if doc else []
            # A present-but-empty doc is a resolution failure, not an absence —
            # see the resolve_by_name comment. Retry before giving up on it.
            if doc and not rows and name_idx:
                alt, alt_cik = resolve_by_name(doc, sess, name_idx,
                                               tried=cik_map[sym.upper()])
                if alt:
                    rows = parse_companyfacts(alt)
                    recovered.append(f"{sym}→{alt_cik}")
            if doc and not rows:
                empty.append(sym)
            for row in rows:
                row["ticker"] = sym
                pending.append(row)
            done += 1
        except KeyboardInterrupt:
            print("\ninterrupted — checkpointing")
            break
        except Exception as e:
            failed += 1
            if failed <= 5:
                print(f"  ! {sym}: {str(e)[:60]}")
        if i % CHECKPOINT_EVERY == 0:
            store = save_store(store, pending, collected_at)
            pending = []
            print(f"  {i}/{len(todo)} checkpointed ({len(store):,} store rows)")
        time.sleep(a.rate)

    store = save_store(store, pending, collected_at)
    print(f"done: {done} fetched, {failed} failed, store {len(store):,} rows "
          f"/ {store['ticker'].nunique() if not store.empty else 0} tickers")
    if recovered:
        print(f"  recovered via successor-CIK: {len(recovered)} "
              f"({', '.join(recovered[:8])}{' …' if len(recovered) > 8 else ''})")
    # Named, not just counted. These are tickers SEC HAS a record for and we
    # could not parse — ETFs and trusts legitimately, but also any new tag or
    # framework we do not yet map. A bare count hides which.
    if empty:
        print(f"  no parseable annual facts: {len(empty)} "
              f"({', '.join(empty[:12])}{' …' if len(empty) > 12 else ''})")
    coverage(store)
    return 0


if __name__ == "__main__":
    sys.exit(main())
