"""Static-mode probe execution.

Runs a probe against an adapter + (optional) stored predictions, without
requiring a live model. The bulk of v0.1 probes — gold-answer leak,
harness-injection, eval-set-visibility, and trajectory-based reward-hacking —
work in static mode.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from bench_audit.adapters.base import Adapter
from bench_audit.probes.base import Probe
from bench_audit.schemas import Prediction, ProbeResult


def run_probe_static(
    probe: Probe,
    adapter: Adapter,
    *,
    predictions: Sequence[Prediction] | None = None,
    out_dir: Path | None = None,
) -> ProbeResult:
    """Run a probe in static mode and (optionally) persist the result.

    Idempotent given the same (probe, adapter, predictions): the probe must
    be deterministic for this to hold.
    """
    if not probe.applies_to(adapter):
        from bench_audit.errors import ProbeInapplicableError

        raise ProbeInapplicableError(
            f"Probe '{probe.name}' does not apply to adapter '{adapter.name}'"
        )
    if probe.requires_live_model:
        raise ValueError(
            f"Probe '{probe.name}' requires a live model; use run_probe_live() instead."
        )
    result = probe.run(adapter, predictions=predictions)
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / f"{adapter.name}__{probe.name}.json"
        target.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return result
