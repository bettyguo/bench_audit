# Paper

Workshop-style preprint for `bench-audit`. Target venues: NeurIPS Datasets & Benchmarks workshop; ICLR Blog Post Track; safety-focused workshops at ICML/NeurIPS.

## Build

```bash
cd paper
latexmk -pdf main.tex
```

Or with docker:

```bash
docker run --rm -v "$PWD:/work" -w /work texlive/texlive:latest \
    latexmk -pdf -interaction=nonstopmode main.tex
```

## Status

Draft. Full-scale reproduction numbers (SWE-bench n=500, WebArena n=812, GAIA n=165) land before arXiv submission; the fixture-based numbers in Section 5 are the in-tree calibration.
