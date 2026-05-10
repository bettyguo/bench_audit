"""Leaderboard static-site generator.

Reads a directory of ProbeResult JSON files, renders a static index page
plus per-benchmark and per-probe pages. No backend, no database, no
telemetry. Every cell links to the raw data + reproduction command.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from bench_audit.schemas import ProbeResult

_env = Environment(
    loader=PackageLoader("bench_audit", "templates"),
    autoescape=select_autoescape(["html", "xml"]),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


@dataclass(frozen=True)
class Cell:
    adapter_name: str
    probe_name: str
    model_name: str | None
    verdict: str
    effect_size: float
    ci_low: float
    ci_high: float
    sample_size: int
    json_url: str
    reproduction_command: str


def discover_results(results_dir: Path) -> list[ProbeResult]:
    out: list[ProbeResult] = []
    if not results_dir.exists():
        return out
    for p in sorted(results_dir.rglob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        try:
            out.append(ProbeResult.model_validate(data))
        except Exception:
            # Skip non-ProbeResult JSONs (manifest files, etc.).
            continue
    return out


def build_site(results_dir: Path, out_dir: Path) -> Path:
    """Render the leaderboard site under `out_dir`.

    Layout:
      out_dir/
        index.html               # top-level matrix
        benchmark/<name>.html    # per-benchmark page
        probe/<name>.html        # per-probe page
        static/leaderboard.css   # styling
        results.json             # cells data dump for downstream consumers
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "benchmark").mkdir(exist_ok=True)
    (out_dir / "probe").mkdir(exist_ok=True)
    (out_dir / "static").mkdir(exist_ok=True)
    site_results = out_dir / "results"
    site_results.mkdir(exist_ok=True)

    results = discover_results(results_dir)

    # Copy the per-result JSON files into out_dir/results/ so the rendered
    # links resolve when only the site is deployed (e.g., GH Pages serves
    # _site/ but not _results/). Fixes leaderboard 404s in production.
    for src in sorted(results_dir.glob("*.json")) if results_dir.exists() else []:
        try:
            content = src.read_bytes()
        except OSError:
            continue
        (site_results / src.name).write_bytes(content)

    cells: list[Cell] = []
    by_adapter: dict[str, list[Cell]] = defaultdict(list)
    by_probe: dict[str, list[Cell]] = defaultdict(list)
    adapters: set[str] = set()
    probes: set[str] = set()

    for r in results:
        # Link relative to the page that contains it. From _site/index.html the
        # results live at results/<file>.json; from _site/benchmark/X.html they
        # live at ../results/<file>.json.
        rel = f"results/{r.adapter_name}__{r.probe_name}.json"
        repro = f"bench-audit run --adapter {r.adapter_name} --probe {r.probe_name}"
        cell = Cell(
            adapter_name=r.adapter_name,
            probe_name=r.probe_name,
            model_name=r.model_name,
            verdict=r.verdict,
            effect_size=r.effect_size,
            ci_low=r.ci_low,
            ci_high=r.ci_high,
            sample_size=r.sample_size,
            json_url=rel,
            reproduction_command=repro,
        )
        cells.append(cell)
        by_adapter[r.adapter_name].append(cell)
        by_probe[r.probe_name].append(cell)
        adapters.add(r.adapter_name)
        probes.add(r.probe_name)

    # Build the index matrix: rows = adapters, columns = probes, cells = latest result
    matrix: dict[tuple[str, str], Cell] = {}
    for c in cells:
        key = (c.adapter_name, c.probe_name)
        # Last-wins ordering by file enumeration is fine for v0.1; v0.2 will sort by timestamp.
        matrix[key] = c

    index_tmpl = _env.get_template("leaderboard/index.html.j2")
    (out_dir / "index.html").write_text(
        index_tmpl.render(
            adapters=sorted(adapters),
            probes=sorted(probes),
            matrix=matrix,
            n_results=len(cells),
        ),
        encoding="utf-8",
    )

    bench_tmpl = _env.get_template("leaderboard/benchmark.html.j2")
    for adapter in adapters:
        page = bench_tmpl.render(
            adapter=adapter, cells=sorted(by_adapter[adapter], key=lambda c: c.probe_name)
        )
        (out_dir / "benchmark" / f"{adapter}.html").write_text(page, encoding="utf-8")

    probe_tmpl = _env.get_template("leaderboard/probe.html.j2")
    for probe in probes:
        page = probe_tmpl.render(
            probe=probe, cells=sorted(by_probe[probe], key=lambda c: c.adapter_name)
        )
        (out_dir / "probe" / f"{probe}.html").write_text(page, encoding="utf-8")

    css = _env.get_template("leaderboard/leaderboard.css.j2").render()
    (out_dir / "static" / "leaderboard.css").write_text(css, encoding="utf-8")

    # Data dump for downstream consumers
    (out_dir / "results.json").write_text(
        json.dumps(
            [
                {
                    "adapter_name": c.adapter_name,
                    "probe_name": c.probe_name,
                    "model_name": c.model_name,
                    "verdict": c.verdict,
                    "effect_size": c.effect_size,
                    "ci_low": c.ci_low,
                    "ci_high": c.ci_high,
                    "sample_size": c.sample_size,
                    "json_url": c.json_url,
                    "reproduction_command": c.reproduction_command,
                }
                for c in cells
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    return out_dir
