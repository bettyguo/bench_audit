# SWE-bench Verified mini fixture

5 synthetic task records used by unit/integration tests. Each record's *shape* matches the upstream SWE-bench Verified format (`instance_id`, `repo`, `base_commit`, `problem_statement`, `test_patch`, `patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`), but the *content* is synthetic — patches are stubbed.

This fixture is **not** the real eval set. Real tasks ship under MIT license from `princeton-nlp/SWE-bench_Verified` on HuggingFace; we fetch them at runtime and verify against `manifest().eval_set_sha256`.

The fixture exists solely so unit tests can exercise the adapter and probe code paths offline.
