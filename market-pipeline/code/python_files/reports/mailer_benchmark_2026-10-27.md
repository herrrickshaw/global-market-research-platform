# Mailer benchmark — time and research quality, 2026-10-27

Measured against the full log history (77 days, 149 phase-runs, 2026-07-29 → 2026-10-27,
`mailer_roster.py --rebuild`) plus the pipeline's own quality instruments. Nothing here
is a projection; every number has a source named beside it.

## 1. Time

### 1.1 Phase wall-time, by era (roster, minutes)

| era | data p50 | data p90 | send p50 | send p90 | n (data/send) |
|---|--:|--:|--:|--:|--:|
| to 2026-08-15 | 15.4 | 143.1 | 2.5 | 22.9 | 10 / 21 |
| 2026-08-16 → 09-30 | 20.8 | 164.3 | 24.2 | 65.3 | 28 / 42 |
| October | 51.2 | 224.2 | 36.1 | 123.4 | 16 / 20 |
| **today, after the declutter** | **16** | — | **8** | — | 1 / 1 |

The send phase grew from 2.5 to 24 min in mid-August because ENSURE-FRESH was added to it
(p50 17.5 min on its own, p90 51 min). October looks worse than September, but the
distribution is bimodal, not slow:

### 1.2 October data phases are two populations

| state | runs | data phase | US scan step [7/13] |
|---|--:|--:|--:|
| no sleep marker in the log | 10 | 15–19 min (one 32, one 43, one 60) | 12–15 min |
| `💤 SUSPENDED` markers present | 6 | 146–262 min | 89–102 min |

Every run over 100 minutes carries suspension markers; no run without them exceeds 60.
The machine sleeping through the 03:00 slot is still the dominant cost, three months
after caffeinate was added (it cannot block Maintenance Sleep on battery — CHANGELOG
2026-10-27). Today's 16-minute data phase is the fastest of the month and is the awake
baseline, not an effect of the declutter.

### 1.3 Where an awake morning goes (step p50 across all runs, seconds)

| phase | step | p50 | p90 | note |
|---|---|--:|--:|---|
| data | [7/13] US full market scan | 816 | 5374 | 85 % of an awake data phase |
| data | [5/13] India combined report | 77 | 2901 | |
| data | [3/13]+[4/13] India EOD + scan | 25 | — | the step everyone blamed in August |
| send | [ENSURE-FRESH] | 1049 | 3085 | half of it today was a US panel refresh that left US behind, and a Europe scan research rebuilt 4 min later |
| send | [11/13] prediction/tiers/re-entry | 31 | 46 | |
| send | [13/13] send gate | 30 | 41 | |
| send | [10/13] screens | 21 | 36 | |
| send | [12/13] regime refresh | 10 | 11 | |

### 1.4 Live timings of the rebuilt send path (this machine, awake, 12:00 IST)

| component | wall | notes |
|---|--:|---|
| `price_gate.py --markets US` (age + signature + Yahoo spot-check) | 4.6 s | |
| `price_gate.py --markets IN US` incl. witness jury | 23.4 s | 12:05 run; 6 AV + 6 TD + 6 Yahoo calls, all agreed |
| `send_mailer.py --draft` (full brief build, no SMTP) | 42.8 s | 17.8 s CPU; the rest is network (digest prices, FX, news) |

What the declutter changed in time terms: step [13/13] went from three process launches to
one and dropped the India Yahoo re-quote (~5 s); one watchlist repair (~5 s) and one Europe
scan (~36 s, research side) per morning. Small against the sleep problem, which is where
the next 100 minutes are.

## 2. Research quality

### 2.1 External witnesses — last 30 days, 151 checks (`validate_brief.py --source-report 30`)

| source | answered | agreed | echo % | avg abs diff | disagreements |
|---|--:|--:|--:|--:|--:|
| alphavantage (BSE) | 83.4 % | 99.2 % | 8.7 | 0.163 % | 1 |
| yfinance (NSE) | 95.4 % | 96.5 % | 84.7 ⚠ | 0.241 % | 5 |
| twelvedata (NSE direct) | 6.0 % | 100 % | 100 ⚠ | 0.0 % | 0 |

Alpha Vantage is the only genuinely independent voice that answers reliably. yfinance
echoes our own number 85 % of the time (same NSE close, so agreement proves little) and
accounts for 5 of 6 disagreements — every one a stale-session quote. Twelve Data answers 6 %
of asks: the tie-breaker registered on 2026-08-29 is effectively absent.

### 2.2 Suppressions — 23 of 108 send phases (21 %), falling

| era | sent | suppressed | rate |
|---|--:|--:|--:|
| to 08-15 | 14 | 7 | 29 % |
| 08-16 → 09-30 | 32 | 12 | 26 % |
| October | 16 | 4 | 19 % |

Causes across all 24 suppression lines in the logs: 9 "screener.in validation" (pre-08-18),
9 "external price validation", 6 "reconcile flagged N market(s)". The external-validation
suppressions name INFY ×4, BSE ×2, HDFCBANK ×1, BHARTIARTL ×1 — each a single witness
lagging a session, none a wrong price. The last time the gate caught a genuinely bad brief
was 2026-07-15 (MODISONLTD, seven weeks stale). The gate's precision is therefore low and
its recall untested since July; the 2026-10-27 abstain rule and the merged `price_gate`
address the precision side.

### 2.3 Picks, marked to market (`reports/paper_track.md`, 2026-10-26)

