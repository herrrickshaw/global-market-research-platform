"""SAP SuccessFactors career sites - where the India arms of the Big Four live.

This exists because of a coverage failure the Apollo feeds could not see. EY's
`ey.com` org returned 3,198 postings and ZERO India roles; Deloitte's returned
4,709 and zero. Neither firm is absent from India -- their India practices post
to separate SuccessFactors career sites:

    careers.ey.com                    EY (incl. EY India GPS, Gurgaon/Delhi)
    southasiacareers.deloitte.com     Deloitte India

That is the same lesson as `pwc.in` resolving to a different org than
`pwc.com`, met for a third time: **a parent-company feed reporting no roles in
a country is not evidence the company is not hiring there.**

TWO FEEDS, AND ONLY ONE OF THEM IS COMPLETE.

`/sitemal.xml` (SAP's own typo, present on every instance and in none of their
docs) is an RSS 1.0 document carrying *every* job on the instance. It takes no
query and it is not truncated, so it is tried first.

`/services/rss/job/` is the keyword search feed, and it returns **at most 20
jobs whatever you ask it for**. A board with 500 openings answers with 20 and
says nothing about the other 480. Left unlabelled that reads as a complete
pull -- the same failure this project already met with Shell's paging and
Siemens' 26 -- so a result that comes back at the cap is logged as a SAMPLE.

The two feeds are different RSS versions, which matters more than it sounds:
RSS 1.0 puts its elements in the `purl.org/rss/1.0` namespace and RSS 2.0 puts
them in no namespace at all, so element lookup here matches on local name and
ignores the namespace entirely. Matching `item` literally finds every posting
in the capped feed and none in the complete one.

UNVERIFIED AGAINST LIVE HOSTS. This environment's egress policy 403s
careers.ey.com along with everything else, so the shapes below come from SAP's
documentation and from published write-ups rather than from a response this
code has parsed. The parsing is deliberately tolerant, and the first real run
is the verification -- which is why a run that matches no endpoint raises
instead of returning an empty list.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import quote_plus
from xml.etree import ElementTree

from ..models import JobPosting
from .base import JobSource, SourceError, http_get_text

log = logging.getLogger(__name__)

# The keyword search feed never returns more than this, whatever the query.
RSS_CAP = 20


class Feed:
    """One candidate endpoint, and whether its answer can be trusted as whole."""

    def __init__(self, path: str, *, capped: bool):
        self.path = path
        self.capped = capped


# Tried in order; the first that parses into postings wins. The complete feed
# goes first so the capped one is only ever reached as a fallback.
FEEDS = (
    Feed("/sitemal.xml", capped=False),                       # every job, RSS 1.0
    Feed("/services/rss/job/?locale=en_US&keywords={q}", capped=True),
    Feed("/services/rss/job/?locale=en_US", capped=True),
)

_TAG = re.compile(r"<[^>]+>")
# Career-site titles usually carry the location after the last dash or pipe:
# "Associate Director-Sector Insights-Govt and Public Sector | Gurgaon"
_TRAILING_LOCATION = re.compile(r"[|–-]\s*([A-Za-z .'-]{3,40})\s*$")


def _local(tag: str) -> str:
    """Element local name, namespace discarded.

    RSS 1.0 namespaces everything and RSS 2.0 namespaces nothing; both are
    served by the same career site. Matching the qualified name finds one and
    silently misses the other.
    """
    return tag.rsplit("}", 1)[-1].lower()


def _field(item, *names: str) -> str:
    wanted = {n.lower() for n in names}
    for child in item.iter():
        if child is item:
            continue
        if _local(child.tag) in wanted and (child.text or "").strip():
            return child.text.strip()
    return ""


def _strip_html(text: str) -> str:
    """Flatten a career-site description to the plain text an ATS scorer reads.

    These feeds escape their HTML *inside* an XML document, so the XML parser
    hands back one decoded layer -- markup and `&amp;` still in the string.
    Stripping tags once therefore leaves entities behind as literal tokens,
    which is worse than useless: `amp` and `nbsp` become CV keywords. Unescape
    and strip until it stops changing (twice is enough for the double
    encoding; the loop just refuses to care how many layers there were).
    """
    out = text or ""
    for _ in range(3):
        flattened = _TAG.sub(" ", unescape(out))
        if flattened == out:
            break
        out = flattened
    return re.sub(r"\s+", " ", out).strip()


def _parse_date(raw: str):
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).date()          # RFC 822, RSS default
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None


class SuccessFactorsSource(JobSource):
    name = "successfactors"

    def __init__(self, host: str):
        # Accept "careers.ey.com" or "https://careers.ey.com/".
        host = (host or "").strip().rstrip("/")
        host = re.sub(r"^https?://", "", host)
        if not host:
            raise ValueError("SuccessFactors needs a career-site host")
        self.host = host

    def fetch(self, company: str | None = None, *, query: str = "",
              location: str = "") -> list[JobPosting]:
        errors: list[str] = []
        for feed in FEEDS:
            url = f"https://{self.host}{feed.path.format(q=quote_plus(query))}"
            try:
                text = http_get_text(url)
            except SourceError as exc:
                # Report the URL actually requested, not the template -- an
                # error naming `keywords={q}` sends the reader looking for a
                # formatting bug that isn't there.
                errors.append(f"{url}: {exc}")
                continue
            jobs = self._parse(text, company)
            if jobs:
                if feed.capped and len(jobs) >= RSS_CAP:
                    # A board with hundreds of roles answers with 20 and says
                    # nothing about it. Never let that read as the whole board.
                    log.warning(
                        "%s: %d postings from the keyword feed, which is its "
                        "hard cap - this is a SAMPLE, not the full board. The "
                        "complete feed (%s) did not answer; narrow with query= "
                        "to reach different roles.",
                        self.host, len(jobs), FEEDS[0].path)
                return jobs
            errors.append(f"{url}: parsed 0 postings")

        # Every endpoint failed or parsed empty. That is a broken integration,
        # not an employer with nothing open, and saying so is the whole point.
        raise SourceError(
            f"{self.host}: no SuccessFactors feed responded with postings "
            f"({'; '.join(errors)})")

    def _parse(self, text: str, company: str | None) -> list[JobPosting]:
        try:
            root = ElementTree.fromstring(text)
        except ElementTree.ParseError:
            return []

        jobs: list[JobPosting] = []
        # RSS 2.0 and RSS 1.0 disagree about namespaces and RMK serves both, so
        # select on local name only. Some CSB exports use a flat <job> list.
        items = ([e for e in root.iter() if _local(e.tag) == "item"]
                 or [e for e in root.iter() if _local(e.tag) == "job"])
        for item in items:
            title = _field(item, "title", "jobtitle", "name")
            if not title:
                continue
            location = _field(item, "location", "city", "joblocation")
            if not location:
                m = _TRAILING_LOCATION.search(title)
                location = m.group(1).strip() if m else ""
            jobs.append(JobPosting(
                source=self.name,
                company=company or _field(item, "company", "employer") or self.host,
                title=title,
                location=location,
                url=_field(item, "link", "url", "applyurl"),
                posted_at=_parse_date(_field(item, "pubDate", "date", "postedDate")),
                description=_strip_html(
                    _field(item, "description", "jobdescription"))[:4000],
                external_id=_field(item, "guid", "jobId", "id"),
            ))
        return jobs
