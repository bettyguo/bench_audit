# Architecture

## Top-level flow

```
benchmark adapters -> probe registry -> execution harness -> results store -> report generator -> leaderboard
```

A benchmark adapter is the only benchmark-specific code path. Everything
downstream is benchmark-agnostic. The probe registry enumerates probes and
asks each whether it applies to a given adapter. The execution harness
runs a probe against either a stored prediction file (static mode) or a
live model (live mode, via Inspect AI). The results store persists
`ProbeResult` records as JSON Lines with content hashes for the test set
and the control set. The report generator emits JSON, Markdown, and a
one-page PDF report card. The leaderboard renderer is a static-site
generator that reads the JSONL store and emits a GitHub Pages site, with
every cell linking to raw data and a reproduction command.

Each component is replaceable. A Rust-based evaluator wraps behind the
adapter ABC. A new probe class is added without touching the harness. The
leaderboard could be replaced by a Streamlit app without changing anything
upstream.

## Layout

```
src/bench_audit/
  schemas.py                 # Task, BenchmarkManifest, ProbeResult, Trajectory, ReportCard
  errors.py                  # exception hierarchy
  adapters/
    base.py                  # Adapter ABC + registry
    swebench_verified.py
    webarena.py
    gaia.py
  probes/
    base.py                  # Probe ABC + registry
    hello.py                 # smoke-test stub
    gold_answer_leak.py      # P1
    near_dup_pretraining.py  # P2
    harness_injection.py     # P4 (Berkeley 7-pattern checklist)
    reward_hacking.py        # P5
    eval_set_visibility.py   # P6
    signatures/              # reward-hacking detectors + LLM grader
  harness/
    static.py
    live.py                  # Inspect AI bridge
    model_factory.py
    inspect_bridge.py
  stats/
    intervals.py             # Wilson, Clopper-Pearson, bootstrap, Cohen's h
    agreement.py             # Cohen's / Fleiss' kappa
  reporting/
    json_report.py
    markdown_report.py
    pdf_report.py            # weasyprint
    leaderboard.py
  templates/                 # Jinja2 templates for report cards + leaderboard
  cli.py
  config.py
  diagnostics.py             # `bench-audit doctor` checks
```

## Adapters

Every adapter implements four methods, enforced by the ABC:

```python
class Adapter(ABC):
    name: str
    version: str
    benchmark_version: str

    @abstractmethod
    def load_eval_set(self, cache_dir: Path) -> Iterable[Task]: ...
    @abstractmethod
    def task_iter(self) -> Iterator[Task]: ...
    @abstractmethod
    def score(self, task: Task, prediction: Prediction) -> float: ...
    @abstractmethod
    def manifest(self) -> BenchmarkManifest: ...
```

`manifest()` carries `eval_set_sha256`. Adapters refuse to operate on a
cached eval set whose hash doesn't match. A hash mismatch raises
`ManifestMismatchError`.

Adding a new adapter is one Python file plus one fixture directory. If
your adapter exceeds 300 LoC, the ABC needs refactoring, not your adapter.

## Probes

```python
class Probe(ABC):
    name: str
    version: str
    description: str
    requires_live_model: bool = False

    @abstractmethod
    def applies_to(self, adapter: Adapter) -> bool: ...
    @abstractmethod
    def run(self, adapter, *, predictions=None, model=None) -> ProbeResult: ...
```

### `ProbeResult` contract

`ProbeResult` is a frozen Pydantic model. Construction enforces:

- A CI is required (`ci_low`, `ci_high`, `ci_method`).
- `ci_low <= ci_high`.
- Non-inconclusive verdicts require `sample_size >= 30` unless
  `allow_small_n=True`.
- Non-inconclusive verdicts require CI half-width `<= 0.1` unless
  `allow_wide_ci=True`.

Both overrides land on the report card so readers can see what was waived.

### v0.1 probes

| Probe | File | Static | Live |
|---|---|---|---|
| P1 Gold-answer leak | `probes/gold_answer_leak.py` | yes | yes |
| P2 Near-duplicate pretraining | `probes/near_dup_pretraining.py` | yes (overlap) | yes (MIA) |
| P4 Harness injection | `probes/harness_injection.py` | yes | n/a |
| P5 Reward hacking | `probes/reward_hacking.py` | yes (trajectory) | yes |
| P6 Eval-set visibility | `probes/eval_set_visibility.py` | yes | n/a |

Power analysis: each probe exposes `min_n_for_half_width(target) -> int`
so callers can compute the minimum sample size that supports a verdict
before running a large probe.

## Execution harness

### Static mode

`harness/static.py`. Inputs: an adapter plus a directory of stored
predictions (harness-injection probes need no predictions; they probe the
adapter directly). No live model required. This is the default mode for
re-running probes against published predictions.

