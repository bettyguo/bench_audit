# P4 — Harness injection

Berkeley RDI (2026-04-12) identified **seven structural vulnerability patterns** that recur across the eight major agent benchmarks. P4 operationalizes those as a checklist of detectors that scan the adapter's grading surface.

## Patterns

| ID | Pattern | Berkeley example |
|---|---|---|
| BA-01 | No agent/evaluator isolation | SWE-bench `conftest.py` pytest hook |
| BA-02 | Answers shipped with tests | WebArena `config_files/{task_id}.json` on disk |
| BA-03 | `eval()` on untrusted input | OSWorld scorer's `eval()` |
| BA-04 | LLM judges without input sanitization | CAR-bench LLM judge prompt-injection |
| BA-05 | Weak string matching in grader | GAIA `re.sub(r"\W", "", x)` collisions |
| BA-06 | Evaluation logic that doesn't actually evaluate | FieldWorkArena dead-code `validate()` |
| BA-07 | Grader trusts output from untrusted code | Terminal-Bench fake `curl` wrapper; SWE-bench `report.resolved` |

## Input

A benchmark adapter. The probe reads the adapter's `score()` source via `inspect.getsource` and its `task_iter()` payload; this is the entire interface.

## Output

`ProbeResult` with:
- `effect_size` = `n_triggered / 7`.
- `ci_method = "clopper_pearson"` on the count.
- `sample_size = 7` (the seven patterns).
- `allow_small_n = True`, `allow_wide_ci = True` — the probe is a checklist, not a proportion estimator over tasks. Both overrides are logged on the report card.
- `notes` lists each pattern with TRIGGERED/clean and evidence.

A planned `--sample N` mode will extend each detector to operate over a random N-task sample and produce a Wilson CI on per-pattern trigger rate. Complements but does not replace the checklist.

## Null distribution / control

The synthetic test adapter (`tests/conftest.py:SyntheticAdapter`) is the canonical control. Its `score()` does a clean string-equality match without weak normalization, no `eval()`, no shelling out, no judge LLM. Expected `effect_size ≈ 0`, `verdict = "pass"`.

## Calibration target

| Benchmark | Berkeley findings | P4 detector expected to flag |
|---|---|---|
| SWE-bench Verified | conftest pytest hook | BA-07 (grader trusts agent-reported status) |
| WebArena | file:// + DOM injection + judge | BA-02, BA-04 |
| GAIA | HF mirror + normalization | BA-02 (if gold in HF), BA-05 |
| FieldWorkArena | dead `validate()` | BA-06 |
| Terminal-Bench | curl wrapper trojan | BA-01, BA-07 |
| OSWorld | `eval()` + HF download | BA-03, BA-02 |
| CAR-bench | LLM judge injection | BA-04 |

Fixture tests demonstrate BA-02 + BA-05 firing on SWE-bench. The full per-benchmark trigger matrix awaits the v0.2 adapter expansion.

## Known limitations

- Source-only static analysis: misses runtime-only vulnerabilities (e.g., a grader that's clean in source but vulnerable via a third-party service it calls).
- High false-positive rate on BA-04 if the grader benignly mentions "judge" — the detector flags any `format`/`f-string` involving the word "judge" without sanitizer markers.
- BA-01 detector is necessarily heuristic: a clean grader that calls Docker can still be unsafe if the Docker isolation is misconfigured.

Dynamic detectors (P4-live) that attempt each pattern against the
adapter's real grading surface, with pre-flight checks, are planned for
v0.2.
