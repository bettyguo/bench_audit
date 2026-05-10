"""task_iter() raises AdapterError if neither a fixture_dir was set at
construction time nor load_eval_set was called explicitly. Otherwise it
yields tasks from the loaded set."""

from __future__ import annotations

from pathlib import Path

import pytest

from bench_audit.adapters.gaia import GAIAAdapter
from bench_audit.adapters.swebench_verified import SWEBenchVerifiedAdapter
from bench_audit.adapters.webarena import WebArenaAdapter
from bench_audit.errors import AdapterError

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def test_webarena_task_iter_without_load_raises() -> None:
    a = WebArenaAdapter()  # no fixture_dir, no load_eval_set
    with pytest.raises(AdapterError, match="load_eval_set"):
        next(a.task_iter())


def test_gaia_task_iter_without_load_raises() -> None:
    a = GAIAAdapter()
    with pytest.raises(AdapterError, match="load_eval_set"):
        next(a.task_iter())


def test_swebench_task_iter_without_load_raises() -> None:
    a = SWEBenchVerifiedAdapter()
    with pytest.raises(AdapterError, match="load_eval_set"):
        next(a.task_iter())


def test_webarena_task_iter_with_fixture_dir_works_implicitly() -> None:
    """fixture_dir is enough — no explicit load_eval_set call needed."""
    a = WebArenaAdapter(fixture_dir=_FIXTURES / "webarena" / "mini")
    tasks = list(a.task_iter())
    assert len(tasks) == 5


def test_gaia_task_iter_with_fixture_dir_works_implicitly() -> None:
    a = GAIAAdapter(fixture_dir=_FIXTURES / "gaia" / "mini")
    tasks = list(a.task_iter())
    assert len(tasks) == 5


def test_swebench_task_iter_with_fixture_dir_works_implicitly() -> None:
    a = SWEBenchVerifiedAdapter(fixture_dir=_FIXTURES / "swebench_verified" / "mini")
    tasks = list(a.task_iter())
    assert len(tasks) == 5