| book | n | mean return | hit rate | excess vs market |
|---|--:|--:|--:|--:|
| all picks | 8,672 | −5.41 % | 33 % | −1.06 % |
| curated (graded-A + fundamentals) | 3,088 | −5.95 % | 32 % | −1.41 % |
| REC-BUY at entry | 2,893 | −5.10 % | 30 % | −0.60 % |
| REC-SELL at entry | 2,915 | −6.84 % | 34 % | −2.54 % |
| curated ∩ REC-BUY | 896 | −4.65 % | 31 % | +0.26 % |

Read: 25 % of the book entered on 2026-07-21 into a KOSDAQ crash, so absolute returns are
negative everywhere; the fair read is excess. The per-market rule discriminates (BUY beats
SELL by 1.7 pp), curation does not yet (−1.41 % vs −1.06 % raw). Entry cohorts since
2026-10-13 are flat to slightly positive. By market, India picks are +3.69 % excess on 70
names; the US book is −2.63 % excess on 4,042 names and is where the drag sits.

### 2.4 Signal health (`global-market-scanners/.../signal_health.json`, asof 10-26)

| market | regime | HEALTHY | DECAYING | FLIPPED | NOISE | strongest recent |
|---|---|--:|--:|--:|--:|---|
| IN | bear | 5 | 2 | 0 | 4 | mom12_1 (IC +0.081, t 3.9) |
| US | bull | 1 | 0 | 0 | 10 | hi52 (t 0.9) |
| JP | bull | 1 | 1 | 0 | 9 | hi52 (t 1.6) |
| KR | bear | 9 | 2 | 0 | 0 | lowvol (t 2.4) |
| EU | bull | 4 | 0 | 0 | 7 | mom12_1 (t 1.4) |

No active rule is FLIPPED. The US has one healthy signal out of eleven, which matches the US
book's negative excess in 2.3: the brief is weakest where it recommends most.

### 2.5 Data behind the claims

- Data quality (`reports/data_quality.md`, 10-22): PE coverage 58 % (gate wants ≥ 70 %), close
  1.6 % null; US shares/equity 53–59 % null so US PE/PB stay gappy.
- Sufficiency (`reports/data_sufficiency.md`): IN powered but 47 % coverage, US powered and
  complete, EU underpowered — EU verdicts are data artifacts.
- Completeness (`reports/completeness_graph.md`, today): 39 sources, 0 erroring, 4 past
  cadence (`india_pe_daily`, `funds.nav`, `nse_daily`, `nse_tri`, all ~90 days), 9 of 39
  conclusions rest on a top-N liquid sample rather than the full market.
- Bundles (`reports/bundle_validation.md`, 10-01): 0/4 overlap with their benchmarks — the
  model portfolios are differentiated, not closet index.

### 2.6 The brief itself (today's draft, 130 KB, 36 headings, 37 tables, 318 rows)

| section | present | note |
|---|:--:|---|
| market snapshot, IN/US mood, screeners, price bands, CCC, news, street talk, Darvas | ✅ | |
| strategy validation, global context, momentum, FX carry, correlations, sector clusters | ✅ | |
| act-today, model portfolios, thematic, value re-rating | ✅ | |
| **prediction filter (Kalman drift, RSI zones, SELL-REVIEW, tiers, re-entry)** | ❌ | missing in 21 of the last ~30 briefs |

The prediction section dies on `reports/reentry_candidates.csv`: when the re-entry engine
finds zero picks (every day since mid-September) it writes a 1-byte file, `pd.read_csv`
raises `EmptyDataError`, and the `except` around the whole block drops the scores, RSI
zones, sell-review and tier counts along with it. Those are computed every morning at
step [11/13] and never reach the reader. **Fixed the same day**: `send_mailer.prediction_section()`
reads every optional input through a tolerant loader and guards each line on its own
(`tests/test_send_mailer_prediction.py`, 6 cases); a 12:30 draft rendered the section with
279 verdicts, the RSI zones and the tier counts.

Also observed: the draft built at 12:00 reported 147 picks / 39 buy-zone against 142 / 37
at 06:37 — the digest re-prices from live quotes at build time, so the same inputs give a
different brief depending on the hour. The vintage caveat names the session, which is
correct, but the counts move intraday.

## 3. Scorecard

| dimension | now | target | gap |
|---|---|---|---|
| data phase, awake | 16 min | ≤ 20 | met; sleep runs are 10× |
| send phase, awake | 8 min | ≤ 10 | met |
| send delivered on schedule | 81 % of send phases | ≥ 95 % | witness staleness; fixed 10-27, unproven on a schedule |
| independent witnesses answering | 1 of 3 reliably | 3 | Twelve Data 6 %, yfinance is an echo |
| picks excess vs market (curated) | −1.4 % | > 0 | US book |
| brief sections delivered | 20 of 21 → 21 of 21 (fixed 10-27, first scheduled send 10-28) | 21 | — |
| fundamentals coverage (PE) | 58 % | ≥ 70 % | US shares/equity fetch |

## 4. What this says to fix next, in order of payoff per hour

1. ~~Guard the empty `reentry_candidates.csv` read~~ — done 2026-10-27.
2. Keep the Mac on AC for the 03:00 slot, or move the data phase to a time it is awake —
   the only change worth 100 minutes.
3. Twelve Data: find out why it answers 6 % of asks; without it the jury is yfinance + AV.
4. Replace ensure-fresh's US panel refresh (2.1 min, no effect) with the Nasdaq fallback the
   07-21 fix added, or skip it when `refresh_panels` cannot close the gap.
5. US picks: the US book carries the paper-track drag and has one healthy signal; the
   playbook's US rule (cheap-vs-market) deserves the same evidence pass IN/KR got on 10-26.
