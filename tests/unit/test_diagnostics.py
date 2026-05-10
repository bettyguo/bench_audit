"""bench-audit doctor diagnostics."""

from __future__ import annotations

from bench_audit.diagnostics import (
    check_adapters,
    check_eval_set_hash_pins,
    check_no_eval_set_in_repo,
    check_probes,
    check_python,
    environment_summary,
    run_all_checks,
)


def test_python_check_passes() -> None:
    r = check_python()
    assert r.status == "ok"


def test_adapters_check_finds_three_plus() -> None:
    r = check_adapters()
    # Our v0.1 ships 3 adapters; should be ok.
    assert r.status == "ok"
    assert "swebench_verified" in r.message
    assert "webarena" in r.message
    assert "gaia" in r.message


def test_probes_check_finds_six_plus() -> None:
    r = check_probes()
    assert r.status == "ok"
    assert "p1_gold_answer_leak" in r.message


def test_eval_set_hash_pins_flags_pending() -> None:
    # v0.1 adapters use 'pending-first-fetch' until the first real download.
    r = check_eval_set_hash_pins()
    # Should be 'warn' because adapter constructors with no fixture_dir produce
    # 'pending-first-fetch' hashes. This is the expected pre-launch state.
    assert r.status == "warn"
    assert "pending" in r.message.lower() or "unpinned" in r.message.lower()


def test_no_eval_set_in_repo() -> None:
    r = check_no_eval_set_in_repo()
    # Fixtures should all be small + synthetic; this should pass.
    assert r.status == "ok"


def test_run_all_checks_returns_records() -> None:
    results = run_all_checks()
    assert len(results) >= 10
    statuses = {c.status for c in results}
    assert statuses <= {"ok", "warn", "fail"}


def test_environment_summary_has_keys() -> None:
    env = environment_summary()
    assert "python" in env
    assert "bench_audit" in env
    assert "platform" in env
