# README_PROMPTS.md

The execution playbook for `ml-intern-mcp-toolkit`. Read this end to end **before starting Phase 0**, then refer back at every phase boundary.

This file's job: make Claude Code go fast without going sloppy across all six phases.

It enforces five things:

1. **Plan before code.** Every prompt is thought through, not just executed.
2. **Subagents for fan-out work.** Independent reads, tests, and implementations get delegated. Dependent work stays on the main thread.
3. **Synchronous phase boundaries.** Inside a phase, parallelise where the dependency graph allows. Across phases, never. Phase N is fully green before Phase N+1 begins.
4. **Quality gates that bite.** Tests, lint, type-check, coverage, schema verification, secrets scan, manual smoke. No skipping.
5. **Hardware-aware defaults.** Apple Silicon M5 Pro is the primary target. Every choice is checked against ARM64 wheel availability and MPS compatibility.

---

## Pre-flight checklist

Confirm all of these before running Prompt 0.1. Five minutes now saves an hour later.

**Local environment (M5 Pro):**

- [ ] macOS 15 or newer.
- [ ] Xcode Command Line Tools installed (`xcode-select -p` returns a path).
- [ ] `homebrew` installed (`brew --version` works).
- [ ] `uv` installed (`uv --version`, expect 0.5+). Install via `curl -LsSf https://astral.sh/uv/install.sh | sh` if missing.
- [ ] Python 3.11 available via `uv` (`uv python install 3.11`).
- [ ] Node.js + npx available (needed for the MCP inspector). Use `nvm` or `homebrew`.
- [ ] `git` configured with name and email.
- [ ] `gh` CLI authenticated (optional but useful).

**Claude Code:**

- [ ] `claude` CLI installed and authenticated (`claude --version`).
- [ ] Anthropic API key in environment or `claude` keychain.

**Repository state:**

- [ ] Empty target directory: `mkdir ml-intern-mcp-toolkit && cd ml-intern-mcp-toolkit`.
- [ ] `CLAUDE.md`, `PROMPTS.md`, `README_PROMPTS.md` placed at the repo root.
- [ ] GitHub repo created (empty), remote configured: `git remote add origin <url>`.

**Credentials:**

- [ ] `ANTHROPIC_API_KEY` ready.
- [ ] `HF_TOKEN` with write access to your `ml-agent-explorers` membership.
- [ ] `GITHUB_TOKEN` (PAT with `public_repo` scope) for the code finder.

**Sibling directory (for Phase 3):**

- [ ] `ml-intern` cloned in a sibling directory: `cd .. && git clone https://github.com/huggingface/ml-intern && cd ml-intern && uv sync`.

**Time:**

- [ ] You have at least one solid 2-3 hour block free. Phase 1 alone needs that much.
- [ ] Total project: roughly 15-25 hours of focused work depending on how much iteration each prompt needs.

---

## The execution loop

Apply this loop to every prompt in `PROMPTS.md`. The single most important pattern in this document.

```
1. PLAN
   Paste the prompt. Tell Claude Code: "Do not execute yet. Produce a plan."
   Read the plan. Push back on anything off-spec.

2. DELEGATE
   For independent sub-tasks in the plan, instruct Claude Code to spawn
   subagents (Task tool). See Subagent Playbook below for which tasks qualify.

3. EXECUTE
   Claude Code carries out dependent work on the main thread; subagents
   run in parallel.

4. INTEGRATE
   When subagents return, integrate their outputs. Resolve conflicts.

5. VERIFY
   Run the relevant quality gate (tests, lint, manual smoke) before
   declaring the prompt done.

6. CHECKPOINT
   Commit. Update CLAUDE.md decisions log if a non-obvious choice was made.
```

The discipline lives in steps 1 and 5. Most failures come from skipping the plan or skipping the verify.

---

## Subagent playbook

Claude Code's Task tool spawns a subagent with its own context. Use it deliberately, not reflexively. A subagent for a 30-second task is overhead. A subagent for a 5-minute parallelisable task is leverage.

### What goes to subagents

