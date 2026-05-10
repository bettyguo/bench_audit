# Safety context

`bench-audit` sits at the operational layer of a chain of alignment ideas going back to Goodhart's Law. This document is for safety researchers who want to cite the project and need a short, defensible mapping from the philosophical literature to the seven probe families.

## The chain

1. **Goodhart's Law** (Strathern 1997 paraphrasing Goodhart 1975): *"When a measure becomes a target, it ceases to be a good measure."* The minimal claim: any optimization process aimed at a proxy will eventually exploit the gap between the proxy and the goal.

2. **Specification gaming** (Krakovna et al. 2020). The empirical demonstration that this happens in machine learning: a curated list of 50+ examples where an ML system found a way to satisfy its training objective without satisfying the designer's intent. The list is the canonical evidence base.

3. **Reward hacking, formally** (Skalse et al. 2022, NeurIPS). A precise definition: a reward function `R̃` is *hackable* relative to a true reward `R` if there exist trajectories where `R̃` rewards behaviour `R` does not. This is the formal framing our P5 probe operationalizes for benchmark scoring functions.

4. **Goodhart in RL** (Karwowski et al. 2024, ICLR). A theoretical study of when proxy-target divergence is benign vs catastrophic in RL. The empirical question for evaluations is what fraction of benchmark scoring functions fall in each regime.

5. **METR's measurements** (Barnes et al. 2025–present). The first systematic measurements of reward-hacking frequency on frontier-model evaluations. Headline numbers: 30.4% on RE-Bench, 100% on Optimize LLM Foundry. METR's two-stage methodology (deterministic filters + LLM grader + manual review) is what our P5 reproduces.

6. **Berkeley's BenchJack** (Wang et al. 2026). The orthogonal demonstration: even before any model runs, the *evaluation pipeline itself* admits structural exploits. The 7-pattern vulnerability catalog (BA-01..BA-07) is what our P4 reproduces.

`bench-audit` is the maintained tool that lets the safety community measure (3)–(6) on each new benchmark and each new model.

## Why this is alignment-relevant

If we cannot trust our evaluations, our claims about alignment progress are unverifiable. The argument is one step:

- We measure alignment progress by improvement on evaluations.
- If evaluations are contaminated, gold-leaking, or reward-hackable, then improvement measures contamination/gaming, not alignment.
- Therefore, **evaluation integrity is upstream of every empirical alignment claim**, including AI safety claims that rely on benchmark numbers.

This is not a peripheral concern. It is a precondition.

## What `bench-audit` is and is not

**Is:** A reproduction + maintained-tool packaging of Berkeley RDI's BenchJack and METR's reward-hacking pipeline. A discipline harness for the contamination literature.

**Is not:** A new theoretical contribution. We do not propose a new definition of reward hacking; Skalse et al. 2022 already did. We do not propose a new measurement methodology; METR already did. We do not propose new vulnerability patterns; Berkeley already did.

**Is also not:** A claim that the seven probes cover the space. The taxonomy ships for v0.1; known gaps:

- Eval-awareness: models behaving differently when they suspect they're being evaluated (cf. Anthropic's BrowseComp work).
- Multi-agent contamination: one agent leaks answers to another in a multi-agent eval.
- Learned judge bias: LLM-judge graders that systematically over-reward outputs from a specific model lineage.
- Cross-benchmark leakage: benchmarks A and B share tasks; contamination on A benefits the model on B.

All four are deferred to v0.2.

Safety researchers who want to propose new probe families are exactly the kind of contributor we want; the contribution path is in [docs/CONTRIBUTING.md](CONTRIBUTING.md).

## Pre-registration discipline

The single most important safety-relevant property of this repo is **pre-registration of measurement gates**:

- P1–P6 operational definitions live in [probes/](probes/). Each probe's null distribution and calibration target are committed before measurement.
- P5's Cohen's κ ≥ 0.7 against three annotators is pre-registered in [fixtures/trajectories/rubric.md](../fixtures/trajectories/rubric.md). The gate exists *before* any external claim is made.
- Reproduction targets land in [published_numbers.json](published_numbers.json) before the corresponding runs.

Pre-registration matters. AI safety has been criticized, fairly, for retroactively constructing claims from data; the discipline here is to write the gate down first and accept whatever the measurement says.

## Citing `bench-audit`

```bibtex
@misc{wu2026benchaudit,
  author = {Wu, Jacob},
  title = {bench-audit: A maintained probe suite for agent-benchmark integrity,
           with calibrated confidence intervals},
  year = {2026},
  url = {https://github.com/jacobwu/bench-audit},
  note = {arXiv preprint pending; reproduces Wang et al. (2026) and METR (2025).}
}
```

Please also cite the source findings (Berkeley RDI 2026 and METR 2025). bench-audit is the packaging, not the discovery.
