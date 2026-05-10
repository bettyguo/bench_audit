"""P4 — harness-injection probe unit tests.

We test on (a) the synthetic adapter (clean grader → no triggers expected on
most patterns) and (b) the SWE-bench adapter (BA-07 trigger expected since
its score() reads `resolved` directly without re-running).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bench_audit.adapters.swebench_verified import SWEBenchVerifiedAdapter
from bench_audit.probes.harness_injection import HarnessInjectionProbe

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "swebench_verified" / "mini"


@pytest.fixture
def swe() -> SWEBenchVerifiedAdapter:
    a = SWEBenchVerifiedAdapter(fixture_dir=FIXTURE)
    a.load_eval_set(cache_dir=Path("/tmp"))
    return a


def test_probe_applies_to_anything(synthetic_adapter, swe) -> None:
    probe = HarnessInjectionProbe()
    assert probe.applies_to(synthetic_adapter)
    assert probe.applies_to(swe)


def test_probe_returns_seven_pattern_checklist(synthetic_adapter) -> None:
    probe = HarnessInjectionProbe()
    r = probe.run(synthetic_adapter)
    assert r.sample_size == 7
    assert r.ci_method == "clopper_pearson"


def test_probe_triggers_ba02_on_swebench(swe: SWEBenchVerifiedAdapter) -> None:
    """SWE-bench fixture exposes `gold_patch` in the task payload — Berkeley's
    BA-02 pattern. The detector should flag it."""
    probe = HarnessInjectionProbe()
    r = probe.run(swe)
    assert "BA-02" in r.notes
    assert "TRIGGERED" in r.notes
    assert r.effect_size > 0.0
    assert r.verdict == "fail"


def test_probe_includes_pattern_names(synthetic_adapter) -> None:
    probe = HarnessInjectionProbe()
    r = probe.run(synthetic_adapter)
    for pid, _ in HarnessInjectionProbe.PATTERNS:
        assert pid in r.notes


def test_probe_is_deterministic(swe: SWEBenchVerifiedAdapter) -> None:
    probe = HarnessInjectionProbe()
    a = probe.run(swe)
    b = probe.run(swe)
    assert a.effect_size == b.effect_size
    assert a.notes == b.notes


def test_ba05_does_not_false_positive_on_routine_normalization(
    swe: SWEBenchVerifiedAdapter,
) -> None:
    """SWE-bench's grader does .strip().lower() — routine, NOT BA-05.

    Tightened detector (post area-chair review): BA-05 fires only on
    re.sub(r"\\W"|"[^\\w]"...), string.punctuation, or whitespace collapse.
    """
    probe = HarnessInjectionProbe()
    r = probe.run(swe)
    # Pull out the BA-05 line specifically and assert it is 'clean'
    ba05_lines = [ln for ln in r.notes.split("\n") if "BA-05" in ln]
    assert ba05_lines
    assert "clean" in ba05_lines[0]


def test_ba05_fires_on_gaia_aggressive_normalizer() -> None:
    """GAIA's grader calls _gaia_normalize which strips ALL whitespace
    + punctuation (Berkeley's BA-05 finding). Detector must fire."""
    from bench_audit.adapters.gaia import GAIAAdapter

    g = GAIAAdapter(fixture_dir=Path(__file__).resolve().parents[2] / "fixtures" / "gaia" / "mini")
    g.load_eval_set(Path("/tmp"))
    probe = HarnessInjectionProbe()
    r = probe.run(g)
    ba05_lines = [ln for ln in r.notes.split("\n") if "BA-05" in ln]
    assert ba05_lines
    assert "TRIGGERED" in ba05_lines[0]
