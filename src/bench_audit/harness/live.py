"""Live-mode probe execution via Inspect AI.

Live mode is required for: Min-K% Prob membership inference (P2-live), some
shortcut-feature checks (P3 live), and trajectory collection for the
reward-hacking probe (P5 with use_llm=True or with on-the-fly trajectory
generation).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bench_audit.adapters.base import Adapter
from bench_audit.errors import ProbeInapplicableError
from bench_audit.probes.base import Probe
from bench_audit.schemas import ProbeResult


def run_probe_live(
    probe: Probe,
    adapter: Adapter,
    *,
    model: Any | str,
    n_samples: int | None = None,
    inspect_log_dir: Path | None = None,
) -> ProbeResult:
    """Run a probe in live mode.

    `model` is either an Inspect AI `Model` instance or a spec string like
    'anthropic/claude-opus-4-7-20260201'. Spec strings are routed through
    `harness.model_factory.get_model` (which refuses 'latest' aliases).

    `n_samples` caps how many tasks are queried (use for development).
    `inspect_log_dir` is forwarded to Inspect AI's logger.
    """
    if not probe.applies_to(adapter):
        raise ProbeInapplicableError(
            f"Probe '{probe.name}' does not apply to adapter '{adapter.name}'"
        )

    if isinstance(model, str):
        from bench_audit.harness.model_factory import get_model

        model_obj = get_model(model)
    else:
        model_obj = model

    if not probe.requires_live_model:
        # A static probe in live mode just runs static — but we still log the
        # model identity for the report card.
        return probe.run(adapter, model=model_obj)

    # For probes that DO require live model, we collect trajectories first.
    from bench_audit.harness.inspect_bridge import (
        eval_log_to_trajectories,
        make_inspect_task,
    )

    try:
        import inspect_ai  # type: ignore[import-not-found]
    except ImportError as e:
        raise RuntimeError(
            "Live mode requires inspect-ai. Install with `uv sync --extra live`."
        ) from e

    task = make_inspect_task(adapter, n_samples=n_samples)
    log_dir = str(inspect_log_dir) if inspect_log_dir else None
    log = inspect_ai.eval(task, model=model_obj, log_dir=log_dir)  # type: ignore[attr-defined]

    trajectories = eval_log_to_trajectories(log)

    # P5 specifically: drive the trajectory classifier
    if probe.name == "p5_reward_hacking":
        from bench_audit.probes.reward_hacking import RewardHackingProbe

        live_probe = RewardHackingProbe(trajectories=trajectories, use_llm=True)
        return live_probe.run(adapter, model=model_obj)

    return probe.run(adapter, model=model_obj)
