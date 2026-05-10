"""GAIA adapter integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from bench_audit.adapters.gaia import GAIAAdapter, _gaia_normalize
from bench_audit.probes.gold_answer_leak import GoldAnswerLeakProbe
from bench_audit.schemas import Prediction

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "gaia" / "mini"


@pytest.fixture
def adapter() -> GAIAAdapter:
    a = GAIAAdapter(fixture_dir=FIXTURE)
    a.load_eval_set(Path("/tmp"))
    return a


def test_loads_5_tasks(adapter: GAIAAdapter) -> None:
    tasks = list(adapter.task_iter())
    assert len(tasks) == 5


def test_score_exact_match(adapter: GAIAAdapter) -> None:
    task = next(t for t in adapter.task_iter() if t.task_id == "gaia-001")
    good = Prediction(task_id=task.task_id, model_name="m", model_version="v", output="1969")
    bad = Prediction(task_id=task.task_id, model_name="m", model_version="v", output="1970")
    assert adapter.score(task, good) == 1.0
    assert adapter.score(task, bad) == 0.0


def test_normalization_strips_punct_and_whitespace() -> None:
    """The GAIA scorer (per Berkeley) strips ALL whitespace + punctuation,
    causing collisions. We reproduce that surface."""
    assert _gaia_normalize("1969.") == _gaia_normalize("1969")
    assert _gaia_normalize("Hello, World!") == _gaia_normalize("helloworld")
    # The collision pattern Berkeley flagged:
    assert _gaia_normalize("12") == _gaia_normalize("1, 2")
    assert _gaia_normalize("Go") == _gaia_normalize(" gO! ")


def test_lazy_agent_recipe_wins_all_tasks(adapter: GAIAAdapter) -> None:
    n_pass = 0
    for t in adapter.task_iter():
        pred = adapter.lazy_agent_recipe(t)
        if adapter.score(t, pred) == 1.0:
            n_pass += 1
    assert n_pass == 5


def test_gold_answer_leak_probe_on_gaia(adapter: GAIAAdapter) -> None:
    probe = GoldAnswerLeakProbe()
    r = probe.run(adapter)
    assert r.effect_size == 1.0
    assert r.verdict == "fail"


def test_manifest_marks_gaia_as_gated(adapter: GAIAAdapter) -> None:
    m = adapter.manifest()
    assert m.requires_auth is True
