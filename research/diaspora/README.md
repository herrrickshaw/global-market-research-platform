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


---

# Expanded destination panel — `immigration_destination_panel.py`

```bash
python3 research/diaspora/immigration_destination_panel.py
```

Widens coverage from 16 destinations to **32**, and adds the dimension the
savings modules cannot see: how long it takes to become permanent, and whether
nationality changes the answer.

## Where the country list comes from — and what that's worth

The candidate list is drawn from the "best countries to migrate from India"
genre (Global Citizen Solutions, CanApprove, Visa Library, Immigrant Invest,
Shiksha, UniAcco). **Those pages are published by firms that sell the visas they
recommend**, so their rankings are advertising and their numbers are unusable.

They are used for exactly one thing: scoping the choice set. *Which destinations
do Indians actually consider?* — that they answer honestly, because it reflects
their own demand. Every number attached comes from elsewhere: OECD for wages,
Eurostat and MoSPI for inflation, published policy for pathways.

**The pages define the rows. They do not fill the cells.**

## The binding constraint moved

Adding 14 OECD average wages (Luxembourg $90,384 · Denmark $88,971 · Belgium
$86,545 · Ireland $86,235 · Austria $83,716 · Norway $82,016 · South Korea
$60,909 · Sweden $60,415 · Finland $59,597 · Spain $54,564 · Italy $51,019 ·
Poland $44,211 · Portugal $40,002 · Czechia $38,489) moved **zero** countries
into the ranked set — because a wage without a matching tax schedule produces no
savings figure.

| Blocked by | Count |
|---|---|
| no tax schedule | 15 |
| no wage | 2 |
| both | 1 |

**It is tax data, not wage data, that is now the gap.** OECD *Taxing Wages*
carries exactly the needed series — net personal average tax rate, single, no
children, at 100% of average wage — and `oecd.org` is blocked here at 403. That
one table would move most of the 14 into the ranking at a stroke. There's a test
pinning this claim so it can't go stale silently.

## Time to permanence

| Years | Countries |
|---|---|
| 1 | **Canada** (Express Entry), **Australia** (GSM 189/190) |
| 2 | Japan (HSP), Ireland, New Zealand |
| 3 | Germany (Blue Card / Opportunity Card), Norway |
| 4 | Sweden, Finland |
| 5 | Netherlands, UK, Austria, Belgium, Luxembourg, Portugal, Spain, Italy, Poland, Czechia, South Korea, France |
| 8 | Denmark |
| 10 | Switzerland |
| none | US, Singapore, all six Gulf states, Malaysia |

Points-based routes reach permanence measurably faster than sponsored ones —
also pinned by a test.

## The fact that dominates this decision for Indian nationals

**EB-2 / EB-3 employment-based green card, India-born: 12–15+ years** on current
Visa Bulletin movement. As of the **August 2026** bulletin the EB-2 India filing
cut-off is *unavailable* — the annual cap is reached; State announced India hit
its yearly EB-2 cap on 21 May 2026. Cause: the **7% per-country cap applies
regardless of population**.

Every other module here ranks the US on money, and the real-savings ranking puts
it **first**. This is the column money cannot see. The same job in Canada or
Australia converts to permanent residence in about a year; in the US an Indian
national may wait over a decade for the same status — a wait attaching to
*nationality*, not to skills or salary. A colleague born elsewhere, in the
identical role, does not face it.

That doesn't make the savings ranking wrong. It makes it one axis of two, and
for many people the slower axis decides.

## Inflation context

Sweden 1.0% · Czechia 1.1% · Denmark 1.8% (Eurostat HICP, Jun-2026) · euro area
2.9% (flash, Jul-2026), against **India CPI 4.45% and WPI 8.30%**. Every host
rate sits below India's — which is why, for savings that are a claim on Indian
goods, the destination's own inflation matters far less than the one at home.

---

# Correction: the tax rate was being applied at the wrong income

The first version of `real_savings_ranking.py` computed
`net_wage = wage_ppp × (1 − tax_burden_120k_pct)`. But `wage_ppp` is the
*average* wage — $40k–$93k across the panel — so a progressive schedule was
being charged at a rate belonging to an income nobody in the sample earns.
Germany was worst: **42.2% applied to a $69,433 wage.**

Now interpolated between the two known points on each schedule ($30k and $120k),
clamped outside them. It is an approximation — real schedules have more kinks —
but one anchored at both ends beats using one end for everything.

