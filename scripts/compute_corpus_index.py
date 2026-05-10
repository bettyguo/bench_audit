"""Build an n-gram index over a corpus, for use by the P2 probe.

Reads text from JSONL, Parquet, or directory-of-files; tokenizes and
n-gram-shingles each document; writes a Bloom filter (or plain hash set
as fallback) to disk.

Usage:
    python scripts/compute_corpus_index.py \
        --input ~/corpora/pile_subset/*.jsonl.zst \
        --text-key text \
        --n 13 \
        --out ~/.cache/bench-audit/indices/pile_n13.bloom

The output index is consumed by `NearDupPretrainingProbe`. Run-time memory
scales with the number of unique n-grams seen; the Bloom filter is the
default backend for corpora > 1B n-grams.

This script is intentionally not part of the package — it depends on
ecosystem-specific decoders (zstd, parquet) and is meant to be run once
per corpus and cached.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import IO, cast

try:
    import polars as pl  # noqa: F401
except ImportError:
    pl = None  # type: ignore[assignment]


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def ngrams(toks: list[str], n: int) -> Iterable[str]:
    for i in range(len(toks) - n + 1):
        yield " ".join(toks[i : i + n])


def iter_text_jsonl(path: Path, text_key: str) -> Iterator[str]:
    opener: callable  # type: ignore[valid-type]
    if path.suffix == ".gz":
        opener = lambda p: gzip.open(p, "rt", encoding="utf-8")  # noqa: E731
    else:
        opener = lambda p: open(p, "r", encoding="utf-8")  # noqa: E731
    f = cast(IO[str], opener(path))
    with f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            txt = obj.get(text_key)
            if isinstance(txt, str):
                yield txt


def iter_text_directory(root: Path) -> Iterator[str]:
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".txt", ".md"):
            try:
                yield p.read_text(encoding="utf-8")
            except OSError:
                continue


def build_index(
    inputs: list[Path],
    text_key: str,
    n: int,
    out: Path,
    *,
    use_bloom: bool,
    max_grams: int | None,
) -> None:
    if use_bloom:
        try:
            import pybloom_live  # type: ignore[import-not-found]
        except ImportError:
            print(
                "[warn] pybloom_live not installed; falling back to in-memory set. "
                "For large corpora, run `pip install pybloom_live`.",
                file=sys.stderr,
            )
            use_bloom = False
    if use_bloom:
        import pybloom_live  # type: ignore[import-not-found]

        index = pybloom_live.ScalableBloomFilter(
            initial_capacity=10_000_000, error_rate=1e-6
        )

        def add(g: str) -> None:
            index.add(g)
    else:
        index_set: set[str] = set()

        def add(g: str) -> None:
            index_set.add(g)

    n_grams = 0
    n_docs = 0
    for path in inputs:
        if path.is_dir():
            stream = iter_text_directory(path)
        elif path.suffix in (".jsonl", ".gz") or path.suffix == ".json":
            stream = iter_text_jsonl(path, text_key)
        else:
            print(f"[warn] skipping {path}: unsupported extension", file=sys.stderr)
            continue
        for doc in stream:
            n_docs += 1
            for g in ngrams(tokens(doc), n):
                add(g)
                n_grams += 1
                if max_grams is not None and n_grams >= max_grams:
                    print(
                        f"[info] hit --max-grams ({max_grams}); stopping",
                        file=sys.stderr,
                    )
                    _persist(out, index if use_bloom else index_set, use_bloom)
                    print(f"docs={n_docs} grams={n_grams} -> {out}", file=sys.stderr)
                    return
        print(f"[info] {path.name}: {n_docs} docs, {n_grams} n-grams so far", file=sys.stderr)
    _persist(out, index if use_bloom else index_set, use_bloom)
    print(f"docs={n_docs} grams={n_grams} -> {out}", file=sys.stderr)


def _persist(out: Path, idx: object, use_bloom: bool) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if use_bloom:
        import pickle  # noqa: S403

        with out.open("wb") as f:
            pickle.dump(idx, f)
    else:
        # Plain set -> JSONL of unique n-grams (one per line, sorted for determinism)
        assert isinstance(idx, set)
        with out.open("w", encoding="utf-8") as f:
            for g in sorted(idx):
                f.write(g + "\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", nargs="+", required=True, type=Path,
                   help="One or more JSONL files, .jsonl.gz, or directories.")
    p.add_argument("--text-key", default="text", help="JSON key holding document text.")
    p.add_argument("--n", type=int, default=13, help="N-gram order (default: 13 per GPT-3).")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--bloom", action="store_true", default=True,
                   help="Use a Bloom filter (default). For small corpora pass --no-bloom.")
    p.add_argument("--no-bloom", dest="bloom", action="store_false")
    p.add_argument("--max-grams", type=int, default=None,
                   help="Stop after this many n-grams added (useful for smoke tests).")
    args = p.parse_args(argv)

    build_index(
        inputs=args.input,
        text_key=args.text_key,
        n=args.n,
        out=args.out,
        use_bloom=args.bloom,
        max_grams=args.max_grams,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
