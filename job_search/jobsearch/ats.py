"""Score a resume against a job description the way an ATS would.

Real applicant tracking systems (Taleo, Workday, iCIMS, Greenhouse) do far less
than candidates imagine: they match keywords, weight the requirements section
above the blurb, and apply knockout filters on years of experience and
education. There is no semantic understanding. So this scorer does the same
thing, deliberately -- modelling what actually screens you out, not what a
thoughtful human reader would conclude.

Three things follow from that, and they shape the whole module:

- **The useful output is the gap, not the number.** `missing` lists the terms
  the JD asks for that the resume never says, ranked by weight. That is the
  edit list. A score alone tells you nothing you can act on.
- **Requirements outweigh prose.** A term in "Qualifications" counts for far
  more than the same term in the company boilerplate, because that is how the
  screen is configured.
- **A knockout is not a low score, it is a rejection.** Ten years required
  against six evidenced does not shade the number down a little; it caps it,
  because that is what the filter does.

WHAT THIS IS NOT. It is a keyword model. It cannot see that "built a 550-person
India delivery centre" answers "experience scaling offshore operations" unless
the words overlap. A low score means "the resume does not use the JD's
vocabulary", which is a real and fixable problem, but it is not the same as
being a poor candidate -- the same distinction this project has had to relearn
five times about title matching.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

# Words that carry no screening signal. Kept deliberately tight: an
# over-eager stoplist silently deletes real requirements ("lead", "manage",
# "develop" are all genuine JD terms).
STOPWORDS = frozenset("""
a an the and or but if then than that this these those there here of in on at to
for with from by as is are was were be been being have has had do does did will
would shall should can could may might must not no nor so such own same too very
you your yours we our ours they their them it its he she his her who whom which
what when where why how all any both each few more most other some only just also
about into over under again further once during before after above below between
across per via within without upon among amongst able etc ie eg
role position job opportunity candidate applicant apply application
new strong good great excellent successful ability abilities
requirement requirements responsibility responsibilities
qualification qualifications preferred required plus must
including include includes included ensure ensuring
supporting help helping join joining looking seeking hiring offer offering
""".split())

# NOT stopwords, despite looking like filler: "business development",
# "team leadership", "work stream", "years experience", "skills matrix" are all
# real JD terms. Dropping the head word makes the phrase unmatchable, so a
# resume that literally says "business development" scores zero on it.

# Sections an ATS weights above the rest of the posting.
_REQ_HEADINGS = re.compile(
    r"^\s*(?:[#*\-•\s]*)?("
    r"requirements?|qualifications?|what (?:you|we)(?:'ll| will)? (?:need|bring|"
    r"look(?:ing)? for)|who you are|about you|skills?(?: (?:and|&) experience)?|"
    r"experience|essential|must[- ]haves?|your profile|we (?:are looking|expect)"
    r")\b.*$",
    re.I | re.M,
)
# Sections that are boilerplate; terms there should not drive the score.
_NOISE_HEADINGS = re.compile(
    r"^\s*(?:[#*\-•\s]*)?("
    r"about (?:us|the company|our)|benefits?|what we offer|perks|"
    r"equal opportunit|diversity|our values|why join|compensation|salary"
    r")\b.*$",
    re.I | re.M,
)

REQUIREMENT_WEIGHT = 2.5
BODY_WEIGHT = 1.0
NOISE_WEIGHT = 0.25

# A term repeated ten times is not ten times more important.
_MAX_TF = 3

# Credit for a term whose words all appear, but not adjacently.
PARTIAL_CREDIT = 0.5

_TOKEN = re.compile(r"[a-z0-9][a-z0-9+#./&-]*")
# Boundaries an n-gram must not cross: line breaks, bullets, sentence ends,
# and the separators JDs use to list items inline.
_SEGMENT = re.compile(r"[\n\r]+|[•·▪]|(?<=[a-z])[.;:!?](?=\s)|\s[-–—]\s|\s*[/|]\s*")
_YEARS = re.compile(
    r"(\d{1,2})\s*(?:\+|plus)?\s*(?:-|to|–)?\s*(?:\d{1,2})?\s*(?:\+)?\s*year", re.I)

DEGREES = {
    "phd": 4, "doctorate": 4,
    "mba": 3, "master": 3, "msc": 3, "ma": 3, "mtech": 3, "postgraduate": 3,
    "bachelor": 2, "bsc": 2, "btech": 2, "be": 2, "degree": 2, "graduate": 2,
}


@dataclass
class AtsMatch:
    """The result of scoring one resume against one job description."""

    score: float                                  # 0-1 overall
    keyword_coverage: float                       # 0-1, weighted
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)      # the edit list
    knockouts: list[str] = field(default_factory=list)    # hard failures
    notes: list[str] = field(default_factory=list)
    scored_against_jd: bool = True                # False => no JD text existed

    @property
    def percent(self) -> int:
        return round(self.score * 100)

    def summary(self) -> str:
        if not self.scored_against_jd:
            return "no job description available - not an ATS score"
        parts = [f"{self.percent}% keyword match"]
        if self.knockouts:
            parts.append("knockout: " + "; ".join(self.knockouts))
        if self.missing:
            parts.append("missing: " + ", ".join(self.missing[:6]))
        return " | ".join(parts)


def tokenize(text: str) -> list[str]:
    """Content tokens only -- used for term frequency, not for phrase building."""
    return [t for t in _TOKEN.findall((text or "").lower()) if t not in STOPWORDS]


def _all_tokens(text: str) -> list[str]:
    """Every token in order, stopwords included.

    Phrases must be built from this, not from `tokenize()`. Removing stopwords
    first both fabricates phrases the document never contained ("10+ years
    experience in business development" collapses to "10+ development strategy")
    and destroys real ones -- with "business" filtered out, "business
    development" can never match, which for a business-development CV is the
    single most expensive false negative available.
    """
    return _TOKEN.findall((text or "").lower())


def phrase_counts(text: str, max_n: int = 3) -> "Counter[str]":
    """Every phrase with how often it occurs, built in one pass.

    Term frequency has to come from the same pass that generates the phrases.
    Counting separately with a different tokenizer silently disagrees -- a
    token like "BOOT/JV" is one token to the counter and two to the phrase
    builder -- yielding a frequency of zero for a phrase that is plainly
    present, which then reaches math.log() as a domain error.
    """
    counts: Counter[str] = Counter()
    for segment in _SEGMENT.split(text or ""):
        words = _all_tokens(segment)
        counts.update(w for w in words if w not in STOPWORDS)
        # A hyphenated compound is one token, so "market-intelligence" in a CV
        # could never match "market intelligence" in a JD -- and CVs hyphenate
        # far more than JDs do. Emitting the spaced form as well makes the two
        # spellings equivalent, which is what a screen does. The stopword-
        # interior rule is deliberately skipped here: the hyphen is the
        # author's own signal that this is one term ("go-to-market"), so it is
        # not a sentence slice even though "to" sits inside it.
        for w in words:
            if "-" in w and len(w) > 3:
                spaced = w.replace("-", " ").strip()
                if spaced and spaced != w:
                    counts[spaced] += 1
        # The spaced form must also take part in n-gram building, not merely
        # stand alone: "front-end design" is one hyphenated token plus one
        # plain one, so the trigram "front end design" that a JD writes only
        # appears if the compound is split first.
        expanded = [part for w in words
                    for part in (w.split("-") if "-" in w and len(w) > 3 else [w])
                    if part]
        if expanded != words:
            for n in range(2, max_n + 1):
                for i in range(len(expanded) - n + 1):
                    gram = expanded[i:i + n]
                    if any(g in STOPWORDS for g in gram):
                        continue
                    counts[" ".join(gram)] += 1
        for n in range(2, max_n + 1):
            for i in range(len(words) - n + 1):
                gram = words[i:i + n]
                # Any stopword INSIDE an n-gram makes it a windowed slice of a
                # sentence, not a term: "experience in business", "lng and
                # natural", "development or strategy". Only edge-filtering
                # leaves these in, where they are unmatchable by construction,
                # bloat the denominator, and fill the gap list with fragments
                # that cannot be acted on. Real compound terms -- "business
                # development", "natural gas markets", "discounted cash flow"
                # -- contain no stopwords at all.
                if any(w in STOPWORDS for w in gram):
                    continue
                counts[" ".join(gram)] += 1
    return counts


def phrases(text: str, max_n: int = 3) -> set[str]:
    """Unigrams plus bigrams/trigrams, so 'business development' survives.

    Splitting that into two unigrams is how a keyword matcher credits a resume
    that says 'business' and 'development' in unrelated sentences.

    N-grams never span a line, bullet or sentence boundary. Letting them do so
    manufactures phrases no document could ever contain -- two adjacent bullets
    produce 'consulting deep knowledge' and '10+ development strategy' -- which
    are unmatchable by construction, yet land in the denominator and drag every
    score down while filling the gap list with nonsense.
    """
    # Stopword-bearing n-grams are sentence slices, not terms -- see
    # phrase_counts() for why that distinction decides the whole score.
    return set(phrase_counts(text, max_n))


_MAX_HEADING_LEN = 60


def _heading_marks(jd: str, pattern: re.Pattern, weight: float) -> list[tuple[int, float]]:
    """Heading hits, but only where the whole line reads like a heading.

    Without the length check, a requirements bullet starting with the word
    "Experience" is treated as a new section header, fragmenting the JD and
    re-weighting the text that follows it.
    """
    marks = []
    for m in pattern.finditer(jd):
        line = m.group(0).strip()
        if len(line) <= _MAX_HEADING_LEN:
            marks.append((m.start(), weight))
    return marks


def split_sections(jd: str) -> list[tuple[str, float]]:
    """Split a JD into (text, weight) spans by heading type.

    Requirements outweigh the body; "about us" and benefits are nearly ignored.
    A JD with no recognisable headings is treated as one body-weight span
    rather than guessed at.
    """
    if not jd:
        return []
    marks = (_heading_marks(jd, _REQ_HEADINGS, REQUIREMENT_WEIGHT)
             + _heading_marks(jd, _NOISE_HEADINGS, NOISE_WEIGHT))
    if not marks:
        return [(jd, BODY_WEIGHT)]

    marks.sort()
    spans: list[tuple[str, float]] = []
    if marks[0][0] > 0:
        spans.append((jd[:marks[0][0]], BODY_WEIGHT))
    for i, (start, weight) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(jd)
        spans.append((jd[start:end], weight))
    return spans


def jd_term_weights(jd: str) -> dict[str, float]:
    """Weight every JD phrase by where it appears and how often."""
    weights: dict[str, float] = {}
    for text, section_weight in split_sections(jd):
        for phrase, raw_tf in phrase_counts(text).items():
            tf = min(raw_tf, _MAX_TF)
            if not phrase or len(phrase) < 3:
                continue
            # Longer phrases are more specific, so they screen harder.
            specificity = 1.0 + 0.5 * phrase.count(" ")
            weights[phrase] = max(weights.get(phrase, 0.0),
                                  section_weight * specificity * (1 + math.log(tf)))
    return weights


def required_years(jd: str) -> int | None:
    """Largest 'N years' figure in the requirements sections, if any."""
    best = None
    for text, weight in split_sections(jd):
        if weight < BODY_WEIGHT:
            continue
        for m in _YEARS.finditer(text):
            n = int(m.group(1))
            if 1 <= n <= 40:
                best = n if best is None else max(best, n)
    return best


def evidenced_years(resume: str) -> int | None:
    """Longest 'N years' figure the resume itself claims."""
    best = None
    for m in _YEARS.finditer(resume or ""):
        n = int(m.group(1))
        if 1 <= n <= 50:
            best = n if best is None else max(best, n)
    return best


def _degree_level(text: str) -> int:
    return max((lvl for kw, lvl in DEGREES.items()
                if re.search(rf"\b{re.escape(kw)}\b", (text or "").lower())),
               default=0)


def _collapse_variants(terms: list[str]) -> list[str]:
    """Keep one representative per overlapping family, highest weight first.

    One requirement generates a whole family of n-grams -- "npv irr",
    "irr discounted", "npv irr discounted", "discounted cash flow" -- and
    listing them all pushes the genuinely disqualifying single-word skills
    ("kubernetes", "terraform", a named certification) far down the page. Those
    short, distinctive tokens are precisely what a screen hard-filters on, so
    burying them defeats the purpose of the gap list.
    """
    kept: list[str] = []
    for term in terms:
        words = set(term.split())
        # Overlapping means sharing a word with something already kept: enough
        # to catch the sliding-window family without collapsing distinct
        # requirements that merely sit in the same sentence.
        if any(words & set(k.split()) for k in kept):
            continue
        kept.append(term)
    return kept


def score_resume(resume: str, jd: str, *, top_missing: int = 15) -> AtsMatch:
    """Score a resume against one job description."""
    if not (jd or "").strip():
        # Never dress a title-only guess up as an ATS score.
        return AtsMatch(score=0.0, keyword_coverage=0.0, scored_against_jd=False,
                        notes=["no job description text available"])
    if not (resume or "").strip():
        return AtsMatch(score=0.0, keyword_coverage=0.0, scored_against_jd=False,
                        notes=["no resume text available"])

    weights = jd_term_weights(jd)
    if not weights:
        return AtsMatch(score=0.0, keyword_coverage=0.0, scored_against_jd=False,
                        notes=["job description had no scorable terms"])

    have = phrases(resume)
    have_tokens = set(_all_tokens(resume))

    # Exact phrase => full credit. All tokens present but not adjacent =>
    # partial. Boolean AND matching is what most screens actually run, so a
    # resume saying "natural gas" and "markets" in separate bullets does
    # surface for "natural gas markets" -- just less reliably than an exact
    # hit. Scoring it as a total miss understates a genuinely strong resume.
    def credit(term: str) -> float:
        if term in have:
            return 1.0
        # Symmetry: a JD writing "market-intelligence" must credit a resume
        # that writes "market intelligence". Without this the term is scored
        # as missing and lands on the edit list, telling the candidate to add
        # something they already say -- advice that is worse than silence.
        if "-" in term and term.replace("-", " ") in have:
            return 1.0
        parts = term.replace("-", " ").split()
        if len(parts) > 1 and all(p in have_tokens for p in parts):
            return PARTIAL_CREDIT
        return 0.0

    credits = {term: credit(term) for term in weights}
    total_w = sum(weights.values())
    matched_w = sum(weights[t] * c for t, c in credits.items())
    coverage = matched_w / total_w if total_w else 0.0

    matched = sorted((t for t, c in credits.items() if c >= 1.0),
                     key=lambda t: -weights[t])
    # Only a zero-credit term is a real gap worth putting on the edit list.
    missing = sorted((t for t, c in credits.items() if c == 0.0),
                     key=lambda t: -weights[t])

    # A gap that is contained in a term already matched is noise, not an edit.
    matched_set = set(matched)
    missing = [m for m in missing
               if not any(m in bigger for bigger in matched_set if " " in bigger)]
    missing = _collapse_variants(missing)

    score = coverage
    knockouts: list[str] = []
    notes: list[str] = []

    need_years = required_years(jd)
    got_years = evidenced_years(resume)
    if need_years:
        if got_years is None:
            notes.append(
                f"JD asks for {need_years}+ years; the resume never states a "
                f"year count an ATS can read")
        elif got_years + 1 < need_years:
            knockouts.append(f"{need_years}+ years required, resume evidences {got_years}")
            score *= 0.4
        else:
            notes.append(f"years requirement met ({got_years} vs {need_years} asked)")

    need_degree = _degree_level(" ".join(t for t, w in split_sections(jd)
                                         if w >= BODY_WEIGHT for t in [t]))
    got_degree = _degree_level(resume)
    if need_degree and got_degree < need_degree:
        knockouts.append("degree requirement not evidenced in the resume")
        score *= 0.7

    return AtsMatch(
        score=max(0.0, min(1.0, score)),
        keyword_coverage=coverage,
        matched=matched[:40],
        missing=missing[:top_missing],
        knockouts=knockouts,
        notes=notes,
    )
