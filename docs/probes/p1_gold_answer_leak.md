# P1 — Gold-answer leak

## Definition

A task is gold-answer-leaking if the gold answer is recoverable from the
task's presentation environment (filesystem, network, prompt context)
without performing the underlying task.

## Input

- A benchmark adapter exposing `lazy_agent_recipe(task) -> Prediction`.
  Adapters without a recipe get `verdict='inconclusive'`.
- The adapter's `task_iter()` and `score()`.

## Output

`ProbeResult` with:

- `effect_size` = proportion of tasks where
  `score(task, lazy_recipe(task)) >= pass_threshold`.
- `ci_method = "wilson"`, 95% level.
- `verdict = "fail"` iff `ci_low > 0.01`. Conservative; a single
  accidentally-leaking task should not flip the verdict.
- `notes` carries leak count, sample size, error count (recipe failures),
  and a stable hash over per-task records.

## Mechanism

The probe runs a lazy agent: a per-adapter recipe that produces a
prediction without doing any task-relevant work. The recipe lives on the
adapter, not the probe, because what counts as "lazy" depends on the
benchmark:

- **SWE-bench Verified**: forge a `report` with `resolved=True` (Berkeley's
  pytest-hook exploit shape). The probe does not run the exploit; it
  produces the prediction the grader would accept if the hook were active.
- **WebArena**: open `file://config_files/{task_id}.json`, read
  `reference_answers`, submit.
- **GAIA**: query the public HuggingFace mirror for the gold answer,
  submit normalized.

## Null distribution / control

A clean control adapter has a `lazy_agent_recipe` identical in shape but
a `score()` that does not accept lazy predictions. The probe should
return `verdict='pass'`, `effect_size ≈ 0` on the control.

## Calibration target

| Benchmark | Berkeley reported | Reproduction target |
|---|---|---|
| SWE-bench Verified (n=500) | 100% (conftest pytest hook) | ≥ 0.97 (Wilson CI above 0.95) |
| WebArena (n=812) | ~100% (file:// gold-answer read) | ≥ 0.97 |
| GAIA (n=165) | ~98% (HF mirror + normalization) | ≥ 0.93 |

The SWE-bench probe is implemented; the full 500-task reproduction
requires running the SWE-bench Docker harness against a real evaluator.
Fixture-based unit tests demonstrate the probe correctly identifies the
leak shape.

## Sample-size recommendation

Wilson 95% half-width at p=0.97, n=500 ≈ 0.015. Sufficient.
At n=50 the half-width is ≈ 0.05, useful for a strong-effect probe.
Minimum recommended sample for a verdict (schema default): 30.

## Known limitations

- Only finds leaks the lazy-agent recipe knows to look for. A novel leak
  channel will not trigger this probe; that's P4's job, plus periodic
  recipe audits.
- The probe trusts the adapter's `score()` to faithfully reproduce
  upstream grading. If the adapter's `score()` diverges, the probe's
  verdict reflects the adapter, not the benchmark.
