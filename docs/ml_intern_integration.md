# Integrating `ml-intern-mcp-toolkit` with `ml-intern`

This guide wires the toolkit's two MCP servers (`arxiv-deep`, `experiment-tracker`) into [Hugging Face's `ml-intern` agent](https://github.com/huggingface/ml-intern) without forking it. After following this you will be able to ask `ml-intern` questions like *"read arxiv 2305.14314 and propose three LoRA-rank variants to try"* and have it call our tools end-to-end.

---

## How the integration works

`ml-intern` already supports user-supplied MCP server configurations. Its config loader (`agent/config.py`) deep-merges a user config over the upstream `configs/cli_agent_config.json` when launched. We exploit this seam: our `demo/ml_intern_config.json` becomes the user-config file, and `ml-intern` adds our two servers to its `ToolRouter` on every launch. **No upstream fork or working-tree edits are required.**

The merge layer is selected as follows (first match wins):

1. `$ML_INTERN_CLI_CONFIG` (path to a JSON file).
2. `~/.config/ml-intern/cli_agent_config.json`.
3. No user config.

We recommend option 1 during development (you can point at the toolkit checkout directly) and option 2 for permanent installation.

---

## Prerequisites

Confirm all of these once before launching `ml-intern`. Most failures in the troubleshooting section trace back to one of these being missing.

- `uv` installed and on `PATH`. Verify with `which uv`. The official installer (`curl -LsSf https://astral.sh/uv/install.sh | sh`) places it at `~/.local/bin/uv`.
- `ml-intern-mcp-toolkit` cloned and synced:
  ```bash
  cd <parent-dir>
  git clone https://github.com/MrRobotop/ml-intern-mcp-toolkit
  cd ml-intern-mcp-toolkit
  uv sync
  ```
  The `uv sync` is **not optional**. If you skip it, `ml-intern` will spawn `uv run arxiv-deep-server`, which will sync on first call and likely time out the MCP handshake.
- `ml-intern` cloned and synced as a sibling:
  ```bash
  cd <parent-dir>
  git clone https://github.com/huggingface/ml-intern
  cd ml-intern
  uv sync
  ```
- An Anthropic or OpenAI API key in `ml-intern/.env` (whichever model the upstream `cli_agent_config.json` selects).

---

## Required and optional environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `ML_INTERN_TOOLKIT_PATH` | **yes** | Absolute path to your `ml-intern-mcp-toolkit` checkout. Substituted into the `--project` flag of every `uv run` invocation. |
| `ML_INTERN_CLI_CONFIG` | recommended | Absolute path to `demo/ml_intern_config.json` so `ml-intern` picks up our servers without polluting `~/.config`. |
| `ARXIV_DEEP_CACHE_DIR` | no | Override for the arxiv-deep PDF / figure cache. Default: `~/.cache/arxiv-deep/`. |
| `EXPERIMENT_TRACKER_DB_PATH` | no | Override for the SQLite tracker database. Default: `~/.cache/experiment-tracker/runs.db`. |
| `HF_TOKEN` | yes for the demo | Hugging Face token for model uploads in Phase 4. Read by `ml-intern` itself. |

Set them in `ml-intern/.env` (or your shell profile):

```bash
ML_INTERN_TOOLKIT_PATH=/absolute/path/to/ml-intern-mcp-toolkit
ML_INTERN_CLI_CONFIG=/absolute/path/to/ml-intern-mcp-toolkit/demo/ml_intern_config.json
HF_TOKEN=hf_xxx...
ANTHROPIC_API_KEY=sk-ant-xxx...
```

---

## Launching ml-intern with our servers

```bash
cd <parent-dir>/ml-intern
uv run ml-intern
```

`ml-intern` reads `configs/cli_agent_config.json`, merges in our `demo/ml_intern_config.json` via the `$ML_INTERN_CLI_CONFIG` pointer, and spawns the two stdio MCP servers as subprocesses. On a clean session, the startup banner reports something like:

```
Loaded N MCP tools: arxiv-deep_fetch_paper, arxiv-deep_extract_figures,
arxiv-deep_find_reference_code, arxiv-deep_implementation_brief,
experiment-tracker_start_run, experiment-tracker_list_runs,
experiment-tracker_complete_run, experiment-tracker_log_metric,
experiment-tracker_log_artifact, experiment-tracker_compare_runs,
experiment-tracker_best_run (0 disabled)
```

`fastmcp` namespaces tools by server name to prevent cross-server collisions: every tool from server `<name>` appears as `<name>_<tool>` in the agent's tool list. The agent does not need help discovering this prefix; it sees the full names in its registered-tools list and calls them directly. If the banner reports fewer than 11 of *our* tools (the upstream `hf-mcp-server` adds its own on top), jump to *Troubleshooting* below.

---

## Verification

Two prompts confirm both servers are healthy. Paste each into the `ml-intern` REPL.

### Verify `arxiv-deep`

```
What arxiv-related tools do you have? Use one of them to fetch the title and
abstract of arxiv 2305.14314.
```

The agent should list `fetch_paper`, `extract_figures`, `find_reference_code`, and `implementation_brief`, then call `fetch_paper("2305.14314")` and report back the QLoRA paper's title and abstract.

### Verify `experiment-tracker`

```
What experiment-tracker tools do you have? Use them to: start a run called
'smoke-test' for model 'foo' on dataset 'bar' with hyperparameters
{"lr": 0.001}; log a metric called 'loss' at step 1 with value 0.5; then list
all runs.
```

The agent should call `start_run`, then `log_metric`, then `list_runs` and surface the persisted row including the `run_uid`.

Both transcripts should land in `ml-intern/session_logs/session_<id>.jsonl` for review.

---

## Common failure modes

**Symptom: ml-intern starts, says "Loaded 0 MCP tools".**

Either the config never loaded or both subprocesses failed. Check, in this order:

1. `echo $ML_INTERN_CLI_CONFIG` — non-empty and points at a file?
2. `cat $ML_INTERN_CLI_CONFIG | jq .` — valid JSON? Trailing commas are the usual culprit.
3. `cd $ML_INTERN_TOOLKIT_PATH && uv run arxiv-deep-server </dev/null` — does the server start? Look for `Starting arxiv-deep MCP server v...` on stderr. Ctrl-C to exit.

**Symptom: server starts manually but ml-intern times out on it.**

Almost always the first-launch venv sync. Run `cd $ML_INTERN_TOOLKIT_PATH && uv sync` once and relaunch ml-intern.

**Symptom: `ValueError: Environment variable 'ML_INTERN_TOOLKIT_PATH' is not set`.**

`ml-intern`'s env-var substituter (`agent/config.py:substitute_env_vars`) raises on undefined required variables. Set the variable in `ml-intern/.env` or your shell. The `${VAR:-default}` syntax allows fallbacks; `${VAR}` is required.

**Symptom: `command not found: uv` in session logs.**

`uv` is not on the PATH inherited by `ml-intern`. Inspect with `which uv` from the same shell that launches `ml-intern`. If empty, source your profile or reinstall `uv` (the official installer adds the right `PATH` line).

**Symptom: MCP tool returns "Error executing tool fetch_paper: ArxivFetchError: ..."**

Network or upstream arxiv issue. The toolkit caches PDFs at `$ARXIV_DEEP_CACHE_DIR/pdfs/`; once cached, subsequent calls do not re-download. Inspect `~/.cache/arxiv-deep/pdfs/` to see what landed.

**Symptom: tracker tool returns "RunNotFoundError".**

The `run_uid` you passed is not in the database under `$EXPERIMENT_TRACKER_DB_PATH`. Confirm by running `sqlite3 ~/.cache/experiment-tracker/runs.db 'SELECT run_uid, recipe, status FROM run;'`. If the database is in a different location, ensure both the agent and your inspection use the same `EXPERIMENT_TRACKER_DB_PATH`.

**Symptom: tools listed correctly but the agent never calls them.**

Tool descriptions are the agent's only signal for *when* to use a tool. If a description sounds vague, the agent will skip the tool. The toolkit's descriptions are tuned for ml-intern's reasoning patterns; if you find an edge case where the agent ignores a tool that should fit, file an issue with the prompt that triggered it so we can tighten the description.

---

## Where to look next

- `demo/ml_intern_config.json` — the canonical config snippet referenced by this doc.
- `arxiv_deep/server.py` and `experiment_tracker/server.py` — entry points that the `uv run` lines invoke.
- `ml-intern/session_logs/` — JSONL transcripts of every agent turn, including MCP tool calls and responses. The HF Agent Trace Viewer renders these natively.
- Phase 4 (in progress) wires this integration into a single `make demo` shell script that runs the full QLoRA-on-Oxford-Pets fine-tune loop.
