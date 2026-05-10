"""Diff a reproduction run against published numbers within a tolerance.

Reads `_reproduce_out/<slice>/results.jsonl`, looks up the target in
`docs/published_numbers.json`, and exits non-zero if any reproduction
falls outside tolerance.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slice", required=True)
    ap.add_argument("--tolerance", type=float, default=0.02)
    ap.add_argument("--published", type=Path, default=Path("docs/published_numbers.json"))
    ap.add_argument("--out", type=Path, default=Path("_reproduce_out"))
    args = ap.parse_args()

    if not args.published.exists():
        print(f"[skip] No published_numbers.json yet at {args.published}")
        return 0

    published = json.loads(args.published.read_text())
    slice_targets = published.get(args.slice)
    if slice_targets is None:
        print(f"[skip] No published numbers for slice '{args.slice}'")
        return 0

    results_path = args.out / args.slice / "results.jsonl"
    if not results_path.exists():
        print(f"[fail] No reproduction output at {results_path}")
        return 2

    failures: list[str] = []
    for line in results_path.read_text().splitlines():
        rec = json.loads(line)
        key = f"{rec['adapter_name']}::{rec['probe_name']}"
        target = slice_targets.get(key)
        if target is None:
            continue
        diff = abs(rec["effect_size"] - target)
        if diff > args.tolerance:
            failures.append(
                f"{key}: reproduced={rec['effect_size']:.4f} published={target:.4f} "
                f"diff={diff:.4f} > tolerance={args.tolerance:.4f}"
            )

    if failures:
        for f in failures:
            print(f"[fail] {f}")
        return 1
    print(f"[ok] All reproductions within ±{args.tolerance} of published.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
