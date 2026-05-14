"""Exception hierarchy."""

from __future__ import annotations


class BenchAuditError(Exception):
    """Base for all bench-audit errors."""


class AdapterError(BenchAuditError):
    """An adapter operation failed."""


class ManifestMismatchError(AdapterError):
    """The cached eval set's hash does not match the manifest."""


class ProbeError(BenchAuditError):
    """A probe encountered an error."""


class ProbeInapplicableError(ProbeError):
    """A probe was asked to run against an adapter where applies_to() is False."""


class ReproducibilityError(BenchAuditError):
    """A reproduction run fell outside tolerance."""


class LicenseError(BenchAuditError):
    """A licensing constraint would be violated."""
