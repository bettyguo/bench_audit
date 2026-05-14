"""Pre-flight diagnostic checks. Drives `bench-audit doctor`."""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from bench_audit import __version__


@dataclass(frozen=True)
class Check:
    name: str
    status: str  # "ok" | "warn" | "fail"
    message: str
    hint: str | None = None


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def check_python() -> Check:
    major, minor = sys.version_info[:2]
    if (major, minor) >= (3, 11):
        return Check("python", "ok", f"Python {major}.{minor}")
    return Check(
        "python",
        "fail",
        f"Python {major}.{minor} < 3.11",
        hint="Install Python 3.11 or 3.12; bench-audit requires 3.11+.",
    )


def check_core_deps() -> Check:
    required = ("pydantic", "pydantic_settings", "typer", "jinja2", "scipy", "numpy", "polars")
    missing = [name for name in required if not _module_available(name)]
    if not missing:
        return Check("core deps", "ok", "all required runtime deps importable")
    return Check(
        "core deps",
        "fail",
        f"missing: {', '.join(missing)}",
        hint="Run `uv sync` to install runtime deps.",
    )


def check_live_extra() -> Check:
    if _module_available("inspect_ai"):
        return Check("[live] extra", "ok", "inspect-ai available")
    return Check(
        "[live] extra",
        "warn",
        "inspect-ai not installed; live-mode probes disabled",
        hint="Run `uv sync --extra live` to enable live mode.",
    )


def check_report_extra() -> Check:
    if _module_available("weasyprint"):
        return Check("[report] extra", "ok", "weasyprint available")
    return Check(
        "[report] extra",
        "warn",
        "weasyprint not installed; PDF report cards disabled",
        hint="Run `uv sync --extra report` to enable PDF output.",
    )


def check_docker() -> Check:
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return Check(
            "docker",
            "warn",
            "`docker` not on PATH; full-scale reproductions disabled",
            hint="Install Docker if you plan to run real SWE-bench / WebArena evals.",
        )
    return Check("docker", "ok", f"docker at {docker_bin}")


def check_adapters() -> Check:
    from bench_audit.adapters import registry

    names = registry.names()
    if len(names) < 3:
        return Check(
            "adapters",
            "warn",
            f"only {len(names)} adapter(s) registered: {names}",
            hint="Expected at least 3 (swebench_verified, webarena, gaia).",
        )
    return Check("adapters", "ok", f"{len(names)} registered: {', '.join(names)}")


def check_probes() -> Check:
    from bench_audit.probes import registry

    names = registry.names()
    if len(names) < 6:
        return Check(
            "probes",
            "warn",
            f"only {len(names)} probe(s) registered: {names}",
            hint="Expected at least 6 (hello, p1, p2, p4, p5, p6).",
        )
    return Check("probes", "ok", f"{len(names)} registered: {', '.join(names)}")


def check_fixtures() -> Check:
    root = _project_root()
    if root is None:
        return Check(
            "fixtures",
            "warn",
            "not running from a source checkout; fixture probe skipped",
        )
    expected = (
        root / "fixtures/swebench_verified/mini/tasks.jsonl",
        root / "fixtures/webarena/mini/tasks.jsonl",
        root / "fixtures/gaia/mini/tasks.jsonl",
        root / "fixtures/trajectories/mini/trajectories.jsonl",
    )
    missing = [p for p in expected if not p.exists()]
    if missing:
        return Check(
            "fixtures",
            "warn",
            f"missing {len(missing)} fixture(s)",
            hint=f"Expected fixture files: {[str(p) for p in missing]}.",
        )
    return Check("fixtures", "ok", "all mini fixtures present")


def check_results_dir() -> Check:
    from bench_audit.config import settings

    d = settings.results_dir
    if not d.exists():
        return Check("results dir", "ok", f"results dir does not exist (will be created): {d}")
    files = list(d.glob("*.json"))
    return Check("results dir", "ok", f"{d}: {len(files)} result(s)")


def check_cache_dir() -> Check:
    from bench_audit.config import settings

    d = settings.cache_dir
    return Check(
        "cache dir",
        "ok",
        f"cache: {d}{' (exists)' if d.exists() else ' (will be created)'}",
    )


def check_eval_set_hash_pins() -> Check:
    """Adapters that have not yet pinned their eval-set hash should be flagged."""
    from bench_audit.adapters import registry

    unpinned: list[str] = []
    for name in registry.names():
        cls = registry.get(name)
        try:
            instance = cls()  # type: ignore[call-arg]
            m = instance.manifest()
            if not m.eval_set_sha256 or "pending" in m.eval_set_sha256.lower():
                unpinned.append(name)
        except Exception:
            unpinned.append(name)
    if unpinned:
        return Check(
            "eval-set hash pins",
            "warn",
            f"adapters with unpinned/pending hashes: {unpinned}",
            hint=(
                "These adapters will reject cache hits when first fetched. "
                "After a clean fetch, pin the hash into the adapter's manifest()."
            ),
        )
    return Check("eval-set hash pins", "ok", "all adapters have pinned hashes")


def check_no_eval_set_in_repo() -> Check:
    """The repo must not contain real eval-set content. Fixtures are 5 synthetic
    tasks per adapter. If a fixture grows past 50 lines, flag it."""
    root = _project_root()
    if root is None:
        return Check("eval-set redistribution", "ok", "no source checkout to inspect")
    too_big: list[str] = []
    for p in root.glob("fixtures/*/mini/tasks.jsonl"):
        n_lines = len(p.read_text(encoding="utf-8").splitlines())
        if n_lines > 50:
            too_big.append(f"{p.relative_to(root)} ({n_lines} lines)")
    if too_big:
        return Check(
            "eval-set redistribution",
            "warn",
            f"large fixtures: {too_big}",
            hint=(
                "Fixtures must stay small + synthetic. If real eval-set content has "
                "leaked into a fixture, REMOVE IT before launch."
            ),
        )
    return Check("eval-set redistribution", "ok", "all fixtures within size limit")


CHECKS: tuple[Callable[[], Check], ...] = (
    check_python,
    check_core_deps,
    check_live_extra,
    check_report_extra,
    check_docker,
    check_adapters,
    check_probes,
    check_fixtures,
    check_results_dir,
    check_cache_dir,
    check_eval_set_hash_pins,
    check_no_eval_set_in_repo,
)


def run_all_checks() -> list[Check]:
    return [c() for c in CHECKS]


def environment_summary() -> dict[str, str]:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "bench_audit": __version__,
        "cwd": str(Path.cwd()),
        "PATH_entries": str(len(os.environ.get("PATH", "").split(os.pathsep))),
    }


def _project_root() -> Path | None:
    """Find the project root by walking up from this file until we find pyproject.toml."""
    p = Path(__file__).resolve().parent
    for _ in range(5):
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    return None
