"""Probe registry and built-in probes."""

from bench_audit.probes.base import Probe, ProbeRegistry, registry
from bench_audit.probes.eval_set_visibility import EvalSetVisibilityProbe
from bench_audit.probes.gold_answer_leak import GoldAnswerLeakProbe
from bench_audit.probes.harness_injection import HarnessInjectionProbe
from bench_audit.probes.hello import HelloProbe
from bench_audit.probes.near_dup_pretraining import NearDupPretrainingProbe
from bench_audit.probes.reward_hacking import RewardHackingProbe

# Built-in probes register themselves on import.
registry.register(HelloProbe)
registry.register(GoldAnswerLeakProbe)
registry.register(NearDupPretrainingProbe)
registry.register(HarnessInjectionProbe)
registry.register(RewardHackingProbe)
registry.register(EvalSetVisibilityProbe)

__all__ = [
    "EvalSetVisibilityProbe",
    "GoldAnswerLeakProbe",
    "HarnessInjectionProbe",
    "HelloProbe",
    "NearDupPretrainingProbe",
    "Probe",
    "ProbeRegistry",
    "RewardHackingProbe",
    "registry",
]
