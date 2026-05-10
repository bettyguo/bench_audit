"""Markdown report. Human-readable; embeddable in a paper or README."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from bench_audit.schemas import ReportCard

_env = Environment(
    loader=PackageLoader("bench_audit", "templates"),
    autoescape=select_autoescape(["html", "xml"]),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_markdown_report(report: ReportCard) -> str:
    template = _env.get_template("report_card.md.j2")
    return template.render(report=report, r=report.result, m=report.manifest)


def write_markdown_report(report: ReportCard, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown_report(report), encoding="utf-8")
    return path
