# PROMPTS.md

The full prompt ladder for `ml-intern-mcp-toolkit`. Six phases, executed in strict order. Inside a phase, follow the prompt sequence top to bottom, applying the parallelisation strategy from `README_PROMPTS.md`.

**Before starting any phase**, read `README_PROMPTS.md` end to end. The execution loop, subagent playbook, and quality gates apply to every prompt below.

**Hardware target:** Apple Silicon M5 Pro. Where M5 Pro specifics matter, prompts call them out explicitly.

---

## Table of contents

- [Phase 0: Bootstrap](#phase-0-bootstrap)
- [Phase 1: arxiv-deep MCP server](#phase-1-arxiv-deep-mcp-server)
- [Phase 2: experiment-tracker MCP server](#phase-2-experiment-tracker-mcp-server)
- [Phase 3: ml-intern integration](#phase-3-ml-intern-integration)
- [Phase 4: End-to-end demo](#phase-4-end-to-end-demo)
- [Phase 5: Documentation and examples](#phase-5-documentation-and-examples)
- [Phase 6: Release engineering](#phase-6-release-engineering)

---

## Phase 0: Bootstrap

**Goal:** A clean, opinionated repository skeleton that other phases can build on without surprises. No application code yet.

**Done when:** `git status` is clean, `uv sync` succeeds, `pre-commit run --all-files` passes, the empty CI workflow runs green on push.

### Prompt 0.1: Repo scaffold

> Read `CLAUDE.md` in full. Confirm in two sentences which phase we are in and what the immediate goal is.
>
> Then scaffold the repository skeleton exactly as documented in the "Repository layout" section of `CLAUDE.md`. Create every directory and an empty `.gitkeep` in any otherwise empty leaf. Do not create any application code yet, only the skeleton.
>
> Initialise `pyproject.toml` with `uv init --package`. Set the project name to `ml-intern-mcp-toolkit`, the Python requirement to `>=3.11,<3.13`, and add an empty `[project.scripts]` section.
>
> Create `.gitignore` covering: `.venv/`, `__pycache__/`, `*.pyc`, `.env`, `.env.*`, `.coverage`, `htmlcov/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `tests/fixtures/cache/`, `~/.cache/arxiv-deep/`, `*.pdf`, `*.png` (except in `docs/images/`), `dist/`, `build/`, `*.egg-info/`, `uv.lock` is committed.
>
> Commit with message `chore: bootstrap repo skeleton`.

### Prompt 0.2: License and governance

> Add three files at the repo root:
>
> 1. `LICENSE` containing the standard Apache 2.0 license text, with copyright line: `Copyright 2026 [Your Name]`. Use the placeholder `[Your Name]`; the user will replace it.
> 2. `CODE_OF_CONDUCT.md` containing the Contributor Covenant 2.1 verbatim.
> 3. `CONTRIBUTING.md` with sections: How to file an issue, How to submit a PR, Local development setup (referencing `make setup`), Coding standards (linking to the Conventions section of CLAUDE.md), Test requirements, Commit message format.
>
> Update the decisions log in `CLAUDE.md` to mark the license decision as confirmed with today's date.
>
> Commit with message `docs: add license, code of conduct, contributing guide`.

### Prompt 0.3: Dependency declaration

> Edit `pyproject.toml` to declare three dependency groups:
>
> 1. Runtime (`dependencies`): `mcp`, `pydantic>=2`, `httpx`, `pymupdf`, `arxiv`, `sqlmodel`, `python-dotenv`.
> 2. Dev (`[dependency-groups].dev`): `pytest`, `pytest-asyncio`, `pytest-cov`, `respx`, `freezegun`, `ruff`, `mypy`, `pre-commit`.
> 3. Demo (`[project.optional-dependencies].demo`): `transformers`, `peft`, `accelerate`, `datasets`, `huggingface_hub`, `torch>=2.5`.
>
> Pin `mcp` to a specific version. Run `uv pip search mcp` or check the PyPI page first to find the latest stable release; pin to that version exactly.
>
> Run `uv sync --all-groups` and verify it succeeds on Apple Silicon. If any package fails to install with an "no compatible wheel" error, stop and report it before continuing.
>
> Commit with message `chore: declare runtime, dev, and demo dependencies`.

### Prompt 0.4: Tooling configuration

> Add the following config files:
>
> 1. `.pre-commit-config.yaml` with hooks: `ruff` (lint and format), `mypy` (scoped to `arxiv_deep/` and `experiment_tracker/`), `gitleaks` for secrets, `check-yaml`, `end-of-file-fixer`, `trailing-whitespace`.
> 2. In `pyproject.toml`, add `[tool.ruff]` with line length 100, target Python 3.11, enable rule sets E, F, I, N, UP, B, A, C4, SIM, RUF.
> 3. In `pyproject.toml`, add `[tool.mypy]` with `strict = true`, `python_version = "3.11"`, exclude tests.
> 4. In `pyproject.toml`, add `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`, `testpaths = ["tests"]`, registered markers: `slow`, `integration`, `network`.
>
> Run `pre-commit install` then `pre-commit run --all-files`. Fix any complaints. The repo must be lint-clean before continuing.
>
> Commit with message `chore: configure ruff, mypy, pre-commit, pytest`.

### Prompt 0.5: Makefile and setup script

> Create `Makefile` at the repo root with these targets:
>
> - `setup`: runs `./scripts/setup.sh`.
> - `test`: runs `uv run pytest`.
> - `test-cov`: runs `uv run pytest --cov=arxiv_deep --cov=experiment_tracker --cov-report=term-missing`.
> - `lint`: runs `uv run ruff check . && uv run ruff format --check .`.
> - `typecheck`: runs `uv run mypy arxiv_deep experiment_tracker`.
> - `format`: runs `uv run ruff format . && uv run ruff check --fix .`.
> - `demo`: runs `./demo/run_demo.sh`.
> - `clean`: removes `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `htmlcov`, coverage files, build artifacts.
>
> Each target has a comment line above describing what it does. The `help` target prints all targets with their descriptions.
>
> Create `scripts/setup.sh` (executable) that:
>
> 1. Verifies `uv` is installed; prints install instructions if not.
> 2. Runs `uv sync --all-groups`.
> 3. Runs `uv run pre-commit install`.
> 4. Copies `.env.example` to `.env` if `.env` does not exist.
> 5. Prints next-step instructions.
>
> Create `.env.example` with placeholder lines for `ANTHROPIC_API_KEY`, `HF_TOKEN`, `GITHUB_TOKEN`, with comments explaining where each is used.
>
> Commit with message `chore: add Makefile, setup script, env example`.

### Prompt 0.6: CI scaffolding

> Create `.github/workflows/ci.yml` with:
>
> - Triggers: push to main, pull request.
> - Matrix: `os` in `[ubuntu-latest, macos-14]`, `python-version` in `["3.11", "3.12"]`.
> - Steps: checkout, install uv, restore uv cache, `uv sync --all-groups`, `make lint`, `make typecheck`, `make test-cov`.
> - Upload coverage as an artifact (no third-party uploader yet).
>
> Create `.github/workflows/lint.yml` for fast feedback on PRs: same as ci.yml but only lint and typecheck on `ubuntu-latest` + `python-3.12`.
>
> Create `.github/dependabot.yml` to auto-update GitHub Actions and Python dependencies weekly.
>
> Create `.github/PULL_REQUEST_TEMPLATE.md` with sections: What changed, Why, Testing done, Checklist (lint, tests, docs).
>
> Create `.github/ISSUE_TEMPLATE/bug_report.md` and `.github/ISSUE_TEMPLATE/feature_request.md` with sensible defaults.
>
> Add a basic placeholder test in `tests/test_smoke.py`: `def test_imports(): import arxiv_deep, experiment_tracker`. The test should fail right now because those packages do not exist yet; create empty `__init__.py` files for them so it passes.
>
> Push to a branch (the user will set up GitHub remote first). Confirm CI runs green.
>
> Commit with message `ci: add GitHub Actions workflows and templates`.

### Phase 0 exit gate

Before starting Phase 1, verify all of these:

- `git status` clean.
- `uv sync --all-groups` succeeds on macOS (M5 Pro) and Linux (CI).
- `make lint`, `make typecheck`, `make test` all pass.
- CI workflow shows green on at least one push.
- `pre-commit run --all-files` passes.
- README skeleton exists (it is fine if it is empty for now; Phase 5 fills it).
- All decisions in `CLAUDE.md` decisions log are dated.

If any are red, fix before Phase 1.

---

## Phase 1: arxiv-deep MCP server

**Goal:** Four working tools (`fetch_paper`, `extract_figures`, `find_reference_code`, `implementation_brief`), test coverage above 85%, MCP inspector verifies all schemas, and ml-intern can list them.

**Parallelisation note:** Prompts 1.6 and 1.7 are the parallel opportunity in this phase. Run them as concurrent subagents per `README_PROMPTS.md`.

### Prompt 1.1: Confirm MCP SDK mental model

> Read the installed `mcp` package source (under `.venv/lib/python*/site-packages/mcp/`) and the official docs at https://github.com/modelcontextprotocol/python-sdk.
>
> Summarise in roughly 10 bullet points:
>
> - How tools are registered (decorator versus class-based, current preferred pattern for the pinned version).
> - How input and output schemas work and how Pydantic models integrate.
> - How errors should be surfaced to the client.
> - Async versus sync tool handlers, and which is preferred.
> - Stdio versus HTTP transport configuration and when each is used.
> - How tool descriptions are exposed to the calling agent.
> - Lifecycle hooks (`initialize`, `shutdown`) and whether we need them.
> - Logging configuration.
> - Any gotchas relevant to a server running under `ml-intern`.
> - Any version-specific quirks compared to general MCP documentation online.
>
> Do not write any tool code yet. I will confirm your mental model before implementation.

### Prompt 1.2: Server skeleton

> Implement the `arxiv-deep` server skeleton:
>
> 1. `arxiv_deep/server.py` with a stdio MCP server, no tools registered yet, an `if __name__ == "__main__"` block that runs the server.
> 2. `arxiv_deep/exceptions.py` with `ArxivDeepError` (base), `InvalidArxivIdError`, `ArxivFetchError`, `FigureExtractionError`, `CodeFinderError`. All inherit from `ArxivDeepError` which inherits from `Exception`.
> 3. `arxiv_deep/__init__.py` exporting the exceptions and a version string read from `pyproject.toml`.
>
> Add an entry-point script in `pyproject.toml`: `arxiv-deep-server = "arxiv_deep.server:main"`.
>
> Verify: `uv run python -m arxiv_deep.server` starts and waits on stdin without errors. Then verify with the MCP inspector: `npx @modelcontextprotocol/inspector uv run python -m arxiv_deep.server`. The tool list should be empty but the server should connect.
>
> Commit with message `feat(arxiv-deep): server skeleton with typed exceptions`.

### Prompt 1.3: Test fixtures

> Create `tests/fixtures/download_fixture.py`:
>
> - Downloads arxiv paper 2305.14314 (QLoRA) PDF once.
> - Caches under `tests/fixtures/cache/2305.14314.pdf`.
> - Idempotent: if the file exists and is non-empty, do nothing.
> - Run via `python tests/fixtures/download_fixture.py`.
>
> Create `tests/conftest.py` with these fixtures:
>
> - `qlora_pdf_path`: returns Path to the cached QLoRA PDF, calling the downloader if missing.
> - `tmp_cache_dir`: yields a tmp directory and patches `arxiv_deep` cache locations to point at it.
> - `mock_github_validator`: a `respx` fixture that mocks GitHub HEAD requests for offline test runs.
>
> Run the downloader once. Confirm `tests/fixtures/cache/2305.14314.pdf` exists and exceeds 1 MB. Confirm it is gitignored.
>
> Commit with message `test: add QLoRA fixture downloader and shared fixtures`.

### Prompt 1.4: Tests for fetch_paper

> Write `tests/arxiv_deep/test_fetch_paper.py` with these tests for a tool `fetch_paper(arxiv_id: str) -> dict`. Returned dict must have keys with these types:
>
> - `title` (str)
> - `authors` (list[str])
> - `abstract` (str)
> - `full_text` (str)
> - `published_date` (str, ISO 8601)
> - `categories` (list[str])
>
> Test cases:
>
> 1. Happy path with the QLoRA fixture. Assert all keys present, types correct, title contains "QLoRA" (case-insensitive), authors list non-empty, full_text length above 5000.
> 2. `fetch_paper("not-a-real-id")` raises `InvalidArxivIdError`.
> 3. `fetch_paper("2305.14314")` called twice does not re-download (mock the downloader and assert call count is 1).
> 4. Full text contains "4-bit" (paper-specific content sanity check).
> 5. ID normalisation: `"arXiv:2305.14314"`, `"https://arxiv.org/abs/2305.14314"`, and `"2305.14314"` all return identical results.
>
> Tests should fail with `ImportError` since the tool does not exist yet. That is expected. Show me the failure output.

### Prompt 1.5: Implement fetch_paper

> Implement `fetch_paper` in `arxiv_deep/tools/fetch.py`. Register it on the MCP server in `arxiv_deep/server.py`. Make all tests from Prompt 1.4 pass.
>
> Constraints:
>
> - Use the `arxiv` library for metadata.
> - Use `pymupdf` for full-text extraction.
> - Cache downloaded PDFs at `~/.cache/arxiv-deep/pdfs/<arxiv_id>.pdf` (use `pathlib.Path.home()`, no `os.path` calls).
> - Catch network errors and raise `ArxivFetchError` with a useful message.
> - Raise `InvalidArxivIdError` for malformed IDs. Validate with a regex matching `^\d{4}\.\d{4,5}(v\d+)?$` after normalisation.
> - Type-hint every function. `mypy --strict` must pass on the new file.
>
> Iterate until all tests pass. Do not skip any test. Then run the full pytest suite to confirm nothing else regressed.
>
> Commit with message `feat(arxiv-deep): implement fetch_paper tool`.

### Prompt 1.6 and 1.7: Parallel implementation of figures and code finder

> **Run these as two parallel subagents per `README_PROMPTS.md`. Both depend only on `fetch_paper`, which is already implemented.**

#### Prompt 1.6 (subagent A): extract_figures

> Brief for subagent A:
>
> CONTEXT: `CLAUDE.md` and the just-merged `fetch_paper`. Read both before starting.
>
> INPUT CONTRACT: `extract_figures(arxiv_id: str) -> list[dict]`. Each dict has `page_number` (int, 1-indexed), `caption` (str, may be empty), `image_path` (str, absolute path to extracted PNG).
>
> CONSTRAINTS:
>
> - Extracted images go under `~/.cache/arxiv-deep/figures/<arxiv_id>/figure_<n>.png`.
> - Use pymupdf's image extraction. For captions, after each extracted image, scan the same page for a line matching `^Figure\s+\d+[:.]` and take that line plus the one following.
> - Raise `FigureExtractionError` on PDF read failure.
> - Type-hint everything; `mypy --strict` must pass.
>
> TESTS FIRST: write `tests/arxiv_deep/test_extract_figures.py` covering:
> - QLoRA fixture returns at least 3 figures.
> - At least one figure has a non-empty caption.
> - Every `image_path` exists on disk and starts with PNG magic bytes.
> - All `page_number` values are positive.
> - Calling twice with the same arxiv_id reuses cached images (assert files are not rewritten).
>
> DEFINITION OF DONE: tests green, MCP server registers `extract_figures`, MCP inspector lists it with valid schema.
>
> Commit with message `feat(arxiv-deep): implement extract_figures tool`.

#### Prompt 1.7 (subagent B): find_reference_code

> Brief for subagent B:
>
> CONTEXT: `CLAUDE.md` and the just-merged `fetch_paper`. Read both before starting.
>
> INPUT CONTRACT: `find_reference_code(arxiv_id: str) -> list[dict]`. Each dict has `url` (str), `context` (str, ~200 chars surrounding text), `validated` (bool).
>
> CONSTRAINTS:
>
> - Regex GitHub URLs from full paper text: `https?://github\.com/[\w.-]+/[\w.-]+`.
> - Validate each via async HTTPX `HEAD` with 5-second timeout.
> - On 403 with rate-limit headers, set `validated = False`, do not raise.
> - On any other error, set `validated = False` and log a warning.
> - Type-hint everything; `mypy --strict` must pass.
>
> TESTS FIRST: write `tests/arxiv_deep/test_find_reference_code.py` covering:
> - QLoRA fixture returns at least one github.com URL.
> - All returned URLs match the GitHub pattern.
> - Validated URLs reachable (mark this test `@pytest.mark.network` and gate on env var).
> - Stub paper with no URLs returns `[]`, no error.
> - Use `respx` to mock GitHub responses for non-network tests.
>
> DEFINITION OF DONE: tests green, MCP server registers `find_reference_code`, MCP inspector lists it.
>
> Commit with message `feat(arxiv-deep): implement find_reference_code tool`.

### Prompt 1.8: Integrate subagent results

> Both subagents have reported back. On the main thread:
>
> 1. Pull both branches/changes into the working tree.
> 2. Resolve any conflicts in `arxiv_deep/server.py` (both subagents register a tool there).
> 3. Run the full test suite. All tests must pass. If a flaky test appears, fix it, do not retry.
> 4. Run `make lint`, `make typecheck`. Both must pass.
> 5. Restart the server and verify with the MCP inspector: all three tools (`fetch_paper`, `extract_figures`, `find_reference_code`) are listed with valid schemas. Call each once and paste the output.

### Prompt 1.9: implementation_brief

> Implement the synthesis tool. Signature: `implementation_brief(arxiv_id: str) -> dict` with keys:
>
> - `title` (str)
> - `core_method` (str, 1-2 sentence summary of the main technique, extracted from abstract)
> - `architecture` (list[str], components mentioned)
> - `hyperparameters` (dict[str, str], identified hyperparameters with values where given)
> - `dataset` (list[str], datasets used)
> - `eval_protocol` (str, how success is measured)
> - `reference_implementations` (list[dict], output from `find_reference_code`)
>
> Implementation rules:
>
> - Call `fetch_paper` and `find_reference_code` internally; do not duplicate their work.
> - Use heuristics for extraction: regex for `learning rate`, `batch size`, `lr = X`, `epochs`; keyword spotting for common datasets (ImageNet, COCO, GLUE, etc.); section heading detection for evaluation.
> - **No LLM calls inside this tool.** The calling agent reasons; this tool extracts structure.
>
> Tests in `tests/arxiv_deep/test_implementation_brief.py`:
>
> - Returns non-empty `architecture`.
> - At least one `reference_implementations` entry for QLoRA.
> - `hyperparameters` contains at least one entry.
> - Structure is correct even when extraction is fuzzy (no assertion on exact content).
>
> Tests first, then implementation. Iterate until green.
>
> Commit with message `feat(arxiv-deep): implement implementation_brief synthesis tool`.

### Prompt 1.10: Phase 1 verification (3 parallel subagents)

> Spawn three subagents in parallel:
>
> **Subagent A (full test suite):** Run `make test-cov`. Confirm coverage is above 85% line and 75% branch on `arxiv_deep/`. Report exact numbers.
>
> **Subagent B (MCP inspector smoke):** Start the arxiv-deep server, connect via MCP inspector, list tools, call `implementation_brief("2305.14314")`. Capture and return the full response.
>
> **Subagent C (hygiene scan):** Run `git status`, `make lint`, `make typecheck`, and a recursive grep for `sk-`, `hf_`, `ghp_`. All must come back clean.
>
> When all three return, integrate. If any fails, stop and fix before declaring Phase 1 done.

### Phase 1 exit gate

- All four arxiv-deep tools have green tests.
- Coverage on `arxiv_deep/` above 85% line, 75% branch.
- MCP inspector lists all four tools with valid schemas.
- `make lint` and `make typecheck` both pass.
- No secrets in git history.
- `CLAUDE.md` decisions log updated with any choices made during the phase.

Commit, push, **start a fresh Claude Code session for Phase 2.**

---

## Phase 2: experiment-tracker MCP server

**Goal:** Six working tools for run logging and comparison, full coverage, MCP inspector verification.

**Parallelisation note:** Prompts 2.5, 2.6, 2.7 (the three independent tool groups) can run as parallel subagents. Schema and DB layer (Prompts 2.2, 2.3) must be sequential on the main thread.

### Prompt 2.1: Confirm SQLModel mental model

> Read the SQLModel docs and source (under `.venv/lib/python*/site-packages/sqlmodel/`). Summarise in ~10 bullets:
>
> - How `SQLModel` differs from raw SQLAlchemy.
> - How sessions are managed; sync versus async patterns.
> - How to define indexes and constraints.
> - How to handle migrations (alembic integration).
> - JSON column support and how it serialises Pydantic models.
> - Connection pooling for SQLite.
> - Test isolation patterns (in-memory DB versus file).
> - Gotchas with concurrent writes on SQLite.
>
> Do not write any code yet.

### Prompt 2.2: Schema and database layer

> Implement `experiment_tracker/models.py`:
>
> Three SQLModel tables:
>
> ```
> Run:
>   id: int (primary key, auto)
>   run_uid: str (uuid4, unique, indexed)
>   created_at: datetime
>   recipe: str (e.g. "lora-rank-8")
>   model_base: str (e.g. "Qwen/Qwen3-VL-2B-Instruct")
>   dataset: str
>   hyperparameters: dict (JSON column)
>   status: str (one of "running", "completed", "failed")
>   notes: str | None
>
> Metric:
>   id: int (primary key, auto)
>   run_id: int (foreign key to Run.id, indexed)
>   step: int
>   name: str (indexed)
>   value: float
>   logged_at: datetime
>
> Artifact:
>   id: int (primary key, auto)
>   run_id: int (foreign key to Run.id, indexed)
>   kind: str (e.g. "model", "checkpoint", "log")
>   uri: str (e.g. "https://huggingface.co/...")
>   created_at: datetime
> ```
>
> Implement `experiment_tracker/db.py`:
>
> - `get_engine(db_path: Path) -> Engine` returning a SQLite engine.
> - `init_db(engine: Engine) -> None` creating tables if missing.
> - `get_session(engine: Engine) -> Session` context manager.
> - Default DB location: `~/.cache/experiment-tracker/runs.db`.
>
> Tests in `tests/experiment_tracker/test_db.py`:
>
> - `init_db` creates all three tables.
> - Inserting a Run and querying it back works.
> - Inserting a Metric with a non-existent run_id raises an integrity error.
> - JSON column round-trips a nested dict.
>
> Commit with message `feat(experiment-tracker): schema and database layer`.

### Prompt 2.3: Server skeleton

> Implement `experiment_tracker/server.py` analogously to `arxiv_deep/server.py`:
>
> - Stdio MCP server.
> - On startup, ensure DB exists at the configured path.
> - Empty tool registry.
>
> Add `experiment_tracker/exceptions.py` with `ExperimentTrackerError` (base), `RunNotFoundError`, `MetricLoggingError`.
>
> Add entry point: `experiment-tracker-server = "experiment_tracker.server:main"`.
>
> Verify with the MCP inspector that the server connects and lists no tools.
>
> Commit with message `feat(experiment-tracker): server skeleton`.

### Prompt 2.4: Tests for the run lifecycle tools

> Write `tests/experiment_tracker/test_runs.py` covering:
>
> Tool `start_run(recipe: str, model_base: str, dataset: str, hyperparameters: dict, notes: str = "") -> dict`. Returns `{"run_uid": str, "id": int}`.
>
> - Happy path: returns valid run_uid (uuid4 format), id is positive int, row exists in DB with `status="running"`.
> - Multiple calls produce distinct run_uids.
> - Hyperparameters dict is stored verbatim and returned by `list_runs`.
>
> Tool `list_runs(filters: dict | None = None) -> list[dict]`. Filters by recipe, model_base, dataset, or status.
>
> - No filters returns all runs.
> - Filter by recipe returns only matching.
> - Empty database returns `[]`.
> - Combined filters AND together.
>
> Use a tmp DB path fixture per test; tests must not share state.

### Prompts 2.5, 2.6, 2.7: Parallel implementation

> **Run as three parallel subagents.**

#### Prompt 2.5 (subagent A): run lifecycle tools

> CONTEXT: `CLAUDE.md`, `experiment_tracker/models.py`, the tests just written.
>
> Implement `experiment_tracker/tools/runs.py`:
>
> - `start_run(...)` as specified in tests.
> - `list_runs(filters)` as specified in tests.
> - Additional: `complete_run(run_uid: str, status: str = "completed") -> dict` updating status.
>
> Register all three on the MCP server. Tests must pass. Commit.

#### Prompt 2.6 (subagent B): metrics and artifacts tools

> CONTEXT: `CLAUDE.md`, `experiment_tracker/models.py`.
>
> Implement `experiment_tracker/tools/metrics.py`:
>
> - `log_metric(run_uid: str, step: int, name: str, value: float) -> dict`. Returns `{"logged": true, "metric_id": int}`. Raises `RunNotFoundError` if run_uid does not exist.
>
> Implement `experiment_tracker/tools/artifacts.py`:
>
> - `log_artifact(run_uid: str, kind: str, uri: str) -> dict`. Returns `{"logged": true, "artifact_id": int}`. Same error handling.
>
> Tests first in `tests/experiment_tracker/test_metrics.py` and `tests/experiment_tracker/test_artifacts.py`. Cover happy path, unknown run_uid, multiple metrics per run, multiple artifacts per run.
>
> Register both tools on the MCP server. Commit.

#### Prompt 2.7 (subagent C): comparison tools

> CONTEXT: `CLAUDE.md`, `experiment_tracker/models.py`.
>
> Implement `experiment_tracker/tools/compare.py`:
>
> - `compare_runs(run_uids: list[str], metric_name: str) -> str`. Returns a Markdown table with one row per run, columns: run_uid (truncated to 8 chars), recipe, hyperparameters (compact JSON), final value of `metric_name`. The table is sorted by metric value, highest first. Returns Markdown so the agent can paste it into reasoning.
> - `best_run(metric_name: str, direction: Literal["max", "min"] = "max", filters: dict | None = None) -> dict`. Returns the run dict with the best final value of the metric.
>
> Tests first in `tests/experiment_tracker/test_compare.py`:
>
> - `compare_runs` produces correct row count and ordering.
> - `compare_runs` raises if any run_uid is unknown.
> - `best_run` returns highest for max direction, lowest for min.
> - `best_run` with empty DB returns None or raises (your choice, document it).
>
> Register both on the MCP server. Commit.

### Prompt 2.8: Integrate and verify

> Pull all three subagent commits. Run the full test suite. Run `make lint`, `make typecheck`, `make test-cov`. Coverage on `experiment_tracker/` must be above 85% line, 75% branch.
>
> Use the MCP inspector to verify all six tools are listed: `start_run`, `list_runs`, `complete_run`, `log_metric`, `log_artifact`, `compare_runs`, `best_run`. Plus `complete_run` makes seven, document the actual count in the commit message.
>
> Run a full happy-path scenario via the inspector:
>
> 1. `start_run` for three different LoRA ranks (4, 8, 16).
> 2. Log a few metrics for each.
> 3. Log an artifact URI for each.
> 4. `compare_runs` on all three.
> 5. `best_run` to identify the winner.
>
> Paste each tool response.

### Phase 2 exit gate

- All experiment-tracker tools registered, tested, green.
- Coverage above thresholds.
- MCP inspector smoke shows the full happy-path scenario.
- Lint and typecheck clean.
- Commit, push, **fresh Claude Code session for Phase 3.**

---

## Phase 3: ml-intern integration

**Goal:** ml-intern, configured with both servers, can list and call every tool. Documented config snippet for users.

### Prompt 3.1: Investigate ml-intern config

> Switch to the ml-intern fork (separate directory the user already cloned). Read `agent/`, `configs/`, and the README.
>
> Determine:
>
> - Exact JSON shape for `mcpServers` config entries.
> - Supported transports (stdio, HTTP, both?).
> - Whether `${VAR}` env var substitution works for command paths.
> - Whether multiple MCP servers can be registered simultaneously.
> - Where session logs go and whether they include MCP tool calls.
>
> Report back with exact field names and a minimal example snippet for one server. Do not edit any files yet.

### Prompt 3.2: Wire arxiv-deep

> Edit `configs/main_agent_config.json` in the ml-intern fork to add the arxiv-deep server.
>
> Use stdio transport if supported. The command should invoke the toolkit via `uv`, pointing at the absolute path of `ml-intern-mcp-toolkit`. Example:
>
> ```json
> "arxiv-deep": {
>   "transport": "stdio",
>   "command": "uv",
>   "args": ["run", "--project", "${ML_INTERN_TOOLKIT_PATH}", "arxiv-deep-server"]
> }
> ```
>
> If only HTTP is supported, run the server with HTTP transport and use the README's HTTP config shape. Document the choice.
>
> Run ml-intern interactively. Ask: "What arxiv-related tools do you have?" Confirm all four arxiv-deep tools appear. Paste the output.
>
> Commit on the ml-intern fork side with message `chore: register arxiv-deep MCP server`.

### Prompt 3.3: Wire experiment-tracker

> Same as 3.2 but for experiment-tracker. After editing config:
>
> - Restart ml-intern.
> - Ask: "What experiment tracking tools do you have?" Confirm all six (or seven) tools appear.
> - Run a quick scripted scenario: "Start a run called 'smoke-test' for model 'foo' on dataset 'bar', log a metric called 'loss' at step 1 with value 0.5, list runs."
> - Paste the full transcript.
>
> Commit on ml-intern fork side.

### Prompt 3.4: Document the config

> Back in `ml-intern-mcp-toolkit`:
>
> Create `demo/ml_intern_config.json` containing the exact config snippet that the demo will use. Include both servers. Use `${ML_INTERN_TOOLKIT_PATH}` placeholder for the path.
>
> Create `docs/ml_intern_integration.md` explaining:
>
> - How to clone and set up ml-intern.
> - How to register both servers (link to `demo/ml_intern_config.json`).
> - Required env vars.
> - How to verify the integration.
> - Common failure modes (server not starting, tools not appearing, JSON syntax errors).
>
> Commit with message `docs: document ml-intern integration steps`.

### Phase 3 exit gate

- ml-intern configured with both servers.
- Manual smoke test confirms all tools visible and callable through the agent.
- `demo/ml_intern_config.json` and `docs/ml_intern_integration.md` exist.
- Commit, push, **fresh session for Phase 4.**

---

## Phase 4: End-to-end demo

**Goal:** A single shell script that runs the full loop. Local MPS path for M5 Pro users; HF Jobs path for everyone else. Selectable via env var. Output: a model on `huggingface.co/ml-agent-explorers` with a generated card.

### Prompt 4.1: Demo prompt design

> Create `demo/prompts/train_qlora_oxford_pets.txt` containing the prompt fed to ml-intern. The prompt instructs the agent to:
>
> 1. Use `arxiv-deep` to read paper 2305.14314 and produce an implementation brief.
> 2. Note that the user wants to fine-tune Qwen3-VL-2B on the Oxford Pets dataset.
> 3. Run three training variants: LoRA rank 4, 8, and 16. All other hyperparameters identical (3 epochs, lr 1e-4, batch size 4).
> 4. For each run, use `experiment-tracker` to: `start_run`, log per-epoch loss as metrics, `log_artifact` for the resulting checkpoint URI, `complete_run` on success.
> 5. Use `compare_runs` and `best_run` to identify the winner.
> 6. Push the winning checkpoint to `ml-agent-explorers/qwen3vl-oxford-pets-lora-r{N}` with a model card citing the paper, the run UIDs, and a link back to the toolkit repo.
>
> The prompt is plain English and well-structured. Do not over-specify; the agent should choose how to call the tools.

### Prompt 4.2: Local MPS training script

> Create `demo/scripts/train_local.py` that the agent can call (or invoke via subprocess) for the Apple Silicon path.
>
> Parameters: `--model-base`, `--dataset`, `--lora-rank`, `--epochs`, `--lr`, `--batch-size`, `--output-dir`, `--run-uid` (for tracker integration).
>
> Implementation:
>
> - Load model and processor via `transformers`.
> - Apply LoRA via `peft` with the specified rank.
> - Device selection: `mps` on Apple Silicon, fallback to CPU. Set `PYTORCH_ENABLE_MPS_FALLBACK=1`.
> - Load Oxford Pets via `datasets`. Use a small subset (1000 train, 200 val) for demo speed.
> - Train. Print one line per epoch with loss.
> - Save adapter to `--output-dir`.
> - Print a final JSON line: `{"final_loss": float, "checkpoint_dir": str}`.
>
> Tests: `tests/integration/test_train_local.py` runs the script for 1 epoch with a tiny model (e.g. `hf-internal-testing/tiny-random-Qwen2VLForConditionalGeneration` if available, otherwise the smallest VLM you can find). Mark `@pytest.mark.integration`. Skipped in default CI; runs with `PYTEST_INTEGRATION=1`.
>
> Commit with message `feat(demo): local MPS training script`.

### Prompt 4.3: HF Jobs training script

> Create `demo/scripts/train_hf_jobs.py` for the cloud path.
>
> Same CLI signature as `train_local.py`. Uses `huggingface_hub` to submit a job that runs the equivalent training on HF infrastructure. Polls for completion. Returns the final-loss JSON line on stdout.
>
> Document the env vars required (`HF_TOKEN` with write access).
>
> Tests are skipped by default (network + cost). Integration test gated on `PYTEST_HF_JOBS=1`.
>
> Commit with message `feat(demo): HF Jobs training script`.

### Prompt 4.4: Demo orchestrator

> Create `demo/run_demo.sh`:
>
> ```bash
> #!/usr/bin/env bash
> set -euo pipefail
>
> MODE="${DEMO_MODE:-local}"  # "local" or "hf-jobs"
> ML_INTERN_TOOLKIT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
> export ML_INTERN_TOOLKIT_PATH
>
> # Pre-flight
> for var in ANTHROPIC_API_KEY HF_TOKEN GITHUB_TOKEN; do
>     if [[ -z "${!var:-}" ]]; then
>         echo "Missing $var in environment." >&2
>         exit 1
>     fi
> done
>
> echo "Demo mode: $MODE"
> echo "Toolkit path: $ML_INTERN_TOOLKIT_PATH"
>
> # Hand off to ml-intern with the demo prompt
> cd "${ML_INTERN_PATH:?Set ML_INTERN_PATH to the cloned ml-intern repo}"
> exec uv run ml-intern --prompt-file "$ML_INTERN_TOOLKIT_PATH/demo/prompts/train_qlora_oxford_pets.txt"
> ```
>
> Make it executable. Add usage docs to `demo/README.md` covering: prerequisites, env vars, how to switch between local and HF Jobs modes, expected runtime (M5 Pro local ~30-90 min depending on memory; HF Jobs ~15-20 min), expected output (link to the published model).
>
> Commit with message `feat(demo): orchestrator script and demo README`.

### Prompt 4.5: Smoke run

> On the M5 Pro:
>
> 1. Set the three env vars in `.env`.
> 2. Source `.env` (or use `direnv`).
> 3. Run `make demo` with `DEMO_MODE=local`.
> 4. Watch the agent execute. Capture the full transcript to `demo/last_run.transcript.txt` (gitignored).
> 5. Verify a model appears in `huggingface.co/ml-agent-explorers`.
> 6. Verify the experiment-tracker DB has three completed runs.
>
> If the agent gets stuck or makes a wrong tool call, do not patch the prompt to work around it. Capture the failure, then improve the tool description in the relevant server. The point of the demo is to validate that tool descriptions are clear enough for autonomous execution.
>
> Then run the same demo with `DEMO_MODE=hf-jobs` (much faster turnaround for verification).

### Prompt 4.6: Asciinema recording

> Once the demo runs cleanly:
>
> 1. Install `asciinema` (`brew install asciinema` on Mac).
> 2. Record a clean run: `asciinema rec demo/recording.cast`.
> 3. Edit `docs/architecture.md` to embed the recording link.
> 4. Add a `demo/README.md` link to the recording.
>
> Commit with message `docs(demo): add asciinema recording`.

### Phase 4 exit gate

- `make demo` runs end to end on the M5 Pro.
- `make demo` with `DEMO_MODE=hf-jobs` runs end to end.
- A model appears in `huggingface.co/ml-agent-explorers` with a generated card.
- Asciinema recording is committed.
- Commit, push, **fresh session for Phase 5.**

---

## Phase 5: Documentation and examples

**Goal:** Anyone landing on the GitHub repo can understand what this is, why it exists, how to install it, how to use it, and how to debug it. No silent assumptions.

### Prompt 5.1: Public README

> Replace `README.md` with a public-facing readme. Sections:
>
> 1. Title and one-line description.
> 2. Badges: CI, license, Python version.
> 3. **What this is** (3-4 sentences).
> 4. **Why it exists** (the problem with stock ml-intern: shallow paper reading, no run memory).
> 5. **Architecture diagram** (link to `docs/architecture.md` for full version).
> 6. **Quickstart** (5 commands max).
> 7. **The two servers** (one paragraph each, with a link to the tool reference).
> 8. **Demo** (link to `demo/README.md` and the asciinema cast).
> 9. **Compatibility** (Apple Silicon M5 Pro confirmed, Linux x86_64 via CI, Windows not tested).
> 10. **Contributing** (link to `CONTRIBUTING.md`).
> 11. **License** (Apache 2.0).
> 12. **Citation** (BibTeX block, even if it is a software citation).
>
> Tone: direct, no marketing fluff. Assume the reader is technical. No em dashes.
>
> Commit with message `docs: public-facing README`.

### Prompt 5.2: Architecture document

> Write `docs/architecture.md`:
>
> - System diagram (use Mermaid, rendered by GitHub). Boxes: ml-intern agent, arxiv-deep server, experiment-tracker server, HF Hub, arxiv.org, GitHub. Arrows show MCP stdio for the servers, HTTPS for external services.
> - Sequence diagram (Mermaid) for a typical demo run: user prompt → agent → arxiv-deep tools → experiment-tracker tools → training script → HF Hub upload.
> - Section per server explaining: responsibilities, dependencies, where data is cached, what state it owns.
> - Decisions log summary (lift from `CLAUDE.md`).

### Prompt 5.3: Tool reference

> Write `docs/tool_reference.md`:
>
> One section per tool. For each:
>
> - Tool name, server.
> - One-sentence purpose.
> - Input schema (table: name, type, required, description).
> - Output schema (table or JSON example).
> - Example call (JSON).
> - Example response.
> - Failure modes (which exceptions, when).
> - Tips for the calling agent (e.g. "always call `fetch_paper` before `extract_figures` if you need both").
>
> Auto-generate as much as possible from the actual MCP server registrations to keep this in sync. Add a `make docs` target if generation is automated.

### Prompt 5.4: Troubleshooting guide

> Write `docs/troubleshooting.md` covering at minimum:
>
> - "MCP inspector cannot connect to my server" → likely causes (PYTHONPATH, uv project root).
> - "ml-intern does not see my tools" → JSON syntax errors, transport mismatch, env var substitution failing.
> - "Training script fails with 'no GPU available'" on Apple Silicon → MPS fallback flag.
> - "pymupdf install fails on Apple Silicon" → wheel availability check.
> - "Rate-limited by GitHub during code finder" → unauthenticated rate limit, set `GITHUB_TOKEN`.
> - "HF Jobs run never returns" → polling timeout, check job status manually.
> - "Demo published model is wrong" → run-uid mismatch, check tracker DB.
>
> Each entry has symptoms, cause, and fix.

### Prompt 5.5: Examples directory

> Create:
>
> 1. `examples/minimal_arxiv_query.py`: 30-line script that connects to the arxiv-deep server (as an MCP client, not via ml-intern) and calls `implementation_brief` once. Pretty-prints the result.
> 2. `examples/minimal_tracker_session.py`: 30-line script that creates a tmp tracker DB, starts a run, logs metrics, calls `compare_runs` with itself, prints the Markdown table.
> 3. `examples/README.md` listing all examples and how to run them.
>
> These are the "I just want to see it work without ml-intern" scripts. They are gold for new users.

### Prompt 5.6: Changelog

> Create `CHANGELOG.md` following Keep a Changelog format. First entry: `## [Unreleased]` with subsections Added, Changed, Fixed, summarising everything done in Phases 0-4.
>
> Update `CONTRIBUTING.md` to require changelog entries on every PR.

### Phase 5 exit gate

- README, architecture, tool reference, troubleshooting all exist and link to each other.
- Examples directory has at least two runnable scripts.
- CHANGELOG started.
- A first-time reader can go from zero to a working demo using only the docs.
- Commit, push, **fresh session for Phase 6.**

---

## Phase 6: Release engineering

**Goal:** The repo is ready to be public and discoverable. CI runs everything that matters. PRs have templates. A release process exists.

### Prompt 6.1: Tighten CI

> Audit `.github/workflows/ci.yml`. Confirm it:
>
> - Runs on push and PR.
> - Matrix covers `{ubuntu-latest, macos-14}` × `{python-3.11, python-3.12}`.
> - Caches `uv` artifacts.
> - Runs `make lint`, `make typecheck`, `make test-cov`.
> - Uploads coverage as an artifact.
> - Has a job summary that shows coverage delta on PRs.
>
> Add a `secrets-scan` job using `gitleaks-action` that fails the workflow on any leak.
>
> Add a `markdown-lint` job for `docs/` and `README.md`.
>
> Commit with message `ci: harden workflows`.

### Prompt 6.2: Release workflow

> Create `.github/workflows/release.yml` triggered on tags matching `v*`:
>
> - Build the package with `uv build`.
> - Run the full test suite.
> - Generate release notes from CHANGELOG (the `[Unreleased]` section becomes the release).
> - Create a GitHub Release with the built wheel attached.
> - Optionally publish to PyPI (gated on a repo secret being present; default off).
>
> Document the release process in `CONTRIBUTING.md`: bump version, update CHANGELOG, tag, push tag.

### Prompt 6.3: Branch protection and repo settings

> Document (in `docs/maintainers.md`) the GitHub repository settings to apply manually:
>
> - Default branch: `main`.
> - Branch protection on `main`: require PR, require CI green, require 1 review, no force push.
> - Required status checks: `ci`, `lint`, `secrets-scan`, `markdown-lint`.
> - Disable wiki and projects unless needed.
> - Topics: `mcp`, `ml-intern`, `huggingface`, `agent`, `arxiv`, `experiment-tracking`, `apple-silicon`.
> - Description: "Production MCP toolkit extending Hugging Face's ml-intern with deep arxiv reading and experiment tracking."
>
> The user applies these manually in the GitHub UI.

### Prompt 6.4: Release dry run

> 1. Bump version in `pyproject.toml` to `0.1.0`.
> 2. Move CHANGELOG `[Unreleased]` content to `[0.1.0] - YYYY-MM-DD`.
> 3. Open a new `[Unreleased]` section.
> 4. Commit: `chore(release): 0.1.0`.
> 5. Tag locally: `git tag v0.1.0`.
> 6. Push tag: `git push origin v0.1.0`.
> 7. Watch the release workflow run. Verify GitHub Release is created with correct notes.
>
> If anything fails, fix the workflow, delete the tag, retry.

### Phase 6 exit gate

- All CI jobs green on `main`.
- Release workflow tested at least once.
- Repo settings documented.
- Version 0.1.0 published as a GitHub Release.
- The project is shippable. Time to share the link.

---

## Final exit gate

The whole project is done when, in a fresh environment with no prior context:

1. A user clones the repo.
2. Runs `make setup`.
3. Sets `ANTHROPIC_API_KEY`, `HF_TOKEN`, `GITHUB_TOKEN`.
4. Runs `make demo`.
5. Sees a model appear in `huggingface.co/ml-agent-explorers`.

If all five work without manual intervention beyond what the README says, ship it.
