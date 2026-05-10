"""Confidence intervals and effect sizes.

All proportion CIs default to Wilson (Wilson 1927); the normal-approximation
interval is intentionally not provided because it degenerates near 0 and 1
— exactly where contamination claims live.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
from scipy import stats


def wilson_ci(successes: int, n: int, level: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a proportion.

    Returns `(low, high)` clipped to [0, 1]. Defined for n=0 as (0.0, 1.0) so
    callers can construct ProbeResults with verdict='inconclusive' on empty
    samples.
    """
    if n == 0:
        return (0.0, 1.0)
    if not 0 <= successes <= n:
        raise ValueError(f"successes ({successes}) not in [0, {n}]")
    if not 0 < level < 1:
        raise ValueError(f"level must be in (0,1); got {level}")
    z = float(stats.norm.ppf(1 - (1 - level) / 2))
    p = successes / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    low = (centre - half) / denom
    high = (centre + half) / denom
    return (float(max(0.0, low)), float(min(1.0, high)))


def clopper_pearson_ci(successes: int, n: int, level: float = 0.95) -> tuple[float, float]:
    """Exact Clopper-Pearson interval. Conservative; useful for small n."""
    if n == 0:
        return (0.0, 1.0)
    if not 0 <= successes <= n:
        raise ValueError(f"successes ({successes}) not in [0, {n}]")
    alpha = 1 - level
    low = 0.0 if successes == 0 else stats.beta.ppf(alpha / 2, successes, n - successes + 1)
    high = 1.0 if successes == n else stats.beta.ppf(1 - alpha / 2, successes + 1, n - successes)
    return (float(low), float(high))


def bootstrap_ci(
    data: Sequence[float],
    statistic: Callable[[np.ndarray[Any, Any]], float],
    *,
    n_resamples: int = 10_000,
    level: float = 0.95,
    seed: int | None = 0,
) -> tuple[float, float]:
    """Bootstrap percentile CI for an arbitrary statistic.

    Use this for non-proportion quantities (mean trajectory length, MI
    estimates, etc.). For proportions, prefer `wilson_ci`.
    """
    if len(data) == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    arr = np.asarray(data, dtype=float)
    n = arr.shape[0]
    idx = rng.integers(0, n, size=(n_resamples, n))
    samples = np.array([statistic(arr[i]) for i in idx])
    alpha = 1 - level
    low = float(np.quantile(samples, alpha / 2))
    high = float(np.quantile(samples, 1 - alpha / 2))
    return (low, high)


def cohens_h(p1: float, p2: float) -> float:
    """Cohen's h for two proportions: difference in arcsine-transformed scale.

    Convention from Cohen (1988): h=0.2 small, 0.5 medium, 0.8 large.
    """
    for p in (p1, p2):
        if not 0.0 <= p <= 1.0:
            raise ValueError(f"proportion out of range: {p}")
    return float(2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p2)))


def min_n_for_wilson_half_width(
    target_half_width: float,
    *,
    p_guess: float = 0.5,
    level: float = 0.95,
) -> int:
    """Compute the minimum n such that the Wilson interval at `p_guess` has
    half-width <= `target_half_width`.

    This is a power-analysis helper. Use it before running an expensive probe
    to decide whether your planned sample size will support a verdict.
    """
    if not 0 < target_half_width < 1:
        raise ValueError(f"target_half_width must be in (0,1); got {target_half_width}")
    if not 0 <= p_guess <= 1:
        raise ValueError(f"p_guess must be in [0,1]; got {p_guess}")
    n = 10
    while n < 10_000_000:
        low, high = wilson_ci(round(p_guess * n), n, level=level)
        if (high - low) / 2 <= target_half_width:
            return n
        n = math.ceil(n * 1.25)
    raise ValueError(
        f"min_n exceeds 10M for target_half_width={target_half_width}; "
        "either widen the target or use a different probe design."
    )
