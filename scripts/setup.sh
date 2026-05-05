#!/usr/bin/env bash
# Bootstrap the local development environment.
#
# Run via `make setup` or directly: `./scripts/setup.sh`.
#
# Steps:
#   1. Verify uv is installed (print install command if missing).
#   2. Sync runtime, dev, and demo dependencies.
#   3. Install pre-commit git hooks.
#   4. Bootstrap .env from .env.example if missing.
#   5. Print next-step instructions.

set -euo pipefail

# 1. Verify uv ----------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
    cat >&2 <<'MISSING'
uv is not installed.

Install on macOS / Linux:
    curl -LsSf https://astral.sh/uv/install.sh | sh

Then re-run this script.
MISSING
    exit 1
fi
echo "Detected $(uv --version)."

# 2. Sync dependencies --------------------------------------------------------
# Includes the demo extras so `make demo` works after a fresh setup. Skip the
# demo group with SETUP_NO_DEMO=1 if you do not need torch / transformers.
if [[ "${SETUP_NO_DEMO:-0}" == "1" ]]; then
    echo "Syncing runtime + dev (SETUP_NO_DEMO=1, demo extras skipped)..."
    uv sync --all-groups
else
    echo "Syncing runtime + dev + demo extras..."
    uv sync --all-groups --all-extras
fi

# 3. Install pre-commit hooks -------------------------------------------------
echo "Installing pre-commit git hooks..."
uv run pre-commit install

# 4. Bootstrap .env -----------------------------------------------------------
if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "Created .env from .env.example. Fill in values before running the demo."
else
    echo ".env already exists; not overwriting."
fi

# 5. Next steps ---------------------------------------------------------------
cat <<'NEXT'

Setup complete.

Next steps:
  - Edit .env with your ANTHROPIC_API_KEY, HF_TOKEN, and HuggingFace HF_TOKEN.
  - Run `make help` to list available targets.
  - Run `make lint typecheck` to verify static checks pass.
  - Run `make test` once tests exist (Phase 1 onward).
  - Run `make demo` once the end-to-end demo lands (Phase 4).
NEXT
