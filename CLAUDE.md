# CLAUDE.md

Project context for `ml-intern-mcp-toolkit`. Read this in full at the start of every Claude Code session in this repo.

---

## What this project is

A production-grade, open-source MCP (Model Context Protocol) toolkit that extends Hugging Face's `ml-intern` agent with two servers:

1. **`arxiv-deep`** — fetches full paper text, extracts figures and tables, finds linked code repositories, and produces structured implementation briefs. Lets the agent read papers properly, not just search abstracts.
2. **`experiment-tracker`** — SQLite-backed store for training run metadata, metrics, artifacts, and cross-run comparison. Gives the agent persistent memory of what it has already tried.

The end deliverable is a public GitHub repository that:

- Anyone can clone, install, and use within 10 minutes.
- Ships green CI on every push.
- Includes a working end-to-end demo where ml-intern reads a paper, runs three training variants, logs them, and publishes the best model to the `ml-agent-explorers` Hugging Face org.
- Has documentation that explains the why, the how, and the gotchas.
- Is reproducible on any Apple Silicon Mac (target: M5 Pro), x86 Linux, and HF Jobs.

This is a portfolio piece and a real tool. It must work, not just look like it works.

---

## Hardware target

**Primary development and demo machine:** Apple Silicon, M5 Pro, 24-64GB unified memory, macOS 15+.

**Implications:**

- ARM64 (`arm64`/`aarch64`) wheels for every dependency. No `x86_64`-only packages. Verify on first install.
- PyTorch uses the MPS backend (`torch.backends.mps.is_available()`). CUDA paths must not be hard-coded.
- Local fine-tuning is viable for LoRA on small VLMs (Qwen3-VL 2B, SmolVLM, etc.) thanks to unified memory and 307 GB/s bandwidth. Anything larger goes to HF Jobs.
- macOS sandboxing: the `mcp` Python SDK runs over stdio without issue, but file I/O paths must use `pathlib.Path` and not assume Linux conventions.
- Filesystem case-insensitive by default. Do not rely on case-sensitive imports or filenames.
- `uv` is the Python package manager. Apple-Silicon-native, fast, deterministic.
- Use `homebrew` only for system deps (e.g. `mupdf-tools` if needed). Never for Python.

**Secondary targets:**

- x86_64 Linux (Ubuntu 22.04+). CI runs here. Demo must work here.
- HF Jobs. The training portion of the demo runs here for users without local GPUs.

Anything that works on the M5 Pro must also work on Linux. CI catches the latter automatically.

---

## Project scope (full)

Six phases, executed in strict order. Inside a phase, parallelisation is allowed where the dependency graph permits (see `README_PROMPTS.md`). Across phases, strictly synchronous: phase N must be fully green before phase N+1 begins.

### Phase 0: Bootstrap
Repo skeleton, license, code of conduct, `pyproject.toml`, pre-commit config, CI scaffolding, README skeleton, contributing guide. No application code yet.

### Phase 1: `arxiv-deep` MCP server
Four tools: `fetch_paper`, `extract_figures`, `find_reference_code`, `implementation_brief`. Full pytest coverage. Live MCP inspector verification.

### Phase 2: `experiment-tracker` MCP server
Six tools: `start_run`, `log_metric`, `log_artifact`, `list_runs`, `compare_runs`, `best_run`. SQLite + SQLModel. Full pytest coverage including concurrency edge cases.

### Phase 3: `ml-intern` integration
Fork ml-intern, wire both MCP servers via config, manual smoke test confirming the agent sees and uses the tools. Document the exact config snippet so users can replicate.

### Phase 4: End-to-end demo
A single shell script that runs the full loop: agent reads QLoRA paper, fine-tunes Qwen3-VL-2B on Oxford Pets with three LoRA rank variants, logs all runs, picks the best, pushes it to `ml-agent-explorers`. Two execution modes: local MPS for M5 Pro users, HF Jobs for everyone else. Selectable via env var.

