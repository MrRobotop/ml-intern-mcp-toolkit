"""Tests for ``experiment_tracker.db``: schema bootstrap, FK enforcement, JSON.

Each test gets its own SQLite file under ``tmp_path`` so state cannot leak
across tests. The ``EXPERIMENT_TRACKER_DB_PATH`` environment variable is
also exercised here as part of the contract that downstream tools depend on.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from experiment_tracker.db import default_db_path, get_engine, get_session, init_db
from experiment_tracker.models import Metric, Run


def test_init_db_creates_all_three_tables(tmp_path: Path) -> None:
    engine = get_engine(tmp_path / "runs.db")
    init_db(engine)

    table_names = set(inspect(engine).get_table_names())

    assert {"run", "metric", "artifact"} <= table_names


def test_run_insert_and_query_round_trip(tmp_path: Path) -> None:
    engine = get_engine(tmp_path / "runs.db")
    init_db(engine)

    with get_session(engine) as session:
        run = Run(
            recipe="lora-rank-8",
            model_base="Qwen/Qwen3-VL-2B-Instruct",
            dataset="oxford-pets",
            hyperparameters={"lr": 0.0002, "batch_size": 4},
            status="running",
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        run_uid = run.run_uid

    with get_session(engine) as session:
        statement = select(Run).where(Run.run_uid == run_uid)
        fetched = session.scalars(statement).one()
        assert fetched.recipe == "lora-rank-8"
        assert fetched.dataset == "oxford-pets"
        assert fetched.status == "running"


def test_metric_with_unknown_run_id_raises_integrity_error(tmp_path: Path) -> None:
    engine = get_engine(tmp_path / "runs.db")
    init_db(engine)

    with pytest.raises(IntegrityError), get_session(engine) as session:
        session.add(Metric(run_id=999_999, step=0, name="loss", value=0.5))
        session.commit()


def test_hyperparameters_round_trip_nested_dict(tmp_path: Path) -> None:
    engine = get_engine(tmp_path / "runs.db")
    init_db(engine)

    nested: dict[str, object] = {
        "optimizer": {"name": "adamw", "betas": [0.9, 0.999]},
        "schedule": {"warmup_steps": 100, "cosine": True},
        "lora": {"r": 8, "alpha": 16, "target_modules": ["q_proj", "v_proj"]},
    }

    with get_session(engine) as session:
        run = Run(
            recipe="qlora",
            model_base="meta-llama/Llama-2-7b",
            dataset="alpaca",
            hyperparameters=nested,
            status="running",
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id

    with get_session(engine) as session:
        fetched = session.get(Run, run_id)
        assert fetched is not None
        assert fetched.hyperparameters == nested


def test_default_db_path_honours_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "redirected.db"
    monkeypatch.setenv("EXPERIMENT_TRACKER_DB_PATH", str(target))

    assert default_db_path() == target


def test_default_db_path_falls_back_to_user_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EXPERIMENT_TRACKER_DB_PATH", raising=False)

    path = default_db_path()

    assert path.name == "runs.db"
    assert path.parent.name == "experiment-tracker"
