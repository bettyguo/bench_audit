"""WebArena adapter integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from bench_audit.adapters.webarena import WebArenaAdapter
from bench_audit.probes.gold_answer_leak import GoldAnswerLeakProbe
from bench_audit.schemas import Prediction

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "webarena" / "mini"


@pytest.fixture
def adapter() -> WebArenaAdapter:
    a = WebArenaAdapter(fixture_dir=FIXTURE)
    a.load_eval_set(Path("/tmp"))
    return a


def test_loads_5_tasks(adapter: WebArenaAdapter) -> None:
    tasks = list(adapter.task_iter())
    assert len(tasks) == 5
    assert tasks[0].payload["intent"]


def test_score_exact_match(adapter: WebArenaAdapter) -> None:
    task = next(t for t in adapter.task_iter() if t.task_id == "wa-001")
    good = Prediction(
        task_id=task.task_id, model_name="m", model_version="v", output={"answer": "42"}
    )
    bad = Prediction(
        task_id=task.task_id, model_name="m", model_version="v", output={"answer": "41"}
    )
    assert adapter.score(task, good) == 1.0
    assert adapter.score(task, bad) == 0.0


def test_score_must_include(adapter: WebArenaAdapter) -> None:
    task = next(t for t in adapter.task_iter() if t.task_id == "wa-002")
    good = Prediction(
        task_id=task.task_id,
        model_name="m",
        model_version="v",
        output={"answer": "Please contact us at info@example.com"},
    )
    bad = Prediction(
        task_id=task.task_id, model_name="m", model_version="v", output={"answer": "no email"}
    )
    assert adapter.score(task, good) == 1.0
    assert adapter.score(task, bad) == 0.0


def test_score_fuzzy_match(adapter: WebArenaAdapter) -> None:
    task = next(t for t in adapter.task_iter() if t.task_id == "wa-003")
    good = Prediction(
        task_id=task.task_id, model_name="m", model_version="v", output={"answer": "$19.99"}
    )
    bad = Prediction(
        task_id=task.task_id, model_name="m", model_version="v", output={"answer": "$29.99"}
    )
    assert adapter.score(task, good) == 1.0
    assert adapter.score(task, bad) == 0.0


def test_lazy_agent_recipe_wins_all_tasks(adapter: WebArenaAdapter) -> None:
    """The Berkeley file:// exploit, reproduced via the adapter's lazy_agent_recipe.
    On our 5-task fixture, the lazy agent should score 100%."""
    n_pass = 0
    for t in adapter.task_iter():
        pred = adapter.lazy_agent_recipe(t)
        if adapter.score(t, pred) == 1.0:
            n_pass += 1
    assert n_pass == 5


def test_gold_answer_leak_probe_reproduces_berkeley_pattern(adapter: WebArenaAdapter) -> None:
    """P1 against WebArena should report leak_rate=1.0 — the Berkeley result
    pattern. Empirically Berkeley measured ~100% on the real 812; we
    demonstrate the *probe behaviour* on the fixture."""
    probe = GoldAnswerLeakProbe()
    r = probe.run(adapter)
    assert r.effect_size == 1.0
    assert r.verdict == "fail"
    assert r.adapter_name == "webarena"
