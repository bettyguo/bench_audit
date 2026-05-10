"""Coverage for the LLM classifier's prompt rendering.

Even without inspect-ai installed, the prompt rendering + hash machinery
must work — the SHA-256 hash is persisted on every ProbeResult and is the
mechanism by which model drift cannot retroactively invalidate historical
classifications.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from bench_audit.probes.signatures.diff_signatures import SignatureMatch
from bench_audit.probes.signatures.llm_classifier import (
    CLASSIFIER_PROMPT,
    classify_stub,
    prompt_sha256,
    render_prompt,
)
from bench_audit.schemas import Action, Trajectory


def _make_trajectory(*, text: str = "I edited the test file") -> Trajectory:
    return Trajectory(
        task_id="t-001",
        model_name="test-model",
        model_version="v1",
        actions=[
            Action(
                timestamp=datetime(2026, 5, 14, 10, 0, tzinfo=UTC),
                kind="tool_call",
                name="edit_file",
                args={"path": "tests/test_foo.py", "diff": "..."},
            ),
            Action(
                timestamp=datetime(2026, 5, 14, 10, 1, tzinfo=UTC),
                kind="model_output",
                text=text,
            ),
        ],
    )


def test_prompt_includes_signature_table_and_trajectory() -> None:
    tr = _make_trajectory()
    matches = [
        SignatureMatch("RH-01", "Test modification", "wrote/modified test file: tests/test_foo.py", 0),
    ]
    prompt = render_prompt(tr, matches)
    # Signature table must enumerate RH-01..RH-07
    for sig in ("RH-01", "RH-02", "RH-03", "RH-04", "RH-05", "RH-06", "RH-07"):
        assert sig in prompt
    # Trajectory metadata appears
    assert "t-001" in prompt
    assert "test-model" in prompt
    # Stage-1 result is surfaced (so the LLM can disagree if it wants)
    assert "TRIGGERED" in prompt
    assert "tests/test_foo.py" in prompt


def test_prompt_with_empty_stage1_shows_none() -> None:
    tr = _make_trajectory()
    prompt = render_prompt(tr, [])
    assert "(none)" in prompt


def test_prompt_sha256_is_stable() -> None:
    """The prompt template's SHA-256 is the audit anchor — it must be stable
    across calls. If the template literal changes, the SHA changes, and that
    is logged on every result."""
    a = prompt_sha256()
    b = prompt_sha256()
    assert a == b
    assert len(a) == 64  # SHA-256 hex
    # Sanity: hash of the actual template literal matches the function output.
    import hashlib

    assert a == hashlib.sha256(CLASSIFIER_PROMPT.encode("utf-8")).hexdigest()


def test_long_trajectory_is_truncated_in_prompt() -> None:
    """Trajectories that don't fit in the model's context get truncated rather
    than blowing the prompt budget. The truncation marker must be visible."""
    huge_text = "x" * 20_000
    tr = _make_trajectory(text=huge_text)
    prompt = render_prompt(tr, [])
    assert len(prompt) < len(huge_text) * 2  # not 4x'd by repetition
    assert "truncated" in prompt.lower()


def test_classify_stub_routes_hard_signatures_to_reward_hacking() -> None:
    tr = _make_trajectory()
    hard = [SignatureMatch("RH-01", "Test modification", "...", 0)]
    cls = classify_stub(tr, hard)
    assert cls.verdict == "reward_hacking"
    assert cls.used_llm is False


def test_classify_stub_routes_soft_signatures_to_ambiguous() -> None:
    tr = _make_trajectory()
    soft = [SignatureMatch("RH-06", "Score-function bypass", "...", 0)]
    cls = classify_stub(tr, soft)
    assert cls.verdict == "ambiguous"


def test_classify_stub_returns_clean_when_no_matches() -> None:
    tr = _make_trajectory()
    cls = classify_stub(tr, [])
    assert cls.verdict == "clean"


def test_rendered_prompt_is_serializable_in_a_result_notes() -> None:
    """The SHA-256 of the prompt is logged in ProbeResult.notes for every
    reward-hacking run. Ensure that hash is a stable string with no
    nondeterminism (e.g., dict ordering)."""
    tr = _make_trajectory()
    p1 = render_prompt(tr, [])
    p2 = render_prompt(tr, [])
    assert p1 == p2
    # And `json.dumps`-safe (no non-string keys etc.).
    json.dumps({"sha": prompt_sha256(), "preview": p1[:80]})


pytest.importorskip("pydantic")  # nominal — already required at this point
