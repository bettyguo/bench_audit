"""bench-audit: an automated probe suite for agent benchmarks."""

from importlib.metadata import PackageNotFoundError, version

from bench_audit.schemas import (
    BenchmarkManifest,
    Prediction,
    ProbeResult,
    ReportCard,
    Task,
    Trajectory,
)

try:
    __version__ = version("bench-audit")
except PackageNotFoundError:
    __version__ = "0.1.0a0+dev"

__all__ = [
    "BenchmarkManifest",
    "Prediction",
    "ProbeResult",
    "ReportCard",
    "Task",
    "Trajectory",
    "__version__",
]
