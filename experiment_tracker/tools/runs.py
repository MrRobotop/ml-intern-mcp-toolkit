"""Run-lifecycle MCP tools: ``start_run``, ``list_runs``, ``complete_run``.

The agent calls :func:`start_run` once at the beginning of a fine-tuning
attempt to obtain a stable ``run_uid``, threads that handle through
:func:`experiment_tracker.tools.metrics.log_metric` and
:func:`experiment_tracker.tools.artifacts.log_artifact` while training, and
finishes with :func:`complete_run` to flip the row's status. Read-only
discovery happens via :func:`list_runs`, which supports a small set of
exact-match filters AND-ed together.

All three tools resolve the database engine through
:func:`experiment_tracker.db.current_engine`, so the path honours
``EXPERIMENT_TRACKER_DB_PATH`` at call time. Datetimes returned to callers
are ISO 8601 strings so the JSON-RPC layer can serialise them without extra
plumbing.
"""

from __future__ import annotations

from typing import Any

from sqlmodel import col, select

from experiment_tracker.db import current_engine, get_session
from experiment_tracker.exceptions import RunNotFoundError
from experiment_tracker.models import Run

_RUN_STATUS_RUNNING = "running"
_TERMINAL_STATUSES: frozenset[str] = frozenset({"completed", "failed"})
_FILTERABLE_FIELDS: frozenset[str] = frozenset(
    {"recipe", "model_base", "dataset", "status"},
)


START_RUN_DESCRIPTION = (
    "Creates a new run row for a fine-tuning attempt and returns its handle. "
    "Call this exactly once at the start of every training attempt, before "
    "logging metrics or artifacts. The tool is NOT idempotent: each call "
    "inserts a new row with a fresh run_uid, so retrying after a transient "
    "client error will produce a duplicate run. Required arguments: recipe "
    "(str, the recipe name such as 'lora-rank-8'), model_base (str, the base "
    "model identifier such as 'Qwen/Qwen3-VL-2B-Instruct'), dataset (str, the "
    "training dataset identifier such as 'oxford-pets'), and hyperparameters "
    "(dict, an arbitrary nested JSON-serialisable dict round-tripped through "
    "a SQLite JSON column). Optional notes (str) is free-form prose, default "
    "empty string. The new row's status is set to 'running'; flip it later "
    "via complete_run. Returns a dict with keys: run_uid (str, a 32-character "
    "uuid4 hex used as the agent-facing handle for every other tracker tool) "
    "and id (int, the integer primary key, surfaced for joins and rarely "
    "needed by the agent directly)."
)


LIST_RUNS_DESCRIPTION = (
    "Lists run rows, optionally narrowed by exact-match filters. Call this "
    "to discover prior runs before deciding whether to start a new one or to "
    "feed compare_runs / best_run. The filters argument is a dict whose keys "
    "may include any subset of: recipe, model_base, dataset, status. All "
    "supplied filters are AND-ed together; unknown keys are ignored. Pass "
    "None or an empty dict to return every row. An empty database returns "
    "an empty list, never an error. Returns a list of dicts, each with keys: "
    "run_uid (str), id (int), recipe (str), model_base (str), dataset (str), "
    "hyperparameters (dict, the original JSON-round-tripped value), status "
    "(str, one of 'running', 'completed', 'failed'), notes (str, empty when "
    "no notes were supplied to start_run), and created_at (str, ISO 8601 "
    "UTC timestamp)."
)


COMPLETE_RUN_DESCRIPTION = (
    "Marks a run as terminal by updating its status. Call this once a "
    "training attempt has finished, regardless of outcome. The status "
    "argument must be 'completed' (default, for successful runs) or "
    "'failed' (for runs that crashed or produced unusable artifacts); any "
    "other value raises a ValueError so the agent can correct the call. "
    "Raises RunNotFoundError if the run_uid does not match a row, which is "
    "how the agent should detect a typo or a stale handle. Returns the "
    "updated row as a dict with the same shape that list_runs returns."
)


