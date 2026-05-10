#!/usr/bin/env bash
# Reproduce a slice's published numbers from a clean machine.
# Usage: ./reproduce.sh <slice-id>

set -euo pipefail

SLICE="${1:?usage: ./reproduce.sh <slice-id>}"
OUT="${OUT:-_reproduce_out}"
TOL="${TOL:-0.02}"

if command -v docker >/dev/null 2>&1 && [ -z "${BENCH_AUDIT_NO_DOCKER:-}" ]; then
  echo "[reproduce] Using Docker."
  docker build -t bench-audit:repro .
  docker run --rm -v "$PWD/$OUT:/work/out" bench-audit:repro \
    reproduce --slice "$SLICE" --out /work/out
else
  echo "[reproduce] Docker unavailable; using local uv environment."
  command -v uv >/dev/null 2>&1 || {
    echo "[reproduce] uv not found; install from https://docs.astral.sh/uv/" >&2
    exit 1
  }
  uv sync --all-extras
  uv run bench-audit reproduce --slice "$SLICE" --out "$OUT"
fi

python scripts/diff_against_published.py --slice "$SLICE" --tolerance "$TOL" --out "$OUT"
