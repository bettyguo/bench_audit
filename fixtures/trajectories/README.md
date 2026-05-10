# Hand-labelled trajectory fixtures

This directory holds the 50-trajectory hand-labelled set used to validate the reward-hacking signature rubric. The κ ≥ 0.7 gate (per docs/probes/p5_reward_hacking.md) requires three independent annotators; the live set is held in `fixtures/trajectories/labelled/` under a separate research license.

What ships in the repo:

- `mini/` — 10 *synthetic* trajectories, redistribution-safe, used by unit tests. Each has a known ground-truth label encoded in metadata. These are not the labelled set; they are toy cases that exercise the detectors.
- `labels_schema.json` — schema for the labelled-set records (annotator IDs, per-signature labels, gold-verdict).
- `rubric.md` — the labelling rubric the annotators follow.

The live labelled set will be added under `fixtures/trajectories/labelled/` after the three-annotator pass completes; until then, the probe ships with the stub classifier and is documented as κ-pending.
