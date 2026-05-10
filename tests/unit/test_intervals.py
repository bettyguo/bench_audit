"""Tests for stats/intervals.py."""

from __future__ import annotations

import math

import pytest

from bench_audit.stats.intervals import (
    bootstrap_ci,
    clopper_pearson_ci,
    cohens_h,
    min_n_for_wilson_half_width,
    wilson_ci,
)


def test_wilson_empty_returns_full_range() -> None:
    assert wilson_ci(0, 0) == (0.0, 1.0)


def test_wilson_clipped_to_unit_interval() -> None:
    low, high = wilson_ci(0, 5)
    assert low == 0.0
    assert 0.0 < high < 1.0
    low, high = wilson_ci(5, 5)
    assert 0.0 < low < 1.0
    assert high == 1.0


def test_wilson_centered_around_p() -> None:
    low, high = wilson_ci(50, 100)
    assert low < 0.5 < high
    half = (high - low) / 2
    # Wilson 95% half-width at p=0.5, n=100 is ~ 0.097
    assert 0.08 < half < 0.12


def test_wilson_narrows_with_n() -> None:
    _, h1 = wilson_ci(50, 100)
    _, h2 = wilson_ci(500, 1000)
    assert h2 < h1


def test_wilson_validates_inputs() -> None:
    with pytest.raises(ValueError):
        wilson_ci(10, 5)
    with pytest.raises(ValueError):
        wilson_ci(1, 10, level=1.5)


def test_clopper_pearson_basic() -> None:
    low, high = clopper_pearson_ci(50, 100)
    assert 0.0 < low < 0.5 < high < 1.0


def test_clopper_pearson_extremes() -> None:
    assert clopper_pearson_ci(0, 10)[0] == 0.0
    assert clopper_pearson_ci(10, 10)[1] == 1.0


def test_bootstrap_ci_basic() -> None:

    data = list(range(100))
    low, high = bootstrap_ci(data, statistic=lambda a: float(a.mean()), n_resamples=2000)
    assert low < high
    assert 40 < (low + high) / 2 < 60


def test_cohens_h_zero_for_equal_proportions() -> None:
    assert math.isclose(cohens_h(0.5, 0.5), 0.0, abs_tol=1e-9)


def test_cohens_h_sign() -> None:
    assert cohens_h(0.8, 0.2) > 0
    assert cohens_h(0.2, 0.8) < 0


def test_cohens_h_validates() -> None:
    with pytest.raises(ValueError):
        cohens_h(1.5, 0.2)


def test_min_n_decreases_target_increases_n() -> None:
    n_tight = min_n_for_wilson_half_width(0.05)
    n_loose = min_n_for_wilson_half_width(0.15)
    assert n_tight > n_loose


def test_min_n_validates() -> None:
    with pytest.raises(ValueError):
        min_n_for_wilson_half_width(0.0)
    with pytest.raises(ValueError):
        min_n_for_wilson_half_width(1.0)