### Phase 5: Documentation and examples
Public-facing README with quickstart, architecture diagram, tool reference, troubleshooting. `examples/` directory with sample configs and minimal runnable snippets. Recorded asciinema demo. CHANGELOG.

### Phase 6: Release engineering
GitHub Actions for tests, lint, type-check, secrets scan. Issue and PR templates. Optional PyPI publish workflow gated on tags. Repository settings (branch protection, required checks).

When all six are green, the project is shipped.

---

## Tech stack

**Runtime:**

- Python 3.11 (3.12 acceptable, 3.13 not yet because some deps lag).
- `uv` for package management. `pip` only as fallback.
- `mcp` Python SDK, version pinned (pre-1.0 is unstable across patches).

**arxiv-deep dependencies:**

- `arxiv` for metadata and PDF download.
- `pymupdf` for text and image extraction. ARM64 wheels available since 1.23.
- `httpx` (async) for GitHub URL validation.
- `pydantic` v2 for tool schemas.

**experiment-tracker dependencies:**

- `sqlmodel` over the standard library `sqlite3`.
- `alembic` for schema migrations once the schema is non-trivial.

**Testing:**

- `pytest` + `pytest-asyncio`.
- `pytest-cov` for coverage. Target: 85% line, 75% branch.
- `respx` for mocking HTTPX in tests.
- `freezegun` for time-dependent tests in the tracker.

**Quality:**

- `ruff` for lint and formatting (replaces black + isort + flake8).
- `mypy --strict` on `arxiv_deep/` and `experiment_tracker/`. Tests are exempt.
- `pre-commit` runs ruff + mypy + a secrets scan on every commit.

**CI:**

- GitHub Actions, matrix on `{ubuntu-latest, macos-14}` × `{python-3.11, python-3.12}`.
- Cache `uv` artifacts between runs.

**Demo:**

- `transformers`, `peft`, `accelerate`, `datasets`.
- `huggingface_hub` for upload.
- For local MPS: `torch>=2.5` with MPS backend, `peft` LoRA path that supports MPS.
- For cloud: HF Jobs API. No CUDA-only deps in the default dependency group; gated as an optional extra.

---

## Repository layout

```
ml-intern-mcp-toolkit/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   ├── lint.yml
│   │   └── release.yml
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── dependabot.yml
├── arxiv_deep/
│   ├── __init__.py
│   ├── server.py
│   ├── exceptions.py
│   └── tools/
│       ├── __init__.py
│       ├── fetch.py
│       ├── figures.py
│       ├── code.py
│       └── brief.py
├── experiment_tracker/
│   ├── __init__.py
│   ├── server.py
│   ├── models.py
│   ├── db.py
│   └── tools/
│       ├── __init__.py
│       ├── runs.py
│       ├── metrics.py
│       ├── artifacts.py
│       └── compare.py
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── download_fixture.py
│   │   └── cache/                    # gitignored
│   ├── arxiv_deep/
│   │   ├── test_fetch_paper.py
│   │   ├── test_extract_figures.py
│   │   ├── test_find_reference_code.py
│   │   └── test_implementation_brief.py
│   ├── experiment_tracker/
│   │   ├── test_runs.py
│   │   ├── test_metrics.py
│   │   ├── test_artifacts.py
│   │   └── test_compare.py
│   └── integration/
│       └── test_end_to_end.py
├── demo/
│   ├── run_demo.sh
│   ├── prompts/
│   │   └── train_qlora_oxford_pets.txt
│   ├── ml_intern_config.json
│   └── README.md
├── examples/
│   ├── minimal_arxiv_query.py
│   ├── minimal_tracker_session.py
│   └── README.md
├── docs/
│   ├── architecture.md
│   ├── tool_reference.md
│   ├── troubleshooting.md
│   └── images/
├── scripts/
│   └── setup.sh
├── CLAUDE.md                         # this file
├── PROMPTS.md                        # the prompt ladder
├── README_PROMPTS.md                 # execution playbook
├── README.md                         # public-facing
├── LICENSE                           # Apache 2.0
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── CHANGELOG.md
├── Makefile
├── .gitignore
├── .pre-commit-config.yaml
├── pyproject.toml
└── uv.lock
```

