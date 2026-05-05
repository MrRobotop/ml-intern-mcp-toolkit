"""Tests for ``experiment_tracker.tools.metrics.log_metric``.

Each test gets its own SQLite file by setting
``EXPERIMENT_TRACKER_DB_PATH`` so production code resolves it through
:func:`experiment_tracker.db.default_db_path`. Runs are seeded directly
through the ORM because ``experiment_tracker.tools.runs`` is being written
in a parallel worktree and is not importable here yet.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from sqlmodel import select

from experiment_tracker.db import current_engine, get_session
from experiment_tracker.exceptions import RunNotFoundError
from experiment_tracker.models import Metric, Run
from experiment_tracker.tools.metrics import log_metric


@pytest.fixture
def tracker_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Per-test SQLite path; overrides EXPERIMENT_TRACKER_DB_PATH."""
    db_path = tmp_path / "runs.db"
    monkeypatch.setenv("EXPERIMENT_TRACKER_DB_PATH", str(db_path))
    return db_path


def _seed_run(
    recipe: str = "lora-rank-8",
    model_base: str = "Qwen/Qwen3-VL-2B-Instruct",
    dataset: str = "oxford-pets",
    hyperparameters: dict[str, Any] | None = None,
) -> str:
    """Insert a minimal :class:`Run` directly via the ORM and return its uid."""
    with get_session(current_engine()) as session:
        run = Run(
            recipe=recipe,
            model_base=model_base,
            dataset=dataset,
            hyperparameters=hyperparameters or {},
            status="running",
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        return run.run_uid


def _count_metrics() -> int:
    with get_session(current_engine()) as session:
        return len(session.scalars(select(Metric)).all())


def test_log_metric_happy_path_returns_positive_id_and_logs_row(
    tracker_db: Path,
) -> None:
    run_uid = _seed_run()

    out = log_metric(run_uid=run_uid, step=0, name="loss", value=1.25)

    assert out["logged"] is True
    assert isinstance(out["metric_id"], int)
    assert out["metric_id"] > 0

    with get_session(current_engine()) as session:
        statement = select(Metric).where(Metric.id == out["metric_id"])
        row = session.scalars(statement).one()
        assert row.step == 0
        assert row.name == "loss"
        assert row.value == 1.25


def test_log_metric_unknown_run_uid_raises_run_not_found(tracker_db: Path) -> None:
    before = _count_metrics()

    with pytest.raises(RunNotFoundError):
        log_metric(run_uid="does-not-exist", step=0, name="loss", value=0.0)

    assert _count_metrics() == before


def test_log_metric_multiple_distinct_combos_round_trip(tracker_db: Path) -> None:
    run_uid = _seed_run()

    combos = [
        (0, "loss", 1.5),
        (0, "accuracy", 0.10),
        (1, "loss", 1.2),
        (1, "accuracy", 0.18),
        (2, "loss", 0.9),
    ]
    metric_ids = [
        log_metric(run_uid=run_uid, step=step, name=name, value=value)["metric_id"]
        for step, name, value in combos
    ]

    assert len(set(metric_ids)) == 5

    with get_session(current_engine()) as session:
        rows = session.scalars(select(Metric)).all()
        assert len(rows) == 5
        observed = {(row.step, row.name, row.value) for row in rows}
        assert observed == set(combos)


def test_log_metric_repeated_combo_creates_new_row_each_call(
    tracker_db: Path,
) -> None:
    run_uid = _seed_run()

    first = log_metric(run_uid=run_uid, step=10, name="loss", value=0.5)
    second = log_metric(run_uid=run_uid, step=10, name="loss", value=0.5)
    third = log_metric(run_uid=run_uid, step=10, name="loss", value=0.5)

    assert first["metric_id"] != second["metric_id"]
    assert second["metric_id"] != third["metric_id"]

    with get_session(current_engine()) as session:
        rows = session.scalars(select(Metric).where(Metric.step == 10, Metric.name == "loss")).all()
        assert len(rows) == 3
