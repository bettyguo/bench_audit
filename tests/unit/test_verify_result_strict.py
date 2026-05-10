"""Tests for the `bench-audit verify-result --strict` leaderboard gate."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from bench_audit.cli import app
from bench_audit.schemas import ProbeResult

runner = CliRunner()


def _make_result(**overrides) -> ProbeResult:
    base = {
        "probe_name": "p1_gold_answer_leak",
        "probe_version": "0.1.0",
        "adapter_name": "swebench_verified",
        "adapter_version": "0.1.0",
        "benchmark_version": "swebench-verified-2024-08",
        "verdict": "fail",
        "effect_size": 0.97,
        "effect_size_kind": "proportion",
        "ci_low": 0.95,
        "ci_high": 0.99,
        "ci_method": "wilson",
        "sample_size": 500,
        "test_set_hash": "a" * 64,
        "harness_version": "0.1.0a0",
    }
    base.update(overrides)
    return ProbeResult(**base)


def _write(path: Path, r: ProbeResult) -> None:
    path.write_text(r.model_dump_json(indent=2))


def test_basic_validation(tmp_path: Path) -> None:
    r = _make_result()
    p = tmp_path / "r.json"
    _write(p, r)
    result = runner.invoke(app, ["verify-result", str(p)])
    assert result.exit_code == 0
    assert "Valid" in result.output


def test_strict_passes_on_clean_result(tmp_path: Path) -> None:
    r = _make_result()
    p = tmp_path / "r.json"
    _write(p, r)
    result = runner.invoke(app, ["verify-result", str(p), "--strict"])
    assert result.exit_code == 0
    assert "strict OK" in result.output


def test_strict_refuses_allow_small_n(tmp_path: Path) -> None:
    r = _make_result(sample_size=5, allow_small_n=True, allow_wide_ci=True)
    p = tmp_path / "r.json"
    _write(p, r)
    result = runner.invoke(app, ["verify-result", str(p), "--strict"])
    assert result.exit_code == 1
    assert "allow_small_n" in result.output


def test_strict_refuses_pending_hash(tmp_path: Path) -> None:
    r = _make_result(test_set_hash="pending-first-fetch")
    p = tmp_path / "r.json"
    _write(p, r)
    result = runner.invoke(app, ["verify-result", str(p), "--strict"])
    assert result.exit_code == 1
    assert "pinned test_set_hash" in result.output


def test_strict_refuses_unknown_adapter(tmp_path: Path) -> None:
    r = _make_result(adapter_name="not_a_real_adapter")
    p = tmp_path / "r.json"
    _write(p, r)
    result = runner.invoke(app, ["verify-result", str(p), "--strict"])
    assert result.exit_code == 1
    assert "unknown adapter" in result.output


def test_strict_refuses_wide_ci(tmp_path: Path) -> None:
    r = _make_result(ci_low=0.5, ci_high=0.9, allow_wide_ci=True)
    p = tmp_path / "r.json"
    _write(p, r)
    result = runner.invoke(app, ["verify-result", str(p), "--strict"])
    assert result.exit_code == 1
    assert "CI half-width" in result.output or "allow_wide_ci" in result.output


def test_invalid_json_exits_nonzero(tmp_path: Path) -> None:
    p = tmp_path / "r.json"
    p.write_text("not json")
    result = runner.invoke(app, ["verify-result", str(p)])
    assert result.exit_code == 1