**This changes the published ranking:**

| | Old rank | New rank | Effective tax (was) |
|---|---|---|---|
| United States | 1 | 1 | 23.2% (29.4%) |
| **Netherlands** | **4** | **2** | **21.2% (37.9%)** |
| Australia | 2 | 3 | 17.0% (27.8%) |
| Canada | 3 | 4 | 24.2% (31.8%) |
| United Kingdom | 5 | 5 | 18.8% (30.1%) |
| Germany | 6 | 6 | 33.8% (42.2%) |
| Japan | 7 | 7 | 24.5% (34.7%) |

The Netherlands was the big casualty of the bug — its $30k rate is 4.3%, so
charging it 37.9% at a $75,370 wage buried it three places below where it
belongs.


---

# ROI on a foreign life — `roi_foreign_life.py`

```bash
python3 research/diaspora/roi_foreign_life.py
python3 research/diaspora/roi_foreign_life.py --migration-cost 25000
```

The savings modules give a *level*: how much lands in India per year. ROI is a
different question — what you paid, how long until it pays back, and what the
Indian career you gave up was doing meanwhile.

## The unit problem, stated rather than fudged

Landed savings are in PPP-USD; the Indian salary is in rupees. Bridging them
needs India's PPP conversion factor (World Bank `PA.NUS.PPP`), which is not
reachable here. So this module computes **no rupee-denominated NPV** — that
would put an invented conversion factor at the centre of the result. It works in
the two units needing no bridge: **payback years** and **growth rates**.

## Term 1 — what you pay

Gulf labour migration is measured: the KNOMAD/ILO returnee survey puts
recruitment cost at **1–9 months of foreign earnings** — at the ILO-anchored
blended Gulf wage, **US$1,260–11,342 before the first day of work**. For skilled
migration to advanced economies no measured figure was reachable, so it is a
swept parameter.

## Term 2 — what you get back

At a US$15,000 migration cost, **six of seven destinations repay inside a year**;
Japan takes 1.68. Only past US$40,000 does every destination cross a year.

On this term the answer is trivially "go" — which is exactly why this term alone
is not the ROI.

## Term 3 — what you gave up

MoSPI PLFS, average monthly earnings from regular salaried employment, All India:

| Year | ₹/month | YoY |
|---|---|---|
| 2022 | 19,315.50 | — |
| 2023 | 20,407.54 | +5.65% |
| 2024 | 21,454.87 | +5.13% |

**CAGR +5.39%.**

## The crossover

| | Rate | Basis |
|---|---|---|
| **Indian salaried wages, nominal** | **5.39%** | PLFS, measured |
| Advanced-economy wages, nominal | 2–4% | cycle range |
| India CPI | 4.45% | MoSPI |
| India WPI | 8.30% | MoSPI |

**The Indian salary you left is growing faster in nominal terms than the foreign
salary you took.** Measured on the India side against a cycle range on the
other, so it is a direction rather than a decimal — but the direction is not
close.

Real terms says the same from the other end: an Indian salary at 5.39% against
4.45% CPI gains about **+0.94%/yr** in purchasing power, while foreign savings
are eroded at that same 4.45% once landed — or 8.30% if destined for property —
having grown at only 2–4%.

## What the ROI actually is

**A foreign life buys a step change in level, not a faster rate.** The step is
large. But the rate underneath it is worse than the one you left, and erosion
applies at Indian prices wherever the money was earned. Three consequences, none
about tax:

1. **The gain is front-loaded** — banked in the early years when the level gap is
   widest, not accumulated steadily across a career.
2. **Deferring the transfer destroys it** — money held abroad to send "later"
   compounds at the host rate and is spent at the Indian one.
3. **What the money is *for* decides whether it worked** — against consumption at
   4.45% the maths holds; against property at 8.30% it does not, and property is
   what remittances most often accumulate toward.

## Known weaknesses

- The PLFS counterfactual is the **all-India salaried average**. Migrants skew
  graduate and urban, so the salary actually given up is higher and the foreign
  premium correspondingly smaller. PLFS carries an education breakdown that
  would fix this; the filter combination returned no rows and was not resolved.
- Advanced-economy migration cost is a parameter, not a measurement.
- No value is placed on residency, healthcare, schooling, or wanting to live
  there — see `immigration_destination_panel.py`.

---

# OECD Taxing Wages — ingest slot

`oecd.org` returns **403** from this environment's egress proxy, so the tax gaps
blocking 15 countries stay open. Rather than leave that as a note, the slot is
wired and tested:

