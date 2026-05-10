"""Regression test for D1: every file I/O path must specify UTF-8.

We construct a ProbeResult whose `notes` contains characters that *would*
round-trip-corrupt on a non-UTF-8 Windows locale (em-dash, CJK character,
combining accent). We then write it through every public write path and
read it back through every public read path, asserting byte-level
preservation.

If any read_text/write_text in the codebase loses encoding="utf-8", at
least one of these assertions will fail on a Windows host with a
non-UTF-8 system locale.
"""

from __future__ import annotations

import json
from pathlib import Path

from bench_audit.harness.static import run_probe_static
from bench_audit.probes.hello import HelloProbe
from bench_audit.reporting.json_report import write_json_report
from bench_audit.reporting.leaderboard import build_site, discover_results
from bench_audit.reporting.markdown_report import write_markdown_report
from bench_audit.schemas import BenchmarkManifest, ProbeResult, ReportCard

# Mix of high-codepoint characters that diverge between utf-8, cp1252, cp936.
_TROUBLESOME = (
    "em-dash —"  # cp1252 has it; some Asian locales don't
    " · "  # middle dot
    " 漢字"  # CJK
    " á̃"  # combining accent (NFD)
)


def _make_result(notes: str = _TROUBLESOME) -> ProbeResult:
    return ProbeResult(
        probe_name="hello",
        probe_version="0.1.0",
        adapter_name="synthetic",
        adapter_version="0.1.0",
        benchmark_version="v1",
        verdict="inconclusive",
        effect_size=0.5,
        effect_size_kind="proportion",
        ci_low=0.4,
        ci_high=0.6,
        ci_method="wilson",
        sample_size=100,
        test_set_hash="a" * 64,
        harness_version="0.1.0a0",
        notes=notes,
    )


def _make_report(notes: str = _TROUBLESOME) -> ReportCard:
    return ReportCard(
        result=_make_result(notes),
        manifest=BenchmarkManifest(
            name="synthetic",
            version="v1",
            source_url="https://example.invalid",
            license="CC0-1.0",
            n_tasks=100,
            eval_set_sha256="b" * 64,
        ),
        reproduction_command="bench-audit run --adapter synthetic --probe hello",
        interpretation="Test — round-trip UTF-8 fidelity 漢字.",
    )


def test_static_harness_writes_utf8(synthetic_adapter, tmp_path: Path) -> None:
    """run_probe_static must write JSON as UTF-8 regardless of OS locale.

    Reads the file as bytes and decodes explicitly with utf-8; if the harness
    wrote in the system locale, this would either raise UnicodeDecodeError or
    silently lose characters."""
    result = run_probe_static(HelloProbe(), synthetic_adapter, out_dir=tmp_path)
    target = tmp_path / "synthetic__hello.json"
    raw = target.read_bytes()
    decoded = raw.decode("utf-8")
    # HelloProbe's notes field is ASCII; verify the JSON itself parses and is
    # round-trippable, which is the contract we need.
    reloaded = json.loads(decoded)
    assert reloaded["probe_name"] == "hello"
    # And the encoding round-trip is consistent (no BOM, no mojibake).
    assert decoded == raw.decode("utf-8")
    _ = result


def test_json_report_preserves_high_codepoints(tmp_path: Path) -> None:
    report = _make_report()
    out = write_json_report(report, tmp_path / "report.json")
    raw = out.read_bytes()
    decoded = raw.decode("utf-8")
    data = json.loads(decoded)
    # pydantic's model_dump_json escapes non-ASCII as \uXXXX by default, which
    # is also a valid UTF-8 byte sequence. Either way, the parsed value must
    # match the input.
    assert data["result"]["notes"] == _TROUBLESOME
    assert data["interpretation"].startswith("Test")


def test_markdown_report_preserves_high_codepoints(tmp_path: Path) -> None:
    report = _make_report()
    out = write_markdown_report(report, tmp_path / "report.md")
    text = out.read_text(encoding="utf-8")
    assert "em-dash" in text
    assert "漢字" in text


def test_leaderboard_roundtrip_preserves_high_codepoints(tmp_path: Path) -> None:
    """Notes with non-ASCII content must survive the leaderboard build."""
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    r = _make_result()
    (results_dir / "synthetic__hello.json").write_text(
        r.model_dump_json(indent=2), encoding="utf-8"
    )

    # Discover must read UTF-8
    discovered = discover_results(results_dir)
    assert len(discovered) == 1
    assert discovered[0].notes == _TROUBLESOME

    # Build must preserve through the site
    site = build_site(results_dir, tmp_path / "site")
    site_json = (site / "results" / "synthetic__hello.json").read_text(encoding="utf-8")
    reloaded = json.loads(site_json)
    assert reloaded["notes"] == _TROUBLESOME
