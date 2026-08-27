#!/usr/bin/env python3
"""
news_crawler.py — scrapling-backed news provider for sentiment_pipeline.

WHAT THIS ADDS
──────────────
The existing providers have two structural limits:

  coverage  IndianRSSProvider pulls a handful of MARKET-WIDE feeds and then
            string-matches the ticker in the pooled entries. A stock that
            simply was not mentioned in today's business.xml scores zero
            articles — absence of coverage is indistinguishable from neutral
            sentiment. There is no per-ticker discovery anywhere in the stack.

  depth     Every provider scores the HEADLINE (plus, sometimes, a one-line
            summary). "Reliance slips after Q2" and a 900-word piece explaining
            why carry very different information, and VADER sees the same
            eight words.

This module fixes both:

  discovery per-ticker search feed → real coverage for quiet names, all markets
  depth     scrapling fetches and extracts the ARTICLE BODY, and sentiment is
            scored on the body instead of the headline

CONDUCT
───────
This crawler is deliberately polite, and deliberately NOT stealthy:

  * robots.txt is fetched and honoured per host, and cached for the run. A
    disallowed URL is skipped, not fetched.
  * one request per host at a time, with a real delay between them, obeying
    Crawl-delay when the host declares one.
  * a truthful User-Agent naming the tool and the contact address.
  * scrapling's StealthyFetcher / DynamicFetcher are NOT used. Those exist to
    defeat bot detection; a site that does not want to be read by a script is
    entitled to that, and evading it is not something this pipeline should do.
    Body extraction degrades to the headline when a fetch is refused.

That also keeps the dependency light — the plain parser needs no browser, so
there is no 400MB playwright install behind this.

Usage:
    from news_crawler import ScraplingProvider
    p = ScraplingProvider()
    arts = p.fetch_news("RELIANCE", "IN")

    # or standalone
    .venv/bin/python3 news_crawler.py --tickers RELIANCE TCS --market IN
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
import urllib.parse
import urllib.robotparser
from dataclasses import asdict
from datetime import datetime, timezone
from typing import List

# Reuse the pipeline's own Article/scoring so this is a provider, not a
# parallel universe. If that import breaks, this module is useless anyway.
from sentiment_pipeline import Article, NewsProvider, score_text

try:
    from scrapling.parser import Selector
    _SCRAPLING_OK = True
except Exception:                                    # pragma: no cover
    _SCRAPLING_OK = False

try:
    import requests
    _REQ_OK = True
except ImportError:                                  # pragma: no cover
    _REQ_OK = False

try:
    import feedparser
    _FP_OK = True
except ImportError:                                  # pragma: no cover
    _FP_OK = False


UA = ("market-pipeline-newsbot/1.0 "
      "(personal research; umashankartd1991@gmail.com)")

# ── two discovery routes, and why both exist ─────────────────────────────────
#
# PUBLISHER feeds give DIRECT article URLs, so the body is fetchable (subject
# to that publisher's robots.txt). This is the route that produces depth.
#
# SEARCH (Google News) gives per-ticker coverage for quiet names that never
# appear in a market-wide feed — but its entries link to
# news.google.com/rss/articles/<opaque>, a redirect that Google's own
# robots.txt disallows, and the entry carries only the publisher's DOMAIN
# ("The Hindu"), never the article URL. Resolving that redirect means fetching
# a disallowed path, so search results stay HEADLINE-ONLY by design. That is a
# deliberate ceiling, not a bug to be worked around.
SEARCH_FEED = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"

# Direct-link feeds. BusinessLine is deliberately absent: its robots.txt
# disallows article paths, so every body fetch would be skipped anyway.
PUBLISHER_FEEDS = {
    "IN": [
        "https://www.moneycontrol.com/rss/business.xml",
        "https://www.moneycontrol.com/rss/results.xml",
        "https://www.moneycontrol.com/rss/marketreports.xml",
        "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "https://www.livemint.com/rss/markets",
        "https://www.business-standard.com/rss/markets-106.rss",
    ],
    "US": [
        "https://finance.yahoo.com/news/rssindex",
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    ],
}

SYMBOL_MASTER = "~/market-pipeline/market_cache/symbol_master.parquet"

MARKET_LOCALE = {
    "IN": ("en-IN", "IN", "IN:en"),
    "US": ("en-US", "US", "US:en"),
    "JP": ("en-US", "JP", "JP:en"),
    "KR": ("en-US", "KR", "KR:en"),
    "EU": ("en-GB", "GB", "GB:en"),
}

# Query hint per market so "TITAN" finds the company, not the moon.
MARKET_HINT = {
    "IN": "NSE OR BSE stock",
    "US": "stock",
    "JP": "TSE stock",
    "KR": "KRX stock",
    "EU": "stock",
}

BODY_SELECTORS = [
    "article p", "div.articleBody p", "div.article-body p",
    "div.story-element-text p", "div[itemprop='articleBody'] p",
    "section.article p", "div.content p", "main p",
]

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def score_document(text: str) -> float:
    """Sentiment for a full article, in [-1, +1].

    NOT score_text() on the whole body. VADER's `compound` is a normalised SUM
    of valence across the text, so it saturates toward ±1 as length grows: the
    first two bodies this crawler pulled scored +0.990 and +0.991, which is not
    a measurement, it is a word count. Any article containing a handful of
    positive words would come back "maximally bullish", and because those
    scores flow into the same feature stream as the headline scores, body
    sentiment would have been strictly WORSE than the headlines it replaced.

    Scoring per sentence and averaging keeps the scale comparable to the
    headline scores the other providers emit, which is the whole point of
    putting them in one stream.
    """
    if not text:
        return 0.0
    if len(text) < 400:
        return score_text(text)
    sents = [s for s in _SENT_SPLIT.split(text) if len(s.strip()) > 25]
    if not sents:
        return score_text(text[:400])
    scores = [score_text(s) for s in sents[:120]]
    return sum(scores) / len(scores)


_STRIP = re.compile(r"\s+")
_BOILER = re.compile(
    r"(subscribe|sign in|newsletter|all rights reserved|read more|also read"
    r"|download the app|follow us on|click here)", re.I)


class ScraplingProvider(NewsProvider):
    """Per-ticker discovery + full-body sentiment, via scrapling's parser."""

    name = "scrapling"
    env_key = ""              # no API key, no quota
    min_interval = 1.5        # polite floor between article fetches

    # Wall-clock ceiling for ALL body fetches this provider will ever do, across
    # every ticker in the run. Body fetching is the most expensive thing in the
    # sentiment pipeline by an order of magnitude: measured 2026-08-27 at 9.8s
    # per ticker (8 articles x (1.5s polite floor + per-host crawl-delay + up to
    # `timeout`s of network)), so 25 picks costs ~245s on its own. The caller's
    # whole Talk-on-the-Street budget is 300s, and when it is exceeded
    # get_street_talk returns {} — which emptied the entire convergence section
    # on 2026-08-27 and read in the brief as "no matching news coverage" rather
    # than "the check never ran".
    #
    # So bodies are now best-effort under a deadline. Past it, discovery still
    # runs and articles still score — on their HEADLINE, the fallback this class
    # already supports (see `got_body` in fetch_news). Sentiment gets noisier for
    # the tail of the ticker list; it does not vanish for all of them.
    BODY_BUDGET = float(os.environ.get("SCRAPLING_BODY_BUDGET", "120"))

    def __init__(self, max_articles: int = 8, fetch_bodies: bool = True,
                 timeout: int = 12, body_budget: float = None):
        super().__init__()
        self.max_articles = max_articles
        self.fetch_bodies = fetch_bodies
        self.timeout = timeout
        self.body_budget = (self.BODY_BUDGET if body_budget is None
                            else float(body_budget))
        self._deadline = None         # set on first fetch_news call
        self._fetched = False         # did the last _extract_body hit network?
        self._robots: dict = {}       # host -> (RobotFileParser | None, delay)
        self._host_last: dict = {}    # host -> last fetch time
        self._pool: dict = {}         # market -> publisher-feed entries
        self.stats = {"discovered": 0, "bodies": 0, "robots_blocked": 0,
                      "fetch_failed": 0, "search_topup": 0,
                      "budget_skipped": 0}

    # ── budget ──────────────────────────────────────────────────────────────
    def _budget_left(self) -> bool:
        """False once the body-fetch deadline has passed (headline fallback)."""
        if self.body_budget <= 0:
            return True                       # 0/negative disables the ceiling
        if self._deadline is None:
            self._deadline = time.time() + self.body_budget
        return time.time() < self._deadline

    # ── availability ────────────────────────────────────────────────────────
    @property
    def available(self) -> bool:
        return _SCRAPLING_OK and _REQ_OK and _FP_OK

    # ── politeness ──────────────────────────────────────────────────────────
    def _robot(self, url: str):
        """(parser, crawl_delay) for the URL's host. Cached per run."""
        host = urllib.parse.urlsplit(url).netloc
        if host in self._robots:
            return self._robots[host]
        rp = urllib.robotparser.RobotFileParser()
        scheme = urllib.parse.urlsplit(url).scheme or "https"
        rp.set_url(f"{scheme}://{host}/robots.txt")
        delay = self.min_interval
        try:
            rp.read()
            d = rp.crawl_delay(UA) or rp.crawl_delay("*")
            if d:
                delay = max(delay, float(d))
        except Exception:
            rp = None            # unreadable robots.txt -> treat as permissive
        self._robots[host] = (rp, delay)
        return self._robots[host]

    def _may_fetch(self, url: str) -> bool:
        rp, _ = self._robot(url)
        if rp is None:
            return True
        try:
            return rp.can_fetch(UA, url)
        except Exception:
            return True

    def _host_throttle(self, url: str):
        host = urllib.parse.urlsplit(url).netloc
        _, delay = self._robot(url)
        last = self._host_last.get(host, 0.0)
        wait = delay - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        self._host_last[host] = time.time()

    # ── body extraction ─────────────────────────────────────────────────────
    def _extract_body(self, url: str) -> str:
        """Full article text, or '' if unavailable/disallowed/out of budget.

        Sets self._fetched to whether this call actually touched the network,
        so the caller knows if the polite floor is owed. A refusal (robots, or
        out of budget) costs nobody anything and owes no delay.
        """
        self._fetched = False
        # Checked BEFORE robots and throttle: once the deadline has passed we
        # want to spend no network and no sleep at all, just fall back to the
        # headline. See BODY_BUDGET.
        if not self._budget_left():
            self.stats["budget_skipped"] += 1
            return ""
        if not self._may_fetch(url):
            self.stats["robots_blocked"] += 1
            return ""
        self._host_throttle(url)
        self._fetched = True
        try:
            r = requests.get(url, timeout=self.timeout,
                             headers={"User-Agent": UA})
            if r.status_code != 200 or "html" not in \
                    r.headers.get("content-type", ""):
                self.stats["fetch_failed"] += 1
                return ""
            sel = Selector(r.text)
        except Exception:
            self.stats["fetch_failed"] += 1
            return ""

        best = ""
        for css in BODY_SELECTORS:
            try:
                paras = [p.text for p in sel.css(css) if p.text]
            except Exception:
                continue
            text = " ".join(t.strip() for t in paras if len(t.strip()) > 40)
            if len(text) > len(best):
                best = text

        if not best:                       # fall back to every <p> on the page
            try:
                paras = [p.text for p in sel.css("p") if p.text]
                best = " ".join(t.strip() for t in paras
                                if len(t.strip()) > 60)
            except Exception:
                return ""

        best = _STRIP.sub(" ", best).strip()
        # drop nav/boilerplate sentences that survive the selectors
        keep = [s for s in re.split(r"(?<=[.!?])\s+", best)
                if not _BOILER.search(s)]
        best = " ".join(keep)
        if len(best) > 60:
            self.stats["bodies"] += 1
        return best[:12000]

    # ── ticker → company name ───────────────────────────────────────────────
    _NAMES = None

    @classmethod
    def _names(cls):
        """symbol -> (name, name_clean). Loaded once per process."""
        if cls._NAMES is not None:
            return cls._NAMES
        cls._NAMES = {}
        try:
            import os
            import pandas as pd
            df = pd.read_parquet(os.path.expanduser(SYMBOL_MASTER),
                                 columns=["symbol", "name", "name_clean"])
            cls._NAMES = {str(r.symbol).upper(): (str(r.name), str(r.name_clean))
                          for r in df.itertuples()}
        except Exception:
            pass                      # degrade to bare-ticker matching
        return cls._NAMES

    def _aliases(self, ticker: str) -> list:
        """Strings that identify this company in prose, longest first.

        Matching on the bare ticker alone is why a "RELIANCE" query returned
        Reliance Power and Reliance Communications — three different listed
        companies sharing a token. The registered name disambiguates.
        """
        t = ticker.upper()
        out = [t]
        name, clean = self._names().get(t, ("", ""))
        for s in (name, clean):
            s = re.sub(r"\b(LTD|LIMITED|INDIA|CORP|CORPORATION|PLC|INC)\b", "",
                       s, flags=re.I).strip()
            if len(s) > 3:
                out.append(s)
        return sorted(set(out), key=len, reverse=True)

    # ── discovery ───────────────────────────────────────────────────────────
    def _discover_search(self, ticker: str, market: str) -> list:
        """Per-ticker coverage. Headline-only — see SEARCH_FEED note above."""
        hl, gl, ceid = MARKET_LOCALE.get(market, MARKET_LOCALE["US"])
        hint = MARKET_HINT.get(market, "stock")
        alias = self._aliases(ticker)
        # quote the company name when we know it, so the query is about the
        # company rather than any headline containing the token
        term = f'"{alias[0]}"' if len(alias[0]) > len(ticker) else f'"{ticker}"'
        q = urllib.parse.quote_plus(f"{term} {hint}")
        # One real request per ticker, so it owes the polite floor. This used to
        # be paid incidentally by the per-article _throttle() in _add(); that
        # now fires only when a body was actually fetched, so without this the
        # search endpoint would see 25 back-to-back requests. Charged once per
        # search rather than once per returned headline: same politeness toward
        # the host, ~8x less sleep.
        self._throttle()
        try:
            feed = feedparser.parse(
                SEARCH_FEED.format(q=q, hl=hl, gl=gl, ceid=ceid))
        except Exception:
            return []
        return list(feed.entries)[: self.max_articles]

    def _feed_pool(self, market: str) -> list:
        """All publisher-feed entries for a market, fetched once per run."""
        if market in self._pool:
            return self._pool[market]
        entries = []
        for url in PUBLISHER_FEEDS.get(market, []):
            try:
                entries.extend(feedparser.parse(url).entries)
            except Exception:
                continue
        self._pool[market] = entries
        return entries

    def _discover_publisher(self, ticker: str, market: str) -> list:
        """Entries from direct-link feeds that actually mention the company."""
        pats = [re.compile(rf"\b{re.escape(a)}\b", re.I)
                for a in self._aliases(ticker)]
        hits = []
        for e in self._feed_pool(market):
            blob = f"{getattr(e, 'title', '')} {getattr(e, 'summary', '')}"
            if any(p.search(blob) for p in pats):
                hits.append(e)
        return hits[: self.max_articles]

    # ── the provider contract ───────────────────────────────────────────────
    def fetch_news(self, ticker: str, market: str = "IN") -> List[Article]:
        """Publisher feeds first (bodies obtainable), then top up via search.

        The top-up is what closes the coverage hole: a name that appears in no
        market-wide feed today returns zero from the publisher route, which the
        existing RSS provider reports as neutral sentiment rather than as
        "no coverage".
        """
        if not self.available:
            return []

        seen, out = set(), []

        def _add(e, allow_body: bool):
            title = _STRIP.sub(" ", getattr(e, "title", "")).strip()
            link = getattr(e, "link", "")
            key = link or title
            if not title or key in seen:
                return
            seen.add(key)
            self.stats["discovered"] += 1

            # Reset here, not only inside _extract_body: on the else-branch that
            # call never happens and a stale True would charge a polite delay
            # for a fetch nobody made.
            self._fetched = False
            body = self._extract_body(link) if (allow_body and self.fetch_bodies
                                                and link) else ""
            got_body = len(body) > 200
            # Score the body when we actually got one; a headline is a much
            # noisier sentiment target and is only the fallback.
            out.append(Article(
                title=title,
                source=f"{self.name}:{'body' if got_body else 'headline'}",
                published=str(getattr(e, "published", "")
                             or datetime.now(timezone.utc).isoformat()),
                sentiment=(score_document(body) if got_body
                           else score_text(title)),
                url=link,
                summary=(body[:400] if body else
                         _STRIP.sub(" ", getattr(e, "summary", ""))[:400]),
            ))
            # The polite floor exists to space out ARTICLE FETCHES. When no
            # fetch happened — headline-only search entries, a robots refusal,
            # or past the body deadline — the entry came off an already
            # downloaded feed, so sleeping here would burn the caller's
            # remaining budget to be polite to nobody.
            if getattr(self, "_fetched", False):
                self._throttle()

        for e in self._discover_publisher(ticker, market):
            _add(e, allow_body=True)

        if len(out) < self.max_articles:
            self.stats["search_topup"] += 1
            for e in self._discover_search(ticker, market):
                if len(out) >= self.max_articles:
                    break
                _add(e, allow_body=False)     # aggregator redirect — see above

        return out