```python
# research/diaspora/real_savings_ranking.py
OECD_NPATR_AT_AVERAGE_WAGE: dict[str, float] = {}   # ← fill this
```

The series is **net personal average tax rate** — income tax plus employee social
security, net of cash benefits, as % of gross, for a **single person without
children at 100% of the average wage**. It is the right series and not merely a
convenient one: it is quoted at exactly the income the OECD average wage
measures, so pairing the two needs **no interpolation at all**. Where a country
appears in the dict, that rate is used directly and the two-point interpolation
is skipped — `tax_basis` records which path each row took.

**To fill:** open Taxing Wages (any recent edition), take the
net-personal-average-tax-rate column from the single-no-children /
100%-of-average-wage table, add `"Country": rate` rows. Countries already
carrying an OECD wage become rankable immediately; nothing else needs changing.

**Sanity anchor for whatever you paste in:** Denmark is the OECD's highest at
**35.3% (2025) / 35.7% (2024)**, and only Denmark, Germany, Lithuania and
Slovenia exceeded 35% in the 2024 edition.

Two tests cover this: one asserts every row is currently on the interpolated
basis, and one injects a rate to prove the override path works before anyone has
data to put in it.


---

# What the American surplus is already promised to — `us_debt_service.py`

```bash
python3 research/diaspora/us_debt_service.py
python3 research/diaspora/us_debt_service.py --inr-per-usd 90
```

The savings chain assumes the surplus above the basket is free to remit. For a
US-based Indian professional it usually is not — a degree was financed, a car
was financed, a house may be. **Debt service comes out of exactly the same
surplus that funds remittances.**

US-only, and deliberately so: the US is the **numeraire of the PPP conversion**,
so PPP dollars *are* dollars there and these figures subtract from the savings
line with no exchange-rate step. That is true of no other destination.

## Three debts, three different treatments

Lumping them together is the mistake worth avoiding.

| Debt | Treatment |
|---|---|
| **Student loan** | Pure claim on the surplus. Nothing comes back. |
| **Auto loan** | Also pure cost — the asset depreciates, so the payment buys transport, not wealth. |
| **Mortgage** | **Not a deduction.** See below. |

## Scenarios — US, per year

