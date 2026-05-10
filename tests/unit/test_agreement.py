"""Cohen's & Fleiss' κ — agreement statistics used by P5's validation gate."""

from __future__ import annotations

import math

import pytest

from bench_audit.stats.agreement import cohens_kappa, fleiss_kappa, pairwise_kappa


def test_cohens_kappa_perfect_agreement() -> None:
    a = ["clean", "reward_hacking", "ambiguous", "clean"]
    b = list(a)
    assert math.isclose(cohens_kappa(a, b), 1.0, abs_tol=1e-9)


def test_cohens_kappa_chance_agreement_is_zero() -> None:
    # 50% agreement on a balanced binary distribution = κ ≈ 0
    a = ["X"] * 50 + ["Y"] * 50
    b = ["X"] * 25 + ["Y"] * 25 + ["X"] * 25 + ["Y"] * 25
    k = cohens_kappa(a, b)
    assert -0.05 < k < 0.05


def test_cohens_kappa_complete_disagreement() -> None:
    a = ["X"] * 50 + ["Y"] * 50
    b = ["Y"] * 50 + ["X"] * 50
    k = cohens_kappa(a, b)
    assert k < -0.5  # strong negative


def test_cohens_kappa_substantial() -> None:
    # 80% agreement on balanced binary -> κ in substantial band
    a = ["X"] * 50 + ["Y"] * 50
    b = ["X"] * 40 + ["Y"] * 10 + ["X"] * 10 + ["Y"] * 40
    k = cohens_kappa(a, b)
    assert 0.55 < k < 0.65


def test_cohens_kappa_length_mismatch() -> None:
    with pytest.raises(ValueError):
        cohens_kappa(["X"], ["X", "Y"])


def test_cohens_kappa_empty() -> None:
    assert math.isnan(cohens_kappa([], []))


def test_fleiss_kappa_perfect_agreement() -> None:
    raters = [
        ["clean", "reward_hacking", "ambiguous"],
        ["clean", "reward_hacking", "ambiguous"],
        ["clean", "reward_hacking", "ambiguous"],
    ]
    assert math.isclose(fleiss_kappa(raters), 1.0, abs_tol=1e-9)


def test_fleiss_kappa_validates_raters() -> None:
    with pytest.raises(ValueError):
        fleiss_kappa([["a", "b"]])  # only 1 rater


def test_fleiss_kappa_validates_length_match() -> None:
    with pytest.raises(ValueError):
        fleiss_kappa([["a"], ["a", "b"]])


def test_pairwise_kappa_three_raters() -> None:
    raters = [
        ["a", "b", "a", "b"],
        ["a", "b", "a", "a"],  # 1 disagreement with rater 0
        ["b", "b", "a", "b"],  # 1 disagreement with rater 0
    ]
    pairs = pairwise_kappa(raters)
    assert set(pairs.keys()) == {(0, 1), (0, 2), (1, 2)}
    for k in pairs.values():
        assert -1.0 <= k <= 1.0


def test_substantial_agreement_band_threshold() -> None:
    """The P5 gate is Cohen's κ ≥ 0.7. Sanity-check on a known-good labelling."""
    # 90% agreement on 3 categories
    a = ["A"] * 30 + ["B"] * 30 + ["C"] * 30
    b = ["A"] * 27 + ["B"] * 3 + ["B"] * 27 + ["A"] * 3 + ["C"] * 27 + ["B"] * 3
    k = cohens_kappa(a, b)
    assert k >= 0.7
