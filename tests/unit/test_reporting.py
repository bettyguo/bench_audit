"""Reporting smoke tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from bench_audit.reporting import (
    render_markdown_report,
    write_json_report,
)
from bench_audit.schemas import BenchmarkManifest, ProbeResult, ReportCard


def _make_report() -> ReportCard:
    result = ProbeResult(
        probe_name="p1_gold_answer_leak",
        probe_version="0.1.0",
        adapter_name="webarena",
        adapter_version="0.1.0",
        benchmark_version="webarena-2024-10",
        verdict="fail",
        effect_size=0.97,
        effect_size_kind="proportion",
        ci_low=0.95,
        ci_high=0.99,
        ci_method="wilson",
        sample_size=812,
        test_set_hash="a" * 64,
        harness_version="0.1.0a0",
        notes="hack_rate=787/812=0.9692; Wilson 95% CI [0.95, 0.99]",
    )
    manifest = BenchmarkManifest(
        name="webarena",
        version="webarena-2024-10",
        source_url="https://github.com/web-arena-x/webarena",
        license="Apache-2.0",
        n_tasks=812,
        eval_set_sha256="a" * 64,
        contamination_statement_url="https://openreview.net/forum?id=CSIo4D7xBG",
    )
    return ReportCard(
        result=result,
        manifest=manifest,
        reproduction_command="uv run bench-audit run --adapter webarena --probe p1_gold_answer_leak",
        raw_data_url="https://example.invalid/raw.jsonl",
        interpretation="WebArena's task config exposes reference answers; a lazy agent achieves 97% via file:// reads.",
    )


def test_json_roundtrip(tmp_path: Path) -> None:
    report = _make_report()
    out = write_json_report(report, tmp_path / "report.json")
    assert out.exists()
    text = out.read_text()
    assert '"verdict": "fail"' in text
    assert '"effect_size": 0.97' in text


def test_markdown_renders(tmp_path: Path) -> None:
    md = render_markdown_report(_make_report())
    assert "bench-audit report card" in md
    assert "p1_gold_answer_leak" in md
    assert "0.9700" in md  # effect_size formatted to 4 places
    assert "file:// reads" in md


def test_pdf_raises_without_weasyprint(tmp_path: Path) -> None:
    try:
        import weasyprint  # noqa: F401
    except ImportError:
        from bench_audit.reporting import write_pdf_report

        with pytest.raises(RuntimeError, match="weasyprint"):
            write_pdf_report(_make_report(), tmp_path / "r.pdf")
    else:
        from bench_audit.reporting import write_pdf_report

        # If installed, render and assert file exists.
        out = write_pdf_report(_make_report(), tmp_path / "r.pdf")
        assert out.exists()
