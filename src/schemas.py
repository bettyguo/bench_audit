"""Pydantic schemas.

Invariants enforced at construction:

- A ProbeResult requires a confidence interval.
- A non-inconclusive verdict at n<30 requires `allow_small_n=True`.
- A BenchmarkManifest must carry an eval-set SHA-256.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TaskId = str


class Task(BaseModel):
    """A single benchmark task.

    `payload` is adapter-specific; we keep this open because benchmarks differ
    wildly (a SWE-bench task has commits + tests; a WebArena task has a URL
    + instruction; a GAIA task is a Q + optional file).
    """

    model_config = ConfigDict(extra="forbid")

    task_id: TaskId
    benchmark_name: str
    benchmark_version: str
    payload: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        """Stable hash of the task content (not including metadata)."""
        s = f"{self.benchmark_name}/{self.benchmark_version}/{self.task_id}"
        return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


class Prediction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: TaskId
    model_name: str
    model_version: str
    output: str | dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    kind: Literal["tool_call", "tool_result", "model_output", "score", "other"]
    name: str | None = None
    args: dict[str, Any] | None = None
    text: str | None = None


class Trajectory(BaseModel):
    """An agent's action log for a single task. P5 (reward-hacking) consumes these."""

    model_config = ConfigDict(extra="forbid")

    task_id: TaskId
    model_name: str
    model_version: str
    actions: list[Action]
    final_score: float | None = None
    raw_files_touched: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkManifest(BaseModel):
    """Metadata + integrity hashes for a benchmark eval set.

    `eval_set_sha256` is the source of truth: adapters verify the cached eval
    set against this on load. Tampering with the eval set shows as a hash
    mismatch and prevents the harness from running.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    version: str
    source_url: str
    license: str
    license_notes: str | None = None
    n_tasks: int
    eval_set_sha256: str
    last_release_date: datetime | None = None
    maintainer: str | None = None
    contamination_statement_url: str | None = None
    requires_auth: bool = False


Verdict = Literal["pass", "fail", "inconclusive"]
EffectSizeKind = Literal["proportion", "risk_difference", "cohens_h", "auc", "mutual_information"]
CIMethod = Literal["wilson", "bootstrap", "clopper_pearson", "asymptotic_normal"]


class ProbeResult(BaseModel):
    """The output of a single probe run.

    Invariants:
    - ci_low <= ci_high
    - 0 < ci_level < 1
    - non-inconclusive verdict at sample_size < 30 requires
      `allow_small_n=True`
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    probe_name: str
    probe_version: str
    adapter_name: str
    adapter_version: str
    benchmark_version: str
    model_name: str | None = None
    model_version: str | None = None

    verdict: Verdict
    effect_size: float
    effect_size_kind: EffectSizeKind

    ci_low: float
    ci_high: float
    ci_method: CIMethod
    ci_level: float = 0.95

    sample_size: int
    test_set_hash: str
    control_set_hash: str | None = None

    raw_data_path: Path | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    harness_version: str

    notes: str | None = None
    allow_small_n: bool = False
    allow_wide_ci: bool = False

    @model_validator(mode="after")
    def _ci_invariants(self) -> ProbeResult:
        if not 0.0 < self.ci_level < 1.0:
            raise ValueError(f"ci_level must be in (0,1); got {self.ci_level}")
        if self.ci_low > self.ci_high:
            raise ValueError(
                f"ci_low ({self.ci_low}) > ci_high ({self.ci_high}); CIs are degenerate"
            )
        if self.verdict != "inconclusive" and self.sample_size < 30 and not self.allow_small_n:
            raise ValueError(
                f"Refusing to issue verdict='{self.verdict}' at sample_size={self.sample_size}. "
                "Either gather more samples, set verdict='inconclusive', or pass "
                "allow_small_n=True (which will be logged on the report card)."
            )
        if (
            self.verdict != "inconclusive"
            and (self.ci_high - self.ci_low) > 0.2
            and not self.allow_wide_ci
        ):
            raise ValueError(
                f"CI half-width {(self.ci_high - self.ci_low) / 2:.3f} > 0.1 with verdict="
                f"'{self.verdict}'. Either widen sample, set inconclusive, or "
                "pass allow_wide_ci=True."
            )
        return self

    @property
    def ci_half_width(self) -> float:
        return (self.ci_high - self.ci_low) / 2


class ReportCard(BaseModel):
    """One-page artifact: one probe × one benchmark × (optionally) one model."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["v1"] = "v1"
    result: ProbeResult
    manifest: BenchmarkManifest
    reproduction_command: str
    raw_data_url: str | None = None
    interpretation: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
