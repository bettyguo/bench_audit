# Security policy

This file covers vulnerabilities in bench-audit itself: bugs in probes
and adapters, false positives or false negatives that change a published
verdict. Vulnerabilities in audited benchmarks go through the
maintainer-outreach process in [docs/maintainer-outreach.md](docs/maintainer-outreach.md).

## Reporting

If you find a bug that could change a published verdict (a false-positive
in a P4 detector, a CI computed off by a factor, a schema invariant that
doesn't actually fire), please report it privately first.

- Email: `jacob.jikun.wu@gmail.com` (PGP on request).
- Or open a GitHub Security Advisory at
  https://github.com/jacobwu/bench-audit/security/advisories/new.

You can expect:

1. Acknowledgement within 48 hours.
2. Confirm or rebut within 7 days.
3. Fix or documented mitigation within 30 days for verdict-changing bugs.
4. Credit on a CHANGELOG entry (unless you decline).

## What counts as verdict-changing

- A probe's effect size or CI is computed incorrectly.
- A probe issues `verdict=fail` or `pass` when the correct verdict would
  be the opposite or `inconclusive`.
- `allow_small_n` or `allow_wide_ci` is set when it shouldn't be.
- An adapter's `manifest().eval_set_sha256` doesn't match the upstream
  eval set.
- A grader silently accepts a prediction shape the upstream evaluator
  would reject.

Typos, doc errors, lint nits, and correctness-neutral perf regressions
go to the public issue tracker.

## What we won't do

- Gag the reporter. Disclosure happens on whatever timeline you agree to.
- Pay for reports. There's no bug bounty budget.
- Retroactively edit a published `ProbeResult` JSON on the leaderboard.
  If a result was wrong, the original stays in place with an annotation
  pointing at the correction, so any paper that cited the wrong number
  can trace the trail.

## Threat model

See [docs/architecture.md](docs/architecture.md) for the longer write-up.
The adversaries on file:

- Cosmetic-patch attacks: maintainer renames a leak path without fixing
  the mechanism.
- Probe-gaming attacks: a model fine-tuned to avoid our lazy-agent
  recipe specifically.
- Manifest forgery: a manifest claims a hash that doesn't match the
  eval set.
- Result forgery: a fabricated `ProbeResult` JSON submitted to the
  leaderboard.

Defences: the schema invariants, the eval-set hash check, and
`bench-audit verify-result --strict`.
