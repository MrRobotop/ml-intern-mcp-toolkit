"""Failing tests for ``experiment_tracker.tools.runs``.

Pins the contract for ``start_run``, ``list_runs``, and ``complete_run``
before Prompt 2.5 lands the implementation. Each test uses a per-test
SQLite file by setting ``EXPERIMENT_TRACKER_DB_PATH`` so production code
can resolve it via :func:`experiment_tracker.db.default_db_path`. State
cannot leak across tests.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from experiment_tracker.exceptions import RunNotFoundError
from experiment_tracker.tools.runs import complete_run, list_runs, start_run

_UUID4_HEX_RE = re.compile(r"^[a-f0-9]{32}$")

_DEFAULT_KW: dict[str, object] = {
    "recipe": "lora-rank-8",
    "model_base": "Qwen/Qwen3-VL-2B-Instruct",
    "dataset": "oxford-pets",
    "hyperparameters": {"lr": 0.0002, "batch_size": 4},
}


@pytest.fixture
def tracker_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Per-test SQLite path; overrides EXPERIMENT_TRACKER_DB_PATH."""
    db_path = tmp_path / "runs.db"
    monkeypatch.setenv("EXPERIMENT_TRACKER_DB_PATH", str(db_path))
    return db_path


def test_start_run_returns_uuid_hex_and_positive_id(tracker_db: Path) -> None:
    out = start_run(**_DEFAULT_KW)  # type: ignore[arg-type]

    assert isinstance(out, dict)
    assert _UUID4_HEX_RE.match(out["run_uid"]), f"not a uuid4 hex: {out['run_uid']!r}"
    assert isinstance(out["id"], int)
    assert out["id"] > 0


def test_start_run_persists_status_running(tracker_db: Path) -> None:
    out = start_run(**_DEFAULT_KW)  # type: ignore[arg-type]

    rows = list_runs()
    matching = [row for row in rows if row["run_uid"] == out["run_uid"]]
    assert len(matching) == 1
    assert matching[0]["status"] == "running"


def test_multiple_start_runs_yield_distinct_uids(tracker_db: Path) -> None:
    a = start_run(**_DEFAULT_KW)  # type: ignore[arg-type]
    b = start_run(**_DEFAULT_KW)  # type: ignore[arg-type]
    c = start_run(**_DEFAULT_KW)  # type: ignore[arg-type]

    uids = {a["run_uid"], b["run_uid"], c["run_uid"]}
    assert len(uids) == 3
    ids = {a["id"], b["id"], c["id"]}
    assert len(ids) == 3


def test_hyperparameters_round_trip_via_list_runs(tracker_db: Path) -> None:
    nested: dict[str, object] = {
        "lr": 1.0e-4,
        "lora": {"r": 8, "alpha": 32, "target_modules": ["q_proj", "v_proj"]},
        "schedule": {"warmup_steps": 100, "cosine": True},
    }
    out = start_run(
        recipe="lora",
        model_base="meta-llama/Llama-2-7b",
        dataset="alpaca",
        hyperparameters=nested,
    )

    rows = list_runs()
    fetched = next(row for row in rows if row["run_uid"] == out["run_uid"])
    assert fetched["hyperparameters"] == nested


def test_list_runs_with_no_filters_returns_all(tracker_db: Path) -> None:
    for _ in range(3):
        start_run(**_DEFAULT_KW)  # type: ignore[arg-type]

    assert len(list_runs()) == 3


def test_list_runs_filter_by_recipe_returns_only_matching(tracker_db: Path) -> None:
    start_run(recipe="lora-r4", model_base="m", dataset="d", hyperparameters={})
    start_run(recipe="lora-r8", model_base="m", dataset="d", hyperparameters={})
    start_run(recipe="lora-r4", model_base="m", dataset="d", hyperparameters={})

    matched = list_runs({"recipe": "lora-r4"})
    assert len(matched) == 2
    assert all(row["recipe"] == "lora-r4" for row in matched)


def test_list_runs_empty_database_returns_empty_list(tracker_db: Path) -> None:
    assert list_runs() == []


def test_list_runs_combined_filters_and_together(tracker_db: Path) -> None:
    start_run(recipe="lora-r4", model_base="A", dataset="d", hyperparameters={})
    start_run(recipe="lora-r4", model_base="B", dataset="d", hyperparameters={})
    start_run(recipe="lora-r8", model_base="A", dataset="d", hyperparameters={})

    matched = list_runs({"recipe": "lora-r4", "model_base": "A"})
    assert len(matched) == 1
    assert matched[0]["recipe"] == "lora-r4"
    assert matched[0]["model_base"] == "A"


def test_complete_run_default_status_is_completed(tracker_db: Path) -> None:
    started = start_run(**_DEFAULT_KW)  # type: ignore[arg-type]

    out = complete_run(started["run_uid"])
    assert out["run_uid"] == started["run_uid"]
    assert out["status"] == "completed"

    persisted = next(row for row in list_runs() if row["run_uid"] == started["run_uid"])
    assert persisted["status"] == "completed"


def test_complete_run_failed_status_persists(tracker_db: Path) -> None:
    started = start_run(**_DEFAULT_KW)  # type: ignore[arg-type]

    out = complete_run(started["run_uid"], status="failed")
    assert out["status"] == "failed"

    persisted = next(row for row in list_runs() if row["run_uid"] == started["run_uid"])
    assert persisted["status"] == "failed"


def test_complete_run_unknown_uid_raises_run_not_found(tracker_db: Path) -> None:
    with pytest.raises(RunNotFoundError):
        complete_run("0" * 32)


def test_complete_run_invalid_status_raises_value_error(tracker_db: Path) -> None:
    started = start_run(**_DEFAULT_KW)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="status must be one of"):
        complete_run(started["run_uid"], status="weird")
