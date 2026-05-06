# Troubleshooting

Things that go wrong, why, and what to do. Each entry is **symptom → cause
→ fix**. Sorted roughly in the order a new user is likely to hit them.

If your symptom is not here, paste the relevant slice of
`session_logs/session_*.jsonl` (from ml-intern) or `demo/last_run.transcript.txt`
(from the demo) into a GitHub issue.

---

## Setup

### `command not found: uv`

**Cause.** `uv` is not on your shell's PATH. The official installer puts it
at `~/.local/bin/uv` but your shell may not source that directory.

**Fix.**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
exec $SHELL -l   # or open a new terminal
which uv
```

### `pymupdf` install fails on Apple Silicon

**Cause.** Older `pymupdf` releases lacked an arm64 wheel and tried to
build from source (which requires `mupdf-tools` from Homebrew). The
toolkit's pin (`pymupdf` from the default extras) is a recent release
that ships arm64 wheels.

**Fix.** Make sure your `uv sync` actually resolved the lockfile rather
than reading a stale cache:
```bash
rm -rf .venv
uv sync --refresh
```

### `ModuleNotFoundError: No module named 'huggingface_hub'`

**Cause.** You are running a script that needs the demo extras but only
ran `uv sync` (which installs the runtime + dev groups, not optional
extras). The demo extras are not in CI by design.

**Fix.**
```bash
uv sync --extra demo
```

---

## MCP servers

### MCP inspector cannot connect to my server

**Cause.** Most often: the server crashed during startup. Stdio over JSON-RPC
goes silent on the wire when the process dies, so the inspector hangs.

**Fix.** Run the server manually and watch stderr:
```bash
uv run arxiv-deep-server </dev/null
# or
uv run experiment-tracker-server </dev/null
```
The first line should be `Starting <server> MCP server v...`. Anything else
is a startup failure with a real traceback.

If the server starts cleanly here but the inspector still cannot connect,
check that the inspector's `--project` flag points at this checkout and
not at a different one without the toolkit installed.

### ml-intern starts but reports 0 of my tools

**Cause.** Either the user-config layer never loaded, or both subprocesses
failed to start. Three classic offenders:

1. **`$ML_INTERN_CLI_CONFIG` is unset or points at the wrong file.**
   `echo $ML_INTERN_CLI_CONFIG` should print the absolute path to
   `demo/ml_intern_config.json` in this checkout.
2. **JSON syntax error in the user config.** `cat $ML_INTERN_CLI_CONFIG | jq .`
   should pretty-print without complaint. Trailing commas are the usual
   failure mode.
3. **`uv` not on the PATH that ml-intern inherits.** Run
   `which uv` from the same shell that launches ml-intern. If empty, fix
   your PATH and relaunch.

### ml-intern times out on my server's first call

**Cause.** First-launch venv sync. `uv run --project ... arxiv-deep-server`
does an implicit `uv sync` if the project's `.venv` is missing or stale.
That can take 15-30 s; ml-intern's MCP handshake will time out before
training begins.

**Fix.**
```bash
cd ml-intern-mcp-toolkit
uv sync
```
once, then relaunch ml-intern. Subsequent starts are instant.

### `ValueError: Environment variable 'ML_INTERN_TOOLKIT_PATH' is not set`

**Cause.** ml-intern's config loader strict-substitutes `${VAR}` (no
default) and raises if the variable is unset.

**Fix.** Add the variable to `ml-intern/.env`:
```bash
echo "ML_INTERN_TOOLKIT_PATH=$(cd path/to/ml-intern-mcp-toolkit && pwd)" \
    >> /path/to/ml-intern/.env
```

---

## arxiv-deep

### `ArxivFetchError: Page request resulted in HTTP 429`

**Cause.** arxiv rate-limits the metadata API per IP. Most common during
parallel CI runs hitting the same paper simultaneously.

**Fix.** Cached PDFs survive across runs; the next attempt should pick up
the cached file and skip the API. If you are seeing this in CI, throttle
the parallel matrix or restrict the live arxiv path to a single matrix
cell.

### Rate-limited by GitHub during `find_reference_code`

**Cause.** GitHub returns HTTP 403 with `X-RateLimit-Remaining: 0` for
unauthenticated HEAD requests after about 60/hour per IP. The tool sets
`validated=False` and continues; nothing is wrong functionally, but the
agent loses signal.

**Fix.** Set `GITHUB_TOKEN` in your shell or `.env`. The HEAD requests
will then run under the token's much higher rate limit.

### `find_reference_code` returns URLs that fail to validate locally

**Cause.** Some legitimate GitHub repos rate-limit unauthenticated HEAD
requests, return 403 with `X-RateLimit-Remaining: 0`, or sit behind a
geo-restriction. The tool flags these as `validated=False` and logs a
warning rather than raising, so the agent can surface the URL anyway.

**Fix.** Check the URL manually, or set `GITHUB_TOKEN` for higher limits.

### `extract_figures` returns fewer figures than the paper has

**Cause.** Some arxiv papers ship figures as vector-only PDF objects
that `pymupdf.Page.get_images()` does not surface (it only sees raster
XObjects). The tool falls back to rendering the entire page at 200 DPI
when a `Figure N:` caption appears on a page without raster images, but
the heuristic depends on the caption regex matching. Papers with non-
standard caption formats may evade detection.

**Fix.** Open the PDF manually to confirm the missing figure exists.
File an issue with the arxiv id and the missing figure number; we can
extend the caption regex if the pattern is generalisable.

---

## experiment-tracker

### `IntegrityError: FOREIGN KEY constraint failed`

**Cause.** This is the *correct* behaviour: you tried to log a metric or
artifact against a `run_uid` that does not exist in the database. The
tracker's FK enforcement is intentional and on every connection.

**Fix.** Verify the run was actually started:
```bash
sqlite3 ~/.cache/experiment-tracker/runs.db \
    'SELECT run_uid, recipe, status FROM run;'