def _row_to_dict(row: Run) -> dict[str, Any]:
    """Return the JSON-friendly dict representation of a :class:`Run` row.

    Args:
        row: A persisted :class:`Run` instance loaded from the database. The
            ``id`` field must be populated (i.e. the row has been flushed),
            otherwise the returned dict will contain ``None`` for ``id``.

    Returns:
        A dict with the contract documented on
        :data:`LIST_RUNS_DESCRIPTION`. ``created_at`` is an ISO 8601 string,
        ``notes`` is the empty string when the column is NULL, and
        ``hyperparameters`` is the JSON-round-tripped dict.
    """
    return {
        "run_uid": row.run_uid,
        "id": row.id,
        "recipe": row.recipe,
        "model_base": row.model_base,
        "dataset": row.dataset,
        "hyperparameters": row.hyperparameters,
        "status": row.status,
        "notes": row.notes if row.notes is not None else "",
        "created_at": row.created_at.isoformat(),
    }


def start_run(
    recipe: str,
    model_base: str,
    dataset: str,
    hyperparameters: dict[str, Any],
    notes: str = "",
) -> dict[str, Any]:
    """Insert a new run row with status ``"running"`` and return its handle.

    Args:
        recipe: Human-readable recipe name (e.g. ``"lora-rank-8"``).
        model_base: Base model identifier (e.g. ``"Qwen/Qwen3-VL-2B-Instruct"``).
        dataset: Training dataset identifier (e.g. ``"oxford-pets"``).
        hyperparameters: Arbitrary nested JSON-serialisable dict; round-trips
            unchanged through the SQLite JSON column.
        notes: Optional free-form prose. Defaults to the empty string.

    Returns:
        A dict with two keys: ``run_uid`` (32-character uuid4 hex) and ``id``
        (positive integer primary key).
    """
    engine = current_engine()
    row = Run(
        recipe=recipe,
        model_base=model_base,
        dataset=dataset,
        hyperparameters=hyperparameters,
        status=_RUN_STATUS_RUNNING,
        notes=notes,
    )
    with get_session(engine) as session:
        session.add(row)
        session.commit()
        session.refresh(row)
        if row.id is None:  # pragma: no cover -- post-flush invariant
            msg = "Run.id was None after commit/refresh"
            raise RuntimeError(msg)
        return {"run_uid": row.run_uid, "id": row.id}


def list_runs(filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return run rows, optionally narrowed by exact-match filters.

    Args:
        filters: Optional dict of column-name to expected value. Recognised
            keys: ``recipe``, ``model_base``, ``dataset``, ``status``. Unknown
            keys are ignored silently. ``None`` and ``{}`` both return every
            row.

    Returns:
        A list of dicts in insertion order. Each dict has the shape
        documented on :data:`LIST_RUNS_DESCRIPTION`.
    """
    engine = current_engine()
    statement = select(Run)
    if filters:
        for key, value in filters.items():
            if key not in _FILTERABLE_FIELDS:
                continue
            statement = statement.where(getattr(Run, key) == value)
    statement = statement.order_by(col(Run.id).asc())
    with get_session(engine) as session:
        rows = session.scalars(statement).all()
        return [_row_to_dict(row) for row in rows]


def complete_run(run_uid: str, status: str = "completed") -> dict[str, Any]:
    """Update a run's status to a terminal value and return the new row.

    Args:
        run_uid: The 32-character uuid4 hex returned by :func:`start_run`.
        status: Terminal status to record. Must be ``"completed"`` (default)
            or ``"failed"``.

    Returns:
        The updated row dict, shape as documented on
        :data:`LIST_RUNS_DESCRIPTION`.

    Raises:
        ValueError: If ``status`` is not one of ``{"completed", "failed"}``.
        RunNotFoundError: If no row matches ``run_uid``.
    """
    if status not in _TERMINAL_STATUSES:
        raise ValueError(
            f"status must be one of {sorted(_TERMINAL_STATUSES)!r}, got {status!r}",
        )
    engine = current_engine()
    statement = select(Run).where(Run.run_uid == run_uid)
    with get_session(engine) as session:
        row = session.scalars(statement).one_or_none()
        if row is None:
            raise RunNotFoundError(f"no run with run_uid={run_uid!r}")
        row.status = status
        session.add(row)
        session.commit()
        session.refresh(row)
        return _row_to_dict(row)


__all__ = [
    "COMPLETE_RUN_DESCRIPTION",
    "LIST_RUNS_DESCRIPTION",
    "START_RUN_DESCRIPTION",
    "complete_run",
    "list_runs",
    "start_run",
]
