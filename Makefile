.DEFAULT_GOAL := help
.PHONY: help setup test test-cov lint typecheck format demo docs docs-check clean

## help: Show this help message
help:
	@awk 'BEGIN { FS = ": " } /^## / { sub(/^## /, ""); print "  " $$0 }' $(MAKEFILE_LIST)

## setup: Bootstrap the development environment (uv sync, pre-commit hooks, .env)
setup:
	./scripts/setup.sh

## test: Run the pytest suite
test:
	uv run pytest

## test-cov: Run pytest with coverage on arxiv_deep and experiment_tracker
test-cov:
	uv run pytest \
		--cov=arxiv_deep --cov=experiment_tracker \
		--cov-branch \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov-fail-under=85

## lint: Check ruff lint and format (read-only)
lint:
	uv run ruff check .
	uv run ruff format --check .

## typecheck: Run mypy --strict on the source packages
typecheck:
	uv run mypy arxiv_deep experiment_tracker

## format: Apply ruff formatter and lint autofixes
format:
	uv run ruff format .
	uv run ruff check --fix .

## demo: Run the end-to-end demo script
demo:
	./demo/run_demo.sh

## docs: Regenerate docs/tool_reference.md from the live MCP server registrations
docs:
	uv run python scripts/gen_tool_reference.py

## docs-check: Verify docs/tool_reference.md is in sync with the source
docs-check:
	uv run python scripts/gen_tool_reference.py --check

## clean: Remove caches, coverage reports, and build artifacts
clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage dist build
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} +
