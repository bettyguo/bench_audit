"""PDF report card. One page, WeasyPrint HTML→PDF.

WeasyPrint is an optional dependency (the `[report]` extra). Without it
the function raises a clear hint.
"""

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


def render_html_report(report: ReportCard) -> str:
    template = _env.get_template("report_card.html.j2")
    return template.render(report=report, r=report.result, m=report.manifest)


def write_pdf_report(report: ReportCard, path: Path) -> Path:
    """Render the HTML template, then convert to PDF via WeasyPrint."""
    try:
        from weasyprint import HTML  # type: ignore[import-not-found]
    except ImportError as e:
        raise RuntimeError(
            "PDF output requires weasyprint. Install with `uv sync --extra report`."
        ) from e
    path.parent.mkdir(parents=True, exist_ok=True)
    html_str = render_html_report(report)
    HTML(string=html_str).write_pdf(target=str(path))
    return path
