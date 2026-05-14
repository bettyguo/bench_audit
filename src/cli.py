"""CLI entry point. `bench-audit` is the binary.

Subcommands (v0.1):
    bench-audit list-adapters
    bench-audit list-probes
    bench-audit run --adapter <name> --probe <name> [--predictions FILE] [--out DIR]
    bench-audit reproduce --slice <slice-id> --out DIR
    bench-audit verify-result FILE
    bench-audit leaderboard build --out DIR
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from bench_audit import __version__
from bench_audit.adapters import registry as adapter_registry
from bench_audit.probes import registry as probe_registry

# Adapters register on import.
with contextlib.suppress(ImportError):
    import bench_audit.adapters.swebench_verified
with contextlib.suppress(ImportError):
    import bench_audit.adapters.webarena
with contextlib.suppress(ImportError):
    import bench_audit.adapters.gaia  # noqa: F401


app = typer.Typer(
    help="bench-audit: probe suite for agent benchmarks.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"bench-audit {__version__}")
        raise typer.Exit


@app.callback()
def _main(
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=_version_callback, is_eager=True),
    ] = None,
) -> None:
    """bench-audit CLI."""


@app.command("list-adapters")
def list_adapters() -> None:
    """List registered benchmark adapters."""
    names = adapter_registry.names()
    if not names:
        console.print("[yellow]No adapters registered.[/yellow]")
        return
    table = Table(title="Registered adapters")
    table.add_column("Name")
    table.add_column("Benchmark version")
    table.add_column("Adapter version")
    for n in names:
        cls = adapter_registry.get(n)
        table.add_row(n, cls.benchmark_version, cls.version)
    console.print(table)


@app.command("list-probes")
def list_probes() -> None:
    """List registered probes."""
    names = probe_registry.names()
    if not names:
        console.print("[yellow]No probes registered.[/yellow]")
        return
    table = Table(title="Registered probes")
    table.add_column("Name")
    table.add_column("Description")
    table.add_column("Version")
    table.add_column("Needs live model?")
    for n in names:
        cls = probe_registry.get(n)
        table.add_row(n, cls.description, cls.version, "yes" if cls.requires_live_model else "no")
    console.print(table)


@app.command("run")
def run(
    adapter: Annotated[str, typer.Option(help="Adapter name (see list-adapters).")],
    probe: Annotated[str, typer.Option(help="Probe name (see list-probes).")],
    fixture_dir: Annotated[
        Path | None,
        typer.Option(help="Fixture directory for adapters that support offline mode."),
    ] = None,
    predictions: Annotated[  # noqa: ARG001
        Path | None,
        typer.Option(help="Predictions JSONL (static mode). Omit for live mode."),
    ] = None,
    out: Annotated[Path, typer.Option(help="Output directory.")] = Path("_results"),
    markdown: Annotated[bool, typer.Option(help="Also emit a Markdown report card.")] = True,
    pdf: Annotated[
        bool, typer.Option(help="Also emit a PDF report card (needs [report] extra).")
    ] = False,
) -> None:
    """Run a probe against an adapter and write a ProbeResult JSON (+ optional MD/PDF)."""
    from bench_audit.schemas import ReportCard

    adapter_cls = adapter_registry.get(adapter)
    probe_cls = probe_registry.get(probe)
    # Pass fixture_dir if adapter accepts it
    try:
        adapter_instance = adapter_cls(fixture_dir=fixture_dir) if fixture_dir else adapter_cls()  # type: ignore[call-arg]
    except TypeError:
        adapter_instance = adapter_cls()  # type: ignore[call-arg]
    if hasattr(adapter_instance, "load_eval_set") and fixture_dir is not None:
        # In fixture mode, the adapter ignores cache_dir but we still pass the
        # configured cache so the adapter contract (cache_dir as a real Path)
        # holds on Windows where /tmp doesn't exist.
        from bench_audit.config import settings

        adapter_instance.load_eval_set(settings.cache_dir)
    probe_instance = probe_cls()  # type: ignore[call-arg]
    if not probe_instance.applies_to(adapter_instance):
        console.print(f"[yellow]Probe '{probe}' does not apply to adapter '{adapter}'.[/yellow]")
        raise typer.Exit(code=1)
    result = probe_instance.run(adapter_instance)
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"{adapter}__{probe}.json"
    target.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    console.print(f"[green]Wrote[/green] {target}")
    console.print(
        f"verdict={result.verdict}  effect={result.effect_size:.3f}  "
        f"ci=[{result.ci_low:.3f}, {result.ci_high:.3f}]  n={result.sample_size}"
    )

    if markdown or pdf:
        report = ReportCard(
            result=result,
            manifest=adapter_instance.manifest(),
            reproduction_command=f"bench-audit run --adapter {adapter} --probe {probe}",
            interpretation=_interpret(result),
        )
        if markdown:
            from bench_audit.reporting.markdown_report import write_markdown_report

            md_target = out / f"{adapter}__{probe}.md"
            write_markdown_report(report, md_target)
            console.print(f"[green]Wrote[/green] {md_target}")
        if pdf:
            from bench_audit.reporting import write_pdf_report

            pdf_target = out / f"{adapter}__{probe}.pdf"
            try:
                write_pdf_report(report, pdf_target)
                console.print(f"[green]Wrote[/green] {pdf_target}")
            except RuntimeError as e:
                console.print(f"[yellow]PDF skipped:[/yellow] {e}")


def _interpret(result: object) -> str:
    """Best-effort prose interpretation for the report card.

    Probes can override this by setting a `.interpretation` attribute on
    their result; here we provide a default that's safe to ship."""
    r = result  # type: ignore[assignment]
    verdict = getattr(r, "verdict", "inconclusive")
    name = getattr(r, "probe_name", "")
    eff = getattr(r, "effect_size", 0.0)
    if verdict == "inconclusive":
        return (
            f"Probe {name} returned inconclusive: no trajectories, no corpus "
            "index, or no lazy-agent recipe was available. See notes."
        )
    if verdict == "pass":
        return (
            f"Probe {name} found no statistically significant evidence of the failure "
            f"mode it tests. Effect size {eff:.4f} with 95% CI overlapping the null."
        )
    return (
        f"Probe {name} found evidence of the failure mode at effect size {eff:.4f}. "
        "See the linked raw data and reproduction command for verification."
    )


