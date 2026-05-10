"""Stub probe — proves the harness loop runs end-to-end. Always inconclusive."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from bench_audit import __version__
from bench_audit.adapters.base import Adapter
from bench_audit.probes.base import Probe
from bench_audit.schemas import Prediction, ProbeResult


class HelloProbe(Probe):
    name = "hello"
    version = "0.1.0"
    description = "Smoke-test probe. Always returns verdict='inconclusive'."

    def applies_to(self, adapter: Adapter) -> bool:  # noqa: ARG002
        return True

    def run(
        self,
        adapter: Adapter,
        *,
        predictions: Sequence[Prediction] | None = None,  # noqa: ARG002
        model: Any | None = None,  # noqa: ARG002
    ) -> ProbeResult:
        manifest = adapter.manifest()
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
            notes="HelloProbe is a smoke-test stub — proves the harness loop works.",
        )