---

## Conventions

These rules apply to every file Claude Code writes in this repo. Violations get reverted, not patched.

**Prose:**

- No em dashes anywhere. Use commas, parentheses, or two sentences.
- No hedging filler ("just", "simply", "basically"). State things directly.
- Active voice. "The tool returns X", not "X is returned by the tool".

**Code:**

- Type hints on every public function. `mypy --strict` is the gate.
- Docstrings on every public function and class. Google style.
- Tool descriptions in MCP server registrations are written for the agent that will read them, not for humans browsing the code. Be specific about when to call the tool and what it returns.
- No bare `except:` or `except Exception:` without re-raise or explicit logging.
- Pathlib for paths. Never `os.path.join`.
- No global mutable state outside of clearly-scoped caches.

**Tests:**

- Test-first for every tool. The test file lands before the implementation.
- One test file per source module. Mirror the structure under `tests/`.
- No `pytest.skip` or `pytest.xfail` to make CI pass. If a test cannot run in CI, mark it `@pytest.mark.integration` and gate it behind an env var.
- Fixtures download once, cache locally, never commit binaries.

**Git:**

- Conventional commit messages: `feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`.
- One concern per commit. No "fix several things" commits.
- Never commit `.env`, secrets, PDFs, model weights, or `__pycache__`.

**Secrets:**

- All secrets live in `.env` (gitignored).
- `pre-commit` runs `gitleaks` or equivalent on every commit.
- The demo script reads from environment variables, never from inline strings.

**Apple Silicon specifics:**

- Every dependency must have an ARM64 wheel. If a package is x86-only, gate its import behind a platform check and document the limitation.
- Default device selection logic:
  ```python
  import torch
  device = (
      "cuda" if torch.cuda.is_available()
      else "mps" if torch.backends.mps.is_available()
      else "cpu"
  )
  ```
- For training scripts, MPS-incompatible ops fall back to CPU explicitly. Set `PYTORCH_ENABLE_MPS_FALLBACK=1` in `demo/run_demo.sh` for the local path.

---

## MCP tool design principles

The agent calling these tools is an LLM. Tools are written for the LLM, not for humans.

- **Tool descriptions are the most important UX surface.** "Fetches paper" is bad. "Fetches the title, abstract, full body text, and metadata for an arxiv paper given its arxiv ID. Call this before any other arxiv-deep tool when working with a new paper." is good.
- **Inputs are minimal and unambiguous.** If a tool can take an arxiv URL or an ID, normalise inside the tool, do not expose both.
- **Outputs are structured.** Dicts with named keys, not free-form strings, except where Markdown rendering helps the agent reason (e.g. `compare_runs` returning a Markdown table).
- **Errors are typed.** `InvalidArxivIdError`, `ArxivFetchError`, `RunNotFoundError`. The agent can catch and react.
- **Tools are pure and idempotent where possible.** `fetch_paper` is safe to call repeatedly; it caches. `start_run` is not idempotent and that is acknowledged in the description.
- **No LLM calls inside tools.** The calling agent is the reasoner. Tools extract structure, they do not interpret.

---

## Decisions log

Append to this section as decisions are made. Format: `[YYYY-MM-DD] decision (rationale)`.

