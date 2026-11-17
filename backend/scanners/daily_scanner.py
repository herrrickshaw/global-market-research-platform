"""
Daily momentum scanner — vectorized for Cassandra Phase-1 data.
No fundamentals required; uses them when available.

Darvas / Buffett  (0–16 max with all data):
  D1  CMP within 15% of 52W high          → +2   (Darvas box ceiling)
  D2  CMP > EMA-50                         → +2   (uptrend)
  D3  Price in top 40% of 52W range        → +1   (range strength)
  D4  RSI 40–68                            → +1   (healthy momentum)
  D5  ROE > 12%        [if available]      → +1   (Buffett quality)
  D6  PE 5–30          [if available]      → +1   (Buffett value)
  D7  D/E < 1          [if available]      → +1   (Buffett safety)
  D8  CMP > EMA-200    [if available]      → +1   (secular uptrend)
  D9  MACD > signal    [if available]      → +1   (momentum confirmed)
  D10 Volume ratio > 1.5 [if available]    → +1   (volume confirms move)
  D11 EMA-20 > EMA-50  [if available]      → +1   (short MA above long)
  D12 BB %B > 0.5      [if available]      → +1   (price in upper Bollinger zone)
  D13 Stoch %K 20–80 & K > D [if avail]   → +1   (stoch bullish, not extreme)
  BUY ≥ 5/6 of max_score · WATCH ≥ 0.70 · AVOID below
  (a FRACTION of what was evaluable for that row, not a flat count — "[if
   available]" above is real, so a flat cut-off silently graded rows against
   criteria they never had. Fundamentals labelled median_imputed or, for pe/pb,
   derived_roe_only are treated as unavailable: a placeholder must not score.)

Piotroski (0–11 max with all data):
  F1  ROE > 0          [if available]      → +1
  F5  D/E < 0.5        [if available]      → +1
  F8  OPM > 15%        [if available]      → +1
  F9  Revenue growth > 0 [if available]    → +1
  FX1 CMP > EMA-50                         → +1
  FX2 RSI 40–70                            → +1
  FX3 CMP within 20% of 52W high           → +1
  FX4 Current ratio > 1.5 [if available]   → +1
  FX5 PB < 3           [if available]      → +1   (value screen)
  FX6 EMA-20 > EMA-50  [if available]      → +1   (momentum confirmation)
  FX7 ATR/CMP < 3%     [if available]      → +1   (low volatility / stable)
  BUY ≥ ceil(max×0.65) · WATCH ≥ ceil(max×0.40)
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

# Darvas signal cut-offs, as a fraction of the criteria actually evaluable for a
# row (score / max_score). See the block above the `signal` assignment in
# scan_darvas for the calibration and why these are fractions rather than counts.
BUY_RATIO = 5 / 6      # unchanged stringency: reproduces `score >= 5` at max 6
WATCH_RATIO = 0.70     # retuned from 0.50 to hold WATCH's universe share


# ── helpers ───────────────────────────────────────────────────────────────────

def _col(df: pd.DataFrame, name: str) -> pd.Series:
    """Return numeric column or an all-NaN series if missing."""
    return pd.to_numeric(df[name], errors='coerce') if name in df.columns \
        else pd.Series(np.nan, index=df.index)


def _vcrit(passes: pd.Series, valid: pd.Series) -> pd.Series:
    """Boolean criterion: True/False where valid, None elsewhere."""
    out = pd.Series(None, index=passes.index, dtype=object)
    out[valid] = passes[valid]
    return out


def _pts(crit: pd.Series, weight: int = 1) -> pd.Series:
    return (crit == True).astype(int) * weight   # noqa: E712


def _r(v) -> float | None:
    try:
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, 2)
    except (TypeError, ValueError):
        return None


def _b(v) -> bool | None:
    if v is None:
        return None
    try:
        return bool(v)
    except Exception:
        return None


def _strs(df: pd.DataFrame, col: str, default: str = '') -> list:
    """Extract a text column as a plain Python list — avoids iloc[i] in the loop."""
    if col in df.columns:
        return df[col].fillna(default).astype(str).tolist()
    return [default] * len(df)


# ── Darvas / Buffett ──────────────────────────────────────────────────────────

def scan_darvas(df: pd.DataFrame, lazy_load: bool = False) -> list[dict]:
    """
    OPTIMIZATION #3: Lazy-load optional metrics.
    Set lazy_load=False to load all metrics (e.g., for detailed analysis).
    Set lazy_load=True to skip expensive metrics (MACD, Bollinger, Stoch) unless needed.
    """
    if df.empty:
        return []

    d = df.reset_index(drop=True)

    # ── REQUIRED columns (always loaded - essential for core signals) ─────────
    cmp    = _col(d, 'cmp')
    h52    = _col(d, 'high_52w')
    l52    = _col(d, 'low_52w')
    e50    = _col(d, 'ema_50')
    rsi    = _col(d, 'rsi')

    # ── OPTIONAL columns (lazy-loaded only if needed) ───────────────────────
    # These are loaded by default unless lazy_load=True (OPTIMIZATION #3)
    if lazy_load:
        # Skip expensive metrics in daily phase — reduces token load by ~2-3%
        e20    = pd.Series(np.nan, index=d.index)  # Not used in core Darvas
        e200   = pd.Series(np.nan, index=d.index)  # Only for confirmation
        roe    = pd.Series(np.nan, index=d.index)  # Buffett filter
        pe     = pd.Series(np.nan, index=d.index)  # Buffett filter
        pb     = pd.Series(np.nan, index=d.index)  # Buffett filter
        de     = pd.Series(np.nan, index=d.index)  # Buffett filter
        macd   = pd.Series(np.nan, index=d.index)  # Optional momentum
        msig   = pd.Series(np.nan, index=d.index)  # Optional momentum
        bb_pct = pd.Series(np.nan, index=d.index)  # Optional support/resist
        bb_u   = pd.Series(np.nan, index=d.index)  # Optional support/resist
        bb_l   = pd.Series(np.nan, index=d.index)  # Optional support/resist
        stk    = pd.Series(np.nan, index=d.index)  # Optional momentum
        std    = pd.Series(np.nan, index=d.index)  # Optional momentum
        atr    = pd.Series(np.nan, index=d.index)  # Optional volatility
        # Load only if needed for portfolio-level analysis
        beta   = pd.Series(np.nan, index=d.index)
        cr     = pd.Series(np.nan, index=d.index)
        vr     = pd.Series(np.nan, index=d.index)
    else:
        # Full load (for detailed analysis, backtesting, etc.)
        e20    = _col(d, 'ema_20')
        e200   = _col(d, 'ema_200')
        roe    = _col(d, 'roe')
        pe     = _col(d, 'pe')
        pb     = _col(d, 'pb')
        de     = _col(d, 'debt_to_equity')
        macd   = _col(d, 'macd')
        msig   = _col(d, 'macd_signal')
        vr     = _col(d, 'volume_ratio')
        beta   = _col(d, 'beta')
        cr     = _col(d, 'current_ratio')
        bb_pct = _col(d, 'bb_pct')
        bb_u   = _col(d, 'bb_upper')
        bb_l   = _col(d, 'bb_lower')
        stk    = _col(d, 'stoch_k')
        std    = _col(d, 'stoch_d')
        atr    = _col(d, 'atr_14')

    # Non-optional metrics (always needed)
    opm    = _col(d, 'opm')
    mcap   = _col(d, 'market_cap')
    vol    = _col(d, 'volume')
    rg     = _col(d, 'revenue_growth')
    eps    = _col(d, 'eps')
    dy     = _col(d, 'dividend_yield')
    r1d    = _col(d, 'ret_1d')
    r1w    = _col(d, 'ret_1w')
    r1m    = _col(d, 'ret_1m')
    r3m    = _col(d, 'ret_3m')
    r6m    = _col(d, 'ret_6m')
    r1y    = _col(d, 'ret_1y')

    # Pre-extract text columns as lists — avoids d.iloc[i] (Series per row)
    tickers    = _strs(d, 'ticker')
    names      = _strs(d, 'name')
    rsi_sigs   = _strs(d, 'rsi_signal', 'HOLD')
    sectors    = _strs(d, 'sector')
    industries = _strs(d, 'industry')
    exchanges  = _strs(d, '_exchange')

    # ── Validity masks ────────────────────────────────────────────────────────
    h52s  = h52.where(h52 > 0)
    v_d1  = cmp.notna() & h52.gt(0) & h52.notna()
    v_d2  = cmp.notna() & e50.notna()
    v_d3  = cmp.notna() & h52.notna() & l52.notna() & (h52 - l52).gt(0)
    v_d4  = rsi.notna()
    # 🔴 AN IMPUTED FUNDAMENTAL IS NOT AN OBSERVATION, SO IT MUST NOT SCORE.
    # fundamentals_source labels each row 'median_imputed' | 'derived_price_join'
    # | 'derived_roe_only' | 'statements'. A median_imputed pe is the market
    # median by construction, which lands inside the Buffett 5-30 band every
    # time and hands out a free point; derived_roe_only rows carry a real roe but
    # left pe/pb untouched, so their pe is still that placeholder.
    #
    # This was harmless while lazy_load nulled these fields before scoring. The
    # moment the overlay was switched on it became load-bearing: 165 of Japan's
    # 319 BUYs (52%) and 14 of India's 23 sat on a placeholder pe. Gating here
    # rather than at read time keeps the values available to other consumers.
    #
    # Treating them as UNAVAILABLE (not as failures) is the correct move: they
    # drop out of max_score too, so a row with two known criteria is judged on
    # those two rather than penalised for what nobody measured.
    _src = _strs(d, 'fundamentals_source')
    _src = pd.Series(_src, index=d.index) if _src else pd.Series('', index=d.index)
    pe_measured = ~_src.isin(('median_imputed', 'derived_roe_only'))
    fund_measured = _src.ne('median_imputed')

    v_d5  = roe.notna() & fund_measured      # roe is real on derived_roe_only
    v_d6  = pe.notna() & pe_measured
    v_d7  = de.notna() & fund_measured
    v_d8  = cmp.notna() & e200.notna()
    v_d9  = macd.notna() & msig.notna()
    v_d10 = vr.notna()
    v_d11 = e20.notna() & e50.notna()
    v_d12 = bb_pct.notna()
    v_d13 = stk.notna() & std.notna()

    # ── Criteria (vectorized) ─────────────────────────────────────────────────
    c_near_high   = _vcrit((h52 - cmp) / h52s <= 0.15,               v_d1)
    c_above_e50   = _vcrit(cmp > e50,                                 v_d2)
    c_range_str   = _vcrit((cmp - l52) / (h52 - l52) >= 0.60,        v_d3)
    c_rsi_health  = _vcrit(rsi.between(40, 68),                       v_d4)
    c_roe         = _vcrit(roe > 12,                                  v_d5)
    c_pe          = _vcrit(pe.between(5, 30),                         v_d6)
    c_de          = _vcrit(de < 1.0,                                  v_d7)
    c_above_e200  = _vcrit(cmp > e200,                                v_d8)
    c_macd_bull   = _vcrit(macd > msig,                               v_d9)
    c_vol_surge   = _vcrit(vr > 1.5,                                  v_d10)
    c_ema_cross   = _vcrit(e20 > e50,                                 v_d11)
    c_bb_upper    = _vcrit(bb_pct > 0.5,                              v_d12)
    c_stoch_bull  = _vcrit(stk.between(20, 80) & (stk > std),        v_d13)

    score = (
        _pts(c_near_high, 2) + _pts(c_above_e50, 2) + _pts(c_range_str) +
        _pts(c_rsi_health) + _pts(c_roe) + _pts(c_pe) + _pts(c_de) +
        _pts(c_above_e200) + _pts(c_macd_bull) + _pts(c_vol_surge) +
        _pts(c_ema_cross) + _pts(c_bb_upper) + _pts(c_stoch_bull)
    )

    max_score = (
        6  # D1(2)+D2(2)+D3+D4 always available
        + v_d5.astype(int)  + v_d6.astype(int)  + v_d7.astype(int)
        + v_d8.astype(int)  + v_d9.astype(int)  + v_d10.astype(int)
        + v_d11.astype(int) + v_d12.astype(int) + v_d13.astype(int)
    )

    # ── thresholds are a FRACTION of what was actually evaluable ──────────────
    # 🔴 max_score was computed above and then thrown away: the signal used flat
    # `score >= 5 / >= 3` regardless of how many criteria existed. Combined with
    # the lazy_load default (which nulled roe/pe/pb/de, MACD, Bollinger,
    # stochastics and EMA-20/200 BEFORE scoring), production was scoring 4 of 13
    # criteria against a 15-point scale's thresholds — so `>= 5` meant 5 of 6,
    # and 31.4% of the whole universe came out BUY. A third of everything is not
    # a screen.
    #
    # Scoring on the fraction fixes both halves at once, and makes lazy_load a
    # coverage choice rather than a silent change of meaning: at max_score=6 the
    # BUY ratio reproduces `score >= 5` exactly, so this is a retune, not a
    # redefinition of BUY.
    #
    # BUY keeps today's stringency (5/6) — deliberately NOT re-fitted to a target
    # count. WATCH moved 0.50 -> 0.70 to hold its universe share. Measured
    # 2026-08-15 over 16,192 names, full criteria set, imputed fundamentals gated
    # out of both score and max_score:
    #     BUY   0.833 -> 1,197 names ( 7.4%)  [was 5,083 = 31.4%]
    #     WATCH 0.700 -> 2,827 names (17.5%)  [was 3,231 = 20.0%]
    #     total flagged 24.9%                 [was 51.4%]
    # Keeping WATCH at 0.50 would have flagged 44%+ of the universe as WATCH.
    #
    # Gating raises BUY relative to an ungated run (504 -> 1,197) because most
    # imputed criteria were FAILING: dropping a failed criterion removes it from
    # score and max_score alike, so a name stops being penalised for a number
    # nobody measured. Tightening BUY to 0.85 would restore ~3.4%, but that
    # target has no justification beyond matching a pre-gating measurement, so
    # the existing definition is kept instead.
    #
    # NOT calibrated against realised returns — that needs a walk-forward replay
    # on stock_quotes_history, which starts accumulating from 2026-08-15 and has
    # no depth yet. These ratios preserve the existing definition of BUY; they do
    # not claim it is the profit-maximising one.
    frac = score / max_score
    signal = np.where(frac >= BUY_RATIO, 'BUY',
                      np.where(frac >= WATCH_RATIO, 'WATCH', 'AVOID'))

    n_avail = (v_d1.astype(int) + v_d2.astype(int) + v_d3.astype(int) + v_d4.astype(int) +
               v_d5.astype(int) + v_d6.astype(int) + v_d7.astype(int) + v_d8.astype(int) +
               v_d9.astype(int) + v_d10.astype(int) + v_d11.astype(int) +
               v_d12.astype(int) + v_d13.astype(int))
    completeness = (n_avail / 13 * 100).round().astype(int)

    # ── Build output (no iloc, no _col inside loop) ────────────────────────────
    results = []
    for i in range(len(d)):
        vi = vol.iat[i]
        results.append({
            'ticker':         tickers[i],
            'name':           names[i],
            'cmp':            _r(cmp.iat[i]),
            'high_52w':       _r(h52.iat[i]),
            'low_52w':        _r(l52.iat[i]),
            'ema_20':         _r(e20.iat[i]),
            'ema_50':         _r(e50.iat[i]),
            'ema_200':        _r(e200.iat[i]),
            'rsi':            _r(rsi.iat[i]),
            'macd':           _r(macd.iat[i]),
            'macd_signal':    _r(msig.iat[i]),
            'volume_ratio':   _r(vr.iat[i]),
            'bb_upper':       _r(bb_u.iat[i]),
            'bb_lower':       _r(bb_l.iat[i]),
            'bb_pct':         _r(bb_pct.iat[i]),
            'stoch_k':        _r(stk.iat[i]),
            'stoch_d':        _r(std.iat[i]),
            'atr_14':         _r(atr.iat[i]),
            'rsi_signal':     rsi_sigs[i],
            'roe':            _r(roe.iat[i]),
            'pe':             _r(pe.iat[i]),
            'pb':             _r(pb.iat[i]),
            'opm':            _r(opm.iat[i]),
            'debt_to_equity': _r(de.iat[i]),
            'market_cap':     _r(mcap.iat[i]),
            'volume':         int(vi) if vi is not None and not (isinstance(vi, float) and math.isnan(vi)) else None,
            'beta':           _r(beta.iat[i]),
            'current_ratio':  _r(cr.iat[i]),
            'revenue_growth': _r(rg.iat[i]),
            'eps':            _r(eps.iat[i]),
            'dividend_yield': _r(dy.iat[i]),
            'ret_1d':         _r(r1d.iat[i]),
            'ret_1w':         _r(r1w.iat[i]),
            'ret_1m':         _r(r1m.iat[i]),
            'ret_3m':         _r(r3m.iat[i]),
            'ret_6m':         _r(r6m.iat[i]),
            'ret_1y':         _r(r1y.iat[i]),
            'sector':         sectors[i],
            'industry':       industries[i],
            'score':          int(score.iat[i]),
            'max_score':      int(max_score.iat[i]),
            'signal':         str(signal[i]),
            'completeness':   int(completeness.iat[i]),
            'criteria': {
                'near_52w_high':  _b(c_near_high.iat[i]),
                'above_ema50':    _b(c_above_e50.iat[i]),
                'range_strength': _b(c_range_str.iat[i]),
                'rsi_healthy':    _b(c_rsi_health.iat[i]),
                'buffett_roe':    _b(c_roe.iat[i]),
                'buffett_pe':     _b(c_pe.iat[i]),
                'buffett_de':     _b(c_de.iat[i]),
                'above_ema200':   _b(c_above_e200.iat[i]),
                'macd_bull':      _b(c_macd_bull.iat[i]),
                'volume_surge':   _b(c_vol_surge.iat[i]),
                'ema_cross':      _b(c_ema_cross.iat[i]),
                'bb_upper_half':  _b(c_bb_upper.iat[i]),
                'stoch_bullish':  _b(c_stoch_bull.iat[i]),
            },
            '_exchange': exchanges[i],
        })
    return results


# ── Piotroski (simplified) ────────────────────────────────────────────────────

def _winsor(s: pd.Series, lo: float = 0.01, hi: float = 0.99) -> pd.Series:
    """Clip to the 1st/99th percentile before any z-score.

    Without this a single ratio blow-up dominates the whole factor: a stock on a
    P/B of 0.02 produces a B/P of 50 against a universe median near 0.3, and the
    resulting z-score buries every other name at the bottom of the distribution.
    Winsorising is the standard fix in factor construction and is why index
    providers quote *normalised* scores rather than raw ratios.
    """
    v = s.dropna()
    if len(v) < 20:
        return s
    return s.clip(v.quantile(lo), v.quantile(hi))


def _z_within(value: pd.Series, group: pd.Series, min_n: int = 8) -> pd.Series:
    """Z-score within industry, falling back to the whole universe.

    🔴 WITHIN-INDUSTRY IS THE POINT, NOT A REFINEMENT. A bank's P/B and a
    software firm's P/B are not comparable numbers, so a universe-wide value
    z-score mostly ranks industries against each other and only incidentally
    ranks companies. The platform already measured this: sector-relative
    cheapness corrects at +5.06%/6M (t=2.87) while the raw cross-section is far
    weaker. min_n mirrors the screen's own MIN_IND — an industry too small to
    have a distribution gets scored against the universe instead of against
    three peers, which would otherwise manufacture extreme z-scores from noise.
    """
    v = _winsor(value)
    out = pd.Series(np.nan, index=v.index, dtype=float)
    g = group.fillna("")
    big = g.map(g.value_counts()) >= min_n
    for key, idx in v.groupby(g).groups.items():
        idx = pd.Index(idx)
        sub = v.loc[idx]
        if not key or not big.loc[idx].iloc[0] or sub.notna().sum() < min_n:
            continue
        sd = sub.std(ddof=0)
        out.loc[idx] = (sub - sub.mean()) / sd if sd and sd > 0 else 0.0
    # universe fallback for everything not scored within its industry
    miss = out.isna() & v.notna()
    if miss.any():
        sd = v.std(ddof=0)
        out.loc[miss] = ((v - v.mean()) / sd).loc[miss] if sd and sd > 0 else 0.0
    return out


def _mean_z(parts: list[pd.Series], min_parts: int = 2) -> tuple[pd.Series, pd.Series]:
    """Average the available z-scores; return (score, n_components).

    Averaging over what EXISTS rather than filling gaps with zero is deliberate:
    a zero fill is a claim that the missing metric was exactly average, which is
    the same fiction as median imputation and is what E-028 punished. Rows below
    min_parts are left NaN — unranked, not mid-ranked.
    """
    stack = pd.concat(parts, axis=1)
    n = stack.notna().sum(axis=1)
    score = stack.mean(axis=1, skipna=True)
    return score.where(n >= min_parts), n


def scan_piotroski(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []

    d = df.reset_index(drop=True)

    # ── Pre-compute every column once ─────────────────────────────────────────
    cmp    = _col(d, 'cmp')
    h52    = _col(d, 'high_52w')
    e20    = _col(d, 'ema_20')
    e50    = _col(d, 'ema_50')
    e200   = _col(d, 'ema_200')
    rsi    = _col(d, 'rsi')
    roe    = _col(d, 'roe')
    opm    = _col(d, 'opm')
    pb     = _col(d, 'pb')
    pe     = _col(d, 'pe')          # for the composite value score, below
    de     = _col(d, 'debt_to_equity')
    cr     = _col(d, 'current_ratio')
    rg     = _col(d, 'revenue_growth')
    mcap   = _col(d, 'market_cap')
    vol    = _col(d, 'volume')
    beta   = _col(d, 'beta')
    eps    = _col(d, 'eps')
    dy     = _col(d, 'dividend_yield')
    vr     = _col(d, 'volume_ratio')
    macd   = _col(d, 'macd')
    msig   = _col(d, 'macd_signal')
    bb_u   = _col(d, 'bb_upper')
    bb_l   = _col(d, 'bb_lower')
    bb_pct = _col(d, 'bb_pct')
    stk    = _col(d, 'stoch_k')
    std    = _col(d, 'stoch_d')
    atr    = _col(d, 'atr_14')
    r1d    = _col(d, 'ret_1d')
    r1w    = _col(d, 'ret_1w')
    r1m    = _col(d, 'ret_1m')
    r3m    = _col(d, 'ret_3m')
    r6m    = _col(d, 'ret_6m')
    r1y    = _col(d, 'ret_1y')

    # Pre-extract text columns
    tickers    = _strs(d, 'ticker')
    names      = _strs(d, 'name')
    rsi_sigs   = _strs(d, 'rsi_signal', 'HOLD')
    sectors    = _strs(d, 'sector')
    industries = _strs(d, 'industry')
    exchanges  = _strs(d, '_exchange')

    # ── Validity masks ────────────────────────────────────────────────────────
    h52s  = h52.where(h52 > 0)
    v_f1  = roe.notna()
    v_f5  = de.notna()
    v_f8  = opm.notna()
    v_f9  = rg.notna()
    v_fx1 = cmp.notna() & e50.notna()
    v_fx2 = rsi.notna()
    v_fx3 = cmp.notna() & h52.gt(0) & h52.notna()
    v_fx4 = cr.notna()
    v_fx5 = pb.notna()
    v_fx6 = e20.notna() & e50.notna()
    v_fx7 = atr.notna() & cmp.gt(0)

    # ── Criteria ──────────────────────────────────────────────────────────────
    c_f1   = _vcrit(roe > 0,                              v_f1)
    c_f5   = _vcrit(de < 0.5,                             v_f5)
    c_f8   = _vcrit(opm > 15,                             v_f8)
    c_f9   = _vcrit(rg > 0,                               v_f9)
    c_fx1  = _vcrit(cmp > e50,                            v_fx1)
    c_fx2  = _vcrit(rsi.between(40, 70),                  v_fx2)
    c_fx3  = _vcrit((h52 - cmp) / h52s <= 0.20,          v_fx3)
    c_fx4  = _vcrit(cr > 1.5,                             v_fx4)
    c_fx5  = _vcrit(pb < 3,                               v_fx5)
    c_fx6  = _vcrit(e20 > e50,                            v_fx6)
    c_fx7  = _vcrit(atr / cmp.where(cmp > 0) < 0.03,     v_fx7)

    score = (
        _pts(c_f1) + _pts(c_f5) + _pts(c_f8) + _pts(c_f9) +
        _pts(c_fx1) + _pts(c_fx2) + _pts(c_fx3) + _pts(c_fx4) +
        _pts(c_fx5) + _pts(c_fx6) + _pts(c_fx7)
    )

    max_score = (
        v_f1.astype(int)  + v_f5.astype(int)  + v_f8.astype(int)  + v_f9.astype(int)  +
        v_fx1.astype(int) + v_fx2.astype(int) + v_fx3.astype(int) + v_fx4.astype(int) +
        v_fx5.astype(int) + v_fx6.astype(int) + v_fx7.astype(int)
    ).clip(lower=1)

    # ── Composite RANKING, replacing the pass/fail cut ────────────────────────
    #
    # 🔴 WHY THE OLD THRESHOLDS HAD TO GO. Scored 2026-08-17 against NSE's own
    # NIFTY200 Quality 30, the pass/fail version flagged 85.5% of the India
    # universe and 196 of the 200 Nifty 200 names. It matched 30 of 30 index
    # members — but chance alone predicts 29.4 of 30 when you admit almost
    # everything, so p=0.52: a null result wearing a perfect score. A filter that
    # admits 85% of its universe transmits almost no information.
    #
    # Piotroski (2000) was never meant to be used this way. The F-score is a
    # 9-point RANKING applied WITHIN a value universe to sort it, not a standalone
    # universal pass/fail. Asness/Frazzini/Pedersen (Quality Minus Junk) and
    # Bender et al. (MSCI, "Foundations of Factor Investing") likewise build
    # continuous scores and take the top slice. So does NSE: its factor indices
    # rank on a normalised score and cut at 30 or 50 names.
    #
    # 🔴 PROVENANCE GATES THE RANKING, and here it matters far more than it did
    # for a filter. India measured 2026-08-17: 39.8% median_imputed, 38.8%
    # derived_roe_only, only 21.3% derived_price_join. A median-imputed pe IS the
    # market median, so ranking on it does not merely add noise — it plants ~40%
    # of the universe at dead centre and pushes genuinely measured names out to
    # the tails, inverting the very ordering the rank exists to produce. Gated
    # exactly as scan_darvas gates (E-028).
    _src_p = _strs(d, 'fundamentals_source')
    _src_p = pd.Series(_src_p, index=d.index) if _src_p else pd.Series('', index=d.index)
    pe_ok = ~_src_p.isin(('median_imputed', 'derived_roe_only'))   # pe/pb untouched on both
    fu_ok = _src_p.ne('median_imputed')                            # roe real on derived_roe_only
    ind_g = pd.Series(industries, index=d.index)

    # VALUE — earnings yield + book yield, the E/P and B/P of NSE's Value 50
    # (its third leg, S/P, needs a sales figure this frame does not carry; the
    # score averages over what exists rather than inventing it).
    #
    # 1/pe is used unguarded ON PURPOSE: a loss-maker's negative P/E inverts to a
    # negative earnings yield and therefore sorts BELOW every profitable name,
    # which is the correct ordering. Special-casing it to NaN would quietly
    # exclude loss-makers from the value screen instead of ranking them last.
    # 🔴 AN IMPLAUSIBLE RATIO IS A BROKEN NUMBER, NOT A CHEAP STOCK, and a rank
    # is far more exposed to that than a filter was. Measured for India
    # 2026-08-17: P/B is well-behaved in the bulk (median 2.93, RELIANCE 3.13,
    # HDFCBANK 1.99, TCS 10.09) but 12 of the 508 value-eligible names carry
    # P/B < 0.10, bottoming at 0.002 — a claim that the market prices the company
    # at a fifth of a percent of its book value. Those 12 took the entire top of
    # the first value ranking built here.
    #
    # Winsorising did NOT save it: the bad tail is ~2.4% of the sample while the
    # clip is at the 1st percentile, so the junk survived and then set the scale.
    # Percentile clipping defends against a heavy tail, not against wrong data.
    #
    # So bound on plausibility and treat anything outside as UNMEASURED rather
    # than clipping it to the edge — clipping would keep a fabricated value at
    # the extreme of the ranking, which is the opposite of what is wanted. The
    # bounds are deliberately loose: a genuine deep-value name at 0.3x book still
    # scores, and only physically implausible values drop out.
    # 🔴 AND A SECOND, WORSE ONE: CORRUPT EPS, WHICH A VALUE RANK ACTIVELY SEEKS
    # OUT. pe itself is computed correctly (verified: pe == cmp/eps exactly for
    # every name checked), but `eps` is wrong for a subset — measured 2026-08-17,
    # DOMS carries eps=2377.87 on a price of 2215.9, ARKADE eps=242.90 on 133.3.
    # An EPS above the share price means earnings were never divided by the share
    # count. RELIANCE (32.40 -> pe 40.4) and TCS (135.70 -> pe 17.4) are correct,
    # so this is a subset defect, not a units problem across the board.
    #
    # This is worse than a merely noisy field because the error is DIRECTIONAL: a
    # too-large EPS produces a too-small P/E, which a cheapness rank reads as
    # maximally attractive. The screen would surface broken records first, every
    # time, and they would look like its best ideas. 37 of the 457 priced names
    # sit under P/E 5 and 21 under P/E 2.
    #
    # A floor of 3 is a data-integrity guard, not a view on valuation, and it has
    # a real cost: a genuine sub-3 P/E would be discarded with the corrupt ones.
    # That trade is worth taking while the source defect is open (E-038) —
    # discarding a rare true positive is recoverable, publishing corrupted data
    # as a top pick is not.
    pb_ok = pb.between(0.10, 100)
    pe_ok_val = pe.between(3.0, 1000)
    ep = (1.0 / pe.where(pe_ok_val)).where(pe_ok)
    bp = (1.0 / pb.where(pb_ok)).where(pe_ok)
    # min_parts=2 — BOTH legs required. With min_parts=1 a name whose P/B was
    # rejected as implausible still scored on E/P alone and could reach BUY while
    # DISPLAYING the broken P/B, which is how a 0.03 survived the bound above.
    # "Composite value" has to mean both ratios actually measured, or the column
    # name is a promise the data does not keep.
    value_z, value_n = _mean_z([_z_within(ep, ind_g), _z_within(bp, ind_g)], min_parts=2)

    # QUALITY — profitability, safety, growth: the QMJ triple, and close to
    # NSE Quality 30's ROE / debt-equity / earnings-variability. True 5-year EPS
    # VARIABILITY needs a history this snapshot does not hold, so revenue growth
    # stands in for the growth leg and the gap is stated rather than papered over.
    quality_z, quality_n = _mean_z([
        _z_within(roe.where(fu_ok), ind_g),          # profitability
        _z_within(opm.where(fu_ok), ind_g),          # profitability
        _z_within(-de.where(fu_ok), ind_g),          # safety (less debt is better)
        _z_within(cr.where(fu_ok), ind_g),           # safety
        _z_within(rg.where(fu_ok), ind_g),           # growth (proxy)
    ], min_parts=2)

    # Percentile ranks, 0-100. pct=True keeps them comparable across markets of
    # different sizes; unranked rows stay NaN and are reported as such.
    value_rank   = (value_z.rank(pct=True) * 100).round(1)
    quality_rank = (quality_z.rank(pct=True) * 100).round(1)
    combined_z, combined_n = _mean_z([value_z, quality_z], min_parts=1)
    combined_rank = (combined_z.rank(pct=True) * 100).round(1)

    # 🔴 THE TWO SCORES COVER DIFFERENT POPULATIONS, so averaging them without
    # saying so would quietly change what the number means row by row. Measured
    # for India 2026-08-17: pe/pb survive the provenance gate for 508 names
    # (21.5%) but roe/opm/de/cr/growth for 1,426 (60.2%). Averaging "whatever
    # exists" lets a quality-only name compete against a value+quality name as
    # though the two were the same measurement. rank_basis makes that visible
    # instead of leaving it implicit in a single column.
    has_v, has_q = value_z.notna(), quality_z.notna()
    rank_basis = np.where(has_v & has_q, 'value+quality',
                 np.where(has_q, 'quality_only',
                 np.where(has_v, 'value_only', 'none')))

    # Signal derives from the RANK now, not from a share of criteria met — and
    # BUY additionally REQUIRES BOTH LEGS. That is Piotroski (2000) read
    # properly: the F-score sorts on quality WITHIN a value universe, so "cheap
    # and financially sound, both actually measured" is the only claim the design
    # supports. A name cheap on an unmeasured book value, or sound on an
    # unmeasured price, has not met that bar and can rise no higher than WATCH.
    #
    # Rows too thin to rank are UNRANKED, not AVOID: an honest third state that
    # keeps them out of the buy list without asserting they were examined and
    # found wanting.
    both = has_v & has_q
    signal = np.where(combined_rank.isna(), 'UNRANKED',
             np.where(both & (combined_rank >= 90), 'BUY',
             np.where(combined_rank >= 67, 'WATCH', 'AVOID')))

    n_avail = (v_f1.astype(int) + v_f5.astype(int) + v_f8.astype(int) + v_f9.astype(int) +
               v_fx1.astype(int) + v_fx2.astype(int) + v_fx3.astype(int) + v_fx4.astype(int) +
               v_fx5.astype(int) + v_fx6.astype(int) + v_fx7.astype(int))
    completeness = (n_avail / 11 * 100).round().astype(int)

    # ── Build output ──────────────────────────────────────────────────────────
    results = []
    for i in range(len(d)):
        vi = vol.iat[i]
        results.append({
            'ticker':         tickers[i],
            'name':           names[i],
            'cmp':            _r(cmp.iat[i]),
            'high_52w':       _r(h52.iat[i]),
            'ema_20':         _r(e20.iat[i]),
            'ema_50':         _r(e50.iat[i]),
            'ema_200':        _r(e200.iat[i]),
            'rsi':            _r(rsi.iat[i]),
            'rsi_signal':     rsi_sigs[i],
            'macd':           _r(macd.iat[i]),
            'macd_signal':    _r(msig.iat[i]),
            'volume_ratio':   _r(vr.iat[i]),
            'bb_upper':       _r(bb_u.iat[i]),
            'bb_lower':       _r(bb_l.iat[i]),
            'bb_pct':         _r(bb_pct.iat[i]),
            'stoch_k':        _r(stk.iat[i]),
            'stoch_d':        _r(std.iat[i]),
            'atr_14':         _r(atr.iat[i]),
            'roe':            _r(roe.iat[i]),
            'opm':            _r(opm.iat[i]),
            'debt_to_equity': _r(de.iat[i]),
            'current_ratio':  _r(cr.iat[i]),
            'revenue_growth': _r(rg.iat[i]),
            'pb':             _r(pb.iat[i]),
            'pe':             _r(pe.iat[i]),
            'market_cap':     _r(mcap.iat[i]),
            'volume':         int(vi) if vi is not None and not (isinstance(vi, float) and math.isnan(vi)) else None,
            'beta':           _r(beta.iat[i]),
            'eps':            _r(eps.iat[i]),
            'dividend_yield': _r(dy.iat[i]),
            'ret_1d':         _r(r1d.iat[i]),
            'ret_1w':         _r(r1w.iat[i]),
            'ret_1m':         _r(r1m.iat[i]),
            'ret_3m':         _r(r3m.iat[i]),
            'ret_6m':         _r(r6m.iat[i]),
            'ret_1y':         _r(r1y.iat[i]),
            'sector':         sectors[i],
            'industry':       industries[i],
            'score':          int(score.iat[i]),
            'max_score':      int(max_score.iat[i]),
            'signal':         str(signal[i]),
            # Composite ranks (0-100 percentile of within-industry z-scores).
            # `score`/`max_score` above are KEPT so the old view stays available
            # and the two can be compared during the cut-over — but `signal` is
            # now derived from combined_rank, not from a share of criteria met.
            'value_rank':     _r(value_rank.iat[i]),
            'quality_rank':   _r(quality_rank.iat[i]),
            'combined_rank':  _r(combined_rank.iat[i]),
            'value_z':        _r(value_z.iat[i]),
            'quality_z':      _r(quality_z.iat[i]),
            # How many components each score actually averaged. A rank built on
            # two metrics is not the same claim as one built on five, and hiding
            # that behind a single number is how thin data starts looking solid.
            'value_n':        int(value_n.iat[i]),
            'quality_n':      int(quality_n.iat[i]),
            # Which legs the rank actually rests on. A BUY always reads
            # 'value+quality'; anything else is explicitly a partial view.
            'rank_basis':     str(rank_basis[i]),
            'completeness':   int(completeness.iat[i]),
            'criteria': {
                'F1_roe_positive':   _b(c_f1.iat[i]),
                'F5_low_leverage':   _b(c_f5.iat[i]),
                'F8_op_margin':      _b(c_f8.iat[i]),
                'F9_rev_growth':     _b(c_f9.iat[i]),
                'FX1_above_ema50':   _b(c_fx1.iat[i]),
                'FX2_rsi_range':     _b(c_fx2.iat[i]),
                'FX3_near_high':     _b(c_fx3.iat[i]),
                'FX4_current_ratio': _b(c_fx4.iat[i]),
                'FX5_pb_value':      _b(c_fx5.iat[i]),
                'FX6_ema_cross':     _b(c_fx6.iat[i]),
                'FX7_low_atr':       _b(c_fx7.iat[i]),
            },
            '_exchange': exchanges[i],
        })
    return results
