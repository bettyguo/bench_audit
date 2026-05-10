"""P6 — eval-set-visibility probe."""

from __future__ import annotations

from pathlib import Path

import pytest

from bench_audit.adapters.gaia import GAIAAdapter
from bench_audit.adapters.swebench_verified import SWEBenchVerifiedAdapter
from bench_audit.adapters.webarena import WebArenaAdapter
from bench_audit.probes.eval_set_visibility import EvalSetVisibilityProbe


@pytest.fixture
def swe() -> SWEBenchVerifiedAdapter:
    a = SWEBenchVerifiedAdapter(
        fixture_dir=Path(__file__).resolve().parents[2] / "fixtures" / "swebench_verified" / "mini"
    )
    a.load_eval_set(Path("/tmp"))
    return a


@pytest.fixture
def webarena() -> WebArenaAdapter:
    a = WebArenaAdapter(
        fixture_dir=Path(__file__).resolve().parents[2] / "fixtures" / "webarena" / "mini"
    )
    a.load_eval_set(Path("/tmp"))
    return a


@pytest.fixture
def gaia() -> GAIAAdapter:
    a = GAIAAdapter(fixture_dir=Path(__file__).resolve().parents[2] / "fixtures" / "gaia" / "mini")
    a.load_eval_set(Path("/tmp"))
    return a


def test_probe_runs_on_all_three(swe, webarena, gaia) -> None:
    probe = EvalSetVisibilityProbe()
    for a in (swe, webarena, gaia):
        r = probe.run(a)
        assert r.sample_size == 3
        assert r.adapter_name == a.name


def test_swe_has_contamination_statement(swe: SWEBenchVerifiedAdapter) -> None:
    probe = EvalSetVisibilityProbe()
    r = probe.run(swe)
    assert "openai.com" in r.notes


def test_gaia_marked_gated(gaia: GAIAAdapter) -> None:
    probe = EvalSetVisibilityProbe()
    r = probe.run(gaia)
    assert "requires_auth: True" in r.notes
