"""Encoding-repair tests.

A real export (Basic_LinkedInDataExport_07-07-2026) was found corrupted at rest:
UTF-8 decoded with a single-byte codepage and re-encoded, 936 affected lines.
A control test proved the retrieval path was innocent -- the same retrieval
against a different export returned byte-clean text -- so parsers must be able
to heal a damaged file rather than assume the source is well-formed.
"""
from jobsearch.normalize import (looks_mojibake, normalize_company,
                                 normalize_person_name, repair_mojibake)


def test_detects_mojibake():
    assert looks_mojibake("JosÃ© Luis")
    assert looks_mojibake("AgropÃ©u")
    assert not looks_mojibake("Jose Luis")
    assert not looks_mojibake("")


def test_repairs_common_cp1252_damage():
    assert repair_mojibake("JosÃ©") == "José"          # Jose with acute
    assert repair_mojibake("AÃ§Ãºcar") == "Açúcar"


def test_clean_text_is_never_altered():
    """A speculative decode must not mangle text that was fine to begin with."""
    for s in ["Søren Lassen", "José", "Shell plc", "", "中国"]:
        assert repair_mojibake(s) == s


def test_input_untouched_when_no_codec_improves_it():
    """If no candidate decode reduces the damage, return the input rather than
    a worse guess."""
    irreparable = "\u00c3\u00c3"      # no codec turns this into valid UTF-8
    assert looks_mojibake(irreparable)
    assert repair_mojibake(irreparable) == irreparable


def test_lossy_damage_is_repaired_but_not_necessarily_correct():
    """Documents a real limitation. The July export mangled byte 0xB8 to a
    character that round-trips to a DIFFERENT letter, so repair yields valid
    UTF-8 that is still the wrong name. Damage of this kind is not recoverable
    from the corrupted text alone -- it needs a fresh export."""
    repaired = repair_mojibake("S\u00c3\u017eren")
    assert not looks_mojibake(repaired)
    assert repaired == "S\u00deren"        # 'SThorn-en', not the correct 'Soren'


def test_repair_feeds_clean_join_keys():
    """Company normalisation must produce the same key for damaged and clean
    spellings, or a corrupted export silently splits one company into two."""
    assert normalize_company(repair_mojibake("AgropÃ©u S/A")) == \
           normalize_company("Agropéu S/A")
    assert normalize_person_name(repair_mojibake("JosÃ© Luis")) == "jose luis"
