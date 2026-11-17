"""Resume-to-JD matching, and the four defects that only showed up on real text.

Every failure pinned here was invisible while reading the code and obvious the
first time a realistic CV met a realistic job description. The recurring shape
is the same one this project keeps meeting: a number that looks like an answer
but was computed against something that was never there.
"""
from __future__ import annotations

import pytest

from jobsearch.ats import (PARTIAL_CREDIT, phrase_counts, phrases,
                           required_years, score_resume, split_sections)
from jobsearch.resume import ResumeError, load_resume, normalize

RESUME = """
Senior business development and strategy leader, 14 years in energy.
ESMT Berlin MBA, Accounting and Finance.
Built a USD 400M India technology hub under a BOOT/JV structure, 550+ hires.
Market intelligence for rigs, offshore vessels and fabrication yards.
NPV, IRR and TCO modelling. Natural gas and LNG markets.
"""

JD = """About Us
We are a global leader in energy. Our values are collaboration and integrity.

Senior Strategy Consultant

Requirements
- 10+ years experience in business development or strategy consulting
- Deep knowledge of LNG and natural gas markets
- Financial modelling: NPV, IRR, discounted cash flow
- Kubernetes and Terraform administration

Benefits
Private healthcare, generous pension, 30 days holiday.
"""


# --------------------------------------------------------------------------
# Phrase construction -- where three of the four defects lived
# --------------------------------------------------------------------------

def test_business_development_survives_phrase_building():
    """The single most expensive false negative available for this CV.

    Stripping stopwords before building n-grams deletes "business", so
    "business development" can never match -- on a business-development resume.
    """
    assert "business development" in phrases(
        "10+ years experience in business development or strategy consulting")


def test_ngrams_do_not_span_line_boundaries():
    """Two adjacent bullets must not manufacture a phrase spanning both.

    Such phrases are unmatchable by construction, yet they land in the
    denominator and drag every score down.
    """
    jd = ("- deep knowledge of gas markets\n"
          "- strategy consulting delivery")
    built = phrases(jd)
    assert "markets strategy" not in built
    assert "gas markets" in built


def test_ngrams_reject_interior_stopwords():
    """'experience in business' is a window onto a sentence, not a term."""
    built = phrases("10+ years experience in business development")
    assert "experience in business" not in built
    assert "business development" in built


def test_phrase_counts_agree_with_phrase_building():
    """Counting with a different tokenizer disagreed on tokens like BOOT/JV,
    yielding a frequency of zero for a phrase plainly present -- which then
    reached math.log() as a domain error."""
    counts = phrase_counts("Experience with BOOT/JV structures and joint ventures")
    assert counts["boot"] == 1 and counts["jv"] == 1
    assert set(phrases("Experience with BOOT/JV structures")) <= set(counts)
    for term, n in counts.items():
        assert n >= 1, term


def test_scoring_a_resume_with_slash_tokens_does_not_crash():
    """Regression for the math domain error above."""
    m = score_resume("BOOT/JV structures and M&A due diligence, 12 years.",
                     "Requirements\n- BOOT/JV and M&A experience\n- 5+ years")
    assert m.scored_against_jd


# --------------------------------------------------------------------------
# Section weighting
# --------------------------------------------------------------------------

def test_requirements_outweigh_boilerplate():
    spans = dict((text.strip().splitlines()[0], weight)
                 for text, weight in split_sections(JD) if text.strip())
    assert spans["Requirements"] > spans["About Us"]


def test_a_long_bullet_is_not_mistaken_for_a_heading():
    """A requirements bullet starting with "Experience" was being read as a new
    section header, fragmenting the JD and re-weighting what followed it."""
    jd = ("Requirements\n"
          "- Experience with market intelligence, competitor analysis and "
          "commercial modelling across several regions\n")
    weights = [w for _, w in split_sections(jd)]
    assert weights.count(max(weights)) == 1        # one heading, not two


def test_a_jd_with_no_headings_is_one_span_not_a_guess():
    spans = split_sections("We need someone to run business development.")
    assert len(spans) == 1


def test_required_years_reads_the_largest_figure():
    assert required_years(JD) == 10
    assert required_years("No numbers here at all") is None


# --------------------------------------------------------------------------
# Scoring behaviour
# --------------------------------------------------------------------------

def test_a_strong_resume_scores_far_above_a_weak_one():
    strong = score_resume(RESUME, JD).score
    weak = score_resume("Pastry chef, 3 years. Bakery operations.", JD).score
    assert strong > weak * 2


def test_partial_credit_for_non_adjacent_terms():
    """A resume saying the words apart still surfaces in a boolean AND screen,
    just less reliably -- scoring it as a total miss understates it."""
    jd = "Requirements\n- natural gas markets expertise"
    adjacent = score_resume("Natural gas markets expertise.", jd)
    apart = score_resume("Natural resources. Gas turbines. Emerging markets.", jd)
    none = score_resume("Pastry and confectionery.", jd)
    assert adjacent.score > apart.score > none.score
    assert 0 < PARTIAL_CREDIT < 1


def test_single_word_skill_gaps_are_not_buried():
    """Kubernetes and Terraform ranked 21st and 22nd behind redundant variants
    of one requirement. Those short, distinctive tokens are exactly what a
    screen hard-filters on, so burying them defeats the gap list."""
    m = score_resume(RESUME, JD, top_missing=10)
    joined = " ".join(m.missing)
    assert "kubernetes" in joined or "terraform" in joined


