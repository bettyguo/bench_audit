# Maintainer outreach

Private outreach to a benchmark maintainer happens 14 days before any
public disclosure of a probe finding against that benchmark. This file
records the cadence and the per-benchmark status.

## Template

The first contact is a short email (and, where preferred, a GitHub issue on
the maintainer's tracker) containing:

1. A one-sentence framing of what we found.
2. The PDF report card for each affected probe.
3. The reproduction command and a link to the raw per-task JSONL.
4. A 14-day window before any public disclosure.
5. An explicit "we want to be wrong" line — corrections are welcome and
   will be documented.

## Cadence

- T-14: private outreach to all affected maintainer teams.
- T-7: follow-up; offer a call.
- T-0: public disclosure; maintainer response (if any) linked from the
  report card.

## v0.1 status

| Benchmark | Contact | Status |
|---|---|---|
| SWE-bench Verified | Carlos E. Jimenez (carlosej@princeton.edu), John Yang (johnby@stanford.edu) | pending; opens when the full-scale SWE-bench run lands |
| WebArena / WebArena Verified | Shuyan Zhou (CMU); ServiceNow for Verified | pending; opens when the full-scale WebArena run lands |
| GAIA | gaia-benchmark org (HF); Grégoire Mialon | pending; opens when the full-scale GAIA run lands |

This table is updated on every PR that progresses outreach. Public
disclosure is gated on `READY-FOR-DISCLOSURE` here.

## Escalation

If a maintainer responds, their response goes into the log below, dated,
with a link to the relevant issue or PR.

If a maintainer does not respond within 14 days, disclosure proceeds and
the report card carries "no response after 14-day window". The timeline
is not weakened.

If a maintainer disputes the finding, the technical thread happens on the
relevant GitHub issue, not Twitter.

## What we will not do

- Contact maintainers via Twitter DMs.
- Tag maintainers in launch tweets before the 14-day window has run.
- Coordinate venue posts (HN, r/MachineLearning) earlier than 14 days
  after outreach opens.

## Responses log

*(empty)*
