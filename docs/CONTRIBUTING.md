# Contributing

## Setup

```bash
git clone https://github.com/jacobwu/bench-audit && cd bench-audit
uv sync --all-extras
uv run pre-commit install
make ci
```

## Adding an adapter

1. `src/bench_audit/adapters/<benchmark>.py`. Subclass `Adapter`; set `name`, `version`, `benchmark_version`.
2. Implement `load_eval_set`, `task_iter`, `score`, `manifest`.
3. Register: `registry.register(YourAdapter)`.
4. Add a small redistribution-safe fixture under `fixtures/<benchmark>/mini/` (no gold answers if license forbids).
5. Add `tests/integration/test_adapter_<benchmark>.py` covering the four ABC methods plus a manifest hash check.

One Python file + one fixture directory + one test file. If your adapter exceeds 300 LoC, the ABC needs refactoring; open an issue.

## Adding a probe

1. `src/bench_audit/probes/<probe>.py`. Subclass `Probe`; set `name`, `version`, `description`.
2. Implement `applies_to` and `run`.
3. `run` must return a `ProbeResult` with a CI. The schema enforces this.
4. Register: `registry.register(YourProbe)`.
5. Add `tests/unit/test_probe_<probe>.py` covering: (a) applies/doesn't where expected, (b) determinism on identical inputs, (c) `inconclusive` on degenerate inputs.
6. Add a spec doc under `docs/probes/<probe>.md` with input, output, statistical interpretation, null distribution, calibration target.

## PR ground rules

- Every PR adding a probe or a claim includes the measured effect size, sample size, CI, and test-set hash.
- If your probe cannot produce a CI, open an issue to discuss the design before submitting.
- Verdict-issuing changes at `n < 30` require an explicit `allow_small_n=True` and a paragraph explaining why.

## Reviewer checklist

- [ ] `make ci` passes.
- [ ] New code has type annotations; `mypy --strict` clean.
- [ ] New probe has a spec doc and a null/control test.
- [ ] No eval-set content committed.
- [ ] No model outputs redistributed.
