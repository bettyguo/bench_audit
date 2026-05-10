"""Leaderboard site generator."""

from __future__ import annotations

from pathlib import Path

from bench_audit.reporting.leaderboard import build_site
from bench_audit.schemas import ProbeResult


def _write_result(results_dir: Path, adapter: str, probe: str, verdict: str, effect: float) -> None:
    r = ProbeResult(
        probe_name=probe,
        probe_version="0.1.0",
        adapter_name=adapter,
        adapter_version="0.1.0",
        benchmark_version="v1",
        verdict=verdict,
        effect_size=effect,
        effect_size_kind="proportion",
        ci_low=max(0.0, effect - 0.04),
        ci_high=min(1.0, effect + 0.04),
        ci_method="wilson",
        sample_size=500,
        test_set_hash="a" * 64,
        harness_version="0.1.0a0",
    )
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / f"{adapter}__{probe}.json").write_text(r.model_dump_json(indent=2))


def test_build_site_empty(tmp_path: Path) -> None:
    site = build_site(tmp_path / "results", tmp_path / "site")
    assert (site / "index.html").exists()


def test_build_site_with_results(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _write_result(results, "webarena", "p1_gold_answer_leak", "fail", 0.97)
    _write_result(results, "swebench_verified", "p4_harness_injection", "fail", 0.29)
    _write_result(results, "gaia", "p1_gold_answer_leak", "fail", 0.98)
    site = build_site(results, tmp_path / "site")

    index = (site / "index.html").read_text()
    assert "webarena" in index
    assert "swebench_verified" in index
    assert "gaia" in index
    assert "p1_gold_answer_leak" in index
    assert "p4_harness_injection" in index

    assert (site / "benchmark" / "webarena.html").exists()
    assert (site / "benchmark" / "swebench_verified.html").exists()
    assert (site / "probe" / "p1_gold_answer_leak.html").exists()
    assert (site / "probe" / "p4_harness_injection.html").exists()
    assert (site / "static" / "leaderboard.css").exists()
    assert (site / "results.json").exists()


def test_json_links_resolve_in_built_site(tmp_path: Path) -> None:
    """Every <a href> pointing at a results JSON in the rendered HTML must
    correspond to an actual file under the site tree. The per-result JSONs
    are copied into `_site/results/` during build so the static deploy
    target is self-contained."""
    import re

    results = tmp_path / "results"
    _write_result(results, "webarena", "p1_gold_answer_leak", "fail", 0.97)
    _write_result(results, "swebench_verified", "p4_harness_injection", "fail", 0.29)
    site = build_site(results, tmp_path / "site")

    # The JSON files must have been copied into site/results/
    assert (site / "results" / "webarena__p1_gold_answer_leak.json").exists()
    assert (site / "results" / "swebench_verified__p4_harness_injection.json").exists()

    # Every href to a .json on each rendered page must point at a file that exists.
    href_re = re.compile(r'href="([^"]+\.json)"')
    pages = {
        site / "index.html": site,
        site / "benchmark" / "webarena.html": site / "benchmark",
        site / "probe" / "p1_gold_answer_leak.html": site / "probe",
    }
    for page, page_dir in pages.items():
        for ref in href_re.findall(page.read_text(encoding="utf-8")):
            resolved = (page_dir / ref).resolve()
            assert resolved.exists(), (
                f"page {page.relative_to(site)} has dangling JSON link {ref!r} "
                f"(resolved={resolved})"
            )


def test_skips_invalid_json(tmp_path: Path) -> None:
    results = tmp_path / "results"
    results.mkdir()
    (results / "bad.json").write_text("not valid json")
    (results / "not-a-probe-result.json").write_text('{"foo": "bar"}')
    site = build_site(results, tmp_path / "site")
    # Should still render an empty index without crashing.
    assert (site / "index.html").exists()
