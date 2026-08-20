"""Normalisation helpers.

Company-name normalisation is the crux of this tool: every join between a job
posting and the connections graph happens on ``normalize_company``. Job boards
write "Shell plc", the LinkedIn export writes "Shell", and both must collapse
to the same key.
"""
from __future__ import annotations

import re
import unicodedata

# Legal-form suffixes stripped from the tail of a company name. Order matters
# only in that longer forms are listed before the shorter ones they contain.
_LEGAL_SUFFIXES = [
    "gmbh & co kg", "gmbh & co", "s p a", "a/s", "s a s", "sarl", "s a r l",
    "pvt ltd", "private limited", "pte ltd", "co ltd", "and company", "& co",
    "incorporated", "corporation", "limited", "holdings", "holding", "group",
    "company", "gmbh", "mbh", "plc", "llc", "llp", "ltd", "inc", "corp", "co",
    "ag", "se", "sa", "nv", "bv", "ab", "as", "oy", "kg", "spa", "srl", "sas",
    "pvt", "pte", "kk", "kabushiki kaisha",
]

_NOISE_WORDS = {"the", "a", "an"}


def strip_accents(text: str) -> str:
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()


def normalize_company(name: str) -> str:
    """Collapse a company name to a stable join key.

    'Boston Consulting Group (BCG)' -> 'boston consulting'
    'Shell plc'                     -> 'shell'
    'Siemens Energy AG'             -> 'siemens energy'
    Returns '' for names that carry no employer signal (freelance, self-employed).
    """
    s = strip_accents(name or "").lower().strip()
    if not s:
        return ""
    # Drop parenthetical asides: "(BCG)", "(formerly X)"
    s = re.sub(r"\([^)]*\)", " ", s)
    # Anything after a separator is usually a division, not the employer.
    s = re.split(r"\s+[-–—|/]\s+", s)[0]
    s = re.sub(r"[^a-z0-9&\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    # Names that mean "no employer" must never become a join key, or every
    # freelancer in the export collapses into one giant fake company.
    if s in {"self employed", "freelance", "freelancer", "self", "independent",
             "unemployed", "none", "n a", "student", "retired", "self employed "}:
        return ""

    # Strip trailing legal forms, repeatedly (e.g. "... gmbh & co kg").
    changed = True
    while changed:
        changed = False
        for suf in _LEGAL_SUFFIXES:
            if s.endswith(" " + suf):
                s = s[: -(len(suf) + 1)].strip()
                changed = True
                break

    tokens = [t for t in s.split() if t not in _NOISE_WORDS]
    return " ".join(tokens).strip()


def normalize_title(title: str) -> str:
    """Normalise a job title for dedup across boards."""
    s = strip_accents(title or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    # Strip req IDs and gender tags common on German boards: "(m/w/d)", "- 12345"
    s = re.sub(r"\b[mfwdxr](\s*/\s*[mfwdxr])+\b", " ", s)
    s = re.sub(r"\b(req|job|id)\s*[#:]?\s*\d+\b", " ", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def normalize_person_name(name: str) -> str:
    """Normalise a human name: accents folded, punctuation and suffixes dropped."""
    s = strip_accents(name or "").lower()
    s = re.sub(r"[^a-z\s]", " ", s)
    tokens = [t for t in s.split() if t not in {
        "mr", "ms", "mrs", "dr", "prof", "phd", "mba", "pmp", "cfa", "jr", "sr",
        "ii", "iii", "cpa", "pe", "msc", "bsc",
    }]
    return " ".join(tokens).strip()


def normalize_linkedin_url(url: str) -> str:
    """Canonicalise a LinkedIn profile URL into a stable identity key.

    Handles locale subdomains (de.linkedin.com), query strings, trailing
    slashes and scheme differences, all of which appear across exports taken at
    different times.
    """
    u = (url or "").strip().lower()
    if not u:
        return ""
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    u = re.sub(r"^[a-z]{2,3}\.linkedin\.com", "linkedin.com", u)
    u = u.split("?")[0].split("#")[0].rstrip("/")
    return u


# --- Encoding repair -------------------------------------------------------
# Some export paths (notably text extraction out of a zip) hand back UTF-8 bytes
# that were decoded with a single-byte codepage and re-encoded, so a name like
# "S\u00f8ren" arrives as "S\u00c3\u017eren". The codepage is not always
# consistent within one file, so repair tries a cascade and accepts only a
# result that decodes as valid UTF-8 AND reduces the mojibake signature.

_MOJIBAKE_SIGNATURE = re.compile("[\u00c3\u00c2\u00d0\u00d1][\u0080-\u024f]")
_REPAIR_CODECS = ("cp1252", "cp1250", "latin-1")


def looks_mojibake(text: str) -> bool:
    return bool(_MOJIBAKE_SIGNATURE.search(text or ""))


def repair_mojibake(text: str) -> str:
    """Undo a UTF-8-decoded-as-codepage round trip.

    Returns the input unchanged when no candidate repair is a strict
    improvement, so clean text is never mangled by a speculative decode.
    """
    if not text or not looks_mojibake(text):
        return text
    before = len(_MOJIBAKE_SIGNATURE.findall(text))
    for codec in _REPAIR_CODECS:
        try:
            candidate = text.encode(codec).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if len(_MOJIBAKE_SIGNATURE.findall(candidate)) < before:
            return candidate
    return text
