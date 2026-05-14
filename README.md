# bench-audit

A library of probes for agent benchmarks: contamination, gold-answer
leaks, harness-injection vulnerabilities, reward hacking. Every probe
result carries a 95% Wilson CI enforced at the schema level.

[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue)](pyproject.toml)

Reproduces and extends two prior findings:

- UC Berkeley RDI ([Wang et al., 2026-04-12](https://rdi.berkeley.edu/blog/trustworthy-benchmarks-cont/)) showed BenchJack scoring ~100% on seven of eight major agent benchmarks (73% on OSWorld) without a single LLM call.
- METR ([Barnes et al., 2025-06–](https://metr.org/blog/2025-06-05-recent-reward-hacking/)) measured frontier models reward-hacking at 30.4% on RE-Bench, 100% on Optimize LLM Foundry, 42.9% on Scaffolding for Rust.

The science is theirs. This is the maintained, plug-in toolkit that
packages it.

## Quickstart

```bash
uv sync --all-extras

uv run bench-audit list-adapters
uv run bench-audit list-probes

uv run bench-audit run \
    --adapter swebench_verified \
    --probe p1_gold_answer_leak \
    --fixture-dir fixtures/swebench_verified/mini

uv run bench-audit leaderboard build --results _results --out _site
```

Output: a `ProbeResult` JSON, a Markdown report card, optionally a
one-page PDF (`--pdf`).

## What ships

### Adapters

| Adapter | Tasks | License |
|---|---|---|
| `swebench_verified` | 500 | MIT (Princeton/Stanford) |
| `webarena` | 812 | Apache-2.0 (CMU) |
| `gaia` | 165 (val) | gated CC-BY-4.0-like (HF) |

### Probes

| Probe | Failure mode | Source |
|---|---|---|
| `p1_gold_answer_leak` | gold answer recoverable from environment | Berkeley WebArena file:// |
| `p2_near_dup_pretraining` | eval set in training corpus (13-gram overlap) | Brown 2020; Shi 2024 |
| `p3_shortcut_feature` | task metadata correlates with gold | Goodhart |
| `p4_harness_injection` | Berkeley's 7-pattern catalog | Wang 2026 |
| `p5_reward_hacking` | METR signature rubric | METR 2025 |
| `p6_eval_set_visibility` | eval set publicly discoverable | factual |

### What the schema enforces

- A `ProbeResult` cannot exist without a 95% CI.
- A non-inconclusive verdict at `n < 30` requires `allow_small_n=True`, and the flag lands on the report card.
- A CI half-width above 0.1 requires `allow_wide_ci=True` and is logged the same way.
- Model IDs must include a date; `latest` aliases are refused at the harness boundary.
- Eval-set content is fetched at runtime under license, never bundled.

## Ground rules

1. No contamination claim without a reproducible probe, effect size, and CI.
2. 14-day private outreach to a benchmark maintainer before any public disclosure ([docs/maintainer-outreach.md](docs/maintainer-outreach.md)).
3. No paid stars or exchange schemes.
4. Discrepancies with prior reported numbers get investigated and documented.
5. Respect upstream licenses.
6. Don't redistribute frontier-lab model outputs.
7. Framing is "we measured a contamination signature in X", not "we broke X".

## Docs

- [docs/architecture.md](docs/architecture.md) — adapter ABC, probe registry, harness modes
- [docs/probes/](docs/probes/) — per-probe specs
- [docs/reproducibility.md](docs/reproducibility.md) — pins and tolerances
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)
- [docs/safety-context.md](docs/safety-context.md) — Goodhart → spec gaming → reward hacking lineage
- [paper/main.tex](paper/main.tex) — workshop preprint draft

## Status

`v0.1.0a0`. Full-scale reproductions against the real n=500 / 812 / 165
eval sets need the upstream Docker/HF infrastructure; fixture-based runs
are in tree and pass.

## Citation

```bibtex
@misc{wu2026benchaudit,
  author = {Wu, Jacob},
  title = {bench-audit: A probe suite for agent-benchmark integrity, with calibrated confidence intervals},
  year = {2026},
  url = {https://github.com/jacobwu/bench-audit},
}
```

## Acknowledgements

- Berkeley RDI (Hao Wang et al.) for BenchJack and the 7-pattern vulnerability taxonomy.
- METR (Beth Barnes et al.) for the reward-hacking measurements and the rubric framing.
- Victoria Krakovna for the spec-gaming examples list.
- UK AI Security Institute for Inspect AI.

## License

Apache-2.0.
