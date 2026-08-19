# India inward remittances by source country, and per-NRI averages

`india_remittance_estimator.py` estimates how much of India's inward remittance
flow comes from each source country, and how much the average remitting migrant
sends. It replaces a first cut that took the RBI survey's country shares at face
value and divided them by the raw MEA diaspora stock.

```bash
python3 research/diaspora/india_remittance_estimator.py            # writes reports/india_remittance_estimates.csv
python3 research/diaspora/india_remittance_estimator.py --h-hub 0  # publish-as-is, no reattribution
python -m pytest tests/test_remittance_estimator.py -v
```

## What was wrong with the first cut

**The numerator.** RBI's country shares are *booking-entity* attributions — the
source country an Authorised Dealer bank or MTO reports a transaction as coming
from — not where the remitter lives and earns. The survey panel is 30 AD banks,
two MTOs and two fintechs, all reporting the leg they see. The three countries
whose shares have risen fastest are also the world's three largest
remittance-processing hubs, and the rise is contemporaneous with digital going
to 73.5% of transactions. Part of the celebrated "shift from the Gulf to the
advanced economies" is a shift in rails.

**The denominator.** Dividing by the whole MEA NRI stock counts students,
dependants and children as remitters, while *excluding* the naturalised PIOs who
do much of the actual remitting in the advanced economies. The UK reading it
produced — $34,743 per NRI — is not an income anyone earns and remits.

## Method

Three estimators of each country's flow:

| | Basis | Role |
|---|---|---|
| **E1** survey attribution | RBI 6th Round share × total | The published number. Upper bound for hubs. |
| **E2** migrant-stock model | stock × per-migrant intensity, calibrated on the KNOMAD 2021 corridors | Lower bound for hubs, upper bound for the Gulf. |
| **E3** reconciled | E1 and E2 blended by hub exposure `h`, then **redistributed** | Headline. E1/E2 are the band. |

E3 is a reattribution, not a haircut: volume taken off the hubs is redistributed
across the non-hub countries in proportion to the headroom the stock model says
the survey is missing there, capped at that headroom. If the pool cannot be
placed, the hub reductions scale back rather than the money disappearing — so
`--h-hub 1.0` resolves to an **effective ceiling of h≈0.88**. That ceiling is a
result: it is the most reattribution the evidence can absorb.

The denominator is an effective remitter base, not the raw stock:

```
base = NRI × earner_share × remit_propensity + PIO × pio_propensity
```

with Gulf and advanced-economy parameters swept low/central/high, so the
per-head answer arrives as a range. The Gulf has no naturalisation path, so PIO
propensity there is pinned at zero.

Then two checks the first cut had no way to run: the KNOMAD cross-check, and an
income-plausibility test against documented remitting behaviour (Gulf labour
migrants 25–55% of net income, advanced-economy professionals 3–15%).

## Findings

**The Gulf numbers are sound.** Two methods built from entirely different data —
a survey of Indian banks, and a migrant-stock model calibrated abroad — agree on
the UAE within 21%. Every Gulf state lands inside documented remitting
behaviour. Per actually-remitting Gulf migrant: **US$6,700–11,400/yr, central
~US$8,700**.

**The advanced-economy numbers are not.** The US survey share implies 3.8× what
the stock model does. Three of the five AE countries imply remittance rates
above documented behaviour even after reattribution. Per-head figures there are
an upper bound, not an estimate.

**No single correction closes the AE gap.** Inverting the model, the US would
need 74% of its attributed flow reclassified as booking artefact to become
plausible, the UK 86%, and Singapore cannot be brought inside the band at all
even at the ceiling. That rules out routing as the whole story. Three things are
running together: booking-entity attribution, an effective remitter base wider
than these parameters allow, and private-transfer flow that is not wage
remittance at all — NRI deposit inflows, property purchase, repatriated
investment — sitting inside the same series.

The consequence for reading the RBI survey: **"advanced economies have overtaken
the Gulf" is not established by this data.** At the reconciliation's midpoint the
Gulf is already back in front (US$61.4bn vs US$43.7bn), and the sensitivity table
shows the crossover happens at h≈0.24 — a modest assumption about routing.

## Sourced vs assumed

The module prints these separately at runtime and the distinction is load-bearing.

**Sourced** (`SOURCES`): RBI 6th Round shares and totals; RBI BoP FY25; World
Bank CY2021/CY2024 totals; KNOMAD 2021 bilateral corridors; MEA January-2025
diaspora counts; RBI ticket-mix and digital-share; World Bank remittance prices.

**Assumed** (`PARAMS`): hub exposure weights; remitter-base parameters;
plausible remittance-rate bands; the archetype incomes standing in for each
bloc's typical earner. Every one is a dial, and `--h-hub` plus the printed
sensitivity table show how far the answer moves when you turn it.

## Known gaps

- **10 of 26 countries still have no denominator.** Hong Kong, the Netherlands,
  Belgium, Ireland, Switzerland, Japan, Indonesia, Thailand, Italy and Spain get
  a flow estimate but no per-head figure. See "The MEA gap" below.
- **The KNOMAD matrix ends at 2021** (the programme was discontinued in 2024), so
  the anchors are scaled forward by growth in India's total. Three corridors
  anchor the whole calibration.
