"""P1 must surface lazy-agent-recipe failures rather than silently
report verdict=pass with a 0/N leak rate."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

import pytest

from bench_audit.adapters.base import Adapter
from bench_audit.probes.gold_answer_leak import GoldAnswerLeakProbe
from bench_audit.schemas import BenchmarkManifest, Prediction, Task


class _AlwaysErroringAdapter(Adapter):
    """Adapter whose lazy_agent_recipe raises on every task. P1 must
    report verdict=inconclusive and surface the error count in notes."""

    name = "always_erroring"
    version = "0.1.0"
    benchmark_version = "always-erroring-v1"

    def __init__(self) -> None:
        self._tasks = [
            Task(
                task_id=f"t{i}",
                benchmark_name=self.name,
                benchmark_version=self.benchmark_version,
                payload={},
            )
            for i in range(40)
        ]

    def load_eval_set(self, cache_dir: Path) -> Iterable[Task]:
        return self._tasks

    def task_iter(self) -> Iterator[Task]:
        return iter(self._tasks)

    def score(self, task: Task, prediction: Prediction) -> float:
        return 0.0

    def lazy_agent_recipe(self, task: Task) -> Prediction:
        raise RuntimeError("simulated recipe failure")

    def manifest(self) -> BenchmarkManifest:
        return BenchmarkManifest(
            name=self.name,
            version=self.benchmark_version,
            source_url="https://example.invalid",
            license="CC0-1.0",
            n_tasks=len(self._tasks),
            eval_set_sha256="a" * 64,
        )


class _PartiallyErroringAdapter(_AlwaysErroringAdapter):
    """Recipe errors on half the tasks; succeeds (and leaks) on the other half."""

    name = "partially_erroring"

    def __init__(self) -> None:
        super().__init__()

    def lazy_agent_recipe(self, task: Task) -> Prediction:
        if int(task.task_id[1:]) % 2 == 0:
            raise RuntimeError("simulated recipe failure")
        return Prediction(
            task_id=task.task_id,
            model_name="lazy",
            model_version="v1",
            output={"answer": "leaked"},
        )

    def score(self, task: Task, prediction: Prediction) -> float:
        out = prediction.output
        if isinstance(out, dict) and out.get("answer") == "leaked":
            return 1.0
        return 0.0


def test_all_recipe_failures_yields_inconclusive() -> None:
    """If every recipe call raises, the verdict is inconclusive and the
    notes carry the error count. We never silently return 'pass'."""
    adapter = _AlwaysErroringAdapter()
    result = GoldAnswerLeakProbe().run(adapter)
    assert result.verdict == "inconclusive"
    assert "RECIPE ERRORS: 40/40" in result.notes
    assert result.verdict != "pass"


def test_partial_recipe_failures_surfaces_count_but_does_not_swallow() -> None:
    """When half the tasks succeed, the leak rate is still measurable but the
    error count must be in notes so the user knows the result is partial."""
    adapter = _PartiallyErroringAdapter()
    result = GoldAnswerLeakProbe().run(adapter)
    assert result.sample_size == 40
    # 20 successful tasks, all leak; 20 errors counted as not-leak.
    assert result.effect_size == pytest.approx(20 / 40)
    assert "RECIPE ERRORS: 20/40" in result.notes
    # Still a real signal; verdict should be fail.
    assert result.verdict == "fail"
