# Probe specs

Each probe has a spec document covering input, output, mechanism, null
distribution / control, calibration target, sample-size recommendation,
and known limitations.

| Probe | Family | Status |
|---|---|---|
| `hello` | smoke test | shipped |
| `p1_gold_answer_leak` | leak discovery | shipped |
| `p2_near_dup_pretraining` | training-data contamination | shipped |
| `p3_shortcut_feature` | structural shortcut | planned |
| `p4_harness_injection` | harness injection (Berkeley 7-pattern catalog) | shipped |
| `p5_reward_hacking` | behavioural | shipped |
| `p6_eval_set_visibility` | discoverability | shipped |
