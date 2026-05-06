# Demo: end-to-end agent-driven LoRA fine-tune

This directory contains everything `make demo` needs to drive an end-to-end
fine-tuning run with `ml-intern`. The agent reads the QLoRA paper via the
`arxiv-deep` MCP server, runs three LoRA-rank training variants on a small
language model, logs every step to the `experiment-tracker` MCP server,
picks the lowest-loss winner, and publishes that adapter to a Hugging Face
model repository with a generated model card.

The demo deliberately uses a small text LM and a small dataset slice. The
narrative ("agent orchestrates the loop end-to-end") matters more than
benchmark-class results. See *Why this model and dataset* below.

## Prerequisites

1. The toolkit is synced with the demo extras:
   ```bash
   cd ml-intern-mcp-toolkit
   uv sync --extra demo
   ```
2. `ml-intern` is cloned and synced as a sibling repo, and the user-config
   layer is wired up per [`docs/ml_intern_integration.md`](../docs/ml_intern_integration.md).
3. `uv` is on your PATH (`which uv` returns a path).

## Required environment variables

| Variable | Notes |
|---|---|
| `ML_INTERN_PATH` | Absolute path to your `ml-intern` checkout. |
| `ANTHROPIC_API_KEY` | `ml-intern`'s default model is Claude. Swap to your provider's key by editing `cli_agent_config.json` if you prefer a different model. |
| `HF_TOKEN` | Write-scope HF token. Used by the training script for the publish step. |

## Optional environment variables

| Variable | Default | Effect |
|---|---|---|
| `DEMO_MODE` | `local` | `local` runs training on this machine; `hf-jobs` submits each variant to HF Jobs. |
| `DEMO_QUICK` | `0` | `1` switches both training scripts to the 50 train / 10 val / 1 epoch subset. Use this while iterating on the agent prompt. |
| `DEMO_PUSH_TO_ORG` | `0` | `1` publishes the winner to `ml-agent-explorers/<repo>`. The default publishes to your own namespace. |
| `DEMO_MODEL` | `HuggingFaceTB/SmolLM2-135M-Instruct` | Base model id. |
| `DEMO_DATASET` | `tatsu-lab/alpaca` | Training dataset id. |
| `ML_INTERN_TOOLKIT_PATH` | auto-detected | Absolute path to this checkout. |
| `ML_INTERN_CLI_CONFIG` | `$ML_INTERN_TOOLKIT_PATH/demo/ml_intern_config.json` | The user-config file `ml-intern` deep-merges over its base config. |
| `HF_JOBS_NAMESPACE` | unset | Override the namespace for `train_hf_jobs.py` submissions. |

## Running it

```bash
# fast iteration (recommended while tuning the agent prompt)
DEMO_QUICK=1 make demo

# full local run on Apple Silicon
make demo

# cloud run
DEMO_MODE=hf-jobs make demo

# publish the winner to ml-agent-explorers/<repo> instead of your namespace
DEMO_PUSH_TO_ORG=1 make demo
```

The agent transcript is mirrored to `demo/last_run.transcript.txt`
(gitignored) for review.

## Expected runtime

| Mode | Quick | Full |
|---|---|---|
| `DEMO_MODE=local` (M5 Pro MPS) | ~1-2 min | ~25 min |
| `DEMO_MODE=hf-jobs` (`cpu-basic`) | ~5-10 min (incl. cold start) | ~30-40 min (incl. cold start) |

Cold-start latency on HF Jobs comes from `uv` provisioning the Python venv
on the runner before any training begins. Subsequent runs in the same
session reuse the cache.

## Expected output

On success the agent prints a summary that includes:

- The QLoRA paper title and a one-sentence summary of its core method.
- Three final losses, one per LoRA rank.
- The winning rank and a link to the published model on Hugging Face.
- A reminder to inspect the experiment-tracker DB for the full run history.

The published model is at `https://huggingface.co/<namespace>/smollm2-lora-rank-{N}-{short_uid}`,
where `short_uid` is the first 8 hex characters of the winning run UID.

## Why this model and dataset

The original Phase 4 spec called for `Qwen3-VL-2B` on Oxford Pets.
`transformers` 5.x has a regression in the auto-loaded image-processor
chain that affects every multimodal preset we tried (SmolVLM, Qwen2-VL,
Qwen3-VL). Rather than pin a stale `transformers` version for the demo,
we pivoted to a text-only LM where the demo is dependency-stable and
iterates fast enough that prompt-tuning is pleasant. `SmolLM2-135M-Instruct`
loads on MPS in ~13s and trains a single rank in ~30s in quick mode. The
agent narrative we want to demonstrate (read paper → run variants → pick
winner → publish) is unchanged.

If you want a vision demo, fork the prompt + override `DEMO_MODEL`,
`DEMO_DATASET`, and the LoRA target modules; the same orchestration works
for any architecture `transformers` and `peft` agree on.

## Troubleshooting

**Symptom:** `Demo aborted; missing required env vars: ...`
**Fix:** export the listed variables and rerun. They should live in
`ml-intern/.env` so `agent.config.load_config` substitutes them.

**Symptom:** `ML_INTERN_PATH=... does not exist or is not a directory.`
**Fix:** clone `ml-intern` per the integration doc and update the variable.

**Symptom:** `huggingface_hub.errors.RepositoryNotFoundError` mid-publish.
**Fix:** typically a token-scope problem. Confirm `HF_TOKEN` has write
access (`huggingface-cli whoami` should report `Token: write`).

**Symptom:** the agent never calls a tool you expected.
**Fix:** improve the tool description in the relevant server, *not* the
prompt. The point of the demo is that tool descriptions carry enough
information for autonomous orchestration.

**Symptom:** training diverges or loss is NaN.
**Fix:** drop the learning rate, drop the batch size, or run with
`DEMO_QUICK=1` first to isolate. The script honours an explicit `--lr`
override via the agent.

**Symptom:** HF Jobs cold start times out.
**Fix:** raise the per-job timeout via the script's `--timeout` flag
(`30m`, `1h`, etc.) or downgrade to `DEMO_QUICK=1` so the budget fits.
