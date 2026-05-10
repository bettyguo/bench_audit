.PHONY: help install dev test lint type fmt fmt-check ci docs serve-docs clean reproduce verify-result build release

PY := python
UV := uv

help:
	@echo "bench-audit Makefile"
	@echo ""
	@echo "Setup:"
	@echo "  install        install runtime deps via uv"
	@echo "  dev            install runtime + dev deps; install pre-commit hooks"
	@echo ""
	@echo "Quality gates (each is also a CI step):"
	@echo "  fmt            ruff format"
	@echo "  fmt-check      ruff format --check"
	@echo "  lint           ruff check"
	@echo "  type           mypy --strict src"
	@echo "  test           pytest -m 'not live and not docker'"
	@echo "  test-all       pytest (includes live, docker if available)"
	@echo "  ci             fmt-check + lint + type + test (the CI gate)"
	@echo ""
	@echo "Docs:"
	@echo "  docs           build mkdocs site"
	@echo "  serve-docs     serve mkdocs site at :8000"
	@echo ""
	@echo "Reproducibility:"
	@echo "  reproduce SLICE=<id>        reproduce a slice's published numbers"
	@echo "  verify-result FILE=path     verify a results JSONL against its raw data"
	@echo ""
	@echo "Release:"
	@echo "  build          build sdist + wheel"
	@echo "  release        tag, build, upload to PyPI (CI-only path)"

install:
	$(UV) sync

dev:
	$(UV) sync --all-extras
	$(UV) run pre-commit install

fmt:
	$(UV) run ruff format .

fmt-check:
	$(UV) run ruff format --check .

lint:
	$(UV) run ruff check .

type:
	$(UV) run mypy --strict src/bench_audit

test:
	$(UV) run pytest -m "not live and not docker" --cov=bench_audit --cov-report=term-missing

test-all:
	$(UV) run pytest --cov=bench_audit --cov-report=term-missing

ci: fmt-check lint type test
	@echo "CI gate passed."

docs:
	$(UV) run mkdocs build --strict

serve-docs:
	$(UV) run mkdocs serve

clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/ \
	    htmlcov/ .coverage coverage.xml _reproduce_out/ _site/ site/

SLICE ?=
reproduce:
	$(UV) run bench-audit reproduce --slice $(SLICE) --out _reproduce_out
	$(UV) run python scripts/diff_against_published.py --slice $(SLICE) --tolerance 0.02

FILE ?=
verify-result:
	@test -n "$(FILE)" || (echo "Usage: make verify-result FILE=path/to/result.jsonl"; exit 1)
	$(UV) run bench-audit verify-result $(FILE)

build:
	$(UV) build

release:
	@echo "Releases happen via tagged CI runs; see .github/workflows/release.yml"
	@exit 1