- [2026-05-05] License: Apache 2.0 (industry standard for ML tooling, permissive, patent grant).
- [TBD] SQLite over Postgres for tracker (single-user local agent, no concurrency need).
- [TBD] QLoRA paper (arxiv 2305.14314) as primary fixture (stable, well-known, has figures and a github reference).
- [TBD] Qwen3-VL-2B as demo base model (already used in `ml-agent-explorers` org, small enough for M5 Pro MPS).
- [TBD] Oxford Pets as demo dataset (small, classification, used by existing org models, fast iteration).
- [TBD] LoRA ranks 4, 8, 16 for the three demo variants (covers a meaningful range without being expensive).
- [2026-05-05] `mcp` Python SDK pinned to 1.27.0 (current PyPI stable as of 2026-04-02; SDK progressed past pre-1.0 since this file was drafted, but the exact-pin policy still holds because minor versions can ship breaking changes).
- [2026-05-05] Build backend: `hatchling` (over the `uv_build` default that `uv init --package` produces). Reason: the flat package layout, `arxiv_deep/` and `experiment_tracker/` at the repo root, is well-documented for hatchling and avoids forcing a `src/` move.
- [2026-05-05] Pre-commit mypy hook uses `language: system` invoking `uv run mypy` (over `mirrors-mypy` with `additional_dependencies`). Reason: keeps the hook in lockstep with the project's actual venv and avoids declaring runtime deps twice.
- [2026-05-05] CI installs `uv sync --all-groups` only, skipping `--all-extras`. Reason: the demo group (`torch`, `transformers`, `peft`, `accelerate`, `datasets`, `huggingface_hub`) is not exercised by tests yet, and skipping it saves ~3 GB of downloads per matrix cell. Revisit when Phase 4 adds tests that import torch.
- [2026-05-05] FastMCP (`mcp.server.fastmcp.FastMCP`) is the chosen API tier over `mcp.server.lowlevel.Server`. Reason: auto-derived JSON Schemas from type hints, decorator/`add_tool` registration, automatic exception wrapping (`ToolError`), and stderr-only logging out of the box. Cuts roughly 70% of boilerplate vs. lowlevel.
- [2026-05-05] mypy override `[[tool.mypy.overrides]] module = ["arxiv", "pymupdf"] ignore_missing_imports = true; follow_imports = "skip"`. Reason: both packages ship partial type info that mypy cannot validate cleanly under `--strict`; the alternative would be hand-written stubs, which is overkill for this project. Trade-off: our usage of those libs becomes effectively `Any`-typed; runtime behaviour is exercised by the test suite instead.
- [2026-05-05] arxiv-deep cache root is overridable via the `ARXIV_DEEP_CACHE_DIR` env var (default `~/.cache/arxiv-deep/`). Reason: lets the `tmp_cache_dir` fixture redirect cache writes per-test without monkey-patching internals, and gives users a knob for sandboxed environments.
- [2026-05-05] Tests for tools that touch the network monkey-patch two private hooks in `arxiv_deep.tools.fetch` (`_download_pdf`, `_fetch_metadata`) and pre-seed via the cached QLoRA fixture. Reason: keeps the suite hermetic and fast, at the cost of declaring those hook names as a stable contract between test and implementation.
- [2026-05-05] `extract_figures` falls back to rendering the entire page at 200 DPI when a `Figure N:` caption appears on a page that has no embedded raster XObject. Reason: the QLoRA paper (and many ML papers) ship vector figures that `page.get_images()` does not surface; without the fallback, two thirds of figures would be invisible to the agent. Surfaces the deviation in the tool description so the calling LLM knows what it is receiving.
- [2026-05-05] `implementation_brief` is heuristic-only (regex / vocabulary spotting); no LLM calls inside the tool. Reason: enforces the "tool extracts structure, agent reasons" boundary from the MCP design principles. Trade-off: extraction is fuzzy; the tool description warns callers to treat empty fields as "unknown" rather than "absent".

---

## Done definition

The project is shipped when, in a fresh environment, a new user can:

1. Clone the repo.
2. Run `make setup` (or `./scripts/setup.sh`).
3. Set three env vars from their own accounts.
4. Run `make demo` (or `./demo/run_demo.sh`).
5. See a model appear in `huggingface.co/ml-agent-explorers` with a generated model card linking back to the paper, the run logs, and the toolkit repo.

If any of those five steps require manual intervention beyond what the README documents, the project is not done.
