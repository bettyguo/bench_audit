FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ca-certificates build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /work

COPY pyproject.toml uv.lock* ./
COPY src/ src/
COPY README.md LICENSE ./

RUN uv sync --all-extras --frozen 2>/dev/null \
    || uv sync --all-extras

ENTRYPOINT ["uv", "run", "bench-audit"]
CMD ["--help"]
