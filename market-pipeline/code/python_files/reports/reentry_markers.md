# Re-entry markers + root cause analysis (2026-07-27)

3,188 historical anomaly events (2018–2026, top-200 liquid × IN/JP/KR/US) with
per-event features; forward excess measured 63d after the re-entry trigger vs a
median-return market index. Data: `reports/reentry_markers.csv`.

## Key markers for re-entry (ranked)

| marker | signal | excess63 spread |
|---|---|---|
| **1. Bounce speed** | trigger within **≤16 days** of eviction | **+12.97%** vs +7.94% (slow >41d) |
| **2. Drawdown depth at eviction** | **≤ −23%** off the 52-week high | **+12.01%** vs +7.42% (shallow) |
| **3. The combination** | FAST + DEEP | **+14.27%** (t 8.1) — and per market: **KR +24.2% (78% win) · IN +19.6% (79% win)** · JP +13.7 · US +7.1 |
| ✗ RSI at eviction | no power | 10.8 vs 8.6 — flat (median 41 both outcomes) |
| ✗ Kalman drift magnitude | no power | 10.4 / 10.8 / 9.2 across terciles — flat |

**Practical rule**: prioritize re-entries where the name snapped back within ~3
weeks of eviction AND was evicted deep in a drawdown. The engine now scores on
exactly these two markers. RSI stays as the *overbought veto* only — it earns
nothing as a selector.

## Root cause analysis — why evictions boomerang

**The eviction criteria are trailing, and trailing + bull regime = selling the
local bottom.**

1. **The rule confirms damage after it happened.** Markov bear-state needs ~21
   days of weak returns; the Kalman slope lags by construction. By the time both
   agree, the median name is already **−17.1% off its high** — the eviction
   fires at or near the local bottom, not at the top of the decline.
2. **Conditioning on market-bull selects maximum stretch.** In a bull market,
   a name in a confirmed bear state is the name with the WIDEST gap to the
   market — which in mean-reverting markets is precisely the strongest
   reversion candidate. The eviction filter is, structurally, a contrarian buy
   screen wearing a sell label. Median time to boomerang: **27 days**.
3. **It is not one regime's artifact.** Excess63 after the trigger is positive
   in EVERY year 2018–2026, including the 2022 bear (+2.9%); best years are
   2025 (+15.7%) and 2026 (+16.2%).
4. **Why RSI adds nothing at eviction:** the Markov bear-state already encodes
   the oversold condition RSI would measure — the two are collinear at the
   eviction moment (median RSI 41 regardless of outcome). RSI only regains
   meaning at RE-entry time as an overbought veto.

**Design consequence (already live):** tier 3 is the re-entry queue; eviction
stays useful as a *discovery* mechanism (it finds stretched names), with the
paper-track separating tracking-eviction (right) from re-entry (also right) —
the same name can legitimately be both.

> Survivorship-lite caveat: the top-200-by-full-period-turnover panel favors
> names that survived. Live validation runs via status=reentry paper-track rows.
