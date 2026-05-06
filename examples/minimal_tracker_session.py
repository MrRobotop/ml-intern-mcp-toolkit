"""Minimal experiment-tracker session.

Spins up a tracker pointed at a temporary SQLite database, simulates three
training runs at different LoRA ranks (no real training; canned losses),
calls ``compare_runs`` and ``best_run``, prints the rendered Markdown table.

The point is to show what the tracker does without the agent or the GPU. New
users can run this in five seconds and see exactly what gets persisted.

Run from the toolkit root:

    uv run python examples/minimal_tracker_session.py
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from experiment_tracker.tools.compare import best_run, compare_runs
from experiment_tracker.tools.metrics import log_metric
from experiment_tracker.tools.runs import complete_run, start_run

_VARIANTS: list[tuple[int, float]] = [
    (4, 0.42),
    (8, 0.31),
    (16, 0.28),
]


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "minimal.db"
        os.environ["EXPERIMENT_TRACKER_DB_PATH"] = str(db_path)

        run_uids: list[str] = []
        for rank, final_loss in _VARIANTS:
            started = start_run(
                recipe=f"smollm2-lora-rank-{rank}",
                model_base="HuggingFaceTB/SmolLM2-135M-Instruct",
                dataset="tatsu-lab/alpaca",
                hyperparameters={"lora_rank": rank, "lr": 1e-4, "batch_size": 4},
                notes="example session",
            )
            run_uid = started["run_uid"]
            run_uids.append(run_uid)
            log_metric(run_uid=run_uid, step=1, name="final_loss", value=final_loss)
            complete_run(run_uid=run_uid, status="completed")

        print("# compare_runs(final_loss)\n")
        print(compare_runs(run_uids=run_uids, metric_name="final_loss"))
        print()

        winner = best_run(metric_name="final_loss", direction="min")
        if winner is None:
            print("best_run: no eligible run")
            return 1
        print("# best_run(final_loss, direction=min)")
        print(f"recipe        : {winner['recipe']}")
        print(f"run_uid       : {winner['run_uid']}")
        print(f"hyperparameters: {winner['hyperparameters']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
