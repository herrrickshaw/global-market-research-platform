#!/usr/bin/env python3
"""
test_validation_registry.py — proves validation_registry.REGISTRY is
genuinely MECE over filter_watchlists.FILTERS, not just asserted to be.

Collectively Exhaustive: every (filter, market) pair that actually exists in
FILTERS has exactly one registry entry — nothing silently falls through.
Mutually Exclusive: every entry has exactly one status from ALL_STATUSES —
no pair is double-counted or ambiguous.

This is the mechanical check behind the "always be MECE" instruction
(https://powerful-problem-solving.com/be-more-mece) — a claim of MECE-ness
that isn't verified against the real, current set of filters is exactly the
kind of thing that silently rots as filter_watchlists.FILTERS grows.

Run: python3 test_validation_registry.py
"""
import filter_watchlists as FW
import validation_registry as VR


def test_collectively_exhaustive_every_filters_pair_is_registered():
    real_pairs = {(f, m) for f, cfg in FW.FILTERS.items() for m in cfg["markets"]}
    registered_pairs = set(VR.REGISTRY.keys())
    missing = real_pairs - registered_pairs
    assert not missing, (
        f"{len(missing)} (filter, market) pair(s) exist in FILTERS but have "
        f"NO validation_registry entry — not collectively exhaustive: {missing}")
    print("  test_collectively_exhaustive_every_filters_pair_is_registered: PASS")


def test_no_stale_registry_entries_for_removed_filters():
    # the mirror check: a registry entry for a pair that NO LONGER exists in
    # FILTERS is stale, not wrong per se, but worth surfacing rather than
    # silently accumulating dead entries as the filter set evolves.
    real_pairs = {(f, m) for f, cfg in FW.FILTERS.items() for m in cfg["markets"]}
    registered_pairs = set(VR.REGISTRY.keys())
    stale = registered_pairs - real_pairs
    assert not stale, f"{len(stale)} registry entries reference (filter, market) " \
                      f"pairs no longer in FILTERS — stale, should be removed: {stale}"
    print("  test_no_stale_registry_entries_for_removed_filters: PASS")


def test_mutually_exclusive_every_entry_has_exactly_one_valid_status():
    for key, v in VR.REGISTRY.items():
        assert v.status in VR.ALL_STATUSES, \
            f"{key}: status {v.status!r} is not one of {VR.ALL_STATUSES}"
        assert isinstance(v.evidence, str) and len(v.evidence) > 10, \
            f"{key}: evidence must be a real, non-trivial string, not a placeholder"
    print("  test_mutually_exclusive_every_entry_has_exactly_one_valid_status: PASS")


def test_status_of_raises_on_unregistered_pair_rather_than_guessing():
    try:
        VR.status_of("darvas", "NOWHERE")
        assert False, "must raise KeyError for an unregistered pair, not return a default"
    except KeyError:
        pass
    print("  test_status_of_raises_on_unregistered_pair_rather_than_guessing: PASS")


def test_darvas_in_is_the_one_validated_edge():
    # the specific, concrete claim this whole registry exists to make
    # checkable rather than asserted in prose.
    v = VR.status_of("darvas", "IN")
    assert v.status == VR.VALIDATED_EDGE
    assert "1.41" in v.evidence, "the real backtested number must be in the evidence string"
    validated = [k for k, v in VR.REGISTRY.items() if v.status == VR.VALIDATED_EDGE]
    assert validated == [("darvas", "IN")], \
        f"expected darvas/IN to be the ONLY VALIDATED_EDGE entry, got {validated}"
    print("  test_darvas_in_is_the_one_validated_edge: PASS")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} tests passed")
