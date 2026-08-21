# job-search-copilot

Joins your **LinkedIn connections export** against **live job postings** and ranks
openings by how good the role is *and* whether you already have a path in.

The premise: for a senior candidate, the binding constraint is rarely finding
openings — it's getting a CV read. A mediocre-fit role where a connection can
hand-carry your application beats a perfect-fit role dropped into a cold ATS
pile. So network strength is weighted at 35% of the final score, and a
talent-acquisition contact counts for far more than raw headcount.

---

## Why not just use the LinkedIn API?

You can't. This is worth stating plainly because it is the first thing everyone
tries:

| Want | Available to an individual developer? |
|---|---|
| Search jobs | **No.** No public jobs API at any tier. |
| Apply to a job | **No.** No such endpoint exists, partner or otherwise. |
| Read your connections | **No.** `r_network` is gone; `r_1st_connections_size` returns *a count*, and is partner-gated. |
| Post / comment as yourself | Yes — `w_member_social` (self-serve). |
| Sign in / read your own profile | Yes — OpenID Connect (self-serve). |

Job data lives behind the **Talent Solutions Partner Program** (incorporated
company + signed agreement + review), and even that is built for *employers
posting jobs*, not candidates applying.

What LinkedIn *will* give you is **your own data**: Settings & Privacy → Data
Privacy → Get a copy of your data → *Connections*. That export is this tool's
only LinkedIn input. No scraping, no automation against LinkedIn, nothing that
puts the account you are job-hunting with at risk.

## Install

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml   # then edit
```

## Use

```bash
python cli.py network      # who you know, and where
python cli.py dedupe       # merge exports, report what changed
python cli.py scan         # fetch jobs, rank against your network
```

Outputs land in `out/` as `matches.csv`, `matches.md`, and `matches.html`
(the HTML highlights every row with a warm path).

---

## Deduplication

`Connections.csv` is keyed on **canonical profile URL** — locale subdomains
(`de.linkedin.com`), query strings, casing and trailing slashes all normalise to
one identity. Two findings from real exports shaped the policy:

**1. A single export is already clean.** Measured on a 13,825-row file:

| Duplicate mode | Count |
|---|---|
| Duplicate profile URLs | 0 |
| Duplicate emails | 0 |
| Same name + same company, different URL (ambiguous) | 3 clusters |
| Same name at *different* companies (**false-merge risk**) | 193 |
| Name-blank placeholder rows (deactivated profiles) | 151 |

So fuzzy name-merging would risk ~193 wrong merges to catch at most 3 real
duplicates. It is **not** done automatically. `find_ambiguous_clusters()`
reports same-name-same-company pairs for human review; `find_name_collisions()`
quantifies the false-merge risk you would be taking on.

**2. Dedup earns its keep across exports, not within one.** Merging exports
from 2026-02-22 and 2026-07-07:

```
overlap ............ 13,366      company changed ..... 1,897
new in July ........  1,927      title changed ....... 2,932
only in February ...    308      merged total ....... 15,601
```

Nearly 5,000 records were stale in the older file. `merge_exports()` takes
batches **oldest-first** and lets the newest win every field.

> **Freshness cannot come from `Connected On`.** That field is the date the
> connection was *made* — it is identical in both exports and never changes, so
> ranking on it silently keeps the *older* record. (This was a real bug: it kept
> the stale row in 1,896 of 1,897 cases before being caught against live data.)
> Record freshness is a property of *which export a row came from*, which is why
> batch order is the ranking key. Regression test:
> `test_merge_keeps_newer_company_and_title`.

Records present only in an older export are **retained**, not dropped — a
profile missing from a later export is usually deactivated, not a lost contact.

Built on `consolidate(key_fn, rank_fn)`, vendored from the parent platform's
`entity_resolution.py`, following its house convention of keying on a primary
id and keeping the most recent occurrence.

## Company matching

Every join runs through `normalize_company()`: legal suffixes stripped
(`plc`, `GmbH & Co KG`, `Pvt Ltd`, `AG`, `Limited`…), parentheticals dropped,
accents folded. `Shell plc` and `Shell` become one company; `Siemens Energy AG`
becomes `siemens energy`.

Names that mean *no employer* — `Self-employed`, `Freelance`, `Student` — map to
an empty key and are excluded, so freelancers don't collapse into one fake
mega-company.

## ATS scoring: does your CV clear the keyword screen?

```bash
python cli.py ats --resume cv.pdf --jd role.txt     # one JD, in detail
python cli.py scan --resume cv.pdf --min-ats 40     # every match, filtered
```

Real applicant tracking systems do far less than candidates imagine: they match
keywords, weight the requirements section above the blurb, and knock out on
years and degree. There is no semantic understanding. `jobsearch/ats.py` models
that deliberately — what actually screens you out, not what a thoughtful reader
would conclude.

**The useful output is the gap, not the number.** `missing` lists the terms the
JD asks for that your CV never says, ranked by weight. That is an edit list:

```
ATS keyword match: 24%

