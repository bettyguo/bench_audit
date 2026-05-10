"""P2 — near-duplicate-pretraining probe unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from bench_audit.adapters.gaia import GAIAAdapter
from bench_audit.probes.near_dup_pretraining import (
    NearDupPretrainingProbe,
    _ngrams,
    _normalize_tokens,
)

FIXTURE_GAIA = Path(__file__).resolve().parents[2] / "fixtures" / "gaia" / "mini"


@pytest.fixture
def gaia() -> GAIAAdapter:
    a = GAIAAdapter(fixture_dir=FIXTURE_GAIA)
    a.load_eval_set(Path("/tmp"))
    return a


def test_normalize_tokens() -> None:
    assert _normalize_tokens("Hello, World!") == ["hello", "world"]
    assert _normalize_tokens("A b c, d") == ["a", "b", "c", "d"]


def test_ngrams_basic() -> None:
    toks = ["a", "b", "c", "d", "e"]
    assert list(_ngrams(toks, 3)) == ["a b c", "b c d", "c d e"]
    assert list(_ngrams(toks, 5)) == ["a b c d e"]
    assert list(_ngrams(toks, 6)) == []


def test_probe_inconclusive_without_corpus(gaia: GAIAAdapter) -> None:
    probe = NearDupPretrainingProbe(n=5)
    r = probe.run(gaia)
    assert r.verdict == "inconclusive"


def test_probe_fail_when_eval_set_in_corpus(gaia: GAIAAdapter) -> None:
    # Build the corpus index from the fixture's task texts so every task overlaps.
    corpus: set[str] = set()
    for task in gaia.task_iter():
        toks = _normalize_tokens(task.payload["Question"])
        # Use n=5 for the fixture (questions are short)
        corpus.update(_ngrams(toks, 5))
    probe = NearDupPretrainingProbe(n=5, corpus_index=corpus)
    r = probe.run(gaia)
    assert r.sample_size == 5
    # All tasks should overlap with themselves
    assert r.effect_size == 1.0
    assert r.verdict == "fail"


def test_probe_pass_when_eval_set_not_in_corpus(gaia: GAIAAdapter) -> None:
    corpus = {"some random text that is unrelated to gaia tasks"}
    probe = NearDupPretrainingProbe(n=5, corpus_index=corpus)
    r = probe.run(gaia)
    # Wilson 95% CI at 0/5 has low=0, so verdict='pass'
    assert r.effect_size == 0.0
    assert r.verdict == "pass"
