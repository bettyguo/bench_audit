"""P6 — Eval-set visibility probe.

A *factual* probe: does the manifest indicate the eval set is publicly
discoverable? Does the source URL resolve? Is auth required?

Output is categorical (pass/fail by policy) with a wide CI by construction —
this probe is informational, not inferential. We allow_wide_ci=True and
report verdict='fail' if the eval set is *both* public *and* lacks a
contamination-prevention mechanism (gating, hashing, private-test-split).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from bench_audit import __version__
from bench_audit.adapters.base import Adapter
from bench_audit.probes.base import Probe
from bench_audit.schemas import Prediction, ProbeResult


class EvalSetVisibilityProbe(Probe):
    name = "p6_eval_set_visibility"
    version = "0.1.0"
    description = (
        "Factual probe: reports visibility/auth/contamination-mitigation status of the eval set."
    )

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
        is_public = not manifest.requires_auth
        has_statement = manifest.contamination_statement_url is not None
        has_pinned_hash = (
            bool(manifest.eval_set_sha256) and manifest.eval_set_sha256 != "pending-first-fetch"
        )

        # Verdict policy: `missing` counts how many of three risk factors hold —
        # (1) the eval set is public, (2) there is no contamination statement,
        # (3) there is no pinned eval-set hash. Failing if `missing >= 2` means
        # the eval set is publicly reachable AND at least one
        # contamination-prevention mechanism (a statement or a pinned hash) is
        # absent. effect_size = missing/3, so public+no-statement+no-hash → 1.0
        # ("maximally exposed") and private+statement+hash → 0.0.
        missing = int(is_public) + int(not has_statement) + int(not has_pinned_hash)
        effect = missing / 3.0
        verdict = "fail" if missing >= 2 else "pass"

        notes_lines = [
            f"source_url: {manifest.source_url}",
            f"license: {manifest.license}",
            f"requires_auth: {manifest.requires_auth}",
            f"contamination_statement_url: {manifest.contamination_statement_url}",
            (
                "eval_set_sha256: "
                + ("pinned" if has_pinned_hash else "PENDING (first-fetch placeholder)")
            ),
            f"last_release_date: {manifest.last_release_date}",
            f"maintainer: {manifest.maintainer}",
        ]
        return ProbeResult(
            probe_name=self.name,
            probe_version=self.version,
            adapter_name=adapter.name,
            adapter_version=adapter.version,
            benchmark_version=adapter.benchmark_version,
            verdict=verdict,
            effect_size=effect,
            effect_size_kind="proportion",
            ci_low=0.0,
            ci_high=1.0,
            ci_method="clopper_pearson",
            sample_size=3,
            test_set_hash=manifest.eval_set_sha256,
            harness_version=__version__,
            notes="\n".join(notes_lines),
            allow_small_n=True,
            allow_wide_ci=True,
        )