```
If the run is missing, call `start_run` again. If it is present, double-
check the `run_uid` you are passing.

### `RunNotFoundError` when the agent thinks the run exists

**Cause.** Almost always a `EXPERIMENT_TRACKER_DB_PATH` mismatch. The
agent and your inspection tool resolved different DB files.

**Fix.** `echo $EXPERIMENT_TRACKER_DB_PATH` and confirm both your shell
and the ml-intern process see the same value. If empty, both default to
`~/.cache/experiment-tracker/runs.db`.

### `compare_runs` Markdown table puts the highest loss first

**Cause.** `compare_runs` always sorts descending by metric value. For
"loss", lower is better, so the visual ordering looks wrong if you
expected a leaderboard.

**Fix.** Use `best_run` with `direction="min"` for the actual winner;
`compare_runs` is a presentational helper, not a ranking. The agent can
interpret either signal.

---

## Demo

### `Demo aborted; missing required env vars: ...`

**Cause.** `run_demo.sh` pre-flights `ML_INTERN_PATH`, `HF_TOKEN`, and
`ANTHROPIC_API_KEY`. One or more is unset.

**Fix.** Set them in `ml-intern/.env` so `agent.config.load_config`
substitutes them:
```bash
read -rs ANTHROPIC_API_KEY  # never paste secrets into chat
echo "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY" >> /path/to/ml-intern/.env
```
Same pattern for `HF_TOKEN`.

### Training script fails with "no GPU available" on Apple Silicon

**Cause.** A model or op the script invokes is not yet supported by the
MPS backend.

**Fix.** Confirm the env var made it through:
```bash
echo $PYTORCH_ENABLE_MPS_FALLBACK
```
The orchestrator and `train_local.py` both set it, but if you are
running the script in an unusual context, set it explicitly:
```bash
export PYTORCH_ENABLE_MPS_FALLBACK=1
```

### HF Jobs run never returns

**Cause.** Jobs cold-start on first invocation can exceed the default
timeout while `uv` provisions the runner. The polling loop in
`train_hf_jobs.py` waits indefinitely; `ml-intern` may give up first.

**Fix.** Inspect the job manually:
```bash
uv run python -c "from huggingface_hub import inspect_job; \
    print(inspect_job(job_id='<id-from-the-logs>', namespace=None))"
```
If the stage is still `RUNNING`, increase `--timeout` (e.g. `--timeout 1h`)
or wait. If `ERROR`, fetch the full logs:
```bash
uv run python -c "from huggingface_hub import fetch_job_logs; \
    [print(l, end='') for l in fetch_job_logs(job_id='<id>', namespace=None)]"
```

### Demo published the wrong adapter

**Cause.** `train_local.py` writes the adapter for whichever rank it was
last invoked with. If the agent invokes `--push-to-hub` for the wrong
run UID by mistake, the published artefact reflects that last call, not
the comparison winner.

**Fix.** Re-invoke `train_local.py` for the correct run with the right
hyperparameters and a fresh repo suffix; the refuse-if-exists guard
prevents overwriting the wrong-but-published one. Check
`experiment_tracker.tools.runs.list_runs` to confirm which run actually
won.

---

## CI

### `tests/integration/test_tool_reference_in_sync.py` fails

**Cause.** A tool description, schema, or registration changed but
`docs/tool_reference.md` was not regenerated.

**Fix.**
```bash
make docs
git add docs/tool_reference.md
git commit
```

### `block_arxiv_api` raises in a test that should be hermetic

**Cause.** A consumer module imported `_download_pdf` or `_fetch_metadata`
directly into its namespace at module load, so the test's
`monkeypatch.setattr` on `arxiv_deep.tools.fetch._download_pdf` did not
take effect.

**Fix.** Switch the consumer to import the *module* and reference the
attribute at call time:
```python
from arxiv_deep.tools import fetch as _fetch
# ... _fetch._download_pdf(...)
```
The decisions log entry from 2026-05-06 in `CLAUDE.md` has the full
backstory.
