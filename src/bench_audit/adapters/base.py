"""Adapter ABC and global registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from pathlib import Path

from bench_audit.errors import AdapterError
from bench_audit.schemas import BenchmarkManifest, Prediction, Task


class Adapter(ABC):
    """Abstract base class for a benchmark adapter.

    Implementations:
        - Must set the four class attributes (`name`, `version`, `benchmark_version`,
          and `applicable_probes` — optional whitelist).
        - Must implement the four abstract methods.
        - Must be deterministic: `task_iter()` yields tasks in a stable order
          across calls; `score(task, prediction)` returns the same float for the
          same inputs.
        - Must verify the cached eval set against `manifest().eval_set_sha256` in
          `load_eval_set()`. A hash mismatch raises ManifestMismatchError.
    """

    name: str
    version: str
    benchmark_version: str
    # Optional: if set, restricts which probes the registry will run against
    # this adapter. None = allow all that pass `applies_to()`.
    applicable_probes: tuple[str, ...] | None = None

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        for attr in ("name", "version", "benchmark_version"):
            if not getattr(cls, attr, None):
                raise TypeError(f"{cls.__name__} must set class attribute `{attr}`")

    @abstractmethod
    def load_eval_set(self, cache_dir: Path) -> Iterable[Task]:
        """Idempotent; verifies cached eval set against manifest.eval_set_sha256."""

    @abstractmethod
    def task_iter(self) -> Iterator[Task]:
        """Yields tasks in a stable order."""

    @abstractmethod
    def score(self, task: Task, prediction: Prediction) -> float:
        """Deterministic. Returns the benchmark's native score in [0.0, 1.0]."""

    @abstractmethod
    def manifest(self) -> BenchmarkManifest:
        """Returns benchmark metadata, including the eval-set SHA-256."""

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r} v={self.version}>"


class AdapterRegistry:
    """Global singleton tracking known adapter classes by name."""

    def __init__(self) -> None:
        self._adapters: dict[str, type[Adapter]] = {}

    def register(self, adapter_cls: type[Adapter]) -> type[Adapter]:
        name = adapter_cls.name
        if name in self._adapters and self._adapters[name] is not adapter_cls:
            raise AdapterError(
                f"Adapter name conflict: '{name}' is already registered by "
                f"{self._adapters[name].__module__}.{self._adapters[name].__name__}"
            )
        self._adapters[name] = adapter_cls
        return adapter_cls

    def get(self, name: str) -> type[Adapter]:
        try:
            return self._adapters[name]
        except KeyError as e:
            known = ", ".join(sorted(self._adapters)) or "(none)"
            raise AdapterError(f"Unknown adapter '{name}'. Known: {known}") from e

    def names(self) -> list[str]:
        return sorted(self._adapters)


registry = AdapterRegistry()
