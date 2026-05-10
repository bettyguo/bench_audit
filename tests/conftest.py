"""Shared pytest fixtures, including a synthetic adapter used by unit tests."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import pytest

from bench_audit.adapters.base import Adapter
from bench_audit.schemas import BenchmarkManifest, Prediction, Task


class SyntheticAdapter(Adapter):
    """In-memory adapter for tests. No I/O, no network."""

    name = "synthetic"
    version = "0.1.0"
    benchmark_version = "synthetic-v1"

    def __init__(self, n_tasks: int = 5) -> None:
        self._tasks = [
            Task(
                task_id=f"t{i:03d}",
                benchmark_name=self.name,
                benchmark_version=self.benchmark_version,
                payload={"prompt": f"task {i}", "gold": f"answer-{i}"},
            )
            for i in range(n_tasks)
        ]

    def load_eval_set(self, cache_dir: Path) -> Iterable[Task]:
        return self._tasks

    def task_iter(self) -> Iterator[Task]:
        return iter(self._tasks)

    def score(self, task: Task, prediction: Prediction) -> float:
        gold = task.payload.get("gold")
        pred: Any = prediction.output
        if isinstance(pred, dict):
            pred = pred.get("answer")
        return 1.0 if pred == gold else 0.0

    def manifest(self) -> BenchmarkManifest:
        canonical = "\n".join(t.payload["prompt"] for t in self._tasks).encode("utf-8")
        return BenchmarkManifest(
            name=self.name,
            version=self.benchmark_version,
            source_url="https://example.invalid/synthetic",
            license="CC0-1.0",
            n_tasks=len(self._tasks),
            eval_set_sha256=hashlib.sha256(canonical).hexdigest(),
        )


@pytest.fixture
def synthetic_adapter() -> SyntheticAdapter:
    return SyntheticAdapter()


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cache"
    d.mkdir()
    return d
