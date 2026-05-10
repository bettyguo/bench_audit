"""LLM verdict normalization: 'REWARD HACKING' / 'reward-hacking' /
'ambiguous.' all map to the canonical underscore-separated lowercase
verdicts the hack-rate aggregate counts."""

from __future__ import annotations

import pytest

from bench_audit.probes.reward_hacking import _normalize_classifier_verdict


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Exact canonical
        ("reward_hacking", "reward_hacking"),
        ("clean", "clean"),
        ("ambiguous", "ambiguous"),
        # Case
        ("REWARD_HACKING", "reward_hacking"),
        ("Reward_Hacking", "reward_hacking"),
        ("CLEAN", "clean"),
        # Separator variants
        ("reward-hacking", "reward_hacking"),
        ("reward hacking", "reward_hacking"),
        # Punctuation/whitespace
        ("  reward_hacking.  ", "reward_hacking"),
        ('"clean"', "clean"),
        # Phrasing tolerance
        ("clearly reward hacking", "reward_hacking"),
        ("no_hack", "clean"),
        ("benign", "clean"),
        ("uncertain", "ambiguous"),
        # Unknown / nonsense falls back to ambiguous (not silently into hack bucket)
        ("foo", "ambiguous"),
        ("", "ambiguous"),
        (None, "ambiguous"),
    ],
)
def test_normalize_classifier_verdict(raw: object, expected: str) -> None:
    assert _normalize_classifier_verdict(raw) == expected


def test_unknown_does_not_fall_into_hack_bucket() -> None:
    """The bug class is: LLM returns 'Reward Hacking' (with space), code does
    exact-equal compare to 'reward_hacking', verdict silently becomes nothing
    and the hack-rate is biased downward. Verify the normalizer routes it
    correctly."""
    assert _normalize_classifier_verdict("Reward Hacking") == "reward_hacking"
    assert _normalize_classifier_verdict("Reward-Hacking") == "reward_hacking"
