"""SWE-bench Verified adapter.

Source: https://www.swebench.com/verified.html
Paper: arXiv:2310.06770 (Jimenez, Yang et al. — Princeton/Stanford)
HuggingFace: princeton-nlp/SWE-bench_Verified
License: MIT
N tasks: 500

Berkeley's exploit on SWE-bench was a pytest hook in conftest.py that forces
every test to report passing. We do not reimplement the exploit; we implement
two probes that detect it: P4 (harness-injection: pytest-hook pattern) and P1
(gold-answer leak: a lazy agent that wins via the hook).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path

from bench_audit.adapters.base import Adapter, registry
from bench_audit.errors import AdapterError, ManifestMismatchError
from bench_audit.schemas import BenchmarkManifest, Prediction, Task

# Cached fixture; real eval set is fetched at runtime from HuggingFace and not
# redistributed. See fixtures/swebench_verified/mini/ for the test fixture.
_MANIFEST_HASH_PINNED = (
    # SHA-256 over the canonical eval-set JSONL (princeton-nlp/SWE-bench_Verified,
    # commit at time of v0.1 release). Populated on first successful fetch +
    # verification. Until then, adapter operates in "manifest-pending" mode.
    ""
)


class SWEBenchVerifiedAdapter(Adapter):
    name = "swebench_verified"
    version = "0.1.0"
    benchmark_version = "swebench-verified-2024-08"

    def __init__(self, fixture_dir: Path | None = None) -> None:
        """If `fixture_dir` is provided, load tasks from there (unit tests).
        Otherwise, load from the configured cache (real eval set)."""
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
                    task_id=rec["instance_id"],
                    benchmark_name=self.name,
                    benchmark_version=self.benchmark_version,
                    payload={
                        "problem_statement": rec["problem_statement"],
                        "repo": rec["repo"],
                        "base_commit": rec["base_commit"],
                        "test_patch": rec.get("test_patch", ""),
                        "gold_patch": rec.get("patch", ""),
                        "FAIL_TO_PASS": rec.get("FAIL_TO_PASS", []),
                        "PASS_TO_PASS": rec.get("PASS_TO_PASS", []),
                    },
                    metadata={
                        "source": "fixture",
                        "license": "MIT",
                    },
                )
            )
        return tasks

    def _load_from_hf(self, cache_dir: Path) -> list[Task]:
        """Fetch the SWE-bench Verified dataset from HuggingFace.

        Pulls only what we need (task IDs + problem statements + test patches)
        and caches under `cache_dir/swebench_verified/`. Verifies SHA-256 of
        the cached file against `manifest().eval_set_sha256` if pinned.
        """
        target = cache_dir / self.name / f"{self.benchmark_version}.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            try:
                from datasets import load_dataset  # type: ignore[import-not-found]
            except ImportError as e:
                raise AdapterError(
                    "Loading the real SWE-bench Verified eval set requires "
                    "`pip install datasets`. For unit tests, pass fixture_dir."
                ) from e
            ds = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")
            with target.open("w", encoding="utf-8") as f:
                for rec in ds:
                    f.write(json.dumps(dict(rec)) + "\n")
        sha = hashlib.sha256(target.read_bytes()).hexdigest()
        pinned = _MANIFEST_HASH_PINNED
        if pinned and sha != pinned:
            raise ManifestMismatchError(
                f"SWE-bench Verified cache hash mismatch: got {sha}, expected {pinned}"
            )
        tasks: list[Task] = []
        for line in target.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            tasks.append(
                Task(
                    task_id=rec["instance_id"],
                    benchmark_name=self.name,
                    benchmark_version=self.benchmark_version,
                    payload={
                        "problem_statement": rec.get("problem_statement", ""),
                        "repo": rec.get("repo", ""),
                        "base_commit": rec.get("base_commit", ""),
                        "test_patch": rec.get("test_patch", ""),
                        "gold_patch": rec.get("patch", ""),
                        "FAIL_TO_PASS": rec.get("FAIL_TO_PASS", []),
                        "PASS_TO_PASS": rec.get("PASS_TO_PASS", []),
                    },
                    metadata={"source": "huggingface:princeton-nlp/SWE-bench_Verified"},
                )
            )
        return tasks

    def load_eval_set(self, cache_dir: Path) -> Iterable[Task]:
        if self._tasks is None:
            self._tasks = (
                self._load_fixture()
                if self._fixture_dir is not None
                else self._load_from_hf(cache_dir)
            )
        return self._tasks

    def task_iter(self) -> Iterator[Task]:
        if self._tasks is None:
            # Lazy: caller must have invoked load_eval_set() first OR is using
            # the fixture path.
            if self._fixture_dir is not None:
                self._tasks = self._load_fixture()
            else:
                raise AdapterError(
                    "task_iter() called before load_eval_set(); call "
                    "load_eval_set(cache_dir) first or instantiate with fixture_dir."
                )
        return iter(self._tasks)

    def score(self, task: Task, prediction: Prediction) -> float:  # noqa: ARG002
        """Returns 1.0 if `prediction.output['report']['resolved']` is True.

        The actual SWE-bench evaluator runs the test patch in a Docker
        sandbox; this method accepts the *already-computed* report (static
        mode). Live-mode runners shell out to the upstream evaluator and
        feed its output back here.
        """
        out = prediction.output
        if isinstance(out, str):
            return 1.0 if out.strip().lower() in ("resolved", "1", "true", "pass") else 0.0
        # prediction.output is typed as str | dict per schema; this branch is dict.
        report = out.get("report") or out
        return 1.0 if bool(report.get("resolved")) else 0.0

    def lazy_agent_recipe(self, task: Task) -> Prediction:
        """Berkeley's SWE-bench exploit, packaged as a per-task lazy-agent recipe.

        The exploit is a conftest.py with a pytest hook that forces every test
        to report as passing — the agent never modifies the source, but the
        grader trusts the test runner's verdict. We *do not execute* the
        exploit here; we synthesize the prediction shape that the grader would
        see if the exploit ran: a `report` dict with `resolved=True`.

        Adapters where the grader re-runs tests in a sandboxed container that
        ignores agent-supplied conftest.py would not be exploited this way.
        SWE-bench Verified, per Berkeley, *is*. The probe demonstrates the
        vulnerability without running adversarial code.
        """
        return Prediction(
            task_id=task.task_id,
            model_name="bench-audit::lazy-agent",
            model_version="conftest-pytest-hook-v1",
            output={
                "report": {
                    "resolved": True,
                    "tests_status": {
                        "FAIL_TO_PASS": {"success": task.payload.get("FAIL_TO_PASS", [])},
                        "PASS_TO_PASS": {"success": task.payload.get("PASS_TO_PASS", [])},
                    },
                    "exploit": "conftest.py pytest_collection_modifyitems hook",
                    "source": "berkeley_rdi_2026_04_12",
                }
            },
            metadata={
                "exploit_id": "BA-01+BA-07",
                "exploit_doc": ("https://rdi.berkeley.edu/blog/trustworthy-benchmarks-cont/"),
            },
        )

    def manifest(self) -> BenchmarkManifest:
        # When loaded from fixture, hash the fixture's tasks.jsonl; otherwise
        # use the pinned hash from the HF dataset commit.
        if self._fixture_dir is not None:
            sha = hashlib.sha256((self._fixture_dir / "tasks.jsonl").read_bytes()).hexdigest()
            n = len(self._tasks) if self._tasks is not None else 0
        else:
            sha = _MANIFEST_HASH_PINNED or "pending-first-fetch"
            n = 500
        return BenchmarkManifest(
            name=self.name,
            version=self.benchmark_version,
            source_url="https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified",
            license="MIT",
            license_notes=(
                "MIT-licensed eval set. Adapter does not redistribute gold patches; "
                "they are fetched from upstream at runtime."
            ),
            n_tasks=n,
            eval_set_sha256=sha,
            last_release_date=datetime(2024, 8, 13, tzinfo=UTC),
            maintainer="Princeton NLP + Stanford (Jimenez, Yang et al.)",
            contamination_statement_url=(
                "https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/"
            ),
        )


registry.register(SWEBenchVerifiedAdapter)