Add these to the CV, highest impact first:
  - strategy consulting
  - commercial acumen
  - financial modelling
  - petrochemicals
  - downstream
```

A knockout is not a low score, it is a rejection: 15 years required against 4
evidenced caps the score rather than shading it. A CV that never states a year
count at all is *flagged*, not failed — that is a fixable resume problem.

**What it is not.** It is a keyword model. It cannot see that "built a 550-person
India delivery centre" answers "experience scaling offshore operations" unless
the words overlap. A low score means your CV does not use the JD's vocabulary —
real and fixable, but not the same as being a poor candidate.

### Four defects that only appeared on real text

Each was invisible while reading the code and obvious the first time a real CV
met a real JD:

- **Stopwords were stripped before building n-grams**, so `business` vanished
  and **`business development` could never match** — on a business-development
  CV, the most expensive false negative available. Phrases are now built from
  the raw token stream.
- **N-grams spanned line breaks**, so two adjacent bullets manufactured
  `consulting deep knowledge` and `10+ development strategy`: unmatchable by
  construction, yet counted in the denominator, dragging every score down.
- **Term frequency was counted with a different tokenizer than phrase
  building.** `BOOT/JV` is one token to one and two to the other, so a phrase
  plainly present scored a frequency of zero — which reached `math.log()` as a
  domain error.
- **Redundant variants buried the real gaps.** One requirement generates
  `npv irr`, `irr discounted`, `npv irr discounted`…, pushing **Kubernetes and
  Terraform to 21st and 22nd** — the two genuinely disqualifying single-word
  skills, which are exactly what a screen hard-filters on.

### Absent is not zero

A posting with no description gets a **blank** ATS score, never `0%`, and
`--min-ats` filters only what was actually measured. Zeroing them would silently
discard every Apollo result, since that feed carries no JD text at all — the
same failure this project has now met in five other guises.

## Scoring

```
total = 0.50 x role_fit  +  0.35 x network  +  0.15 x freshness
```

- **role_fit** — weighted title keywords, sector lift, seniority lift, location
  penalty. Description-only matches are discounted to 35%. A hard-negative in
  the title (`intern`, `software engineer`, `warehouse`) zeroes the score, and
  **no amount of network can rescue a zero fit**. An entry-rung title carrying
  no seniority marker is damped to 45%, so "Research Analyst" ranks below
  "Senior Research Analyst" instead of beside it.
- **network** — `0.35 x breadth + 0.40 x talent-contacts + 0.25 x senior-contacts`.
  Breadth is `log1p`-damped: the 1st connection is transformative, the 40th
  adds nothing.
- **freshness** — exponential decay, 30-day half-life. Undated postings get a
  neutral 0.5 rather than being buried, since several sources omit dates.

Targeting lives in `jobsearch/profile.py` as plain data and is overridable from
`config.yaml`.

## Sources

| Source | Auth | Notes |
|---|---|---|
| Greenhouse / Lever / Ashby | none | Public board APIs. Slugs are probed and cached per company. |
| SmartRecruiters / Workable / Personio | none | Same slug-probe path, three more ATS families. Personio's feed is XML and covers the German-speaking mid-market, which the JSON-first sources reach worst. |
| **Workday** | none | **Shell and Wood Mackenzie run on it.** POST-only, `limit` capped at 20, pages to an explicit `total` — so no coverage caveat. Configured per company, or discovered automatically (below). |
| Arbeitnow | none | Strong Germany/EU coverage. |
| Remotive | none | Remote roles. |
| Adzuna | free key | Good India + UK + DE coverage. Set `ADZUNA_APP_ID` / `ADZUNA_APP_KEY`. |
| Careers pages | none, or a Zyte key | schema.org JSON-LD, with a link-scrape fallback. Brittle — opt-in per company. A Zyte key renders JS-only sites so the same parser can read them. |
| Apollo.io | API key | `ApolloSource` pages the organization job-postings endpoint (1 credit/page). `ApolloDumpSource` replays postings saved from an Apollo MCP session — no key, no credits. |
| JSearch | RapidAPI **or** OpenWebNinja key | One query across LinkedIn, Indeed, Glassdoor and ZipRecruiter. Two front doors sell the same index; when both keys are set the direct one is preferred. |
| LinkedIn feeds | RapidAPI key | `linkedin-job-search-api` and `linkedin-jobs-api2`. Also exposes `count()` — size a query for one call before paging it. |
| Active-ATS | RapidAPI key | `active-jobs-db`: postings read off company ATSes across many employers. |
| Indeed | RapidAPI key | `indeed12`. Company-scoped, so it is driven by the network ranking rather than a keyword sweep. |
| Google Jobs | SerpApi key | The only source here that carries **iimjobs, Naukri, Foundit and Hirist**. |
| Jooble | free key | 60+ countries. Covers India far better than Adzuna. |
| Careerjet | free affid | 80+ countries; indexes Indian boards no ATS-first source reaches. |

Apollo needs an organization id, which comes from enriching a domain; ids are
never guessed. Large employers advertise at real scale (Siemens Energy returned
**1,817 postings across 19 pages**) and the endpoint sorts by recency, not
relevance — so `ApolloSource.fetch` pages through rather than assuming page 1
holds anything useful, and a dump that only captured part of a company is
flagged with a `_caveat` that is logged as a warning instead of quietly reading
as full coverage.

### Workday: the free feed the paid one was standing in for

Every Shell posting collected through Apollo carries a
`shell.wd3.myworkdayjobs.com` URL — Shell publishes to Workday, and Workday has
a public JSON endpoint. Closing Shell's 30-day window through Apollo took five
credit-charged pages and still needed a caveat recording what was not fetched;
Workday pages to an explicit `total`, for nothing, with no caveat.

Because the tenant, data-centre number and site all sit inside a posting URL —
and none of them is guessable from a company name — `scan` derives its Workday
config from URLs it already has:

```
144 stored posting URLs -> 2 Workday tenants derived
  shell     site=shellcareers     wd3
  woodmac   site=woodmaccareers   wd3