### Live mode

`harness/live.py`. Inputs: an adapter plus a model identifier. Queried
via Inspect AI's `Solver` and `Model` abstractions. Inspect AI handles
retries, rate limiting, caching, model adapters for OpenAI / Anthropic /
local-via-vLLM, and reproducible randomization. The bench-audit bridge is
thin: construct an Inspect AI `Task` from the adapter, read results back
via Inspect AI's logging.

Why Inspect AI rather than rolling our own:

- Built and maintained by UK AISI; >200 pre-built evals.
- MIT-licensed, actively developed.
- Native OpenAI / Anthropic / Google / vLLM model adapters with consistent
  retry and caching.
- Its `Task` model maps cleanly to ours.

Alternatives that didn't make the cut: lm-eval-harness (generation-only,
not agent loops); HELM (heavyweight, scenario abstraction doesn't map);
bespoke (recreating Inspect AI is a six-month project).

### Sandboxing

Live-mode probes that run agent code (P1, P4, P5) execute in Docker with
network restricted to the benchmark's allow-list, filesystem confined to
the task working dir, a 300s per-task timeout, and a 4 GB memory cap.
This is not an air gap; it's defence against accidental DNS exfiltration.
The probe code is trusted; agent code is partially trusted (possibly
adversarial).

### Caching

Inspect AI calls cache by `(model, prompt_sha256, sampling_params)` under
`~/.cache/bench-audit/`. The cache is content-addressed; reproduction
runs hit it and skip API calls.

## Reproducibility

Pinned:

- Python 3.11+ (CI runs 3.11 and 3.12).
- Dependencies via `uv.lock`.
- Models by full ID including date; the harness refuses `latest` aliases.
- Prompt templates under `src/bench_audit/templates/`; SHA-256 logged on
  every result.
- Eval-set SHA-256 in each `BenchmarkManifest`; verified on cache load.
- Canonical environment in `Dockerfile`.
- RNG seeds declared per probe and logged.

`reproduce.sh <slice>` rebuilds the Docker image, runs the slice, and
diffs against `docs/published_numbers.json`. Default tolerance is ±0.02
on proportions; per-slice overrides live in the JSON.

The published Docker image contains the harness, adapters, and probes
but no eval-set content. Eval sets are fetched on first use, gated by
license-acceptance prompts where required.

## Reporting

Three artifacts per probe run:

1. **JSON.** Machine-readable, schema-versioned (`schemas.py:ReportCard`).
2. **Markdown.** Human-readable; embeds in a paper or README.
3. **PDF.** One page, via WeasyPrint. The shareable artifact.

Every card includes the verdict, effect size + 95% CI, sample size, any
`allow_*` overrides used, the reproduction command, the eval-set SHA-256,
a timestamp, and the harness version.

## Leaderboard

Static Jinja2 -> HTML, deployed to GitHub Pages from the `gh-pages`
branch. The site has a per-benchmark page, a per-probe page, and a top
matrix. Every cell links to the raw JSON in `_site/results/`. The
reproduction command appears on hover.

There is no login, no submit button, no telemetry. Submissions are PRs
that add a JSONL entry to `results/` and pass `bench-audit verify-result
--strict` in CI.

## Stack

| Pick | Notes |
|---|---|
| Python 3.11+ | Eval ecosystem is Python-native |
| `uv` | Faster than pip-tools/poetry; lockfile-by-default |
| `pydantic` v2 | `ProbeResult` validation at the type level |
| `inspect-ai` | Live-eval substrate |
| `polars` | Fast, no `inplace=True` footguns |
| `scipy.stats` | Wilson, bootstrap, KSG MI |
| `typer` | Type-hint driven CLI |
| `jinja2` | Templates everywhere |
| `weasyprint` | HTML -> PDF for report cards |
| `ruff` + `mypy --strict` | Lint + types in CI |
| Apache-2.0 | Patent grant matters when probing closed models |

## Threat model

Adversaries we plan for:

- **Cosmetic-patch attack.** Maintainer renames `config_files/` to `_cfg/`
  and claims the leak is fixed. P1 is mechanism-targeted (file matching
  by regex over name + content sniff), so renames don't defeat it.
- **Probe-gaming attack.** A model is fine-tuned not to take the lazy
  path. P1 measures the adapter's property, not the model's; the
  lazy-agent is a synthetic baseline.
- **Manifest forgery.** A benchmark author publishes a manifest hash that
  doesn't match the eval set. Adapters compute the hash at load and
  refuse mismatches.
- **Result forgery.** Someone submits a fabricated `ProbeResult` JSON.
  Submissions must include the raw per-task data; CI verifies aggregate
  matches the raw data and that the eval-set hash is a known-good value.
