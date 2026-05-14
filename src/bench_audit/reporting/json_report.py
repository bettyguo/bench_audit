"""JSON report. Machine-readable, schema-versioned."""

from __future__ import annotations

from pathlib import Path

from bench_audit.schemas import ReportCard


def write_json_report(report: ReportCard, path: Path) -> Path:
    """Serialize a ReportCard to JSON. Path is created if necessary."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return path
