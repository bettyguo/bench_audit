"""Reward-hacking signature detectors.

Two stages:
  1. `diff_signatures` — deterministic regex/diff/AST detectors over a trajectory.
  2. `llm_classifier` — LLM-based classifier; second-stage so we can ablate it.

The signature rubric is in docs/probes/p5_reward_hacking.md and the
hand-labelled trajectory set is in fixtures/trajectories/.
"""

from bench_audit.probes.signatures.diff_signatures import (
    SIGNATURE_IDS,
    SignatureMatch,
    detect_all,
)

__all__ = ["SIGNATURE_IDS", "SignatureMatch", "detect_all"]
