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

Cost of living and wage levels are **now modelled** — see the next section,
which inverts this ranking. Still absent: currency, asset returns, healthcare,
schooling, visa risk, or whether you would want to live there.

Weights are judgement and are swept at runtime (`retention only`, `retention
halved`, `ssa doubled`). The Gulf's ACCUMULATE lead survives every reweighting;
only the ordering within it moves.

One structural caveat the score reports but cannot weigh: several top-ranked
destinations are missing a component (no World Bank send-cost datum for Qatar,
Kuwait, Oman or Bahrain), so they are scored on ~85–97% of the weight and
normalised up. `data_completeness_pct` flags this on every row.


---

# Real savings and the inflation test — `real_savings_ranking.py`

```bash
python3 research/diaspora/real_savings_ranking.py            # writes reports/real_savings_ranking.csv
python3 research/diaspora/real_savings_ranking.py --basket 32000
```

Closes the retention ranking's stated blind spot by adding what you earn and
what you spend, then asks whether the resulting savings stream beats inflation
**in India**, where the money lands.

## The PPP trap

The obvious construction — nominal wage minus a cost-of-living index — double
counts, because the OECD wage series is already PPP-adjusted, i.e. already
deflated by the host price level. So this works in PPP-USD throughout. In PPP
terms a fixed real basket costs the same everywhere by construction, so cost of
living collapses into one constant:

```
savings_ppp = wage_ppp × (1 − tax) − real_basket
```

The basket is the single free parameter and is swept ($20k–$36k). Converting
the surplus into Indian purchasing power multiplies by a constant identical
across host countries, so it moves the level, never the order.

## The headline result: the two rankings invert

Rank correlation between retention efficiency and absolute savings is **−0.51**.

| Country | Retention rank | Savings rank | Lands in India / yr |
|---|---|---|---|
| United States | 19 | **1** | $29,300 |
| Australia | 16 | 2 | $19,121 |
| Canada | 15 | 3 | $18,514 |
| Netherlands | 11 | 4 | $18,035 |
| United Kingdom | 12 | 5 | $16,204 |
| Germany | 17 | 6 | $11,635 |
| Japan | 13 | 7 | $4,112 |

The US ranks 19th on retention and 1st on absolute savings. It has the largest
wage and the 2nd-lightest burden of the seven — and it is the *wage* that
separates it: Australia's burden is lighter still and it lands 1.5x less. The
earlier ranking named this as its blind spot; this measures it.

Order is stable across every basket size tested.

## The inflation test

Savings earned abroad are a claim on Indian goods, so the hurdle is Indian
inflation — and which one depends on what the money is for. All figures from
**MoSPI, live via MCP** (CPI base 2024, All India Combined, July 2026;
WPI base 2011-12, April 2026 vs April 2025).

| Money is for | Priced by | India inflation | Breakeven host wage growth |
|---|---|---|---|
| Gold / personal effects | CPI personal care & effects | **14.77%** | 14.77% |
| Property / construction | **WPI headline** | **8.30%** | 8.30% |
| Restaurants / accommodation | CPI restaurants | 7.72% | 7.72% |
| Family consumption | CPI food & beverages | 5.24% | 5.24% |
| *(general / mixed)* | *CPI headline* | *4.45%* | *4.45%* |
| Education fees | CPI education services | 3.64% | 3.64% |
| Rent / utilities at home | CPI housing & fuels | 2.16% | 2.16% |
| Medical support | CPI health | 1.34% | 1.34% |

**India WPI is running at 8.30% against CPI's 4.45% — nearly double.** That gap
is the most consequential number here, because remittances disproportionately
fund exactly the things WPI prices: property, construction, and (via the
14.77% personal-effects division) gold.

The implication is uncomfortable. Advanced-economy nominal wage growth runs in
the low single digits. So:

- Medical support (1.34%) and home rent/utilities (2.16%) clear comfortably.
- Education (3.64%) and headline (4.45%) are roughly a coin toss.
- **Property (8.30%) and gold (14.77%) are not cleared by any advanced-economy
  wage.** A remitter saving abroad to buy Indian property is losing ground every
  year the transfer is deferred.

A destination can top the retention table and still lose real ground, because
the hurdle is set in India and has nothing to do with the host country's tax code.

## Data grades — read before quoting

- **Grade A** (like-for-like table): OECD average annual wages 2024, USD PPP —
  US, Switzerland, Netherlands, Germany, Canada, Australia, UK, Japan.
- **Grade B**: Singapore — OECD Asia/Pacific report, different vintage.
- **Grade B**: UAE, Qatar, Saudi Arabia, Kuwait, Oman, Bahrain — the
  ILO-anchored segment model, which replaced the recruitment-survey national
  averages. See the next section.
- Switzerland has a wage but no tax datum, so it is reported and not ranked.

Per-country nominal wage growth is not sourced, which is why the inflation test
is framed as a breakeven rather than a realised real return.

## On the requested source