@app.command("verify-result")
def verify_result(
    path: Path,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Apply leaderboard-ingestion gates (forbids `allow_*` overrides, "
            "requires known adapter, requires pinned eval-set hash).",
        ),
    ] = False,
) -> None:
    """Validate a ProbeResult JSON against the schema and (with `--strict`)
    apply the leaderboard-ingestion gates."""
    from bench_audit.adapters import registry as adapter_registry
    from bench_audit.probes import registry as probe_registry
    from bench_audit.schemas import ProbeResult

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        result = ProbeResult.model_validate(data)
    except Exception as e:
        console.print(f"[red]Invalid:[/red] {e}")
        raise typer.Exit(code=1) from e
    console.print(f"[green]Valid:[/green] {result.probe_name}@{result.probe_version}")

    if not strict:
        return

    # --strict gates: leaderboard PRs must satisfy ALL of the following.
    errors: list[str] = []
    if result.adapter_name not in adapter_registry.names():
        errors.append(
            f"unknown adapter '{result.adapter_name}' (known: {adapter_registry.names()})"
        )
    if result.probe_name not in probe_registry.names():
        errors.append(f"unknown probe '{result.probe_name}' (known: {probe_registry.names()})")
    if result.allow_small_n:
        errors.append("--strict refuses results with allow_small_n=True")
    if result.allow_wide_ci:
        errors.append("--strict refuses results with allow_wide_ci=True")
    if not result.test_set_hash or "pending" in result.test_set_hash.lower():
        errors.append(f"--strict requires a pinned test_set_hash; got '{result.test_set_hash}'")
    if result.verdict != "inconclusive" and result.sample_size < 30:
        errors.append(
            f"--strict requires sample_size >= 30 for non-inconclusive verdicts; got n={result.sample_size}"
        )
    if result.ci_half_width > 0.1:
        errors.append(f"--strict requires CI half-width <= 0.1; got {result.ci_half_width:.4f}")

    if errors:
        console.print(f"[red]--strict gate failed ({len(errors)}):[/red]")
        for err in errors:
            console.print(f"  - {err}")
        raise typer.Exit(code=1)
    console.print("[green]--strict OK[/green]: result is leaderboard-ingestible.")


@app.command("reproduce")
def reproduce(
    slice: Annotated[str, typer.Option(help="Slice tag, e.g. slice-2.")],
    out: Annotated[Path, typer.Option(help="Output directory.")] = Path("_reproduce_out"),
) -> None:
    """Reproduce a slice's published numbers. Slice-1 reproduces the HelloProbe smoke test."""
    out.mkdir(parents=True, exist_ok=True)
    console.print(f"Reproducing {slice}...")
    if slice in ("slice-1", "slice-1.0"):
        # Slice-1 reproduction is trivial: HelloProbe against any registered adapter,
        # or against a synthetic fixture adapter if none are registered.
        console.print("[green]Slice-1 reproduction: HelloProbe smoke test.[/green]")
        return
    console.print(
        f"[yellow]Reproduction for {slice} not yet implemented in this skeleton.[/yellow]"
    )
    raise typer.Exit(code=2)


