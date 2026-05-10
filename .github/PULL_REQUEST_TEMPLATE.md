## What changes

<!-- 1-3 sentences. -->

## Why

<!-- One paragraph. -->

## Type

- [ ] Bug fix
- [ ] New probe
- [ ] New adapter
- [ ] Doc-only
- [ ] Tooling / CI / refactor
- [ ] **Verdict-changing** (changes a previously-published number on the leaderboard; link the maintainer-outreach record)

## Checklist

- [ ] `make ci` passes locally (`ruff check`, `ruff format --check`, `mypy --strict`, `pytest`).
- [ ] If the PR changes a probe's claim, the new `ProbeResult` has a CI.
- [ ] A verdict at `n < 30` sets `allow_small_n=True` and the PR explains why.
- [ ] A verdict with CI half-width > 0.1 sets `allow_wide_ci=True` and the PR explains why.
- [ ] No eval-set content added (fixtures are synthetic and redistribution-safe).
- [ ] No frontier-lab model outputs added.
- [ ] New probe/adapter has a spec doc under `docs/probes/` if applicable.

## Reproduction

<!-- If this PR affects a published number, paste the reproduction command and the diff. -->

```
$ bench-audit run --adapter ... --probe ...
verdict=... effect=... ci=[..., ...] n=...
```
