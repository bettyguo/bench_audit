"""SWE-bench Verified adapter — integration tests against the mini fixture."""

from __future__ import annotations

from pathlib import Path

import pytest

from bench_audit.adapters.swebench_verified import SWEBenchVerifiedAdapter
from bench_audit.schemas import BenchmarkManifest, Prediction, Task

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "swebench_verified" / "mini"


@pytest.fixture
def adapter() -> SWEBenchVerifiedAdapter:
    a = SWEBenchVerifiedAdapter(fixture_dir=FIXTURE)
    a.load_eval_set(cache_dir=Path("/tmp"))
    return a


def test_adapter_metadata(adapter: SWEBenchVerifiedAdapter) -> None:
    assert adapter.name == "swebench_verified"
    assert adapter.version.startswith("0.")
    assert adapter.benchmark_version.startswith("swebench-verified-")


def test_task_iter_yields_5(adapter: SWEBenchVerifiedAdapter) -> None:
    tasks = list(adapter.task_iter())
    assert len(tasks) == 5
    for t in tasks:
        assert isinstance(t, Task)
        assert t.benchmark_name == "swebench_verified"
        assert "problem_statement" in t.payload


def test_task_iter_is_stable(adapter: SWEBenchVerifiedAdapter) -> None:
    ids_a = [t.task_id for t in adapter.task_iter()]
    ids_b = [t.task_id for t in adapter.task_iter()]
    assert ids_a == ids_b


def test_manifest_has_hash(adapter: SWEBenchVerifiedAdapter) -> None:
    m: BenchmarkManifest = adapter.manifest()
    assert m.n_tasks == 5
    assert len(m.eval_set_sha256) == 64  # sha256 hex
    assert m.license == "MIT"
    assert "swebench" in m.source_url.lower() or "SWE" in m.source_url


def test_score_pass_on_resolved(adapter: SWEBenchVerifiedAdapter) -> None:
    task = next(adapter.task_iter())
    p = Prediction(
        task_id=task.task_id,
        model_name="m",
        model_version="v1",
        output={"report": {"resolved": True}},
    )
    assert adapter.score(task, p) == 1.0


def test_score_fail_on_unresolved(adapter: SWEBenchVerifiedAdapter) -> None:
    task = next(adapter.task_iter())
    p = Prediction(
        task_id=task.task_id,
        model_name="m",
        model_version="v1",
        output={"report": {"resolved": False}},
    )
    assert adapter.score(task, p) == 0.0


def test_lazy_agent_recipe_is_exploit_shaped(adapter: SWEBenchVerifiedAdapter) -> None:
    task = next(adapter.task_iter())
    pred = adapter.lazy_agent_recipe(task)
    assert pred.task_id == task.task_id
    out = pred.output
    assert isinstance(out, dict)
    report = out.get("report")
    assert isinstance(report, dict)
    assert report["resolved"] is True
    assert "conftest" in report["exploit"].lower()
