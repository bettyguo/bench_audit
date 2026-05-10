"""P1 — gold-answer leak probe unit tests.

We use the SWE-bench fixture-mode adapter as the probe's target. The adapter's
`lazy_agent_recipe()` returns a `report.resolved=True` Prediction; the
adapter's `score()` accepts that and returns 1.0. The probe should therefore
report leak_rate=1.0 across all 5 fixture tasks.

That isn't a Berkeley-number reproduction (the real number is on n=500), but
it demonstrates the probe correctly identifies a leak-shaped adapter.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bench_audit.adapters.swebench_verified import SWEBenchVerifiedAdapter
from bench_audit.probes.gold_answer_leak import GoldAnswerLeakProbe

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "swebench_verified" / "mini"


@pytest.fixture
def adapter() -> SWEBenchVerifiedAdapter:
    a = SWEBenchVerifiedAdapter(fixture_dir=FIXTURE)
    a.load_eval_set(cache_dir=Path("/tmp"))
    return a


def test_probe_applies_to_swebench(adapter: SWEBenchVerifiedAdapter) -> None:
    probe = GoldAnswerLeakProbe()
    assert probe.applies_to(adapter) is True


def test_probe_detects_full_leak_on_fixture(adapter: SWEBenchVerifiedAdapter) -> None:
    probe = GoldAnswerLeakProbe()
    result = probe.run(adapter)
    # The fixture has 5 tasks; the SWE-bench lazy_agent_recipe is the Berkeley
    # exploit; the adapter accepts the exploit; so the probe sees a 100% leak.
    assert result.effect_size == 1.0
    assert result.sample_size == 5
    # Verdict is forced to inconclusive at n<30 unless allow_small_n is True.
    # The probe sets allow_small_n=True when n<30; verdict should still be "fail"
    # (ci_low > 0.01).
    assert result.allow_small_n is True
    assert result.verdict == "fail"
    assert result.ci_low > 0.0
    assert result.ci_high <= 1.0
    assert result.ci_method == "wilson"


def test_probe_is_deterministic(adapter: SWEBenchVerifiedAdapter) -> None:
    probe = GoldAnswerLeakProbe()
    a = probe.run(adapter)
    b = probe.run(adapter)
    assert a.effect_size == b.effect_size
    assert a.sample_size == b.sample_size
    assert a.test_set_hash == b.test_set_hash
