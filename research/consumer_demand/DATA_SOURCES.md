# Amazon demand data sources

Surveyed while building `amazon_demand_compare.py`, which currently talks to one
provider (OpenWeb Ninja's Realtime Amazon Data). This is the map of what else
exists, organised by **what the source actually measures** rather than by
vendor, because the tiers below are not substitutes for one another — they
answer different questions and only one of them reports real orders.

Prices are as advertised in August 2026 and move often; treat them as order of
magnitude, not as quotes.

---

## Tier 1 — Real order data, straight from Amazon

The only sources where "orders" means orders rather than an estimate.

| Source | What you get | The catch |
|---|---|---|
| **SP-API → Brand Analytics → Search Query Performance** | The complete funnel per search term: impressions → clicks → add-to-carts → **purchases**. Real counts, not modelled. Programmatic via SP-API since Feb 2025. | Requires **Brand Registry**, and returns data **only for your own brand's ASINs**. |
| **SP-API sales & traffic reports** | Your own units ordered, sessions, conversion. | Your own catalogue only. |
| **Product Advertising API (PA-API 5.0)** | Catalogue, price, availability, images. | Requires an Associates account with qualifying sales, and it reports **no sales volume at all**. |

**For the moringa-oil-vs-honey question this tier is unusable.** You do not own
either brand, so Amazon will not show you their funnel. Anyone claiming
category-wide order counts is modelling them — which is Tier 2.

## Tier 2 — Sales *estimates* modelled from Best Sellers Rank

The standard approach: BSR is public, and each vendor fits BSR → units per
category from panel data. This is where "X sells 4,000 units/month" numbers
come from, and the models disagree with each other by a lot in thin categories.

| Source | Notes |
|---|---|
| **Keepa** | The reference for **BSR and price history** — deep time series across marketplaces, with a real data API on a token model (~€49/mo tier). Does not hand you units directly, but the BSR history is the best raw input for estimating them, and it is the only affordable way to get **trend** rather than a snapshot. |
| **Jungle Scout** | Sales estimates from BSR; official API on the Cobalt/enterprise tiers. |
| **Helium 10** | Xray sales estimates, Magnet keyword volume; API on the top tiers. |
| **SellerAmp, ZonGuru, PLOTT DATA** | Cheaper estimate tools, mostly UI-first. |

Accuracy is directional, not exact — it varies by category and by sales
velocity, and thin categories like moringa oil are exactly where BSR→units
models are weakest. Treat a single vendor's estimate as one opinion.

## Tier 3 — Search-result aggregators

The class `amazon_demand_compare.py` already targets: they return parsed search
results — title, price, rating count, BSR, and Amazon's **"N+ bought in past
month"** badge, which is the closest thing to a public order count.

| Provider | Shape | Rough entry price |
|---|---|---|
| **OpenWeb Ninja** (current) | REST, Amazon-specific | RapidAPI-style tiers |
| **Rainforest API** (Traject Data) | Deepest Amazon coverage; search, product, reviews, BSR pages | ~$66/mo |
| **Canopy API** | GraphQL, Amazon-specific | mid |
| **SerpApi** | Amazon engine among many; subscription per successful search | ~$3,750/mo at 1M searches |
| **DataForSEO** | Cheapest at volume — ~$0.60/1k queued, ~$2/1k live | pay-as-you-go |
| **Bright Data / Oxylabs / ScraperAPI / Apify** | Infrastructure plays: proxies, scrapers, prebuilt Amazon datasets | volume-priced |
| **FlyByAPIs / Pangolin / Easyparser** | Newer, cheaper entrants (~$20/mo for 10k requests) | low |

Because they all return the same underlying page, **switching provider changes
cost and reliability, not what can be measured**. The scoring in
`amazon_demand_compare.py` — badge parsing, ASIN dedupe, coverage-aware
totals — carries over to any of them; only `fetch()` and `products_of()` need a
new adapter.

## Tier 4 — Demand proxies outside Amazon

Free or cheap, and worth running as a cross-check rather than a primary source.
If Amazon says one thing and all of these say the opposite, suspect the sample.

- **Google Trends** (`pytrends`) — relative search interest, free, years of
  history. The right tool for seasonality and for a sanity check on a ratio.
  It measures interest, not purchases.
- **Amazon Ads API / Amazon Marketing Stream** — keyword search volume and
  competitive metrics; needs an advertising account.
- **Helium 10 Magnet / Jungle Scout Keyword Scout** — Amazon-native search
  volume estimates.

---

## Recommended stack for a category comparison you don't sell in

1. **Tier 3 for the snapshot** — the sales badge, coverage-adjusted. This is
   what the tool already does.
2. **Keepa for the trend** — BSR history on the top listings of each group
   turns a one-day snapshot into a direction, and is far less lossy than the
   bucketed `N+` badge.
3. **Google Trends for the sanity check** — free, and it will catch a Tier 3
   sample that happened to land on an unrepresentative page.

Tier 1 enters the picture only once you actually sell one of these products,
at which point it replaces every estimate above for your own ASINs.

## Note on running any of this

None of the hosts in this document are reachable from the Claude Code sandbox —
`api.openwebninja.com`, `api.keepa.com`, `api.rainforestapi.com`, `serpapi.com`,
`api.dataforseo.com`, `graphql.canopyapi.co`, `trends.google.com`,
`sellingpartnerapi-na.amazon.com` and `www.amazon.com` were each tested and each
returned a 403 on CONNECT from the egress proxy. The constraint is the
sandbox's allowlist, not any one vendor, so changing provider does not make the
analysis runnable there. Run it anywhere with ordinary internet access.
