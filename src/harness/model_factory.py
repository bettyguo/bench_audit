"""Model factory: returns an Inspect AI `Model` from a user-friendly spec string.

We refuse to run live mode against "latest" aliases — every model must be
pinned by date so reproductions are deterministic.
"""

from __future__ import annotations

import re
from typing import Any

_LATEST_ALIAS_RE = re.compile(r"latest|main|head|stable", re.I)
_PINNED_DATE_RE = re.compile(r"\d{4}-?\d{2}-?\d{2}|\d{8}")


def get_model(spec: str) -> Any:
    """Return an Inspect AI Model given a spec like:

    - `anthropic/claude-opus-4-7-20260201`
    - `openai/gpt-5-2-20260301`
    - `local/Qwen3-72B`
    - `hf/meta-llama/Llama-4-70B`

    Raises ValueError on "latest" aliases or unpinned model IDs.
    """
    if not spec or "/" not in spec:
        raise ValueError(
            f"Invalid model spec '{spec}'. Use 'provider/model_id', e.g. "
            "'anthropic/claude-opus-4-7-20260201'."
        )
    provider, model_id = spec.split("/", 1)
    if _LATEST_ALIAS_RE.search(model_id):
        raise ValueError(
            f"Refusing 'latest'-style alias in model spec '{spec}'. Pin a "
            "specific dated model ID for reproducibility."
        )
    if provider in ("anthropic", "openai", "google", "azure") and not _PINNED_DATE_RE.search(
        model_id
    ):
        raise ValueError(
            f"Provider '{provider}' models must include a date suffix (YYYY-MM-DD or YYYYMMDD). "
            f"Got '{model_id}'. This protects reproducibility — see "
            "docs/reproducibility.md."
        )
    try:
        import inspect_ai  # type: ignore[import-not-found]
    except ImportError as e:
        raise RuntimeError(
            "Live mode requires inspect-ai. Install with `uv sync --extra live`."
        ) from e
    return inspect_ai.model.get_model(spec)  # type: ignore[attr-defined]
