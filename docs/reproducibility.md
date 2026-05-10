# Reproducibility

Published numbers are reproducible via `./reproduce.sh` or `make
reproduce SLICE=<id>`. Default tolerance is ±0.02 absolute on
proportion-valued probe results; per-key overrides live in
`published_numbers.json`.

## What is pinned

| Layer | Pin |
|---|---|
| Python | 3.11+ (CI: 3.11, 3.12) |
| Deps | `uv.lock` |
| OS | `Dockerfile` (Debian 12 + Python 3.12) |
| Models | Full model ID + date (e.g. `claude-opus-4-7-20260201`). The harness refuses `latest` aliases. |
| Prompts | SHA-256 of every template under `src/bench_audit/templates/`, logged on every result |
| Eval sets | `BenchmarkManifest.eval_set_sha256`; adapter refuses to run on mismatch |
| Randomness | Probe declares its seed; harness logs `(probe_seed, sampling_seed)` |

## Targets

`published_numbers.json` format:

```json
{
  "webarena::p1_gold_answer_leak": 0.97,
  "swebench_verified::p4_harness_injection": 0.29
}
```

## Caveats

- Live-mode probes against frontier models depend on the provider's
  behaviour. Inspect AI caches by `(model, prompt_sha256,
  sampling_params)`; cached reproductions are deterministic. Uncached
  drift is expected and tolerance widens accordingly.
- Eval-set content is not redistributed. If an upstream eval set changes
  (e.g. SWE-bench Verified is patched), `manifest().eval_set_sha256`
  updates and prior reproduction targets are marked obsolete in
  `published_numbers.json`.
