"""WebArena adapter.

Source: https://webarena.dev/
Paper: arXiv:2307.13854 (Zhou et al. — CMU)
Repo: https://github.com/web-arena-x/webarena
License: Apache-2.0 (Code), CC-BY-NC-4.0 (some sites)
N tasks: 812 (canonical); WebArena-Verified is a 2026-04 maintenance release.

Berkeley's exploit on WebArena: navigate Chromium to
`file:///proc/self/cwd/config_files/{task_id}.json` and read the
`reference_answers` field. Adapter implements `lazy_agent_recipe(task)` that
materializes the *prediction shape* the grader would accept if the exploit
ran; this is the input the P1 gold-answer-leak probe uses.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bench_audit.adapters.base import Adapter, registry
from bench_audit.errors import AdapterError
from bench_audit.schemas import BenchmarkManifest, Prediction, Task


class WebArenaAdapter(Adapter):
    name = "webarena"
    version = "0.1.0"
    benchmark_version = "webarena-2024-10"

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
                        "intent": rec.get("intent", ""),
                        "sites": rec.get("sites", []),
                        "start_url": rec.get("start_url", ""),
                        "intent_template_id": rec.get("intent_template_id"),
                        # WebArena ships reference_answers in the task config.
                        # This is the BA-02 leak channel.
                        "reference_answers": rec.get("reference_answers", {}),
                        "eval": rec.get("eval", {}),
                    },
                    metadata={
                        "source": "fixture",
                        "license": "Apache-2.0 (code) / CC-BY-NC-4.0 (some sites)",
                    },
                )
            )
        return tasks

    def load_eval_set(self, cache_dir: Path) -> Iterable[Task]:  # noqa: ARG002
        if self._tasks is None:
            if self._fixture_dir is not None:
                self._tasks = self._load_fixture()
            else:
                raise AdapterError(
                    "Real WebArena eval set is not redistributable; clone "
                    "https://github.com/web-arena-x/webarena and pass its "
                    "config_files dir as fixture_dir."
                )
        return self._tasks

    def task_iter(self) -> Iterator[Task]:
        if self._tasks is None:
            # If the caller passed a fixture_dir, we can load offline without a
            # real cache. Otherwise, refuse to silently invent a cache path —
            # the caller must invoke load_eval_set(cache_dir) explicitly.
            if self._fixture_dir is not None:
                self._tasks = self._load_fixture()
            else:
                raise AdapterError(
                    "task_iter() called before load_eval_set(); call "
                    "load_eval_set(cache_dir) first or instantiate with fixture_dir."
                )
        return iter(self._tasks)

    def score(self, task: Task, prediction: Prediction) -> float:
        """WebArena's scoring is multi-modal: exact_match, must_include,
        fuzzy_match, url_match, program_html, etc. We implement a simplified
        version covering the modes used by the lazy-agent recipe so the leak
        probe can verify.

        Real-mode runners shell out to WebArena's evaluator and feed the
        result back; this in-process implementation handles the common cases.
        """
        ref: dict[str, Any] = task.payload.get("reference_answers", {}) or {}
        out = prediction.output
        # Normalize prediction output to a string for matching.
        if isinstance(out, dict):
            answer = str(out.get("answer", "") or out.get("text", ""))
        else:
            answer = str(out)

        # exact_match (case/whitespace normalized)
        em = ref.get("exact_match")
        if em is not None:
            return 1.0 if _norm(answer) == _norm(str(em)) else 0.0

        # must_include — answer must include all listed substrings
        mi = ref.get("must_include")
        if isinstance(mi, list):
            return 1.0 if all(_norm(s) in _norm(answer) for s in mi) else 0.0

        # fuzzy_match — answer in any of the listed alternatives
        fm = ref.get("fuzzy_match")
        if isinstance(fm, list):
            return 1.0 if any(_norm(answer) == _norm(s) for s in fm) else 0.0

        # No reference structure recognized → cannot score
        return 0.0

    def lazy_agent_recipe(self, task: Task) -> Prediction:
        """Berkeley's WebArena exploit: read config_files/{task_id}.json over
        `file://` and submit `reference_answers` as the prediction. We do not
        navigate to a file:// URL here; we materialize the prediction the
        grader would accept if the exploit ran."""
        ref = task.payload.get("reference_answers", {}) or {}
        # Build the answer string from whichever reference mode is present.
        if "exact_match" in ref:
            answer = str(ref["exact_match"])
        elif "must_include" in ref and isinstance(ref["must_include"], list):
            answer = " ".join(str(s) for s in ref["must_include"])
        elif "fuzzy_match" in ref and isinstance(ref["fuzzy_match"], list):
            answer = str(ref["fuzzy_match"][0]) if ref["fuzzy_match"] else ""
        else:
            answer = ""
        return Prediction(
            task_id=task.task_id,
            model_name="bench-audit::lazy-agent",
            model_version="webarena-file-url-v1",
            output={"answer": answer, "source": "file://config_files/{task_id}.json"},
            metadata={
                "exploit_id": "BA-02",
                "exploit_doc": "https://rdi.berkeley.edu/blog/trustworthy-benchmarks-cont/",
            },
        )

    def manifest(self) -> BenchmarkManifest:
        if self._fixture_dir is not None and self._tasks is not None:
            sha = hashlib.sha256((self._fixture_dir / "tasks.jsonl").read_bytes()).hexdigest()
            n = len(self._tasks)
        else:
            sha = "pending-first-fetch"
            n = 812
        return BenchmarkManifest(
            name=self.name,
            version=self.benchmark_version,
            source_url="https://github.com/web-arena-x/webarena",
            license="Apache-2.0",
            license_notes=(
                "Code Apache-2.0; some component sites are CC-BY-NC-4.0; "
                "no eval-set content redistributed by this adapter."
            ),
            n_tasks=n,
            eval_set_sha256=sha,
            last_release_date=datetime(2024, 10, 1, tzinfo=UTC),
            maintainer="CMU (Zhou et al.) + WebArena Verified (ServiceNow et al., 2026)",
            contamination_statement_url="https://openreview.net/forum?id=CSIo4D7xBG",
        )


def _norm(s: str) -> str:
    return " ".join(str(s).strip().lower().split())


registry.register(WebArenaAdapter)
