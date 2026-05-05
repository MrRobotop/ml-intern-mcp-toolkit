"""Tests for ``experiment_tracker.tools.artifacts.log_artifact``.

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
from experiment_tracker.models import Artifact, Run
from experiment_tracker.tools.artifacts import log_artifact


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


def _count_artifacts() -> int:
    with get_session(current_engine()) as session:
        return len(session.scalars(select(Artifact)).all())


def test_log_artifact_happy_path_returns_positive_id_and_logs_row(
    tracker_db: Path,
) -> None:
    run_uid = _seed_run()

    out = log_artifact(
        run_uid=run_uid,
        kind="model",
        uri="hf://ml-agent-explorers/qwen3-vl-2b-pets",
    )

    assert out["logged"] is True
    assert isinstance(out["artifact_id"], int)
    assert out["artifact_id"] > 0

    with get_session(current_engine()) as session:
        statement = select(Artifact).where(Artifact.id == out["artifact_id"])
        row = session.scalars(statement).one()
        assert row.kind == "model"
        assert row.uri == "hf://ml-agent-explorers/qwen3-vl-2b-pets"


def test_log_artifact_unknown_run_uid_raises_run_not_found(
    tracker_db: Path,
) -> None:
    before = _count_artifacts()

    with pytest.raises(RunNotFoundError):
        log_artifact(run_uid="does-not-exist", kind="model", uri="hf://nope")

    assert _count_artifacts() == before


def test_log_artifact_multiple_uris_per_run_round_trip(tracker_db: Path) -> None:
    run_uid = _seed_run()

    uris = [
        "hf://ml-agent-explorers/run-1",
        "hf://ml-agent-explorers/run-2",
        "file:///tmp/checkpoint.bin",
        "s3://my-bucket/logs/train.log",
    ]
    ids = [log_artifact(run_uid=run_uid, kind="model", uri=uri)["artifact_id"] for uri in uris]

    assert len(set(ids)) == 4

    with get_session(current_engine()) as session:
        rows = session.scalars(select(Artifact)).all()
        assert len(rows) == 4
        assert {row.uri for row in rows} == set(uris)


def test_log_artifact_different_kinds_round_trip(tracker_db: Path) -> None:
    run_uid = _seed_run()

    pairs = [
        ("model", "hf://ml-agent-explorers/best"),
        ("checkpoint", "file:///tmp/ckpt-step-100.bin"),
        ("log", "file:///tmp/train.log"),
    ]
    for kind, uri in pairs:
        out = log_artifact(run_uid=run_uid, kind=kind, uri=uri)
        assert out["logged"] is True

    with get_session(current_engine()) as session:
        rows = session.scalars(select(Artifact)).all()
        observed = {(row.kind, row.uri) for row in rows}
        assert observed == set(pairs)
