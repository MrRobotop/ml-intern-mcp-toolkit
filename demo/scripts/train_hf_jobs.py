"""HF Jobs wrapper around :mod:`demo.scripts.train_local`.

Submits the same training script to Hugging Face's Jobs infrastructure and
streams logs back to stdout/stderr so the calling agent sees the same
single-line ``{"final_loss": ..., "checkpoint_dir": ...}`` contract on
completion.

Why a wrapper rather than reimplementing the loop in ``run_uv_job``:
``train_local.py`` already handles model + LoRA + dataset + push-to-hub.
HF Jobs runs UV scripts on its own runners, so we hand it the *URL* of the
script in our toolkit's main branch (or a fallback inline path) and the same
CLI flags. One source of truth for training; HF Jobs is just a transport.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass

logger = logging.getLogger("demo.train_hf_jobs")

DEFAULT_FLAVOR = "cpu-basic"
DEFAULT_TIMEOUT_QUICK = "10m"
DEFAULT_TIMEOUT_FULL = "60m"
DEFAULT_DEPENDENCIES = [
    "torch>=2.5",
    "transformers",
    "peft",
    "accelerate",
    "datasets",
    "huggingface_hub",
]
DEFAULT_SCRIPT_URL = (
    "https://raw.githubusercontent.com/MrRobotop/ml-intern-mcp-toolkit/"
    "main/demo/scripts/train_local.py"
)

POLL_INTERVAL_SECONDS = 5.0
TERMINAL_STAGES = {"COMPLETED", "ERROR", "CANCELED", "DELETED"}


@dataclass
class JobsArgs:
    """Subset of train_local.py's args, plus HF Jobs-specific knobs."""

    model_base: str
    dataset: str
    lora_rank: int
    epochs: int
    lr: float
    batch_size: int
    output_dir: str
    run_uid: str
    quick: bool
    push_to_hub: str | None
    flavor: str
    timeout: str
    script_url: str


def _parse_args(argv: list[str] | None = None) -> JobsArgs:
    parser = argparse.ArgumentParser(description="Submit train_local.py as a Hugging Face Job.")
    parser.add_argument("--model-base", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--lora-rank", type=int, required=True)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-uid", required=True)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--push-to-hub", default=None)
    parser.add_argument("--flavor", default=DEFAULT_FLAVOR)
    parser.add_argument(
        "--timeout",
        default=None,
        help="HF Jobs timeout string (e.g. '10m', '1h'). Defaults depend on --quick.",
    )
    parser.add_argument(
        "--script-url",
        default=DEFAULT_SCRIPT_URL,
        help="URL of the train_local.py script the job will execute.",
    )
    ns = parser.parse_args(argv)
    return JobsArgs(
        model_base=ns.model_base,
        dataset=ns.dataset,
        lora_rank=ns.lora_rank,
        epochs=ns.epochs,
        lr=ns.lr,
        batch_size=ns.batch_size,
        output_dir=ns.output_dir,
        run_uid=ns.run_uid,
        quick=ns.quick,
        push_to_hub=ns.push_to_hub,
        flavor=ns.flavor,
        timeout=ns.timeout or (DEFAULT_TIMEOUT_QUICK if ns.quick else DEFAULT_TIMEOUT_FULL),
        script_url=ns.script_url,
    )


def _build_script_args(args: JobsArgs) -> list[str]:
    """Translate ``JobsArgs`` into ``train_local.py``'s CLI flags."""
    flags = [
        "--model-base",
        args.model_base,
        "--dataset",
        args.dataset,
        "--lora-rank",
        str(args.lora_rank),
        "--epochs",
        str(args.epochs),
        "--lr",
        str(args.lr),
        "--batch-size",
        str(args.batch_size),
        "--output-dir",
        args.output_dir,
        "--run-uid",
        args.run_uid,
    ]
    if args.quick:
        flags.append("--quick")
    if args.push_to_hub:
        flags.extend(["--push-to-hub", args.push_to_hub])
    return flags


def _wait_for_completion(job_id: str, namespace: str | None) -> str:
    """Poll ``inspect_job`` until the job reaches a terminal stage.

    Returns the final stage as a string. Raises if HF returns an unexpected
    error during polling. The ``namespace`` argument matches the value the
    job was submitted with so polling targets the right space.
    """
    from huggingface_hub import inspect_job

    while True:
        info = inspect_job(job_id=job_id, namespace=namespace)
        stage = info.status.stage if hasattr(info.status, "stage") else str(info.status)
        logger.info("job %s stage=%s", job_id, stage)
        if str(stage) in TERMINAL_STAGES:
            return str(stage)
        time.sleep(POLL_INTERVAL_SECONDS)


def _stream_logs(job_id: str, namespace: str | None) -> str:
    """Stream remaining job logs and return the concatenated string."""
    from huggingface_hub import fetch_job_logs

    captured: list[str] = []
    for line in fetch_job_logs(job_id=job_id, namespace=namespace, follow=False):
        sys.stderr.write(line if line.endswith("\n") else line + "\n")
        captured.append(line)
    return "\n".join(captured)


def _extract_final_loss_line(logs: str, run_uid: str) -> str:
    """Return the JSON line emitted by ``train_local.py`` on completion.

    ``train_local.py`` writes one ``{"final_loss": ..., "checkpoint_dir": ...,
    "run_uid": ...}`` line to stdout. HF Jobs interleaves stdout and stderr in
    the captured logs; we identify the contract line by parsing each line as
    JSON and matching ``run_uid``.
    """
    for raw in reversed(logs.splitlines()):
        line = raw.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("run_uid") == run_uid and "final_loss" in obj:
            return line
    raise RuntimeError(
        f"Could not find the final-loss JSON line in HF Jobs logs for run {run_uid!r}. "
        "The training script may have crashed before emitting its result; check the "
        "streamed log output above."
    )


def main(argv: list[str] | None = None) -> int:
    """Submit, wait, surface the result. Returns a process exit code."""
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from huggingface_hub import run_uv_job

    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN must be set for HF Jobs submission.")
    namespace = os.environ.get("HF_JOBS_NAMESPACE") or None

    logger.info(
        "submitting HF Jobs run uid=%s rank=%d flavor=%s timeout=%s",
        args.run_uid,
        args.lora_rank,
        args.flavor,
        args.timeout,
    )
    job_info = run_uv_job(
        script=args.script_url,
        script_args=_build_script_args(args),
        dependencies=DEFAULT_DEPENDENCIES,
        flavor=args.flavor,
        timeout=args.timeout,
        env={
            "PYTORCH_ENABLE_MPS_FALLBACK": "1",
            "TRANSFORMERS_VERBOSITY": "error",
        },
        secrets={"HF_TOKEN": token},
        namespace=namespace,
        token=token,
    )
    job_id: str = job_info.id
    logger.info("submitted; job_id=%s", job_id)

    stage = _wait_for_completion(job_id, namespace)
    logs = _stream_logs(job_id, namespace)

    if stage != "COMPLETED":
        raise RuntimeError(f"HF Jobs run {job_id!r} ended in stage {stage!r}; see logs above.")

    final_line = _extract_final_loss_line(logs, args.run_uid)
    print(final_line)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via the CLI
    raise SystemExit(main())
