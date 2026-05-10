"""Schema invariants."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bench_audit.schemas import BenchmarkManifest, ProbeResult, Task


def _valid_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "probe_name": "test",
        "probe_version": "0.1.0",
        "adapter_name": "synthetic",
        "adapter_version": "0.1.0",
        "benchmark_version": "v1",
        "verdict": "inconclusive",
        "effect_size": 0.5,
        "effect_size_kind": "proportion",
        "ci_low": 0.4,
        "ci_high": 0.6,
        "ci_method": "wilson",
        "sample_size": 100,
        "test_set_hash": "abc",
        "harness_version": "0.1.0",
    }
    base.update(overrides)
    return base


def test_probe_result_requires_ci_in_bounds() -> None:
    with pytest.raises(ValidationError):
        ProbeResult(**_valid_kwargs(ci_low=0.7, ci_high=0.3))


def test_probe_result_refuses_verdict_at_small_n() -> None:
    with pytest.raises(ValidationError):
        ProbeResult(**_valid_kwargs(verdict="fail", sample_size=10))


def test_probe_result_allows_inconclusive_at_small_n() -> None:
    r = ProbeResult(**_valid_kwargs(verdict="inconclusive", sample_size=10))
    assert r.verdict == "inconclusive"


def test_probe_result_small_n_override() -> None:
    r = ProbeResult(
        **_valid_kwargs(verdict="fail", sample_size=10, allow_small_n=True, ci_low=0.4, ci_high=0.6)
    )
    assert r.allow_small_n is True


def test_probe_result_refuses_wide_ci() -> None:
    with pytest.raises(ValidationError):
        ProbeResult(**_valid_kwargs(verdict="fail", ci_low=0.0, ci_high=1.0))


def test_probe_result_wide_ci_override() -> None:
    r = ProbeResult(**_valid_kwargs(verdict="fail", ci_low=0.0, ci_high=1.0, allow_wide_ci=True))
    assert r.allow_wide_ci is True


def test_probe_result_is_frozen() -> None:
    r = ProbeResult(**_valid_kwargs())
    with pytest.raises(ValidationError):
        r.verdict = "pass"  # type: ignore[misc]


def test_benchmark_manifest_is_frozen() -> None:
    m = BenchmarkManifest(
        name="synthetic",
        version="v1",
        source_url="https://x.invalid",
        license="CC0-1.0",
        n_tasks=1,
        eval_set_sha256="deadbeef",
    )
    with pytest.raises(ValidationError):
        m.n_tasks = 999  # type: ignore[misc]


def test_task_fingerprint_is_stable() -> None:
    t1 = Task(task_id="x", benchmark_name="b", benchmark_version="v1", payload={})
    t2 = Task(task_id="x", benchmark_name="b", benchmark_version="v1", payload={"different": True})
    # Fingerprint is over task_id + benchmark_version + benchmark_name, not payload
    assert t1.fingerprint == t2.fingerprint


def test_probe_result_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        ProbeResult(**_valid_kwargs(undefined_field=1))