`masaladeutsch.blogspot.com` was named as a source. It is **blocked by this
environment's egress policy (403)**, the same organization-level denial that
blocks `mea.gov.in`. Nothing from it is used. India CPI/WPI here come from
MoSPI directly, which is the primary source a blog on the subject would itself
be citing — so the substance is covered, but if the blog carries analysis you
want reflected, paste the relevant figures and they can be wired in.


---

# Closing the Gulf wage gap — `gulf_wage_model.py`

```bash
python3 research/diaspora/gulf_wage_model.py
```

The Gulf previously carried recruitment-survey *national* averages — UAE
$73,500, Qatar $81,600, Saudi $64,800 — describing a workforce that includes
Emirati nationals, Western expatriate executives and Gulf managers. Indian
migrants are not that population. This replaces them with a two-segment model
of the Indian migrant wage, anchored on ILO-linked statutory floors.

## What the floors actually are

| Country | Binds on migrants? | Basic | Package |
|---|---|---|---|
| **Qatar** | **yes** | $275/mo | **$495/mo** |
| **Kuwait** | **yes** | $244/mo | $244/mo |
| UAE | **no** | — | — |
| Saudi Arabia | **no** | — | — |
| Oman / Bahrain | **no** | — | — |

Qatar's is the region's only universal, non-discriminatory minimum wage —
QAR 1,000 basic + QAR 500 accommodation + QAR 300 food, all nationalities and
sectors including domestic workers, developed with the ILO, in force 20 March
2021. **In the UAE and Saudi Arabia — between them the destination of most
Indian migrants — expatriate pay has no statutory floor at all.**

## The correction, and its size

Stock-weighted at 70% blue-collar / 30% professional:

| Scenario | Blue-collar | Professional | **Blended Indian migrant** |
|---|---|---|---|
| low | $3,297 | $22,873 | **$9,170** |
| central | $4,800 | $39,210 | **$15,123** |
| high | $5,934 | $65,000 | **$23,654** |

**The national averages overstated the Indian migrant wage by 4.3–5.4x.**

Composition uses the **stock**, not the arrival flow. MEA emigration-clearance
tags show the flow shifting from 38% skilled (2014) to 61% (2025), but the stock
still reflects decades of blue-collar arrivals. Using the flow mix would roughly
double the modelled wage — the classic error, and there's a test pinning it.

Independent check: the KNOMAD/ILO returnee survey (2,000+ GCC returnees, 2015)
puts Filipino median pay in Qatar at $435/mo and Ethiopian at $265/mo. The
Filipino median sits inside the modelled band. The Ethiopian median sits *below*
Qatar's later statutory floor — corroboration rather than contradiction, since
the ILO recorded that floor lifting 400,000 workers, 20% of the private sector,
precisely because such wages were common before it.

## The cross-module finding

The remittance estimator puts Gulf flow at **$8,659 per remitting migrant/yr**.
The Gulf levies no income tax, so that must come out of the wage above:

| Wage scenario | Blended wage | Implied remit rate | Verdict |
|---|---|---|---|
| low | $9,170 | 94.4% | **above band** |
| central | $15,123 | 57.3% | **above band** |
| high | $23,654 | 36.6% | fits |

It fits **only** at the high scenario — which requires assuming the top of every
band at once. The segment decomposition agrees: at low and central, the
professional 30% would have to remit 58–108% of income, which nobody does.

**So the Gulf's "grade A, two methods agree" result needs qualifying.** The two
methods still agree on the *flow*, and the ILO data doesn't overturn that. What
it overturns is the *interpretation*: Gulf remittances cannot be predominantly
wage remittances sent by labour migrants out of salary. Business and trade
income from the Gulf's Indian merchant community, NRI deposit flows, and gold
and trade settlement routed through Dubai must carry much of the value.

That is the same conclusion the advanced-economy analysis reached from the
opposite direction. **In both blocs, the remittance series is measuring
considerably more than migrant workers sending wages home.**

## What is now the binding gap

The wage gap is closed; the **basket** gap is not. Applying the
advanced-economy basket ($28,000) to a $15,123 Gulf wage returns *negative*
savings, which the observed remittance flow falsifies outright — Gulf migrants
plainly do save. Inferring the living cost instead gives
$15,123 − $8,659 = **$6,464/yr, about $539/month**, which Qatar's minimum-wage
*structure* independently corroborates: basic pay plus accommodation plus food
in kind leaves exactly that small an out-of-pocket basket.

But that figure is derived *from* the remittance number, so using it would make
Gulf savings equal Gulf remittances by construction. The Gulf therefore stays
out of the ranked savings tables — what changed is the reason. It is no longer
the wage that is unknown.

## The remaining asymmetry runs against the advanced economies

Gulf wages are now migrant-specific; OECD wages are still national averages.
Indian migrants in the Gulf earn far *below* their host average — corrected
here. Indian migrants in the US and UK earn *above* theirs, concentrated in
technology, medicine and finance — **not** corrected, because no
migrant-specific series for them was reachable. So the advanced-economy savings
figures are understated, and every Gulf-versus-AE comparison in these modules is
now the conservative one.