| Scenario | Debt service | Share of surplus | Lands in India |
|---|---|---|---|
| No debt *(the ranking's assumption)* | $0 | 0% | **$34,215** |
| Used car only | $6,372 | 17.9% | $28,104 |
| US student loan, master's only | $7,680 | 21.5% | $26,850 |
| New car | $9,240 | 25.9% | $25,353 |
| US student loan incl. undergrad | $11,100 | 31.1% | $23,570 |
| Indian education loan, ₹85L @ 9.15% | $11,996 | 33.6% | $22,710 |
| **US student loan + used car** | $14,052 | 39.4% | **$20,738** |
| **Indian education loan + new car** | $21,236 | **59.5%** | **$13,848** |

## The finding that connects back to the remittance work

An Indian who financed a US master's with an **Indian** education loan services
a rupee debt out of dollar income — and those payments **cross into India and
are recorded as remittances**. They are not family support and they are not
savings. They are loan amortisation.

Every module here has been circling the conclusion that India's remittance
series measures more than migrants sending wages home. **This is one concrete
channel, and at ₹9,600–14,800/yr per borrower it is not small.**

A ₹70–100 lakh loan at 8.65–9.95% over 15 years costs **$9,593–14,780 a year**
to service. And the sensitivity runs the unusual way:

| ₹/US$ | EMI $/yr | Share of US surplus |
|---|---|---|
| 80 | $13,046 | 36.6% |
| 87 | $11,996 | 33.6% |
| 95 | $10,986 | 30.8% |

**A weaker rupee makes the loan cheaper to service out of dollars** — the one
line in this whole analysis where rupee depreciation helps the migrant.

## The mortgage is not a deduction

Treating $2,883/month as lost savings is wrong twice:

1. **It replaces rent**, which the $28,000 basket already contains. Only the
   excess is new spending, and the basket's rent share is not separately sourced
   — so this module **does not net a mortgage against the surplus**, because
   doing so would double-count housing.
2. **Principal is not consumption.** On an early payment $260 of $1,930 builds
   equity — saving redirected into American property rather than sent to India.
   Only the $1,670 of interest, plus tax and insurance, is cost.

So a mortgage **relocates** savings rather than destroying them — out of rupees
into a dollar asset. And that is a real decision with a real answer, because
Indian property inflates at the 8.30% WPI rate no advanced-economy wage clears.
Against *that* hurdle, holding property in the US is not obviously the worse
side of the trade.

## What it does to the headline — and what it does not

Debt-free the US lands $34,215 and ranks **first of seven**. Indian-financed
with a new car it lands **$13,848**, which is below every other country in the
table.

**That is not a fair fight, and the module says so.** Those comparisons put a
debt-laden American against six debt-*free* peers; migrants to Germany, Canada
and Australia borrow too. Read it as *how far the US position can move*, not as
"Germany now beats the US".

What is genuinely US-specific — and why the module is US-only:

- A US master's costs ₹70–100 lakh. **German public universities charge no
  tuition**, so the same qualification carries no comparable debt.
- US car dependence is structural in most metros, so the payment is closer to a
  fixed cost than a choice.
- The Indian-education-loan route exists at scale **because US study is what it
  is most often taken out to fund**.

Doing this properly for the other six needs their borrowing data, which was not
gathered. Until then the honest statement is conditional: **a debt-financed US
route lands materially less than the headline, and the gap to the rest is
smaller than the ranking implies.**

Sources: NY Fed Household Debt and Credit Report Q1 2026 (mortgage $13.19tn,
auto $1.69tn, student $1.66tn, cards $1.25tn, total $18.8tn); educationdata.org
2026; Experian State of the Automotive Finance Market Q1 2026; SBI Global
Ed-Vantage, HDFC Credila, Credila, Prodigy Finance.


---

# Do wages keep up with rent? — `rent_vs_wages.py`

```bash
python3 research/diaspora/rent_vs_wages.py
python3 research/diaspora/rent_vs_wages.py --rent-share 0.45 --years 10
```

Non-US destinations. The savings chain holds the basket at a constant $28,000 —
fine for ranking countries in one year, wrong for asking whether the surplus
survives. Rent is the largest and fastest-moving item in it.

## The measurement problem, which is the point

There are **two** rent inflation numbers per country and they are not close:

- **Sitting-tenant rent** — what the CPI housing component measures. It averages
  over the whole rented stock, most of it occupied by people on running
  contracts protected by caps, indexation and long leases.
- **New-listing rent** — what someone signing a fresh lease actually pays.

**A migrant is always a new tenant.** They arrive and sign at market. So the CPI
figure — the one every cost-of-living comparison uses, *including this repo's own
$28,000 basket* — systematically understates a migrant's housing cost, and
understates it **most where tenant protections are strongest**, because that is
where the two series diverge.

| Country | Wage growth | Rent (sitting) | Gap | Rent (new) | Gap |
|---|---|---|---|---|---|
| Canada | 2.3% | **−4.0%** | **+6.30pp** | −4.0% | **+6.30pp** |
| Japan | 2.3% | 0.7% | +1.60pp | **7.82%** | **−5.52pp** |
| Germany | 3.5% | 3.0% | +0.50pp | 4.0% | −0.50pp |
| Netherlands | 4.5% | 4.1% | +0.40pp | 6.5% | −2.00pp |
| United Kingdom | 3.4% | 3.3% | +0.10pp | — | — |
| Australia | 3.3% | 3.6% | −0.30pp | — | — |

**The basis flips the sign for Japan, Germany and the Netherlands.** On the
published CPI a migrant to Japan is gaining ground on rent; on Tokyo listings
they are losing more than five points a year. The gap is widest exactly where
protection is strongest — Japan +7.12pp, Netherlands +2.40pp, Germany +1.00pp.

## What it does to the surplus over 10 years

Rent at 35% of the basket, other items at 2.5%:

| Country | New-letting basis | Surplus in 10 yrs |
|---|---|---|
| Netherlands | +61.0% | $50,492 |
| Germany | +50.5% | $27,062 |
| United Kingdom | +49.2% | $35,359 |
| Canada | +47.2% | $36,275 |
| Australia | +43.7% | $39,667 |
| **Japan** | **−70.5%** | **$2,753** |

## Two findings, one of them negative

**The ordering survives.** Netherlands > Australia > Canada > UK > Germany >
Japan, both today and in ten years. That is a real result worth stating plainly:
the savings ranking is robust to a decade of divergent rent inflation. What moves
is the size of the gaps, not who is ahead.

**Japan is the exception, and not a small one** — the surplus falls 70% over ten
years on the migrant's own rent basis, turning a thin surplus into almost none.
It already ranked last; this widens the gap.

**Canada is the one genuinely favourable case.** Asking rents have fallen for 22
consecutive months — the only negative rent figure in the panel — so a migrant
arriving now signs into a *falling* market while wages still rise. It improves
Canada's position without changing its rank, because the countries above start
far enough ahead.

The general lesson is the one this directory keeps arriving at from different
directions: **the published series measures a population the migrant is not in.**

Sources: Eurostat and national statistics offices, ABS, StatCan, Rentals.ca,
Kiel Institute, Japan CPI and listing indices, Indeed Hiring Lab and OECD wage
bulletins, 2026 vintages. Rent share of the basket is a swept parameter, not a
measurement.


---

# Verification pass, 2026-08-20

## What checked out

- **US average wage $82,933 confirmed exactly** against OECD. It is the single
  most load-bearing figure in the stack and it is right.
- **Aggregate tax sanity passes.** The mean effective rate across the ranked set
  is **23.3%**, against an OECD-wide **25.1%** net personal average tax rate for
  a single worker at average earnings, 2025. Right neighbourhood.

## What was corrected

**Switzerland's wage was wrong** — carried at ~$83,000, actually **$87,468**
(OECD 2024). Switzerland is unranked for want of a tax datum, so no result
moved, but the figure is fixed.

## What could *not* be verified, and why it matters

**Country-level tax rates remain the weakest input in the stack.** The OECD
publishes net income at the average wage in USD and those figures were
retrieved — Switzerland $87,303, Netherlands $67,017, UK $63,277, Canada
$60,811, Australia $60,275 (single, average wage, 2025). They **cannot be
reconciled** with the average-wage series used here:

| Country | OECD net | Our gross | Implied rate |
|---|---|---|---|
| Switzerland | $87,303 | $87,468 | **0.19%** |
| United Kingdom | $63,277 | $63,691 | **0.65%** |
| Netherlands | $67,017 | $75,370 | 11.08% |
| Canada | $60,811 | $69,417 | 12.40% |
| Australia | $60,275 | $67,000 | 10.04% |

**No country taxes an average wage at 0.19%.** The two series are published on
different conversion bases, so dividing one by the other produces nonsense. They
are carried in `OECD_NET_INCOME_AT_AW_USD_2025` **flagged as unusable for that
purpose**, and the ingest slot stays empty — filling it from figures that cannot
be reconciled would be worse than the gap it leaves. A test enforces both.

---

# The ranking, after everything — `consolidated_ranking.py`

```bash
python3 research/diaspora/consolidated_ranking.py
```

Puts the three orderings side by side and reports where they agree. **No
weighted composite** — weighting savings against residency against rent
trajectory needs exchange rates between incommensurable things, chosen by me,
and the output would look more authoritative than any of its inputs.

| # | Country | Lands/yr | Permanence | Confidence |
|---|---|---|---|---|
| 1 | **Netherlands** | $30,077 | 5 yr | firm |
| 2 | Australia | $25,900 | **1 yr** | firm |
| 3 | Canada | $23,591 | **1 yr** | firm |
| 4 | United Kingdom | $23,239 | 5 yr | firm |
| 5 | Germany | $17,249 | 3 yr | firm |
| 6 | Japan | $8,945 | 2 yr | firm |
| — | *United States* | *$34,215 debt-free · $20,738 debt-loaded* | *no route* | **not placed** |

**Nothing moves.** Across a debt adjustment and a decade of divergent rent
inflation, the ordering of those six is unchanged — a stronger result than any
single ordering on its own, and pinned by a test.

**The US is deliberately not placed.** It tops the one-year debt-free table,
falls to fifth of seven once its own debt is netted, has no rent series here,
and carries the longest green-card queue in the set. Three reasons no single
position would be honest.

Ranks are re-based over the countries present in all three orderings — the US
dropping out of the ten-year view would otherwise shift everyone up one and read
as movement that did not happen.

## What would change it

1. **Borrowing data for the six non-US destinations.** The US is the only row
   carrying a debt figure and it is the row most exposed. Give the others their
   real debt and the gap narrows, probably a lot.
2. **Country-level tax rates** — see the verification pass above.
3. **Migrant-specific wages outside the Gulf.** Indian migrants to the US and UK
   earn above the national averages used here; correcting that widens the lead
   of the countries already at the top.
