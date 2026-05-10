# FAQ

### What is bench-audit?

A library of probes that test agent benchmarks for known integrity failures: contamination, gold-answer leaks, harness-injection vulnerabilities, reward hacking. Every probe result carries a 95% Wilson CI enforced at the schema level.

### How is this different from Inspect AI / HELM / lm-eval-harness?

Those run models against benchmarks. bench-audit runs probes against benchmarks (and optionally against models). Inspect AI is the live-mode substrate.

### Are you saying SWE-bench / WebArena / GAIA are broken?

No. Specific failure modes documented by Berkeley RDI exist on every benchmark audited so far, including these three. The benchmarks are not worthless; they have measurable confounds.

### Did you find these contaminations?

No. Berkeley RDI (Wang et al., 2026-04) found the harness-injection patterns. METR (2025–present) measured the reward-hacking frequencies. OpenAI's internal audit (2026-02) found the SWE-bench Verified test breakages. This is a maintained tool for re-running those probes on new benchmarks and models.

### Your fixture-mode CIs are wide.

By construction. Fixtures are 5 tasks; Wilson 95% CI on 5/5 has half-width ≈0.22. Fixture runs are probe-validation. Real claims need the full eval set; every fixture-mode result is flagged `allow_wide_ci=True` and that flag is on the report card.

### Will you run bench-audit against my model?

Not without permission and budget. Use published predictions where labs have released them; live mode requires explicit permission.

### How do I add my benchmark?

[CONTRIBUTING.md](CONTRIBUTING.md). One Python file + one fixture directory + one test file.

### How is this licensed?

Apache-2.0.

### I want to cite this in a paper.

Cite Berkeley RDI 2026 and METR 2025 alongside bench-audit. The science is theirs; the packaging is ours.
