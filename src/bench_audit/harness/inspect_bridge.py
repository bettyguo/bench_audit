"""Inspect AI bridge.

Wraps Inspect AI as the live-eval substrate. Three jobs:

  1. Convert a bench-audit `Task` into an Inspect AI `Sample`.
  2. Construct an Inspect AI `Solver` chain that drives the adapter's task.
  3. Read Inspect AI's result `EvalLog` back into bench-audit `Trajectory` records.

The integration is *optional* (Inspect AI is a `[live]` extra). All Inspect
AI imports happen lazily inside functions so the offline test suite never
imports inspect-ai. The functions raise `RuntimeError` with a clear install
hint when the extra is missing.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from bench_audit.adapters.base import Adapter
from bench_audit.schemas import Action, Task, Trajectory


def _require_inspect() -> Any:
    try:
        import inspect_ai  # type: ignore[import-not-found]
    except ImportError as e:
        raise RuntimeError(
            "Live mode requires inspect-ai. Install with `uv sync --extra live` "
            "or `pip install bench-audit[live]`."
        ) from e
    return inspect_ai


def task_to_sample(task: Task) -> Any:
    """Convert a bench-audit Task into an Inspect AI Sample.

    The Sample's `input` is the benchmark-native prompt; `target` is the
    benchmark-native gold (where it exists). Adapter-specific payload fields
    are preserved under `metadata` so downstream solvers can use them.
    """
    inspect_ai = _require_inspect()
    Sample = inspect_ai.dataset.Sample  # type: ignore[attr-defined]  # noqa: N806
    prompt = _extract_prompt(task)
    target = _extract_target(task)
    return Sample(
        id=task.task_id,
        input=prompt,
        target=target,
        metadata={**task.payload, "benchmark": task.benchmark_name},
    )


def _extract_prompt(task: Task) -> str:
    for key in ("problem_statement", "intent", "Question", "question", "prompt"):
        v = task.payload.get(key)
        if isinstance(v, str) and v:
            return v
    return ""


def _extract_target(task: Task) -> str:
    for key in ("Final answer", "gold_patch", "answer"):
        v = task.payload.get(key)
        if isinstance(v, str) and v:
            return v
    # reference_answers (WebArena style)
    ref = task.payload.get("reference_answers")
    if isinstance(ref, dict):
        return str(
            ref.get("exact_match")
            or (ref.get("fuzzy_match") or [None])[0]
            or " ".join(ref.get("must_include") or [])
            or ""
        )
    return ""


def make_inspect_task(adapter: Adapter, *, n_samples: int | None = None) -> Any:
    """Construct an Inspect AI Task that wraps the adapter."""
    inspect_ai = _require_inspect()
    InspectTask = inspect_ai.Task  # type: ignore[attr-defined]  # noqa: N806
    samples = list(_iter_samples(adapter, n_samples))
    return InspectTask(
        dataset=samples,
        solver=inspect_ai.solver.generate(),  # type: ignore[attr-defined]
        scorer=_make_scorer(adapter),
    )


def _iter_samples(adapter: Adapter, n_samples: int | None) -> Iterable[Any]:
    for i, task in enumerate(adapter.task_iter()):
        if n_samples is not None and i >= n_samples:
            break
        yield task_to_sample(task)


def _make_scorer(adapter: Adapter) -> Any:
    """Build an Inspect AI scorer that calls back into the adapter's `score()`."""
    inspect_ai = _require_inspect()
    scorer = inspect_ai.scorer.scorer  # type: ignore[attr-defined]
    Score = inspect_ai.scorer.Score  # type: ignore[attr-defined]  # noqa: N806

    @scorer(metrics=[inspect_ai.scorer.accuracy()])  # type: ignore[untyped-decorator]
    def _wrapped_scorer() -> Any:
        async def _score(state: Any, target: Any) -> Any:  # noqa: ARG001
            from bench_audit.schemas import Prediction

            # Reconstruct a Task from state.metadata
            metadata = dict(state.metadata)
            task = Task(
                task_id=str(state.sample_id),
                benchmark_name=metadata.get("benchmark", adapter.name),
                benchmark_version=adapter.benchmark_version,
                payload=metadata,
            )
            output = state.output.completion if state.output else ""
            prediction = Prediction(
                task_id=task.task_id,
                model_name=state.model_name or "live",
                model_version=getattr(state, "model_version", "unknown"),
                output=output,
            )
            value = adapter.score(task, prediction)
            return Score(value=value, explanation=f"bench-audit::adapter.score = {value}")

        return _score

    return _wrapped_scorer()


def eval_log_to_trajectories(log: Any) -> list[Trajectory]:
    """Convert an Inspect AI EvalLog into bench-audit Trajectory records."""
    out: list[Trajectory] = []
    for sample in getattr(log, "samples", []) or []:
        actions: list[Action] = []
        messages = getattr(sample, "messages", []) or []
        for msg in messages:
            kind = "model_output" if msg.role == "assistant" else "other"
            actions.append(
                Action(
                    timestamp=getattr(msg, "timestamp", None) or _utcnow(),
                    kind=kind,  # type: ignore[arg-type]
                    name=msg.role,
                    text=msg.content if isinstance(msg.content, str) else None,
                )
            )
        tool_calls = getattr(sample, "tool_calls", []) or []
        for tc in tool_calls:
            actions.append(
                Action(
                    timestamp=getattr(tc, "timestamp", None) or _utcnow(),
                    kind="tool_call",
                    name=getattr(tc, "name", None),
                    args=dict(getattr(tc, "arguments", {}) or {}),
                )
            )
        final_score = None
        score = getattr(sample, "score", None)
        if score is not None:
            try:
                final_score = float(getattr(score, "value", score))
            except (TypeError, ValueError):
                final_score = None
        out.append(
            Trajectory(
                task_id=str(sample.id),
                model_name=getattr(log, "model", "unknown"),
                model_version=getattr(log, "model_version", "unknown"),
                actions=actions,
                final_score=final_score,
            )
        )
    return out


def _utcnow() -> Any:
    from datetime import UTC, datetime

    return datetime.now(UTC)
