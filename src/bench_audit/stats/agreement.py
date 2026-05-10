"""Inter-annotator agreement statistics.

Used by the reward-hacking probe's κ-validation gate. The rubric in
docs/probes/p5_reward_hacking.md pre-registers Cohen's κ ≥ 0.7 against
three human annotators on the 50-trajectory hand-labelled set.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from itertools import combinations

import numpy as np


def cohens_kappa(rater_a: Sequence[str], rater_b: Sequence[str]) -> float:
    """Cohen's κ for two raters with categorical labels.

    Returns κ ∈ [-1, 1]. Conventional bands (Landis & Koch 1977):
      < 0     no agreement
      0–0.20  slight
      0.21–0.40 fair
      0.41–0.60 moderate
      0.61–0.80 substantial   ← our gate is the lower edge of this band
      0.81–1.0  almost perfect
    """
    if len(rater_a) != len(rater_b):
        raise ValueError(
            f"rater_a and rater_b must have equal length; got {len(rater_a)} vs {len(rater_b)}"
        )
    n = len(rater_a)
    if n == 0:
        return float("nan")
    a = list(rater_a)
    b = list(rater_b)
    n_agree = sum(1 for x, y in zip(a, b, strict=True) if x == y)
    po = n_agree / n
    categories = set(a) | set(b)
    ca = Counter(a)
    cb = Counter(b)
    pe = sum((ca.get(c, 0) / n) * (cb.get(c, 0) / n) for c in categories)
    if pe >= 1.0:
        return 1.0 if po >= 1.0 else 0.0
    return float((po - pe) / (1 - pe))


def fleiss_kappa(rater_matrix: Sequence[Sequence[str]]) -> float:
    """Fleiss' κ for multiple raters with categorical labels.

    `rater_matrix` is a list of rater-label sequences, one per rater. All rater
    sequences must have the same length (one entry per item). For exactly two
    raters Fleiss reduces to Cohen's κ; the documented use case is ≥3 raters
    (the P5 validation gate). Two raters is accepted and consistent.
    """
    n_raters = len(rater_matrix)
    if n_raters < 2:
        raise ValueError("Fleiss κ requires at least 2 raters")
    n_items = len(rater_matrix[0])
    if any(len(r) != n_items for r in rater_matrix):
        raise ValueError("All rater sequences must have the same length")
    categories = sorted({label for r in rater_matrix for label in r})
    k = len(categories)
    cat_idx = {c: i for i, c in enumerate(categories)}
    counts = np.zeros((n_items, k), dtype=int)
    for r in rater_matrix:
        for item_i, label in enumerate(r):
            counts[item_i, cat_idx[label]] += 1
    # Sanity: each row must sum to n_raters
    if not np.all(counts.sum(axis=1) == n_raters):
        raise AssertionError("internal: counts row-sums != n_raters")
    # P_i: per-item proportion of agreeing rater-pairs
    p_i = (counts * (counts - 1)).sum(axis=1) / (n_raters * (n_raters - 1))
    p_bar = float(p_i.mean())
    # P_e: chance agreement
    p_j = counts.sum(axis=0) / (n_items * n_raters)
    pe = float((p_j**2).sum())
    if pe >= 1.0:
        return 1.0 if p_bar >= 1.0 else 0.0
    return (p_bar - pe) / (1 - pe)


def pairwise_kappa(rater_matrix: Sequence[Sequence[str]]) -> dict[tuple[int, int], float]:
    """Pairwise Cohen's κ between every pair of raters. Useful for spot-checks
    when Fleiss' κ is borderline — which pair disagrees?"""
    out: dict[tuple[int, int], float] = {}
    for i, j in combinations(range(len(rater_matrix)), 2):
        out[(i, j)] = cohens_kappa(rater_matrix[i], rater_matrix[j])
    return out