**Research and reading (always parallel-friendly):**
- Reading and summarising the MCP SDK source.
- Reading SQLModel docs and patterns.
- Reading the upstream `ml-intern` agent code to understand a config field.
- Surveying GitHub for prior art on a specific extraction heuristic.

**Test authoring (parallel once fixtures exist):**
- One subagent per tool's test file, fanned out after fixture setup.

**Independent implementation (parallel where the dependency graph allows):**
- Phase 1: `extract_figures` and `find_reference_code` are independent; both depend on `fetch_paper`. Fan out after `fetch_paper` lands.
- Phase 2: `runs.py`, `metrics.py`, `artifacts.py`, and `compare.py` are independent once the schema is fixed. Fan out three ways.

**Verification (parallel at phase end):**
- One subagent runs the full pytest suite.
- Another runs the MCP inspector tool listing.
- Another lints, typechecks, and scans for secrets.
- Main thread waits for all three.

### What stays on the main thread

- Anything that mutates shared files multiple subagents would also touch (`pyproject.toml`, `server.py`).
- Schema and contract decisions. Subagents must consume contracts, not invent them.
- Anything that requires the calling user's environment (credentials, network access to private resources).
- Cross-phase work (e.g. editing the ml-intern fork in Phase 3).
- The integration step where subagent outputs get merged.

### How to brief a subagent

Bad brief: "implement extract_figures."
Good brief: specifies inputs, outputs, constraints, and the contract it must honour.

Template:

```
Spawn a subagent with this brief:

CONTEXT: [link to CLAUDE.md, point at the relevant section]
INPUT CONTRACT: [exact function signature, exact return type]
OUTPUT CONTRACT: [what the subagent reports back]
CONSTRAINTS: [libraries to use, files to touch, files NOT to touch]
DEFINITION OF DONE: [tests pass / inspector shows tool / coverage threshold]
```

Keep briefs under 250 words. Long briefs eat into the subagent's context budget for actual work.

### Phase-by-phase parallelisation map

| Phase | Sequential prompts | Parallel opportunities |
|---|---|---|
| 0. Bootstrap | All sequential. Repo skeleton mutations are not safe to parallelise. | None. |
| 1. arxiv-deep | 1.1-1.5, 1.8, 1.9 | 1.6 + 1.7 (figures + code finder), 1.10 (3-way verification) |
| 2. tracker | 2.1-2.4, 2.8 | 2.5 + 2.6 + 2.7 (3-way tool implementation) |
| 3. integration | All sequential. Cross-repo edits need careful state. | None. |
| 4. demo | 4.1, 4.4-4.6 sequential | 4.2 + 4.3 (local + HF Jobs scripts can be parallel) |
| 5. docs | 5.1-5.6 mostly sequential, but 5.3 + 5.4 + 5.5 can parallel | 5.3 + 5.4 + 5.5 (tool ref + troubleshooting + examples) |
| 6. release | All sequential. Release engineering is sensitive to ordering. | None. |

Use the parallel slots. They cut roughly 30-40% off total time.

---

## Quality gates

Each prompt has an explicit done condition in `PROMPTS.md`. These global gates also apply at every phase exit.

**Code:**

- `make test` exits 0.
- `make test-cov` shows coverage above thresholds (85% line, 75% branch on the source packages).
- `make lint` and `make typecheck` both pass.
- No `pytest.skip` or `pytest.xfail` added during the phase.
- `uv run python -m arxiv_deep.server` and `uv run python -m experiment_tracker.server` start without error.

**Schema:**

- MCP inspector lists every registered tool.
- Each tool's input schema validates against a sample payload.
- Tool descriptions read clearly to a non-author reviewer (sanity check by re-reading them yourself).

**Hygiene:**

- `git status` shows no untracked PDFs, PNGs, model weights, or `.cache/` directories.
- `gitleaks` (or `pre-commit run gitleaks --all-files`) returns clean.
- `pyproject.toml` has no dependencies that were not declared in advance.

**Documentation:**

