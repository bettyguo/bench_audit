"""Benchmark adapters. Each benchmark gets exactly one adapter file."""

from bench_audit.adapters.base import Adapter, AdapterRegistry, registry

__all__ = ["Adapter", "AdapterRegistry", "registry"]
