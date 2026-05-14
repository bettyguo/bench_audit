"""GAIA adapter.

Source: https://huggingface.co/datasets/gaia-benchmark/GAIA
Paper: arXiv:2311.12983 (Mialon et al. — Meta/HuggingFace)
License: Gated (CC-BY-4.0-like, requires HF terms acceptance)
N tasks: 165 validation (with answers) + larger test set (private answers)

Berkeley's GAIA exploits:
  (a) public HuggingFace mirrors expose answers; lazy agent fetches and submits.
  (b) GAIA's `question_scorer` strips ALL whitespace + ALL punctuation, creating
      collisions. We reproduce the scorer faithfully to expose this surface.
"""

from __future__ import annotations

import hashlib
import json
import re
import string
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path

from bench_audit.adapters.base import Adapter, registry
from bench_audit.errors import AdapterError
from bench_audit.schemas import BenchmarkManifest, Prediction, Task


class GAIAAdapter(Adapter):
    name = "gaia"
    version = "0.1.0"
    benchmark_version = "gaia-validation-2023-11"

    def __init__(self, fixture_dir: Path | None = None) -> None:
        self._fixture_dir = fixture_dir
        self._tasks: list[Task] | None = None

    def _load_fixture(self) -> list[Task]:
        assert self._fixture_dir is not None
        tasks_path = self._fixture_dir / "tasks.jsonl"
        if not tasks_path.exists():
            raise AdapterError(f"Fixture not found at {tasks_path}")
        tasks: list[Task] = []
        for line in tasks_path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            tasks.append(
                Task(
                    task_id=str(rec["task_id"]),
                    benchmark_name=self.name,
                    benchmark_version=self.benchmark_version,
                    payload={
                        "Question": rec.get("Question", ""),
                        "Level": rec.get("Level", 1),
                        "Final answer": rec.get("Final answer", ""),
                        "file_name": rec.get("file_name", ""),
                        "Annotator Metadata": rec.get("Annotator Metadata", {}),
                    },
                    metadata={"source": "fixture", "license": "Gated CC-BY-4.0-like"},
                )
            )
        return tasks

    def load_eval_set(self, cache_dir: Path) -> Iterable[Task]:  # noqa: ARG002
        if self._tasks is None:
            if self._fixture_dir is not None:
                self._tasks = self._load_fixture()
            else:
                raise AdapterError(
                    "GAIA's eval set is gated on HuggingFace. After accepting the "
                    "terms at https://huggingface.co/datasets/gaia-benchmark/GAIA, "
                    "pass the local checkout path as fixture_dir."
                )
        return self._tasks

    def task_iter(self) -> Iterator[Task]:
        if self._tasks is None:
            if self._fixture_dir is not None:
                self._tasks = self._load_fixture()
            else:
                raise AdapterError(
                    "task_iter() called before load_eval_set(); call "
                    "load_eval_set(cache_dir) first or instantiate with fixture_dir."
                )
        return iter(self._tasks)

    def score(self, task: Task, prediction: Prediction) -> float:
        """GAIA's official `question_scorer` strips whitespace + punctuation
        and lowercases before comparing. We reproduce that faithfully — the
        normalization is the BA-05 attack surface."""
        gold = task.payload.get("Final answer", "")
        out = prediction.output
        if isinstance(out, dict):
            pred = str(out.get("answer", "") or out.get("text", ""))
        else:
            pred = str(out)
        return 1.0 if _gaia_normalize(pred) == _gaia_normalize(str(gold)) else 0.0

    def lazy_agent_recipe(self, task: Task) -> Prediction:
        """Berkeley's GAIA exploit: pull the gold answer from a public HF mirror
        (or from the task payload, which conceptually models the same leak —
        the answer is somewhere the agent can reach). Submit it verbatim."""
        gold = str(task.payload.get("Final answer", ""))
        return Prediction(
            task_id=task.task_id,
            model_name="bench-audit::lazy-agent",
            model_version="gaia-hf-mirror-v1",
            output={"answer": gold, "source": "huggingface-mirror"},
            metadata={
                "exploit_id": "BA-02+BA-05",
                "exploit_doc": "https://rdi.berkeley.edu/blog/trustworthy-benchmarks-cont/",
            },
        )

    def manifest(self) -> BenchmarkManifest:
        if self._fixture_dir is not None and self._tasks is not None:
            sha = hashlib.sha256((self._fixture_dir / "tasks.jsonl").read_bytes()).hexdigest()
            n = len(self._tasks)
        else:
            sha = "pending-first-fetch"
            n = 165
        return BenchmarkManifest(
            name=self.name,
            version=self.benchmark_version,
            source_url="https://huggingface.co/datasets/gaia-benchmark/GAIA",
            license="Gated CC-BY-4.0-like",
            license_notes=(
                "GAIA's HF dataset is gated to prevent contamination. Users must "
                "accept terms before downloading; this adapter does not redistribute."
            ),
            n_tasks=n,
            eval_set_sha256=sha,
            last_release_date=datetime(2023, 11, 30, tzinfo=UTC),
            maintainer="gaia-benchmark org (Mialon et al.)",
            requires_auth=True,
        )


# GAIA's question_scorer strips whitespace and punctuation aggressively —
# this *is* the BA-05 attack surface. We reproduce it for fidelity.
_PUNCT_RE = re.compile(f"[{re.escape(string.punctuation)}]")


def _gaia_normalize(s: str) -> str:
    s = s.strip().lower()
    s = _PUNCT_RE.sub("", s)
    return re.sub(r"\s+", "", s)


registry.register(GAIAAdapter)