- Any non-obvious decision made during the phase is appended to the `CLAUDE.md` decisions log with the date.
- The CHANGELOG `[Unreleased]` section is updated.

**Hardware:**

- Every dependency installed has an ARM64 wheel (Apple Silicon).
- No CUDA-only imports outside of clearly-gated optional code paths.
- Default device selection respects the priority `cuda > mps > cpu`.

If any gate fails, stop. Fix it before the next prompt. A failure carried forward gets ten times harder to debug after two more prompts have landed on top of it.

---

## Session hygiene

Claude Code sessions degrade as context fills. Treat sessions as cheap and start new ones often.

**Start a new session when:**

- Beginning a new phase (mandatory).
- A prompt has produced more than ~50 tool calls in one session.
- The previous prompt failed badly and you are about to retry from scratch.
- You have been at it for more than two hours.

**On every new session, the first message should be:**

> Read `CLAUDE.md` and `README_PROMPTS.md`. Confirm in two sentences which phase we are in and what the immediate next prompt is. Do not start work yet.

This single habit removes about 80% of the "the agent forgot what we were doing" failures.

**Between phases, also do:**

- `git log --oneline -20` to remind yourself of recent commits.
- `make test && make lint && make typecheck` as a pre-flight before the next phase.

---

## Failure recovery

Things will fail. Plan for it.

**Test failure on a tool implementation:**

1. Do not let Claude Code patch the test to make it pass. Read the failure first.
2. If the test was wrong, fix the test, explain why in the commit message.
3. If the implementation is wrong, fix the implementation. Do not stack workarounds.

**MCP inspector cannot see a tool:**

- 90% of the time the tool was registered with the wrong decorator or the schema is malformed.
- Have Claude Code re-read the SDK summary from Prompt 1.1 (or 2.1) before guessing.
- Try `uv run python -c "from arxiv_deep.server import server; print(server.list_tools())"` to verify in-process.

**ml-intern does not pick up the server (Phase 3):**

- Check `configs/main_agent_config.json` is valid JSON. Trailing commas kill it silently.
- Check the absolute path in the `args` field actually exists.
- Run the server manually first, confirm it speaks MCP over stdio, then point ml-intern at it.
- Check ml-intern logs (location depends on its config; usually `~/.cache/ml-intern/sessions/`).

**Subagent returns garbage:**

- The brief was probably under-specified. Re-brief with explicit contracts.
- If the same brief fails twice, pull the work back to the main thread.

**Apple Silicon-specific failures:**

- "no compatible wheel" on install: the package is x86-only or its ARM build lags. Check PyPI release files; if no `arm64` wheel, find an alternative or build from source.
- MPS training NaNs or hangs: set `PYTORCH_ENABLE_MPS_FALLBACK=1`, retry. Some ops still need CPU.
- Out of memory on M5 Pro: drop batch size, enable gradient checkpointing, or switch to HF Jobs.

**Anything cascading:**

- `git stash` or `git reset --hard` to a known-good commit.
- Start a fresh session.
- Resume from the last green checkpoint, not from where the failure happened.

---

## Optimisation notes

Things that reliably save time on this specific project.

**Cache aggressively.** Paper PDFs, extracted figures, GitHub validation responses, demo dataset, training checkpoints. The QLoRA fixture should be downloaded exactly once across the entire project lifetime.

**Fixtures are not optional.** Every test that needs a paper uses the cached fixture. Tests that hit live arxiv on every run are why test suites get marked `slow` and then ignored.

**Pin the MCP SDK version.** Pre-1.0 SDKs change. Use `mcp == <version>` in `pyproject.toml`, not `>=`.

**Write tool descriptions for the agent, not for humans.** ml-intern reads the `description` field to decide when to call a tool. "Fetches a paper from arxiv." is bad. "Fetches the title, abstract, full text, and metadata of an arxiv paper given its arxiv ID. Use this before any other arxiv-deep tool when working with a new paper." is good.

**Keep `implementation_brief` heuristic, not LLM-based.** This is in `CLAUDE.md` already and worth repeating: the calling agent is the LLM. Do not embed a second LLM call inside a tool the agent uses. It hides reasoning, costs tokens, and obscures failures.