```

The same pass finds `apply.workable.com/rystad-energy`, so **Rystad Energy**
becomes readable through the Workable adapter. No configuration needed for any
of the three.

Two traps in the Workday endpoint: a **GET returns nothing useful** (it is
POST-only), and **`limit` is capped at 20** — asking for more returns an empty
`jobPostings` array rather than an error, which reads exactly like an employer
with no openings. The cap is enforced in the adapter rather than trusted to the
caller.

**Assume nothing about an employer's ATS.** The same check found Siemens Energy
on `jobs.siemens-energy.com`, S&P Global on `careers.spglobal.com` and
TotalEnergies on `jobs.totalenergies.com` — own-domain career sites, not
Workday. Read the host off a posting URL rather than guessing.

### Reading LinkedIn and Indeed without scraping them

Neither offers a jobs API to an individual developer, and both forbid scraping.
The aggregators above license an index instead, so postings arrive without any
automation pointed at the account you are job-hunting with. Every posting keeps
the portal it came from in its `source` (`jsearch:LinkedIn`,
`google_jobs:Naukri.com`), so a report can show how much of its coverage is
LinkedIn versus elsewhere rather than implying it read the site directly.

Three things these feeds punish if you take them at face value:

- **The window can be in the path, not the parameter.** `/active-jb-7d` with
  `time_frame=30d` returns seven days for a thirty-day question, succeeds, and
  says nothing. The path is now built from `time_frame`; an unsupported window
  404s, which is the better failure. Pinned by
  `test_linkedin_window_is_the_one_actually_fetched`.
- **A 200 can be a failure.** SerpApi reports a bad key or an exhausted quota as
  HTTP 200 with an `error` body, which otherwise reads as "no jobs found".
- **Well-formed XML is not a jobs feed.** Personio returns HTML error pages
  that parse cleanly as XML, contain no `<position>`, and yield `[]` —
  indistinguishable from a company with nothing open. Caught by checking the
  root element, not by catching a parse error. (Found because a test written to
  assert the parse-error path *failed*: the error page parsed fine.)
- **Field names drift.** The same value ships as `organization` or
  `company_name`, `date_posted` or `datePosted`; locations arrive as a string, a
  list, or a list of dicts; rows come bare or wrapped in `data`/`jobs`. Every
  field is read through a list of accepted names, and unrecognised keys are
  logged so drift surfaces as a log line instead of a blank column.

Cost is a query × location fan-out against a metered quota, so trim those lists
before widening the window. Google Jobs gives only a relative date ("3 days
ago"); anything unparseable becomes `None` rather than an invented date, which
would otherwise feed straight into the freshness term of the score.

### Credentials never reach the logs

Adzuna and SerpApi authenticate via query string, so a raw request URL contains
the API key. `sources/base.redact()` masks `app_key`, `app_id`, `api_key`,
`token` and friends before any URL is logged or embedded in an exception. The
RapidAPI family authenticates by header instead, which keeps the key out of the
URL entirely — asserted by `test_rapidapi_key_travels_in_headers_not_the_url`.

### A failing source is not an empty one

If page 1 of a source fails, the error propagates instead of returning `[]`. An
unreachable host and "no matching jobs" produce identical output otherwise,
which silently understates coverage in every report downstream.

Postings are deduped across sources on (company, title, location), preferring a
dated record and the canonical ATS link over an aggregator's copy. Any source
that fails is logged and skipped; one dead feed never kills a run.

## Employer coverage, and what "empty" means for each

Which employers have been pulled, how completely, and what was deliberately
skipped. Recorded here because the alternative is re-spending credits to
rediscover it, and because a partial pull that is not labelled as partial reads
as a complete one:

| Employer | Coverage | Note |
|---|---|---|
| Uniper | **complete** (103 of 103) | page 2 held 3 rows, none in-window. Board is dominated by German apprenticeship and plant-technician roles; the commercial roles are a small minority |
| Argus Media | **complete** (60 of 60) | price-reporting agency for energy commodities — closest institutional match to the Shell Category Analyst work. India (Mumbai) is analyst-grade; senior commercial sits in London/Houston/Singapore |
| Aurora Energy Research | **complete** (84 of 84) | sector-perfect, grade-wrong: overwhelmingly analyst/associate. India (Gurugram) is payroll, IT and billing |
| Rystad Energy, Invest India | complete (12 of 12, 13 of 13) | Invest India is contracting (−8.8% 12mo); Rystad is the inverse (+9%) |
| Shell | pages 1–5 of 7 | full 30-day window. Feed repeats each requisition per `?source=` variant, so a page advances only ~3–6 days |
| S&P Global | pages 1–2 of 5 | full 30-day window |
| **Siemens** | **page 1 of 26** | 2,518 postings, ~95% software/building-automation on page 1, yielding one relevant role. Pages 2–26 **not fetched** — the yield did not justify 25 credits. A gap, not an absence |
| Deloitte, EY | page 1 only | both **carry no India at all** — see below |
| Accenture, KPMG, PwC India, TotalEnergies | page 1 | see below |

## Where a company's India roles actually live

Measured across 11 employers. A global feed is not the same as a global company,
and assuming it is silently drops entire countries:

| Employer | Feed carries India? | Note |
|---|---|---|
| PwC India | yes, 100% | `pwc.in` resolves to a **separate** org from global PwC |
| Accenture | yes, heavy | but volume is BPO/tech; the fit is Strategy & Consulting Global Network |
| KPMG | yes | `kpmg.com` is the global org, and its feed still carries India |
| Shell, Wood Mackenzie, S&P Global | yes | ordinary global ATS |
| **Deloitte** | **no** | 4,709 postings, page 1 100% US. India lives on `southasiacareers.deloitte.com` |
| **EY** | **no** | 3,198 postings, page 1 100% US/EU. EY India / GDS absent |
| TotalEnergies | no India in window | France/US/Africa/Gulf heavy |

Two lessons worth encoding: try the **country domain first** (`pwc.in` beat
`pwc.com`), and never read an empty country result as "not hiring" until you have
confirmed the feed covers that country at all.

## The line on scraping, enforced in code

`sources/zyte.py` can render any page, which makes it exactly the tool for
quietly doing what this project has declined to do throughout. It is wired to
one job — turning the JS-only **own-domain** careers sites (Siemens Energy, S&P
Global, TotalEnergies) from empty shells into readable HTML, which the existing
schema.org parser then handles unchanged.

It will not fetch **LinkedIn, Naukri, iimjobs, Hirist, Instahyre, Foundit,
Glassdoor or Indeed**. Putting a vendor in front of a scrape does not change
what the scrape is: those terms forbid it, and the account at risk is the one
being job-hunted with.

That refusal lives in `DENIED_HOSTS` and is checked on every call, *before* the
credential check, so a denied host is refused even with no key — otherwise the
refusal would read as a configuration problem a key would fix. No config
setting disables it, so a later edit pointing `careers_pages` at a LinkedIn URL
raises rather than silently scraping. Matching is on domain boundaries, so
subdomains (`in.linkedin.com`) are caught while unrelated hosts
(`notlinkedin.com`) are not. A README paragraph is not a control; the tests in
`test_zyte_policy.py` are.

## Portals this tool does not read

India's senior-hire market runs through portals with no public API and no ATS
feed: **iimjobs** (the main one for BD / strategy / consulting at 8+ years),
**Naukri**, **Foundit**, **Hirist**, **Instahyre**. They are worth searching by
hand -- iimjobs in particular carries roles that never reach a company ATS, and
lists experience bands (e.g. "6-8 yrs") that make grade mismatches obvious
before you apply. Scraping them is against their terms and is not attempted here.

The partial way in is **SerpApi Google Jobs**: Google indexes iimjobs, Naukri
and Foundit, so their postings arrive through a licensed index rather than a
scraper. Coverage is whatever Google chose to index, not the portal's full
inventory — treat it as a supplement to searching them by hand, not a
replacement.

## Layout

```
jobsearch/
  normalize.py    company / title / name / URL keys      <- every join runs on this
  connections.py  export parser (finds the real header past LinkedIn's preamble)
  dedupe.py       consolidate, merge_exports, ambiguity reporting
  network.py      company index, talent + senior detection, strength scoring
  profile.py      targeting keywords (data, not logic)
  scoring.py      role fit, freshness, blended score
  discovery.py    ATS slug probing + disk cache
  sources/        greenhouse lever ashby arbeitnow remotive adzuna careers_page
  pipeline.py     orchestration
  report.py       CSV / Markdown / HTML
```

## Privacy

`Connections.csv` holds personal data for every contact — names, employers,
titles, and any shared emails. It is gitignored along with `config.yaml` and
`out/`. Keep it that way.

## Tests

```bash
python -m pytest
```

53 tests, no network access required — sources are exercised through fixtures.
