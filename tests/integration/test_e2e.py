"""End-to-end: run a probe via the static harness, render JSON + Markdown
report cards, build a leaderboard, and verify the leaderboard has the
right cells.

This is the smoke test for the slice integration. If this fails, the
quickstart in the README does not work.
"""

from __future__ import annotations

from pathlib import Path

from bench_audit.adapters.gaia import GAIAAdapter
from bench_audit.adapters.swebench_verified import SWEBenchVerifiedAdapter
from bench_audit.adapters.webarena import WebArenaAdapter
from bench_audit.harness import run_probe_static
from bench_audit.probes.eval_set_visibility import EvalSetVisibilityProbe
from bench_audit.probes.gold_answer_leak import GoldAnswerLeakProbe
from bench_audit.probes.harness_injection import HarnessInjectionProbe
from bench_audit.reporting import (
    render_markdown_report,
)
from bench_audit.reporting.leaderboard import build_site
from bench_audit.schemas import ReportCard

ROOT = Path(__file__).resolve().parents[2]


def _swe() -> SWEBenchVerifiedAdapter:
    a = SWEBenchVerifiedAdapter(fixture_dir=ROOT / "fixtures" / "swebench_verified" / "mini")
    a.load_eval_set(Path("/tmp"))
    return a


def _webarena() -> WebArenaAdapter:
    a = WebArenaAdapter(fixture_dir=ROOT / "fixtures" / "webarena" / "mini")
    a.load_eval_set(Path("/tmp"))
    return a


def _gaia() -> GAIAAdapter:
    a = GAIAAdapter(fixture_dir=ROOT / "fixtures" / "gaia" / "mini")
    a.load_eval_set(Path("/tmp"))
    return a


def test_full_pipeline_three_adapters_three_probes(tmp_path: Path) -> None:
    """Run P1+P4+P6 across SWE-bench / WebArena / GAIA, render markdown,
    build leaderboard, verify all 9 cells exist on the leaderboard."""
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    adapters = {"swe": _swe(), "webarena": _webarena(), "gaia": _gaia()}
    probes = [GoldAnswerLeakProbe(), HarnessInjectionProbe(), EvalSetVisibilityProbe()]

    n_results = 0
    for _adapter_label, adapter in adapters.items():
        for probe in probes:
            if not probe.applies_to(adapter):
                continue
            result = run_probe_static(probe, adapter, out_dir=results_dir)
            assert result.adapter_name == adapter.name
            assert result.probe_name == probe.name

            # Render report card
            report = ReportCard(
                result=result,
                manifest=adapter.manifest(),
                reproduction_command=(
                    f"bench-audit run --adapter {adapter.name} --probe {probe.name}"
                ),
                interpretation=f"Test fixture run of {probe.name} against {adapter.name}.",
            )
            md_text = render_markdown_report(report)
            assert "bench-audit report card" in md_text
            assert adapter.name in md_text
            assert probe.name in md_text
            (results_dir / f"{adapter.name}__{probe.name}.md").write_text(md_text)

            n_results += 1

    # 3 adapters × 3 probes (each probe applies to each adapter)
    assert n_results == 9

    # Build leaderboard, verify cells
    site = build_site(results_dir, tmp_path / "site")
    index_html = (site / "index.html").read_text()
    for adapter in adapters.values():
        assert adapter.name in index_html
    for probe in probes:
        assert probe.name in index_html
    # per-benchmark + per-probe pages exist
    for adapter in adapters.values():
        assert (site / "benchmark" / f"{adapter.name}.html").exists()
    for probe in probes:
        assert (site / "probe" / f"{probe.name}.html").exists()


def test_json_roundtrip_through_filesystem(tmp_path: Path) -> None:
    """Serialize a ProbeResult to disk; deserialize and verify it round-trips."""
    swe = _swe()
    result = run_probe_static(GoldAnswerLeakProbe(), swe, out_dir=tmp_path)
    json_path = tmp_path / "swebench_verified__p1_gold_answer_leak.json"
    assert json_path.exists()

    # Load the report card via the leaderboard discovery
    from bench_audit.reporting.leaderboard import discover_results

    discovered = discover_results(tmp_path)
    assert len(discovered) == 1
    assert discovered[0].adapter_name == "swebench_verified"
    assert discovered[0].probe_name == "p1_gold_answer_leak"
    assert discovered[0].effect_size == result.effect_size


def test_report_card_carries_caveat_block_when_overrides_set(tmp_path: Path) -> None:
    """When a probe issues a verdict with allow_small_n or allow_wide_ci, the
    report card must show that as a caveat so readers can see what was
    waived."""
    swe = _swe()
    result = run_probe_static(GoldAnswerLeakProbe(), swe)
    assert result.allow_small_n is True  # n=5 < 30
    report = ReportCard(
        result=result,
        manifest=swe.manifest(),
        reproduction_command="...",
        interpretation="...",
    )
    md = render_markdown_report(report)
    assert "Caveats" in md
    assert "allow_small_n" in md