def test_gap_list_collapses_redundant_variants():
    m = score_resume(RESUME, JD, top_missing=20)
    npv_family = [t for t in m.missing if "irr" in t or "discounted" in t]
    assert len(npv_family) <= 1


def test_years_shortfall_is_a_knockout_not_a_nudge():
    jd = "Requirements\n- 15+ years of business development leadership"
    m = score_resume("Business development leadership, 4 years.", jd)
    assert m.knockouts and "15" in m.knockouts[0]


def test_years_met_is_recorded_as_a_note_not_a_knockout():
    m = score_resume(RESUME, JD)
    assert not m.knockouts
    assert any("years requirement met" in n for n in m.notes)


def test_a_resume_stating_no_year_count_is_flagged_not_failed():
    """Silence about years is a resume problem to fix, not a rejection."""
    jd = "Requirements\n- 10+ years in strategy"
    m = score_resume("Strategy leadership across energy markets.", jd)
    assert not m.knockouts
    assert any("never states a year count" in n for n in m.notes)


# --------------------------------------------------------------------------
# Absent is not zero -- the distinction this whole project keeps relearning
# --------------------------------------------------------------------------

def test_no_jd_is_reported_as_absent_not_as_zero_percent():
    m = score_resume(RESUME, "")
    assert m.scored_against_jd is False
    assert "no job description" in m.summary()


def test_no_resume_is_reported_as_absent_too():
    m = score_resume("", JD)
    assert m.scored_against_jd is False


def test_a_jd_with_no_scorable_terms_is_absent_not_zero():
    m = score_resume(RESUME, "the and of to for with")
    assert m.scored_against_jd is False


# --------------------------------------------------------------------------
# Resume loading
# --------------------------------------------------------------------------

def test_missing_resume_names_the_path(tmp_path):
    with pytest.raises(ResumeError, match="not found"):
        load_resume(tmp_path / "nope.txt")


def test_unsupported_format_names_what_is_accepted(tmp_path):
    p = tmp_path / "cv.pages"
    p.write_text("x" * 400)
    with pytest.raises(ResumeError, match="unsupported format"):
        load_resume(p)


def test_legacy_doc_is_refused_with_the_fix(tmp_path):
    p = tmp_path / "cv.doc"
    p.write_text("x" * 400)
    with pytest.raises(ResumeError, match="Save as .docx"):
        load_resume(p)


def test_a_scanned_pdf_extracting_nothing_is_an_error_not_a_zero_score(tmp_path):
    """An empty extraction would score 0% against every job -- a wrong answer
    that looks exactly like a real one."""
    p = tmp_path / "cv.txt"
    p.write_text("Name\nPhone")
    with pytest.raises(ResumeError, match="extracted only"):
        load_resume(p)


def test_normalize_repairs_pdf_extraction_artefacts():
    assert "development" in normalize("develop-\nment")
    assert normalize("a  b") == "a b"


# --------------------------------------------------------------------------
# PDF loading survives a broken cryptography install
# --------------------------------------------------------------------------

def test_pdf_import_survives_a_pyo3_panic(monkeypatch):
    """pypdf imports a crypt provider that pulls in `cryptography`, whose Rust
    bindings panic on some installs. That gates ENCRYPTED PDFs only, yet it
    made every PDF unreadable.

    Two things make this easy to get wrong, and both are pinned here: the
    panic inherits from BaseException so `except Exception` never sees it, and
    neither its message ("Python API call failed") nor its class name mentions
    the culprit -- only its module does.
    """
    from jobsearch import resume as R

    class PanicException(BaseException):
        pass
    PanicException.__module__ = "pyo3_runtime"

    calls = {"n": 0}

    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "pypdf" and calls["n"] == 0:
            calls["n"] += 1
            raise PanicException("Python API call failed")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    reader = R._import_pdf_reader()          # must not raise
    assert reader is not None
    assert calls["n"] == 1


def test_a_genuine_interrupt_is_not_swallowed(monkeypatch):
    from jobsearch import resume as R
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "pypdf":
            raise KeyboardInterrupt
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(KeyboardInterrupt):
        R._import_pdf_reader()


def test_an_unrelated_import_failure_still_reports_the_fix(monkeypatch):
    from jobsearch import resume as R
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "pypdf":
            raise ImportError("No module named 'pypdf'")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ResumeError, match="pip install pypdf"):
        R._import_pdf_reader()


def test_hyphenated_compounds_match_their_spaced_form():
    """CVs hyphenate far more than JDs do.

    "market-intelligence" is a single token, so it could never match a JD
    asking for "market intelligence" -- a silent, systematic understatement of
    exactly the terms a CV is most likely to hyphenate.
    """
    cv = phrases("Led market-intelligence analysis and front-end design work.")
    assert "market intelligence" in cv
    assert "front end design" in cv          # spaced form joins n-gram building
    assert "market-intelligence" in cv       # original spelling still counts


def test_hyphen_expansion_keeps_stopword_bearing_compounds():
    """"go-to-market" is one term its author hyphenated, not a sentence slice,
    so the interior-stopword rule must not delete it."""
    assert "go to market" in phrases("Owned go-to-market strategy.")


def test_a_hyphenated_jd_term_matches_a_spaced_resume():
    """The mismatch runs both ways."""
    m = score_resume("Market intelligence and competitor analysis.",
                     "Requirements\n- market-intelligence expertise")
    assert "market intelligence" in m.matched
    # The hyphenated spelling must not be reported as a gap: telling the
    # candidate to add a term they already say is worse than saying nothing.
    assert "market-intelligence" not in m.missing
