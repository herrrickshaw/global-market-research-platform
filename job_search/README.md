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
| Arbeitnow | none | Strong Germany/EU coverage. |
| Remotive | none | Remote roles. |
| Adzuna | free key | Good India + UK + DE coverage. Set `ADZUNA_APP_ID` / `ADZUNA_APP_KEY`. |
| Careers pages | none | schema.org JSON-LD, with a link-scrape fallback. Brittle — opt-in per company. |
| Apollo.io | API key | `ApolloSource` pages the organization job-postings endpoint (1 credit/page). `ApolloDumpSource` replays postings saved from an Apollo MCP session — no key, no credits. |

Apollo needs an organization id, which comes from enriching a domain; ids are
never guessed. Large employers advertise at real scale (Siemens Energy returned
**1,817 postings across 19 pages**) and the endpoint sorts by recency, not
relevance — so `ApolloSource.fetch` pages through rather than assuming page 1
holds anything useful, and a dump that only captured part of a company is
flagged with a `_caveat` that is logged as a warning instead of quietly reading
as full coverage.

### Credentials never reach the logs

Adzuna authenticates via query string, so a raw request URL contains the API
key. `sources/base.redact()` masks `app_key`, `app_id`, `api_key`, `token` and
friends before any URL is logged or embedded in an exception. Covered by
`test_credentials_are_redacted_before_logging`.

### A failing source is not an empty one

If page 1 of a source fails, the error propagates instead of returning `[]`. An
unreachable host and "no matching jobs" produce identical output otherwise,
which silently understates coverage in every report downstream.

Postings are deduped across sources on (company, title, location), preferring a
dated record and the canonical ATS link over an aggregator's copy. Any source
that fails is logged and skipped; one dead feed never kills a run.

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
