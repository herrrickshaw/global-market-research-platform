#!/usr/bin/env python3
"""
test_eval_contract.py — proves the evaluation gate cannot move silently.

The contract is only worth something if a changed threshold actually breaks
something loud. These tests are that loudness: they fail when a number moves
without CONTRACT_HASH and the CHANGELOG moving with it.

Run: pytest test_eval_contract.py -q
"""
from __future__ import annotations

import copy

import pytest

import eval_contract as EC


def test_recorded_hash_matches_the_rules():
    """The headline guarantee: hash on disk == hash of the live values."""
    assert EC.contract_digest() == EC.CONTRACT_HASH
    EC.verify()          # must not raise


def test_moving_a_threshold_is_detected(monkeypatch):
    """Nudge a gate the way an over-eager tune would, and verify() must object."""
    tampered = copy.deepcopy(EC.CONTRACT)
    tampered["min_nonoverlap_obs"] = EC.Rule(
        12, "loosened so a thin sample would pass", "none — this is the bad case")
    monkeypatch.setattr(EC, "CONTRACT", tampered)

    with pytest.raises(EC.ContractViolation):
        EC.verify()


def test_every_rule_carries_its_reasoning():
    """A threshold with no recorded evidence is indistinguishable from one that
    was tuned until the answer was nice."""
    for name, rule in EC.CONTRACT.items():
        assert rule.rationale.strip(), f"{name} has no rationale"
        assert rule.evidence.strip(), f"{name} has no evidence"
        assert len(rule.evidence) > 20, f"{name} evidence is too thin to check"


def test_rules_are_frozen_objects():
    """Rule is frozen, so a rule cannot be mutated in place to dodge the hash."""
    rule = next(iter(EC.CONTRACT.values()))
    with pytest.raises(Exception):
        rule.value = 999


def test_changelog_is_ordered_and_dated():
    dates = [e["date"] for e in EC.CHANGELOG]
    assert dates == sorted(dates), "CHANGELOG must be oldest-first"
    for e in EC.CHANGELOG:
        assert e["why"].strip(), f"{e['date']} entry has no reason"


def test_consumers_read_the_contract_not_their_own_copy():
    """data_sufficiency.py used to hold the only machine-readable copy of the
    sufficiency gate. If it ever re-declares its own, this fails."""
    import data_sufficiency as DS
    assert DS.MIN_NONOVERLAP is EC.MIN_NONOVERLAP_OBS
    assert DS.MIN_UNIVERSE_COV == EC.MIN_LIQUID_COVERAGE


def test_the_published_thresholds_are_what_methodology_documents():
    """Guards against the contract itself drifting away from docs/METHODOLOGY.md,
    which is what a reader actually reads. Values transcribed 2026-08-27."""
    assert EC.MIN_NONOVERLAP_OBS == 15
    assert EC.MIN_LIQUID_COVERAGE == 0.60
    assert EC.MIN_ABS_T == 2.0
    assert EC.MIN_DSR == 0.95
