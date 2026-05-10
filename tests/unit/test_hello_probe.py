"""End-to-end smoke test for the harness loop."""

from __future__ import annotations

from pathlib import Path

from bench_audit.harness import run_probe_static
from bench_audit.probes import HelloProbe


def test_hello_probe_runs(synthetic_adapter, tmp_path: Path) -> None:
    probe = HelloProbe()
    result = run_probe_static(probe, synthetic_adapter, out_dir=tmp_path)
    assert result.probe_name == "hello"
    assert result.verdict == "inconclusive"
    assert result.adapter_name == "synthetic"
    assert (tmp_path / "synthetic__hello.json").exists()


def test_hello_probe_applies_to_anything(synthetic_adapter) -> None:
    assert HelloProbe().applies_to(synthetic_adapter) is True
