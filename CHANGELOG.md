# Changelog

All notable changes to `ml-intern-mcp-toolkit` are recorded here. Format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`arxiv-deep` MCP server** with four tools that let an LLM agent read
  arxiv papers properly:
  - `fetch_paper(arxiv_id)`: title, authors, abstract, full body text
    (PyMuPDF), publication date, categories. Caches PDFs at
    `$ARXIV_DEEP_CACHE_DIR/pdfs/`.
  - `extract_figures(arxiv_id)`: per-figure dicts with page number,
    caption, and a path to a cached PNG. Falls back to rendering the
    full page when a `Figure N:` caption appears on a vector-only page
    so vector figures remain visible.
  - `find_reference_code(arxiv_id)`: GitHub URLs scraped from the paper
    body, validated concurrently via async HTTPX HEAD. Rate-limit and
    connection failures are reported, never raised.
  - `implementation_brief(arxiv_id)`: heuristic synthesis tool that
    surfaces title, core method, architecture components,
    hyperparameters, datasets, an evaluation paragraph, and the linked
    code repos. No LLM calls inside the tool; the calling agent is the
    reasoner.
- **`experiment-tracker` MCP server** with seven tools backed by a local
  SQLite database (SQLModel + SQLAlchemy 2.x):
  - `start_run`, `list_runs` (with filter dict), `complete_run`.
  - `log_metric`, `log_artifact`. Both raise `RunNotFoundError` on an
    unknown `run_uid`.
  - `compare_runs` (Markdown table sorted by metric value descending),
    `best_run` (returns `None` on empty DB / no-match filters / metric
    not present, documented in the tool description).
- **Foreign-key enforcement on every SQLite connection** via a
  SQLAlchemy `connect` event listener that issues
  `PRAGMA foreign_keys = ON`.
- **JSON column for `Run.hyperparameters`** with explicit
  `sa_column=Column(JSON, nullable=False)` so dicts round-trip cleanly.
- **End-to-end demo** at `demo/`:
  - `prompts/train_lora_alpaca.txt`: agent-facing instructions.
  - `scripts/train_local.py`: standalone CLI for LoRA fine-tuning
    `HuggingFaceTB/SmolLM2-135M-Instruct` on `tatsu-lab/alpaca`. Honours
    cuda > mps > cpu device selection, supports `--quick` (50/10/1ep
    iteration mode), `--push-to-hub` (refuses to overwrite an existing
    repo), and emits a generated model card.
  - `scripts/train_hf_jobs.py`: thin wrapper that submits the same
    script to Hugging Face's Jobs infrastructure via
    `huggingface_hub.run_uv_job` and parses the result line out of
    streamed logs.
  - `run_demo.sh`: orchestrator with env-var pre-flight, mode validation,
    and transcript capture to `demo/last_run.transcript.txt`.
- **`ml-intern` integration via the user-config layer**: `demo/ml_intern_config.json`
  is a real file users point `$ML_INTERN_CLI_CONFIG` at. No fork of
  upstream `ml-intern` required.
- **Documentation:** public README, architecture (with Mermaid diagrams),
  generated tool reference, troubleshooting guide, ml-intern integration
  guide, demo README. Two runnable example scripts under `examples/`.
- **CI matrix** across `{ubuntu-latest, macos-14}` x `{python-3.11,
  python-3.12}`. Lint + format + mypy + pytest with branch coverage.
  Pre-commit hooks: ruff, ruff format, secrets scan, mypy strict.
- **Test infrastructure:** hermetic suite with QLoRA fixture downloader,
  per-test cache redirection via env var, `block_arxiv_api` regression
  sentinel, schema round-trip test for the demo config, drift guard for
  the auto-generated tool reference.

### Changed

- **Demo target model and dataset** pivoted from `Qwen3-VL-2B` on
  Oxford Pets (the original PROMPTS.md spec) to
  `HuggingFaceTB/SmolLM2-135M-Instruct` on `tatsu-lab/alpaca`. Reason:
  `transformers` v5.x has a regression in the auto-loaded image-processor
  chain that affects every multimodal preset tested. The demo's
  narrative ("agent reads paper, runs three LoRA-rank variants, picks a
  winner, publishes") is unchanged; the iteration loop is roughly 25×
  faster.
- **Demo publish target** defaults to the authenticated user's HF
  namespace. `DEMO_PUSH_TO_ORG=1` opts in to publishing to
  `ml-agent-explorers/<repo>`.
- **`ml-intern` integration mechanism** is the user-config deep-merge
  layer (`$ML_INTERN_CLI_CONFIG`) rather than a direct edit of upstream's
  `configs/cli_agent_config.json`. PROMPTS.md's literal instruction would
  have forced consumers into a maintenance trap.

### Fixed

- **`extract_figures` test isolation regression.** `figures.py` imported
  `_download_pdf` directly into its module namespace, so test
  `monkeypatch.setattr(fetch_mod, "_download_pdf", fake)` calls did not
  take effect. The test "passed" by silently hitting live arxiv on every
  run and only failed when arxiv rate-limited macos-14/py3.12 with HTTP
  429. Switched to module-level reference + added the `block_arxiv_api`
  conftest fixture as a regression sentinel.

[Unreleased]: https://github.com/MrRobotop/ml-intern-mcp-toolkit/compare/HEAD
