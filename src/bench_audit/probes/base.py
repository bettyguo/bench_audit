"""Probe ABC and global registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from bench_audit.errors import ProbeError
from bench_audit.schemas import Prediction, ProbeResult

if TYPE_CHECKING:
    from bench_audit.adapters.base import Adapter


class Probe(ABC):
    """Abstract base class for a probe.

    A probe answers a specific integrity question about a benchmark. It must:
        - Set `name`, `version`, `description` class attributes.
        - Implement `applies_to(adapter)` (returns True/False).
        - Implement `run(adapter, *, predictions, model)` -> ProbeResult.
        - Never mutate the adapter's state.
        - Return a ProbeResult with a confidence interval (enforced by schema).
    """

    name: str
    version: str
    description: str
    requires_live_model: bool = False

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        for attr in ("name", "version", "description"):
            if not getattr(cls, attr, None):
                raise TypeError(f"{cls.__name__} must set class attribute `{attr}`")

    @abstractmethod
    def applies_to(self, adapter: Adapter) -> bool: ...

    @abstractmethod
    def run(
        self,
        adapter: Adapter,
        *,
        predictions: Sequence[Prediction] | None = None,
        model: Any | None = None,
    ) -> ProbeResult: ...

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r} v={self.version}>"


class ProbeRegistry:
    def __init__(self) -> None:
        self._probes: dict[str, type[Probe]] = {}

    def register(self, probe_cls: type[Probe]) -> type[Probe]:
        name = probe_cls.name
        if name in self._probes and self._probes[name] is not probe_cls:
            raise ProbeError(
                f"Probe name conflict: '{name}' is already registered by "
                f"{self._probes[name].__module__}.{self._probes[name].__name__}"
            )
        self._probes[name] = probe_cls
        return probe_cls

    def get(self, name: str) -> type[Probe]:
        try:
            return self._probes[name]
        except KeyError as e:
            known = ", ".join(sorted(self._probes)) or "(none)"
            raise ProbeError(f"Unknown probe '{name}'. Known: {known}") from e

    def names(self) -> list[str]:
        return sorted(self._probes)

    def applicable_to(self, adapter: Adapter) -> list[type[Probe]]:
        return [p for p in self._probes.values() if p().applies_to(adapter)]


registry = ProbeRegistry()
