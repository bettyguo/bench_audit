# GAIA mini fixture

5 synthetic tasks following GAIA's task schema. Final answers are trivial public-knowledge facts, not real GAIA tasks (whose answers are gated on HuggingFace per the maintainer's contamination-prevention policy). The fixture exists solely to exercise the adapter and the gold-answer-leak probe offline.

Real GAIA tasks require accepting the dataset terms at https://huggingface.co/datasets/gaia-benchmark/GAIA and supplying the local checkout path as `fixture_dir`.