# ══════════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--tickers", nargs="+", required=True)
    ap.add_argument("--market", default="IN", choices=sorted(MARKET_LOCALE))
    ap.add_argument("--max", type=int, default=6)
    ap.add_argument("--no-bodies", action="store_true",
                    help="discovery only — skip article fetches")
    ap.add_argument("--csv", default="", help="write articles to this path")
    args = ap.parse_args()

    p = ScraplingProvider(max_articles=args.max,
                          fetch_bodies=not args.no_bodies)
    if not p.available:
        sys.exit("scrapling / requests / feedparser not importable — "
                 "pip install scrapling feedparser requests")

    rows = []
    for t in args.tickers:
        arts = p.fetch_news(t, args.market)
        print(f"\n=== {t} ({args.market}) — {len(arts)} article(s)")
        for a in arts:
            tag = "BODY" if a.source.endswith("body") else "head"
            print(f"  [{tag}] {a.sentiment:+.3f}  {a.title[:88]}")
            rows.append({"ticker": t, **asdict(a)})
        if arts:
            mean = sum(a.sentiment for a in arts) / len(arts)
            print(f"  → mean sentiment {mean:+.3f} over {len(arts)}")

    print(f"\nstats: {p.stats}")
    if args.csv and rows:
        import pandas as pd
        pd.DataFrame(rows).to_csv(args.csv, index=False)
        print(f"wrote {args.csv} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
