"""P1 — Gold-answer leak probe.

A task is gold-answer-leaking if the gold answer is recoverable from the
task's presentation environment (filesystem, network, prompt context)
without performing the underlying task. Operationalized: a fixed "lazy
agent" that performs no task-relevant computation achieves score above a
task-specific threshold.

The probe runs the adapter-supplied lazy-agent recipe against every task
and reports leak_rate with a Wilson 95% CI. Adapters without a recipe get
verdict=inconclusive.

Reproduces Berkeley's WebArena finding (file:// reads of
config_files/{task_id}.json yield ~100% on all 812 tasks); calibration
target on WebArena is effect_size >= 0.97 with CI strictly above 0.95.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from bench_audit import __version__
from bench_audit.adapters.base import Adapter
from bench_audit.probes.base import Probe
from bench_audit.schemas import Prediction, ProbeResult, Task
from bench_audit.stats.intervals import wilson_ci


@runtime_checkable
class LazyAgentRecipe(Protocol):
    """An adapter-side recipe for constructing a lazy-agent prediction.

    A *lazy agent* takes a task and produces a prediction without doing any
    task-relevant work — it pulls the answer from a known leak channel
    (filesystem, public URL, prompt-encoded metadata, etc.). The probe runs the
    recipe against each task and asks the adapter to score it.
    """

    def __call__(self, task: Task) -> Prediction: ...


@dataclass(frozen=True)
class _PerTaskRecord:
    task_id: str
    score: float
    is_leak: bool
    recipe_error: str | None = None


class GoldAnswerLeakProbe(Probe):
    name = "p1_gold_answer_leak"
    version = "0.1.0"
    description = (
        "Runs a fixed lazy agent per task; reports leak_rate (proportion that pass) with Wilson CI."
    )

    # Task-pass threshold. A task counts as "leaking" if score >= threshold.
    # Default 0.5 because SWE-bench/WebArena/GAIA all have effectively binary
    # scoring; tweak via constructor if the adapter has graded scoring.
    DEFAULT_PASS_THRESHOLD: float = 0.5

    def __init__(
        self,
        pass_threshold: float | None = None,
        max_tasks: int | None = None,
    ) -> None:
        self.pass_threshold = (
            pass_threshold if pass_threshold is not None else self.DEFAULT_PASS_THRESHOLD
        )
        self.max_tasks = max_tasks

    def applies_to(self, adapter: Adapter) -> bool:
        recipe = getattr(adapter, "lazy_agent_recipe", None)
        return callable(recipe)

    def run(
        self,
        adapter: Adapter,
        *,
        predictions: Sequence[Prediction] | None = None,  # noqa: ARG002
        model: Any | None = None,  # noqa: ARG002
    ) -> ProbeResult:
        manifest = adapter.manifest()
        recipe_fn: Callable[[Task], Prediction] | None = getattr(adapter, "lazy_agent_recipe", None)
        if recipe_fn is None or not callable(recipe_fn):
            return ProbeResult(
                probe_name=self.name,
                probe_version=self.version,
                adapter_name=adapter.name,
                adapter_version=adapter.version,
                benchmark_version=adapter.benchmark_version,
                verdict="inconclusive",
                effect_size=0.0,
                effect_size_kind="proportion",
                ci_low=0.0,
                ci_high=1.0,
                ci_method="wilson",
                sample_size=0,
                test_set_hash=manifest.eval_set_sha256,
                harness_version=__version__,
                notes=(
                    f"Adapter '{adapter.name}' did not provide a lazy_agent_recipe; "
                    "this probe cannot be evaluated. Define a recipe to enable."
                ),
            )

        records: list[_PerTaskRecord] = []
        for i, task in enumerate(adapter.task_iter()):
            if self.max_tasks is not None and i >= self.max_tasks:
                break
            try:
                pred = recipe_fn(task)
                score = adapter.score(task, pred)
            except Exception as exc:
                # A recipe that errors gets recorded with the error message so
                # the aggregate can surface it. If the recipe errors on every
                # task, the user must see that — not a silent verdict=pass.
                records.append(
                    _PerTaskRecord(
                        task_id=task.task_id,
                        score=0.0,
                        is_leak=False,
                        recipe_error=f"{type(exc).__name__}: {exc}",
                    )
                )
                continue
            records.append(
                _PerTaskRecord(
                    task_id=task.task_id,
                    score=score,
                    is_leak=score >= self.pass_threshold,
                )
            )

        n = len(records)
        n_leaks = sum(1 for r in records if r.is_leak)
        n_errors = sum(1 for r in records if r.recipe_error is not None)
        leak_rate = n_leaks / n if n > 0 else 0.0
        ci_low, ci_high = wilson_ci(n_leaks, n)

        # Verdict: fail if leak_rate is statistically above the null. But if
        # the recipe errored on EVERY task, the result has no information value
        # and verdict must be inconclusive — otherwise the probe would silently
        # report 'pass' (the C6 bug).
        if n == 0 or (n_errors > 0 and n_errors == n):
            verdict = "inconclusive"
        elif ci_low > 0.01:
            verdict = "fail"
        else:
            verdict = "pass"

        error_clause = (
            f" RECIPE ERRORS: {n_errors}/{n} tasks failed in the lazy-agent recipe."
            if n_errors > 0
            else ""
        )
        notes = (
            f"Lazy-agent leak rate: {n_leaks}/{n} = {leak_rate:.4f} "
            f"(Wilson 95% CI [{ci_low:.4f}, {ci_high:.4f}]). "
            f"pass_threshold={self.pass_threshold}.{error_clause}"
        )
        raw_hash = hashlib.sha256(
            json.dumps([r.__dict__ for r in records], sort_keys=True).encode()
        ).hexdigest()[:16]

        ci_half_width = (ci_high - ci_low) / 2
        return ProbeResult(
            probe_name=self.name,
            probe_version=self.version,
            adapter_name=adapter.name,
            adapter_version=adapter.version,
            benchmark_version=adapter.benchmark_version,
            verdict=verdict,
            effect_size=leak_rate,
            effect_size_kind="proportion",
            ci_low=ci_low,
            ci_high=ci_high,
            ci_method="wilson",
            sample_size=n,
            test_set_hash=manifest.eval_set_sha256,
            harness_version=__version__,
            notes=f"{notes} raw_hash={raw_hash}",
            # Small n implies wide CI. Both overrides flow together because
            # the user already opted into a small-sample run. Both flags get
            # logged on the report card so any reader can see the caveat.
            allow_small_n=(n < 30),
            allow_wide_ci=(ci_half_width > 0.1),
        )
