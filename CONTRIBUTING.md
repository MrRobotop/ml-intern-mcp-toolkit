# Contributing to ml-intern-mcp-toolkit

Thanks for your interest in contributing. This guide covers what you need to know before opening an issue or a pull request.

By participating, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).

## How to file an issue

Open issues against the GitHub tracker. Use one of the templates under [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/) where one fits.

A useful bug report includes:

- What you ran (exact command, prompt, or tool call).
- What you expected to happen.
- What actually happened (full traceback if any, copied from the terminal).
- Your environment: OS and version, Python version, `uv --version`, hardware (Apple Silicon model or x86_64), and whether you are using the local or HF Jobs demo path.
- Whether the failure is reproducible. A minimal repro snippet beats a description.

For feature requests, describe the use case before the proposed solution. The "what" and "why" matter more than the "how"; we will work out implementation together.

## How to submit a pull request

1. Open an issue first for non-trivial changes, so we can agree on direction before code is written.
2. Branch off `main`. One concern per PR. Refactors and feature work do not mix.
3. Run `make lint`, `make typecheck`, and `make test` locally before pushing.
4. Add a line to the `[Unreleased]` section of [`CHANGELOG.md`](CHANGELOG.md). The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Group entries under `Added`, `Changed`, `Fixed`, `Deprecated`, `Removed`, or `Security` as appropriate. PRs without a changelog entry will be asked to add one.
5. If your change touches a tool description or schema, run `make docs` and commit the regenerated `docs/tool_reference.md`. The `tests/integration/test_tool_reference_in_sync.py` test will fail in CI otherwise.
6. Push to a feature branch and open a PR against `main`. Fill out the PR template at [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md).
7. CI must be green. PRs with red CI will not be reviewed.
8. Expect review feedback. Push fixups; we will squash-merge.

## Local development setup

Prerequisites:

- Python 3.11 (3.12 also supported).
- [`uv`](https://docs.astral.sh/uv/) 0.5 or newer.
- `git`.
- Optional: Node.js and `npx` if you plan to use the MCP inspector. Install via `nvm` or `homebrew`.

Setup:

```
git clone https://github.com/<your-account>/ml-intern-mcp-toolkit.git
cd ml-intern-mcp-toolkit
make setup
```

`make setup` runs `uv sync --all-groups`, installs pre-commit hooks, and copies `.env.example` to `.env`. Fill in the env vars listed in `.env.example` before running the demo.

Hardware targets:

- **Primary:** Apple Silicon, M5 Pro, macOS 15+. The end-to-end demo trains locally via the MPS backend.
- **Supported:** x86_64 Linux (Ubuntu 22.04+). CI runs here on every push.
- **Not tested:** Windows. PRs adding Windows support are welcome but not required.

If a dependency lacks an ARM64 wheel, stop and open an issue rather than working around it locally; the project's policy is to keep Apple Silicon installation friction-free.

## Coding standards

The canonical source of truth is the **Conventions** section of [`CLAUDE.md`](CLAUDE.md). Read it before writing code.

In short:

- Type hints on every public function. `mypy --strict` is the gate.
- Google-style docstrings on every public function and class.
- `pathlib.Path` for filesystem paths. Never `os.path.join`.
- No bare `except:` or `except Exception:` without a re-raise or explicit logging.
- No global mutable state outside clearly-scoped caches.
- Prose: no em dashes, no hedging filler, active voice.
- MCP tool descriptions are written for the calling LLM, not for humans browsing the source. Be specific about when to call the tool and what it returns.

`ruff` handles lint and format; `mypy` handles types. Both run on pre-commit and in CI. Fix on commit, do not silence with `# noqa` or `# type: ignore` unless you also leave a comment explaining why.

## Test requirements

- Tests live under `tests/`, mirroring the source layout (`tests/arxiv_deep/`, `tests/experiment_tracker/`, `tests/integration/`).
- Test-first for tool implementations in Phase 1 and Phase 2: the test file lands in a separate commit before the implementation file.
- Coverage targets: 85% line and 75% branch on `arxiv_deep/` and `experiment_tracker/`. CI enforces this.
- Do not use `pytest.skip` or `pytest.xfail` to make CI pass. If a test cannot run in CI (because it hits the network, depends on credentials, or runs a long training loop), mark it `@pytest.mark.integration` and gate it behind an environment variable such as `PYTEST_INTEGRATION=1`.
- Fixtures download once and cache locally. Never commit binaries (PDFs, PNGs, model weights). The `.gitignore` enforces this; respect it.

Run tests:

```
make test          # fast unit tests
make test-cov      # with coverage report
```

## Commit message format

Conventional Commits, lowercase type prefix, imperative mood, one concern per commit:

- `feat(scope): add X` for new features.
- `fix(scope): correct Y` for bug fixes.
- `docs: update Z` for documentation only.
- `test(scope): cover edge case` for tests only.
- `chore: bump dependency` for housekeeping.
- `refactor(scope): simplify` for non-behavioural changes.
- `ci: tweak workflow` for CI changes.

Keep the subject line under 72 characters. Add a body when the change is non-obvious; explain the *why*, not the *what*. Examples:

- `feat(arxiv-deep): implement fetch_paper tool`
- `chore: declare runtime, dev, and demo dependencies`
- `fix(experiment-tracker): handle concurrent log_metric writes`

Avoid commits that bundle unrelated changes. If you find yourself writing "and" in a subject line, split the commit.