- **The archetype incomes are tax scenarios, not measured migrant means.** The
  Gulf median sits well below the $30k archetype, which makes the Gulf
  plausibility test the looser of the two — it is a floor on the verdict, not a
  precise rate.
- **E2 is a within-set allocation**, so Stage 1's five-country figures are not a
  preview of Stage 2's — the pot and the weights differ.


---

# The MEA gap — why 10 countries are still empty

The authoritative source is the MEA "Population of Overseas Indians" table,
January-2025 vintage. It is unreachable from this environment: `mea.gov.in`
returns **403 from the egress proxy**, which is an organization policy denial,
not a transient failure. The proxy README is explicit that such denials must be
reported rather than routed around, so they were.

Search is a separate allowed channel and was tried. It returns fragments across
incompatible vintages, and using them would be worse than the gap:

| Fragment recovered | Vintage | Why it is unusable |
|---|---|---|
| Belgium 10,651 NRI / 8,000 PIO | **2016** | Nine years stale against a Jan-2025 frame |
| Netherlands 28,912 overseas Indians | **2017** | Conflicts with other sources reporting ~240,000 — the Indo-Surinamese PIO population is counted differently across sources |
| EU country shares (NL 8.31%, IT 6.98%, DE 6%, FR 3.85%) | **2017** | Shares of a 2.83m EU total that no longer holds |
| Global totals 35.42m / 15.85m NRI / 19.57m PIO | **May 2024** | A third vintage again, and doesn't disaggregate |

The per-head estimate is a ratio, so a denominator from the wrong year does not
degrade gracefully — it produces a confidently wrong number in exactly the
column the rebuild exists to fix. The Netherlands case shows the size of the
hazard: an 8x spread between sources depending on whether Indo-Surinamese PIOs
are counted.

**To close it:** download the table and re-run. `mea.gov.in/images/attach/nris-and-pios_1.pdf`
opens fine from an ordinary browser. Drop the country/NRI/PIO columns into the
`COUNTRIES` list and the 10 rows move from grade `D` to `B` automatically — no
other change is needed.

---

# Destination ranking — `savings_destination_ranking.py`

```bash
python3 research/diaspora/savings_destination_ranking.py     # writes reports/savings_destination_ranking.csv
python3 research/diaspora/savings_destination_ranking.py --archetype professional
```

Ranks destinations on how well a given gross salary converts into repatriated
savings, across five sourced components: income retention, remittance friction
(send cost plus any levy on the transfer), India-side treaty treatment (DTAA
withholding plus the capital-gains shield on non-share assets), social-security
portability, and whether you can legally remain.

Two objectives, because the answer genuinely differs:

**ACCUMULATE** (finite stint, then repatriate) — Qatar, Kuwait, Oman, Bahrain,
UAE, Saudi Arabia, then Singapore a long way back at 68. Zero income tax
dominates a weighting where residency is worth nothing because you are leaving.

**SETTLE** (build a life) — Singapore 78.5, then the Gulf's long-term-residency
states (Qatar, UAE, Saudi) at 73–75, then the citizenship-path advanced
economies: Australia, Japan, Canada, Netherlands, UK at 60–66. Kuwait, Oman and
Bahrain collapse from the top of one ranking to the bottom of the other — they
tie residence to an employer, so there is nothing to settle into.

**The United States ranks 16th and 15th** despite being the largest single
source of remittances to India. Four things stack against it: ~29% burden at
$120k, no social security agreement with India (FICA forfeited short of 40
quarters), no treaty shield on non-share capital gains, and a 1% excise on
cash-funded remittances from January 2026. That people go anyway is the
ranking's blind spot, stated plainly at runtime: **US wage levels are high
enough that a worse multiplier on a much larger number still wins on absolute
savings. Retention efficiency is not income.**

## Two corrections this cross-check produced

- **The UK's SSA flag was wrong.** The India–UK Social Security Agreement was
  *signed* on 10 February 2026 and is **not yet in force**; the column means "in
  force". Carrying it as `True` overstated the protection on contributions made
  there today. The field is now three-state.
- **Two undocumented assumptions inside the tax burdens**, now surfaced: the US
  29.4% is federal + FICA + a mid-range state, and state choice swings it ~10pp
  (TX/FL 0%, CA ~9%); Singapore's 8.4% is income tax only, which is *correct*
  here because CPF does not apply to Employment Pass holders — a citizen or PR
  would face ~20%+.

The SSA list was verified against India's 18 in-force agreements. Every other
country's flag in the table checks out.

## What the ranking cannot see

Cost of living is not modelled — this ranks how much of a salary survives tax
and transfer, not what is left after rent and school fees. Neither are wage
levels: the same-gross premise flatters low-tax, low-wage markets and penalises
high-tax, high-wage ones. Nor currency, asset returns, healthcare, schooling,
visa risk, or whether you would want to live there.

Weights are judgement and are swept at runtime (`retention only`, `retention
halved`, `ssa doubled`). The Gulf's ACCUMULATE lead survives every reweighting;
only the ordering within it moves.

One structural caveat the score reports but cannot weigh: several top-ranked
destinations are missing a component (no World Bank send-cost datum for Qatar,
Kuwait, Oman or Bahrain), so they are scored on ~85–97% of the weight and
normalised up. `data_completeness_pct` flags this on every row.
