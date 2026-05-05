"""SQLModel table definitions for the experiment tracker.

Three tables make up the schema:

* :class:`Run` is the parent row for every fine-tuning attempt the agent
  starts. It carries the immutable identity (``run_uid``), recipe, base
  model, dataset, hyperparameter dict, and the lifecycle ``status``.
* :class:`Metric` stores time-series values logged during a run (loss,
  accuracy, throughput, ...). Each row points back to a :class:`Run` via
  ``run_id``.
* :class:`Artifact` records URIs (model weights, checkpoints, log files)
  produced by a run.

The ``hyperparameters`` field uses a SQLite JSON column so nested dicts
round-trip without pickling. Foreign keys are enforced at the database
level by the connection event handler in :mod:`experiment_tracker.db`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON
from sqlmodel import Column, Field, SQLModel


def _utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime.

    Centralised so tests and code paths agree on the timestamp source and
    so :func:`freezegun.freeze_time` patches a single function.
    """
    return datetime.now(UTC)


def _new_run_uid() -> str:
    """Return a fresh uuid4 hex string for a new :class:`Run`."""
    return uuid4().hex


class Run(SQLModel, table=True):
    """One fine-tuning attempt the agent has started.

    Identity uses two keys: an integer ``id`` for foreign-key joins (cheap,
    fast indexes) and a string ``run_uid`` for the agent-facing handle that
    is stable, opaque, and safe to expose in tool outputs.
    """

    __tablename__ = "run"

    id: int | None = Field(default=None, primary_key=True)
    run_uid: str = Field(default_factory=_new_run_uid, index=True, unique=True)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    recipe: str = Field(nullable=False, index=True)
    model_base: str = Field(nullable=False, index=True)
    dataset: str = Field(nullable=False, index=True)
    hyperparameters: dict[str, Any] = Field(
        sa_column=Column(JSON, nullable=False),
    )
    status: str = Field(nullable=False, index=True)
    notes: str | None = Field(default=None)


class Metric(SQLModel, table=True):
    """A single metric value logged at a particular step of a run."""

    __tablename__ = "metric"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True, nullable=False)
    step: int = Field(nullable=False)
    name: str = Field(nullable=False, index=True)
    value: float = Field(nullable=False)
    logged_at: datetime = Field(default_factory=_utcnow, nullable=False)


class Artifact(SQLModel, table=True):
    """A URI pointing to a model, checkpoint, or log produced by a run."""

    __tablename__ = "artifact"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True, nullable=False)
    kind: str = Field(nullable=False, index=True)
    uri: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)


__all__ = ["Artifact", "Metric", "Run"]
