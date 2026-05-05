"""``log_metric`` MCP tool implementation.

Writes a single ``(step, name, value)`` triple to the ``metric`` table for
an existing run. The function resolves the agent-facing ``run_uid`` to the
internal integer ``run_id`` foreign key, raises :class:`RunNotFoundError`
when no run matches, and returns the new ``metric_id`` so the caller can
correlate writes with downstream reads.

There is no uniqueness constraint on ``(run_id, step, name)``: repeated
calls with identical arguments append new rows, which lets the agent log
the same metric across retries without losing earlier values.
"""

from __future__ import annotations

from typing import Any

from sqlmodel import select

from experiment_tracker.db import current_engine, get_session
from experiment_tracker.exceptions import RunNotFoundError
from experiment_tracker.models import Metric, Run

LOG_METRIC_DESCRIPTION = (
    "Records one metric value for an existing run, identified by its "
    "run_uid (the opaque string handle returned by start_run). Call this "
    "after each training step to build the time series the agent will "
    "later compare across runs. Inputs: run_uid (str), step (int, "
    "monotonically increasing within a run by convention but not "
    "enforced), name (str, the metric label such as 'loss' or "
    "'accuracy'), value (float). Returns a dict with keys logged (bool, "
    "always True on success) and metric_id (int, the database row id of "
    "the newly inserted metric). Raises RunNotFoundError if run_uid does "
    "not match any existing run; the agent should call start_run first or "
    "verify the uid via list_runs. The same (step, name) tuple may be "
    "logged multiple times: each call appends a new row, no implicit "
    "deduplication."
)


def log_metric(run_uid: str, step: int, name: str, value: float) -> dict[str, Any]:
    """Persist a metric value for an existing run.

    Args:
        run_uid: The opaque string handle for the parent run, as returned
            by ``start_run`` and surfaced by ``list_runs``.
        step: The training step or epoch the value belongs to.
        name: The metric label, for example ``"loss"`` or ``"accuracy"``.
        value: The numeric value to record.

    Returns:
        A dict with two keys: ``logged`` (always ``True`` on success) and
        ``metric_id`` (the positive integer primary key of the newly
        inserted row).

    Raises:
        RunNotFoundError: If no run exists with the supplied ``run_uid``.
    """
    engine = current_engine()
    with get_session(engine) as session:
        statement = select(Run).where(Run.run_uid == run_uid)
        run = session.scalars(statement).first()
        if run is None or run.id is None:
            raise RunNotFoundError(f"no run with run_uid={run_uid!r}")

        metric = Metric(run_id=run.id, step=step, name=name, value=value)
        session.add(metric)
        session.commit()
        session.refresh(metric)
        metric_id = metric.id

    assert metric_id is not None  # primary key populated by the commit/refresh
    return {"logged": True, "metric_id": metric_id}


__all__ = ["LOG_METRIC_DESCRIPTION", "log_metric"]
