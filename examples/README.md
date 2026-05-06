# Examples

Standalone scripts that exercise the toolkit's MCP servers without ml-intern
in the loop. Useful for debugging tool descriptions, embedding the servers in
a different agent, or just confirming an install works.

| Script | What it does | Network? | Runtime |
|---|---|---|---|
| [`minimal_arxiv_query.py`](minimal_arxiv_query.py) | Builds the `arxiv-deep` server in-process and calls `implementation_brief` once on a paper of your choice. | yes (arxiv.org first time, then cached) | ~5 s warm, ~30 s cold |
| [`minimal_tracker_session.py`](minimal_tracker_session.py) | Creates a tmp SQLite tracker, runs three canned `start_run` / `log_metric` / `complete_run` cycles, prints `compare_runs` Markdown plus the `best_run` winner. | no | <1 s |

## Run them

```bash
cd ml-intern-mcp-toolkit
uv sync
uv run python examples/minimal_arxiv_query.py 2305.14314
uv run python examples/minimal_tracker_session.py
```

Pass any arxiv id as the first positional to `minimal_arxiv_query.py`; the
default is the QLoRA paper (`2305.14314`).

The tracker example does not write to your real database; it sets
`EXPERIMENT_TRACKER_DB_PATH` to a temp dir for the duration of the run.

## What to read after these

- `demo/README.md` for the full agent-driven loop.
- `docs/tool_reference.md` for every tool's input and output schema.
- `docs/architecture.md` for how the pieces fit together.
