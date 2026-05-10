"""Model factory: pin enforcement (no Inspect AI dependency required for this test)."""

from __future__ import annotations

import pytest

from bench_audit.harness.model_factory import get_model


def test_rejects_empty_spec() -> None:
    with pytest.raises(ValueError):
        get_model("")


def test_rejects_no_provider() -> None:
    with pytest.raises(ValueError):
        get_model("claude-opus-4-7")


def test_rejects_latest_alias() -> None:
    with pytest.raises(ValueError, match="latest"):
        get_model("anthropic/claude-latest")
    with pytest.raises(ValueError, match="latest"):
        get_model("openai/gpt-5-stable")


def test_rejects_undated_provider_model() -> None:
    with pytest.raises(ValueError, match="date"):
        get_model("anthropic/claude-opus-4-7")
    with pytest.raises(ValueError, match="date"):
        get_model("openai/gpt-5-2")


def test_accepts_dated_model_when_inspect_ai_missing() -> None:
    # When inspect-ai is not installed, we raise RuntimeError AFTER passing the
    # pin check — which is the right ordering. We assert we get the install
    # hint, not a ValueError.
    try:
        import inspect_ai  # noqa: F401
    except ImportError:
        with pytest.raises(RuntimeError, match="inspect-ai"):
            get_model("anthropic/claude-opus-4-7-20260201")
    else:
        # If installed, get_model returns a Model — just check it doesn't error
        m = get_model("anthropic/claude-opus-4-7-20260201")
        assert m is not None


def test_local_provider_does_not_require_date() -> None:
    try:
        import inspect_ai  # noqa: F401
    except ImportError:
        with pytest.raises(RuntimeError, match="inspect-ai"):
            get_model("local/Qwen3-72B")
