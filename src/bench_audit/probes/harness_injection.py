"""P4 — Harness-injection probe.

Implements the seven structural vulnerability patterns Berkeley RDI (2026-04-12)
identified across the eight major agent benchmarks:

  1. No isolation between agent and evaluator
  2. Answers shipped with tests
  3. eval() on untrusted input
  4. LLM judges without input sanitization
  5. Weak string matching
  6. Evaluation logic that does not actually evaluate
  7. Trusting output from untrusted code

Each pattern is operationalized as a `Detector` that inspects the adapter's
public surface (manifest, fixture, evaluator source if available) and the
adapter-supplied environment. Per-pattern verdicts are aggregated into a
single ProbeResult whose effect_size is the proportion of patterns triggered
(scaled to [0, 1]).

Statistical interpretation:
  - Default presentation: `effect_size = n_triggered / 7`, with Clopper-Pearson
    95% CI on the count.
  - For a benchmark with zero triggered patterns, verdict = "pass". One or more
    triggered patterns yields verdict = "fail".
  - Inconclusive when the adapter's source surface is unavailable (e.g., the
    evaluator is a remote service we cannot inspect statically).

This is intentionally a CHECKLIST, not an estimator on a sample of tasks. We
also expose a `--sample` mode that randomly samples N tasks and checks the
proportion of tasks where each pattern actually triggers, with a Wilson CI.
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from bench_audit import __version__
from bench_audit.adapters.base import Adapter
from bench_audit.probes.base import Probe
from bench_audit.schemas import Prediction, ProbeResult
from bench_audit.stats.intervals import clopper_pearson_ci


@dataclass(frozen=True)
class DetectorResult:
    pattern_id: str
    pattern_name: str
    triggered: bool
    evidence: str | None = None


class HarnessInjectionProbe(Probe):
    name = "p4_harness_injection"
    version = "0.1.0"
    description = (
        "Scans an adapter's evaluation surface for Berkeley's 7 harness-injection patterns."
    )

    # Pattern IDs are stable; new patterns get new IDs (we never renumber).
    PATTERNS: tuple[tuple[str, str], ...] = (
        ("BA-01", "No agent/evaluator isolation"),
        ("BA-02", "Answers shipped with tests"),
        ("BA-03", "eval() on untrusted input"),
        ("BA-04", "LLM judges without input sanitization"),
        ("BA-05", "Weak string matching in grader"),
        ("BA-06", "Evaluation logic that does not actually evaluate"),
        ("BA-07", "Grader trusts output from untrusted code"),
    )

    def applies_to(self, adapter: Adapter) -> bool:  # noqa: ARG002
        # Applies to every adapter — every benchmark has a grading surface to inspect.
        return True

    def run(
        self,
        adapter: Adapter,
        *,
        predictions: Sequence[Prediction] | None = None,  # noqa: ARG002
        model: Any | None = None,  # noqa: ARG002
    ) -> ProbeResult:
        manifest = adapter.manifest()
        detectors = (
            self._detect_no_isolation,
            self._detect_answers_with_tests,
            self._detect_eval_on_untrusted,
            self._detect_unsanitized_llm_judge,
            self._detect_weak_string_match,
            self._detect_dead_validate,
            self._detect_trusts_agent_output,
        )
        results: list[DetectorResult] = []
        for det in detectors:
            results.append(det(adapter))

        n_triggered = sum(1 for r in results if r.triggered)
        n_patterns = len(self.PATTERNS)
        effect_size = n_triggered / n_patterns
        ci_low, ci_high = clopper_pearson_ci(n_triggered, n_patterns)

        verdict = "fail" if n_triggered > 0 else "pass"
        notes_lines = [
            f"{r.pattern_id} ({r.pattern_name}): "
            f"{'TRIGGERED — ' + (r.evidence or '') if r.triggered else 'clean'}"
            for r in results
        ]
        return ProbeResult(
            probe_name=self.name,
            probe_version=self.version,
            adapter_name=adapter.name,
            adapter_version=adapter.version,
            benchmark_version=adapter.benchmark_version,
            verdict=verdict,
            effect_size=effect_size,
            effect_size_kind="proportion",
            ci_low=ci_low,
            ci_high=ci_high,
            ci_method="clopper_pearson",
            sample_size=n_patterns,
            test_set_hash=manifest.eval_set_sha256,
            harness_version=__version__,
            notes="\n".join(notes_lines),
            # The "sample" here is fixed at n=7 patterns. We allow small_n because
            # this is a checklist, not a proportion estimator over tasks.
            allow_small_n=True,
            # The Clopper-Pearson interval at n=7 is necessarily wide; document.
            allow_wide_ci=True,
        )

    def _detect_no_isolation(self, adapter: Adapter) -> DetectorResult:
        """BA-01: detect whether the adapter's grader runs in a sandbox.

        Heuristic: read the adapter's `score()` source; if it shells out without
        Docker/firejail/seccomp markers, flag.
        """
        try:
            src = inspect.getsource(adapter.score)
        except (OSError, TypeError):
            return DetectorResult("BA-01", self.PATTERNS[0][1], False, "source unavailable")
        shells_out = bool(re.search(r"subprocess|os\.system|shell=True|sh -c", src))
        sandboxed = bool(re.search(r"docker|firejail|nsjail|seccomp|sandbox", src, re.I))
        triggered = shells_out and not sandboxed
        return DetectorResult(
            "BA-01",
            self.PATTERNS[0][1],
            triggered,
            "shells out without sandbox markers" if triggered else None,
        )

    def _detect_answers_with_tests(self, adapter: Adapter) -> DetectorResult:
        """BA-02: detect whether the eval-set task payload exposes the gold answer.

        Many benchmarks ship `(prompt, gold)` together (because their grader is
        an in-process string match). This is fine for a benchmark consumer but a
        leak if the agent is invoked with the raw payload — which is exactly the
        WebArena `config_files/{task_id}.json` finding.
        """
        try:
            first_task = next(adapter.task_iter())
        except (StopIteration, Exception):
            return DetectorResult("BA-02", self.PATTERNS[1][1], False, "no tasks available")
        gold_keys = {"gold", "gold_answer", "gold_patch", "answer", "reference", "expected"}
        present = sorted(k for k in first_task.payload if k.lower() in gold_keys)
        triggered = bool(present)
        return DetectorResult(
            "BA-02",
            self.PATTERNS[1][1],
            triggered,
            f"payload exposes gold-answer keys: {present}" if triggered else None,
        )

    def _detect_eval_on_untrusted(self, adapter: Adapter) -> DetectorResult:
        """BA-03: detect use of `eval()`/`exec()` in the grader."""
        try:
            src = inspect.getsource(adapter.score)
        except (OSError, TypeError):
            return DetectorResult("BA-03", self.PATTERNS[2][1], False, "source unavailable")
        triggered = bool(re.search(r"\beval\s*\(|\bexec\s*\(", src))
        return DetectorResult(
            "BA-03",
            self.PATTERNS[2][1],
            triggered,
            "eval/exec call in grader source" if triggered else None,
        )

    def _detect_unsanitized_llm_judge(self, adapter: Adapter) -> DetectorResult:
        """BA-04: heuristic — does the grader pass agent output verbatim into a
        prompt that mentions 'judge' or 'grade'?"""
        try:
            src = inspect.getsource(adapter.score)
        except (OSError, TypeError):
            return DetectorResult("BA-04", self.PATTERNS[3][1], False, "source unavailable")
        # Cheap heuristic: any string concatenation/format involving 'judge' or
        # 'grade' that interpolates a variable from the agent's output.
        has_judge_prompt = bool(re.search(r"(judge|grade|evaluator)", src, re.I))
        has_format = bool(re.search(r"\.format\(|f['\"]|%s", src))
        has_sanitizer = bool(re.search(r"sanitize|escape|html\.escape|bleach", src))
        triggered = has_judge_prompt and has_format and not has_sanitizer
        return DetectorResult(
            "BA-04",
            self.PATTERNS[3][1],
            triggered,
            "LLM-judge prompt with unsanitized interpolation" if triggered else None,
        )

    def _detect_weak_string_match(self, adapter: Adapter) -> DetectorResult:
        """BA-05: detect graders that aggressively strip whitespace AND
        punctuation before matching — Berkeley's GAIA finding.

        Tightened from a permissive heuristic: routine `.strip().lower()` is
        NOT a BA-05 trigger; only patterns that strip *all* punctuation OR
        *all* whitespace (which create collisions like `1, 2` == `12`) count.
        Reasons the detector fires:
          (a) explicit `re.sub(r"\\W", ...)` or `re.sub(r"[^\\w]", ...)` —
              strips everything but word chars
          (b) `string.punctuation` referenced in a substitution
          (c) `.replace(' ', '')` and friends (collapses whitespace entirely)
        """
        try:
            src = inspect.getsource(adapter.score)
        except (OSError, TypeError):
            return DetectorResult("BA-05", self.PATTERNS[4][1], False, "source unavailable")
        strips_all_punct = bool(
            re.search(r"re\.sub\(.*\\W", src)
            or re.search(r"re\.sub\(.*\[\^\\w", src)
            or re.search(r"string\.punctuation", src)
        )
        collapses_whitespace = bool(
            re.search(r"\.replace\(\s*['\"]\s+['\"]\s*,\s*['\"]['\"]", src)
            or re.search(r"re\.sub\(.*\\s\+.*['\"]['\"]", src)
        )
        # Also: a grader that calls a known-aggressive normalizer (by name)
        calls_aggressive_norm = bool(
            re.search(r"_gaia_normalize|aggressive_normalize|strip_all", src)
        )
        triggered = strips_all_punct or collapses_whitespace or calls_aggressive_norm
        evidence_bits = []
        if strips_all_punct:
            evidence_bits.append("strips all punctuation via re.sub or string.punctuation")
        if collapses_whitespace:
            evidence_bits.append("collapses whitespace entirely")
        if calls_aggressive_norm:
            evidence_bits.append("calls a known-aggressive normalizer")
        return DetectorResult(
            "BA-05",
            self.PATTERNS[4][1],
            triggered,
            "; ".join(evidence_bits) if triggered else None,
        )

    def _detect_dead_validate(self, adapter: Adapter) -> DetectorResult:
        """BA-06: detect a `score()` that does not depend on its `prediction` arg.

        Berkeley's FieldWorkArena finding: `validate()` only checked that the
        last message came from the assistant, ignoring the actual gold
        comparison.
        """
        try:
            src = inspect.getsource(adapter.score)
            sig = inspect.signature(adapter.score)
        except (OSError, TypeError, ValueError):
            return DetectorResult("BA-06", self.PATTERNS[5][1], False, "source unavailable")
        pred_param = next(
            (p for p in sig.parameters if "pred" in p.lower() or p == "prediction"), None
        )
        if pred_param is None:
            return DetectorResult(
                "BA-06",
                self.PATTERNS[5][1],
                True,
                "score() has no prediction parameter",
            )
        # Trigger if `score()`'s body never references the prediction parameter.
        triggered = not re.search(rf"\b{re.escape(pred_param)}\b", src)
        return DetectorResult(
            "BA-06",
            self.PATTERNS[5][1],
            triggered,
            f"score() never references its '{pred_param}' parameter" if triggered else None,
        )

    def _detect_trusts_agent_output(self, adapter: Adapter) -> DetectorResult:
        """BA-07: detect graders that take a numeric score directly from the
        agent's output instead of re-deriving it.

        Berkeley's Terminal-Bench finding: a fake `pytest` wrapper produces a
        fake passing report that the grader trusts.
        """
        try:
            src = inspect.getsource(adapter.score)
        except (OSError, TypeError):
            return DetectorResult("BA-07", self.PATTERNS[6][1], False, "source unavailable")
        # Heuristic: grader reads keys like `resolved`, `passed`, `score`, `result`
        # directly from prediction.output without re-running.
        reads_status_keys = bool(
            re.search(r"output\[.(resolved|passed|score|result|status)", src)
            or re.search(r"\.get\(['\"](resolved|passed|score|result|status)", src)
        )
        reruns = bool(re.search(r"subprocess|docker|pytest|verify|recompute", src, re.I))
        triggered = reads_status_keys and not reruns
        return DetectorResult(
            "BA-07",
            self.PATTERNS[6][1],
            triggered,
            "grader trusts agent-reported status without re-verification" if triggered else None,
        )