**On the M5 Pro, prefer HF Jobs for the demo during development.** Local MPS training is slower than the cloud path for small models. Use local MPS for the final demo recording and for the README screenshot, but iterate on HF Jobs.

**Commit on every green test.** Cheap insurance. `git reset --hard` becomes risk-free.

**Use `make` targets, not raw commands.** Easy for users to discover. Easy for CI to call. Consistent across local and remote.

---

## Dependency graph (visual)

```
Phase 0 (bootstrap)
    │
    ▼
Phase 1 (arxiv-deep)
    │   ├── fetch_paper (sequential)
    │   ├── extract_figures ┐
    │   ├── find_reference_code ┘ parallel
    │   └── implementation_brief (sequential, depends on the above)
    │
    ▼
Phase 2 (experiment-tracker)
    │   ├── schema + db (sequential)
    │   └── runs / metrics+artifacts / compare (parallel)
    │
    ▼
Phase 3 (integration)
    │   └── all sequential, cross-repo
    │
    ▼
Phase 4 (demo)
    │   ├── prompt design (sequential)
    │   ├── train_local + train_hf_jobs (parallel)
    │   └── orchestrator + smoke + recording (sequential)
    │
    ▼
Phase 5 (docs)
    │   ├── README + architecture (sequential)
    │   └── tool reference / troubleshooting / examples (parallel)
    │
    ▼
Phase 6 (release)
    │   └── all sequential, sensitive to ordering
    │
    ▼
SHIP
```

---

## Estimated time per phase

Realistic estimates assuming Claude Code with one user babysitting it. Add 50% if it is your first time using the SDK or `uv`.

| Phase | Estimate (focused work) |
|---|---|
| 0. Bootstrap | 1-2 hours |
| 1. arxiv-deep | 4-6 hours |
| 2. experiment-tracker | 3-5 hours |
| 3. ml-intern integration | 1-2 hours |
| 4. End-to-end demo | 4-6 hours (most spent on the demo smoke run iterating prompt + tool descriptions) |
| 5. Documentation | 2-3 hours |
| 6. Release | 1-2 hours |
| **Total** | **16-26 hours** |

Spread it over a week of evenings, or three intense days. Do not try to do it all in one sitting.

---

## Phase exit ritual

At the end of every phase, do this in order:

1. `make test`, `make lint`, `make typecheck` all green.
2. `make test-cov` shows coverage above threshold.
3. MCP inspector verifies all newly-added tools (Phases 1, 2 only).
4. `git status` clean.
5. `git push` to origin.
6. CI on GitHub goes green.
7. Update `CLAUDE.md` decisions log with anything non-obvious decided this phase.
8. Update CHANGELOG `[Unreleased]` with what changed.
9. Commit the doc updates.
10. Start a fresh Claude Code session for the next phase.

This ritual is boring. That is the point. Boring rituals catch the failures that exciting rituals miss.

---

## When you are stuck

If a prompt has been failing for more than 30 minutes, do this in order:

1. Re-read the prompt. Did Claude Code actually understand the contract?
2. Re-read `CLAUDE.md` for relevant constraints. Did the agent violate one?
3. Run the failing test in isolation, read the actual error.
4. Search the dependency's GitHub issues for the error message.
5. Start a fresh session, re-paste the prompt, see if it goes differently with clean context.
6. If still stuck, simplify the prompt. Drop one requirement, ship the partial, file an issue for the rest.

Never spiral. The right move at minute 31 is almost always "step away, return tomorrow."

---

## Final word

This project is not exotic. Two MCP servers, a demo, some docs, some CI. The reason it takes 20 hours instead of 5 is that "production-grade" means every detail matters: the typed exceptions, the cached fixtures, the ARM64 wheel checks, the tool descriptions written for an LLM consumer, the failure modes documented before they happen.

The prompts in `PROMPTS.md` enforce all of those. Trust them. Resist the urge to skip ahead.

Ship it.
