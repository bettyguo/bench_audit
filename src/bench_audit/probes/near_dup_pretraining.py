"""P2 — Near-duplicate-pretraining probe.

Two tracks:

- String track: 13-gram overlap of eval-set task text against a
  configurable corpus index (GPT-3 convention, whitespace-tokenized
  lowercased text). Reports `overlap_rate` with Wilson 95% CI.
- Behavioural track (live-only, not in v0.1): Min-K% Prob membership
  inference. Reported as a secondary signal; MIA alone is unreliable
  (Duan et al. 2024) so we never issue a verdict on MIA only.

The probe reports the overlap signal on the corpus, not a model verdict.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Sequence
from typing import Any

from bench_audit import __version__
from bench_audit.adapters.base import Adapter
from bench_audit.probes.base import Probe
from bench_audit.schemas import Prediction, ProbeResult, Task
from bench_audit.stats.intervals import wilson_ci


def _normalize_tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _ngrams(tokens: Sequence[str], n: int) -> Iterable[str]:
    for i in range(len(tokens) - n + 1):
        yield " ".join(tokens[i : i + n])


def _task_text(task: Task) -> str:
    parts: list[str] = []
    for key in ("problem_statement", "intent", "Question", "question", "task"):
        v = task.payload.get(key)
        if isinstance(v, str):
            parts.append(v)
    return "\n".join(parts) if parts else ""


class NearDupPretrainingProbe(Probe):
    name = "p2_near_dup_pretraining"
    version = "0.1.0"
    description = "13-gram overlap against a corpus index. Reports overlap_rate with Wilson 95% CI."

    DEFAULT_N: int = 13

    def __init__(
        self,
        corpus_index: set[str] | None = None,
        n: int | None = None,
        max_tasks: int | None = None,
    ) -> None:
        self.n = n if n is not None else self.DEFAULT_N
        self.corpus_index = corpus_index or set()
        self.max_tasks = max_tasks

    def applies_to(self, adapter: Adapter) -> bool:
        try:
            first = next(adapter.task_iter())
        except (StopIteration, Exception):
            return False
        return bool(_task_text(first))

    def run(
        self,
        adapter: Adapter,
        *,
        predictions: Sequence[Prediction] | None = None,  # noqa: ARG002
        model: Any | None = None,  # noqa: ARG002
    ) -> ProbeResult:
        manifest = adapter.manifest()
        records: list[tuple[str, bool]] = []
        for i, task in enumerate(adapter.task_iter()):
            if self.max_tasks is not None and i >= self.max_tasks:
                break
            text = _task_text(task)
            toks = _normalize_tokens(text)
            if len(toks) < self.n:
                records.append((task.task_id, False))
                continue
            overlapped = any(g in self.corpus_index for g in _ngrams(toks, self.n))
            records.append((task.task_id, overlapped))

        n = len(records)
        n_overlap = sum(1 for _, h in records if h)
        rate = n_overlap / n if n > 0 else 0.0
        ci_low, ci_high = wilson_ci(n_overlap, n)
        ci_half = (ci_high - ci_low) / 2

        if n == 0 or not self.corpus_index:
            verdict = "inconclusive"
            notes = (
                "Corpus index empty or no tasks; this probe needs an n-gram "
                "index of a candidate pretraining corpus (Pile, RedPajama, "
                "BigCode, FineWeb, DCLM). Pass via constructor."
            )
        elif ci_low > 0.01:
            verdict = "fail"
            notes = (
                f"{n_overlap}/{n} tasks ({rate:.4f}) have a {self.n}-gram in the "
                f"provided corpus; Wilson 95% CI [{ci_low:.4f}, {ci_high:.4f}]."
            )
        else:
            verdict = "pass"
            notes = (
                f"No statistically significant overlap detected. "
                f"{n_overlap}/{n} = {rate:.4f}; Wilson 95% CI "
                f"[{ci_low:.4f}, {ci_high:.4f}]."
            )

        raw = "\n".join(f"{tid},{int(h)}" for tid, h in records).encode()
        raw_hash = hashlib.sha256(raw).hexdigest()[:16]
        return ProbeResult(
            probe_name=self.name,
            probe_version=self.version,
            adapter_name=adapter.name,
            adapter_version=adapter.version,
            benchmark_version=adapter.benchmark_version,
            verdict=verdict,
            effect_size=rate,
            effect_size_kind="proportion",
            ci_low=ci_low,
            ci_high=ci_high,
            ci_method="wilson",
            sample_size=n,
            test_set_hash=manifest.eval_set_sha256,
            harness_version=__version__,
            notes=f"{notes}\nn-gram order={self.n}; raw_hash={raw_hash}",
            allow_small_n=(n < 30),
            allow_wide_ci=(ci_half > 0.1),
        )
