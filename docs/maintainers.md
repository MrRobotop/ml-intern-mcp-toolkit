# Maintainer playbook

Settings and procedures that live outside the repo's CI / code surface.
Apply these in the GitHub UI on first deploy, then refer back when the
project's published artefacts or governance need attention.

---

## One-time GitHub repository settings

Apply these once after first push. Most live under
`Settings -> ...` in the repository.

### General

- **Description:**
  > Production MCP toolkit extending Hugging Face's ml-intern with deep arxiv reading and experiment tracking.
- **Website:** leave empty for now (or link to a future docs site).
- **Topics:** `mcp`, `ml-intern`, `huggingface`, `agent`, `arxiv`,
  `experiment-tracking`, `apple-silicon`, `lora`, `peft`, `python`.
- **Disable** Wikis, Discussions, and Projects unless the maintainer plans
  to use them; each tab adds support surface for no inbound value at
  this scale.

### Branches

Apply branch protection on `main`:

- Require a pull request before merging.
  - Require **1 approval** for review.
  - Dismiss stale approvals on new commits.
  - Require review of the most recent push.
- Require status checks to pass before merging:
  - `ci / ubuntu-latest / py3.11`
  - `ci / ubuntu-latest / py3.12`
  - `ci / macos-14 / py3.11`
  - `ci / macos-14 / py3.12`
  - `lint`
  - `secrets-scan / gitleaks`
  - `markdown-lint`
- Require branches to be up to date before merging.
- Require linear history (no merge commits).
- **Disallow** force pushes.
- **Disallow** deletions.
- Apply to administrators (no override on main).

### Actions

- Allow GitHub Actions: **Allow all actions and reusable workflows**.
  We pin third-party actions to specific tags in our workflows; the
  remaining risk is not worth the friction of an allowlist for a
  two-maintainer project.
- Workflow permissions: **Read repository contents and packages
  permissions** by default. Workflows that need write access declare it
  per-job via `permissions:` (release.yml does this for `contents: write`).

### Secrets and variables -> Actions

Add only when needed; nothing is required by the default CI:

| Secret | When | Notes |
|---|---|---|
| `PYPI_API_TOKEN` | Optional, for PyPI publish | Used by `release.yml` if present. Generate at https://pypi.org/manage/account/token/ scoped to this project only. |

Do **not** store `ANTHROPIC_API_KEY`, `HF_TOKEN`, or `GITHUB_TOKEN`
(personal) in repo secrets; those are user-side only and live in
`ml-intern/.env` on the operator's machine.

---

## Release procedure

End-to-end checklist for cutting a new version. Steps 1-3 happen on a
local branch; step 4 is the only operation that touches origin.

1. **Bump the version.** Edit `pyproject.toml`'s `[project] version`.
   Use [SemVer](https://semver.org/): patch for bug fixes, minor for
   backwards-compatible features, major for breaking changes.
2. **Move the `[Unreleased]` block.** In `CHANGELOG.md`, rename the
   `[Unreleased]` heading to `[X.Y.Z] - YYYY-MM-DD` and open a fresh
   empty `[Unreleased]` block above it. The release workflow extracts
   the new section verbatim into the GitHub Release notes.
3. **Commit.** `git add pyproject.toml CHANGELOG.md && git commit -m
   "chore(release): X.Y.Z"`.
4. **Tag and push.**
   ```bash
   git tag vX.Y.Z
   git push origin main
   git push origin vX.Y.Z
   ```
   Pushing the tag triggers `.github/workflows/release.yml`. Watch it at
   https://github.com/MrRobotop/ml-intern-mcp-toolkit/actions/workflows/release.yml.
5. **Verify.** Confirm the GitHub Release at
   https://github.com/MrRobotop/ml-intern-mcp-toolkit/releases/tag/vX.Y.Z
   shows the wheel + sdist and the changelog notes look right.

If a release fails partway:

- The tag exists on origin but the release does not.
- `git push --delete origin vX.Y.Z && git tag -d vX.Y.Z`, fix the
  workflow, then re-tag and re-push.
- The release workflow is idempotent on the artefact upload step
  (`gh release create` will fail if the release already exists; that's
  the safety check).

---

## Yanking a release

If a release ships with a critical bug or accidental secret:

1. Mark the GitHub Release as a pre-release or delete it.
2. If published to PyPI, run `uv publish --yank vX.Y.Z` (or use the
   PyPI web UI) so installers stop selecting it.
3. Cut a follow-up `vX.Y.Z+1` with the fix and a `Fixed` entry in the
   CHANGELOG.

Do **not** force-push over a tag. Once a tag is on origin, downstream
consumers may have already pinned it; a force-push silently changes
their behaviour. Yank + new tag is always safer.

---

## Rotating any leaked secret

If a token ever appears in a public artefact (commit, release notes, CI
log, GitHub Issue):

1. Revoke the token immediately at the provider's console (Anthropic /
   Hugging Face / GitHub / etc.).
2. If the token was committed: do **not** rewrite history. Force-pushing
   over a leak does not remove it from forks, mirrors, or scrapers.
   Revocation is the only reliable mitigation.
3. Generate a replacement, store it in the operator's local `.env`, and
   confirm via the provider's audit log that no calls were made between
   leak and revocation.
4. Add the leak prefix to a new entry in the CHANGELOG under `Security`
   so the audit trail is permanent.

---

## What lives where (orientation map)

| Concern | Where |
|---|---|
| New dependency | `pyproject.toml` `[project] dependencies` (or `[project.optional-dependencies] demo` for training-only deps). |
| New tool | New file under `arxiv_deep/tools/` or `experiment_tracker/tools/`, registered in the corresponding `server.py`. Run `make docs` to refresh `docs/tool_reference.md`. |
| New CI gate | New step in `.github/workflows/ci.yml`, or a new workflow file. |
| New env var the demo needs | `demo/run_demo.sh` pre-flight, `demo/README.md` env-var table, `.env.example`. |
| Style change to all docs | `.markdownlint.json`. |
| Decision worth recording | Append to the decisions log in `CLAUDE.md`. |
