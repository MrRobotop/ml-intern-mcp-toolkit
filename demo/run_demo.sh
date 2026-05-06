#!/usr/bin/env bash
# End-to-end demo orchestrator.
#
# Reads the demo prompt, exports the env vars ml-intern needs, and hands the
# prompt to ml-intern's CLI in headless mode. The agent then drives the full
# loop (read paper, run three LoRA-rank variants, log to the tracker, pick a
# winner, publish).
#
# Required environment:
#
#   ML_INTERN_PATH         absolute path to the ml-intern checkout
#   ANTHROPIC_API_KEY      ml-intern's default model is Claude
#   HF_TOKEN               write-scope HF token for the publish step
#
# Optional environment:
#
#   DEMO_MODE              "local" (default) or "hf-jobs"
#   DEMO_QUICK             "1" to use the 50/10 subset instead of 1000/200
#   DEMO_PUSH_TO_ORG       "1" to publish to ml-agent-explorers/<repo>
#                          (default is the authenticated user's namespace)
#   DEMO_MODEL             override the default base model
#   DEMO_DATASET           override the default dataset
#   ML_INTERN_TOOLKIT_PATH absolute path to this checkout (auto-detected)
#   ML_INTERN_CLI_CONFIG   absolute path to demo/ml_intern_config.json
#                          (auto-detected from ML_INTERN_TOOLKIT_PATH)
#
# Output:
#
#   The agent transcript streams to stdout/stderr. A copy lands at
#   demo/last_run.transcript.txt (gitignored).

set -euo pipefail

# --- Paths -------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLKIT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ML_INTERN_TOOLKIT_PATH="${ML_INTERN_TOOLKIT_PATH:-$TOOLKIT_ROOT}"
ML_INTERN_CLI_CONFIG="${ML_INTERN_CLI_CONFIG:-$ML_INTERN_TOOLKIT_PATH/demo/ml_intern_config.json}"

PROMPT_FILE="$ML_INTERN_TOOLKIT_PATH/demo/prompts/train_lora_alpaca.txt"
TRANSCRIPT_FILE="$ML_INTERN_TOOLKIT_PATH/demo/last_run.transcript.txt"

# --- Defaults ----------------------------------------------------------------

DEMO_MODE="${DEMO_MODE:-local}"
DEMO_QUICK="${DEMO_QUICK:-0}"
DEMO_PUSH_TO_ORG="${DEMO_PUSH_TO_ORG:-0}"
DEMO_MODEL="${DEMO_MODEL:-HuggingFaceTB/SmolLM2-135M-Instruct}"
DEMO_DATASET="${DEMO_DATASET:-tatsu-lab/alpaca}"

# --- Pre-flight --------------------------------------------------------------

required_vars=(ML_INTERN_PATH HF_TOKEN ANTHROPIC_API_KEY)
missing=()
for var in "${required_vars[@]}"; do
    if [[ -z "${!var:-}" ]]; then
        missing+=("$var")
    fi
done
if (( ${#missing[@]} > 0 )); then
    echo "Demo aborted; missing required env vars: ${missing[*]}" >&2
    echo "See demo/README.md for the full list." >&2
    exit 1
fi

if [[ ! -d "$ML_INTERN_PATH" ]]; then
    echo "ML_INTERN_PATH=$ML_INTERN_PATH does not exist or is not a directory." >&2
    exit 1
fi

if [[ ! -f "$PROMPT_FILE" ]]; then
    echo "Prompt file missing: $PROMPT_FILE" >&2
    exit 1
fi

if [[ ! -f "$ML_INTERN_CLI_CONFIG" ]]; then
    echo "ml-intern user config missing: $ML_INTERN_CLI_CONFIG" >&2
    exit 1
fi

case "$DEMO_MODE" in
    local|hf-jobs) ;;
    *)
        echo "DEMO_MODE must be 'local' or 'hf-jobs'; got '$DEMO_MODE'." >&2
        exit 1
        ;;
esac

# --- Banner ------------------------------------------------------------------

cat <<EOF >&2
ml-intern-mcp-toolkit demo
  toolkit root  : $ML_INTERN_TOOLKIT_PATH
  ml-intern     : $ML_INTERN_PATH
  user config   : $ML_INTERN_CLI_CONFIG
  mode          : $DEMO_MODE
  quick         : $DEMO_QUICK
  push to org   : $DEMO_PUSH_TO_ORG
  base model    : $DEMO_MODEL
  dataset       : $DEMO_DATASET
  prompt        : $PROMPT_FILE
  transcript    : $TRANSCRIPT_FILE
EOF

# --- Hand off to ml-intern ---------------------------------------------------

export ML_INTERN_TOOLKIT_PATH ML_INTERN_CLI_CONFIG
export DEMO_MODE DEMO_QUICK DEMO_PUSH_TO_ORG DEMO_MODEL DEMO_DATASET

PROMPT="$(cat "$PROMPT_FILE")"

cd "$ML_INTERN_PATH"
# `tee` mirrors the transcript to disk so the user can review the run after
# the agent finishes; the transcript file is gitignored.
exec uv run ml-intern "$PROMPT" 2>&1 | tee "$TRANSCRIPT_FILE"