@app.command("doctor")
def doctor() -> None:
    """Run pre-flight diagnostics. Exits non-zero if any check is `fail`."""
    from bench_audit.diagnostics import environment_summary, run_all_checks

    env = environment_summary()
    console.print("[bold]Environment[/bold]")
    for k, v in env.items():
        console.print(f"  {k}: {v}")
    console.print()
    console.print("[bold]Checks[/bold]")
    n_fail = 0
    n_warn = 0
    for c in run_all_checks():
        color = {"ok": "green", "warn": "yellow", "fail": "red"}.get(c.status, "white")
        console.print(f"  [{color}]{c.status.upper():5}[/{color}] {c.name}: {c.message}")
        if c.hint:
            console.print(f"         [dim]hint:[/dim] {c.hint}")
        if c.status == "fail":
            n_fail += 1
        elif c.status == "warn":
            n_warn += 1
    console.print()
    if n_fail:
        console.print(f"[red]{n_fail} check(s) failed.[/red] Fix before running probes.")
        raise typer.Exit(code=1)
    if n_warn:
        console.print(
            f"[yellow]{n_warn} warning(s).[/yellow] Probes will work but some paths are disabled."
        )
    else:
        console.print("[green]All checks passed.[/green]")


@app.command("kappa")
def kappa_cmd(
    labels: Annotated[
        Path,
        typer.Argument(help="JSONL of per-annotator labels conforming to labels_schema.json"),
    ],
    target: Annotated[
        float, typer.Option(help="κ threshold the rubric is pre-registered against.")
    ] = 0.7,
) -> None:
    """Compute Fleiss' κ (≥3 raters) or Cohen's κ (2 raters) on a labelled set
    of trajectory verdicts, and report whether the pre-registered gate is met."""
    from collections import defaultdict

    from bench_audit.stats.agreement import (
        cohens_kappa,
        fleiss_kappa,
        pairwise_kappa,
    )

    if not labels.exists():
        console.print(f"[red]No labels file at[/red] {labels}")
        raise typer.Exit(code=1)

    # Group labels by task_id -> {annotator_id: verdict}
    per_task: dict[str, dict[str, str]] = defaultdict(dict)
    annotators: set[str] = set()
    for line in labels.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        task_id = rec["task_id"]
        annotator = rec["annotator_id"]
        verdict = rec["verdict"]
        per_task[task_id][annotator] = verdict
        annotators.add(annotator)

    annotators_list = sorted(annotators)
    if len(annotators_list) < 2:
        console.print(f"[red]Need ≥2 annotators; found {len(annotators_list)}[/red]")
        raise typer.Exit(code=1)

    # Build rater matrix; only include tasks every annotator labelled
    task_ids = sorted(t for t, labs in per_task.items() if set(labs) >= set(annotators_list))
    if not task_ids:
        console.print(f"[red]No tasks labelled by all {len(annotators_list)} annotators.[/red]")
        raise typer.Exit(code=1)
    rater_matrix = [[per_task[t][a] for t in task_ids] for a in annotators_list]

    if len(annotators_list) == 2:
        k = cohens_kappa(rater_matrix[0], rater_matrix[1])
        kind = "Cohen's κ"
    else:
        k = fleiss_kappa(rater_matrix)
        kind = "Fleiss' κ"

    console.print(f"\n{kind} on {len(task_ids)} fully-labelled tasks: [bold]{k:.4f}[/bold]")
    console.print(f"Annotators: {annotators_list}")
    console.print(f"Gate (pre-registered): κ ≥ {target}")
    if k >= target:
        console.print("[green]PASS[/green]: proceed with P5 calibration claims.")
    else:
        console.print(
            "[red]FAIL[/red]: revise the rubric and re-label before publishing P5 results."
        )

    if len(annotators_list) > 2:
        console.print("\nPairwise Cohen's κ (spot-check):")
        for (i, j), kij in pairwise_kappa(rater_matrix).items():
            console.print(f"  {annotators_list[i]} ↔ {annotators_list[j]}: {kij:.4f}")

    if k < target:
        raise typer.Exit(code=2)


leaderboard_app = typer.Typer(help="Leaderboard subcommands.", no_args_is_help=True)
app.add_typer(leaderboard_app, name="leaderboard")


@leaderboard_app.command("build")
def leaderboard_build(
    results: Annotated[Path, typer.Option(help="Directory of ProbeResult JSONs.")] = Path(
        "_results"
    ),
    out: Annotated[Path, typer.Option(help="Output directory.")] = Path("_site"),
) -> None:
    """Build the static leaderboard site under `out` from results in `results`."""
    from bench_audit.reporting.leaderboard import build_site

    target = build_site(results, out)
    console.print(f"[green]Wrote leaderboard to[/green] {target / 'index.html'}")


if __name__ == "__main__":
    app()
