"""Cross-run comparison tools for the experiment tracker.

Two tools live here:

* :func:`compare_runs` renders a Markdown table comparing the final value
  of one metric across an explicit list of runs. The Markdown payload is
  designed for the calling agent to paste into its own reasoning trace.
* :func:`best_run` returns the single run dict with the best final value
  of a metric, optionally narrowed by the same filter set that
  :func:`experiment_tracker.tools.runs.list_runs` accepts.

"Final value" of a metric for a run is the :class:`~experiment_tracker.models.Metric`
row with the highest ``step`` for that ``(run_id, name)`` pair. Both tools
compute it via a SQL subquery rather than loading metrics into Python so
they stay correct as the metric history grows.
"""

from __future__ import annotations

import json
from typing import Any, Literal, cast

from sqlalchemy import func
from sqlmodel import col, select

from experiment_tracker.db import current_engine, get_session
from experiment_tracker.exceptions import RunNotFoundError
from experiment_tracker.models import Metric, Run

_RUN_FILTER_FIELDS: frozenset[str] = frozenset({"recipe", "model_base", "dataset", "status"})


COMPARE_RUNS_DESCRIPTION = (
    "Renders a Markdown table comparing the final value of a single metric "
    "across an explicit list of runs. Call this when the agent needs to "
    "reason about how several runs stack up on one metric (e.g. final "
    "accuracy or final loss). Inputs: run_uids (list of run_uid strings as "
    "returned by start_run / list_runs) and metric_name (e.g. 'accuracy', "
    "'loss'). Returns a Markdown table with columns run_uid (truncated to "
    "the first 8 characters), recipe, hyperparameters (compact JSON), and "
    "the final value of metric_name. The 'final value' is the Metric row "
    "with the highest step for that (run, metric_name) pair. Rows are "
    "sorted by metric value, highest first; runs with no recorded value for "
    "the metric render as 'n/a' and sort to the bottom. Raises "
    "RunNotFoundError if any run_uid does not exist."
)


BEST_RUN_DESCRIPTION = (
    "Returns the run with the best final value of a metric, optionally "
    "filtered. Use this when the agent needs to pick a winner (e.g. for "
    "model upload). Inputs: metric_name (e.g. 'accuracy'), direction "
    "('max' for higher-is-better, 'min' for lower-is-better; default "
    "'max'), and an optional filters dict with the same keys list_runs "
    "accepts (recipe, model_base, dataset, status), AND-combined. The "
    "'best' run is the one whose final metric value (the Metric row with "
    "the highest step for that (run, metric_name) pair) is the maximum or "
    "minimum across the candidate set. Returns the same dict shape as "
    "list_runs entries (run_uid, recipe, model_base, dataset, "
    "hyperparameters, status, created_at, notes), or None if the database "
    "is empty, no run matches the filters, or no candidate run has a "
    "value for metric_name. Does not raise on missing data; the agent "
    "should check for None."
)


def _final_metric_subquery(metric_name: str) -> Any:
    """Build a subquery returning the final value of ``metric_name`` per run.

    The subquery joins the metric table to itself on ``(run_id, name,
    MAX(step))`` so that each row gives one (``run_id``, ``value``) pair
    representing the metric reading at the highest step for that run.
    """
    max_step = (
        select(
            col(Metric.run_id).label("run_id"),
            func.max(col(Metric.step)).label("max_step"),
        )
        .where(col(Metric.name) == metric_name)
        .group_by(col(Metric.run_id))
        .subquery()
    )
    return (
        select(col(Metric.run_id), col(Metric.value))
        .join(
            max_step,
            (col(Metric.run_id) == max_step.c.run_id) & (col(Metric.step) == max_step.c.max_step),
        )
        .where(col(Metric.name) == metric_name)
        .subquery()
    )


def _run_to_dict(run: Run) -> dict[str, Any]:
    """Project a :class:`Run` ORM row into the plain dict shape tools expose."""
    return {
        "run_uid": run.run_uid,
        "recipe": run.recipe,
        "model_base": run.model_base,
        "dataset": run.dataset,
        "hyperparameters": run.hyperparameters,
        "status": run.status,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "notes": run.notes,
    }


def compare_runs(run_uids: list[str], metric_name: str) -> str:
    """Render a Markdown comparison table for the given runs and metric.

    Args:
        run_uids: The runs to compare, in any order. Every uid must exist
            in the runs table.
        metric_name: Name of the metric to compare on (e.g. ``"accuracy"``
            or ``"loss"``).

    Returns:
        A Markdown table string. Columns: run_uid (first 8 chars), recipe,
        hyperparameters (compact JSON), the metric. Rows are sorted by
        metric value descending; runs with no recorded metric value
        render as ``n/a`` and sort last.

    Raises:
        RunNotFoundError: If any uid in ``run_uids`` does not exist.
    """
    engine = current_engine()
    with get_session(engine) as session:
        runs = list(
            session.scalars(
                select(Run).where(col(Run.run_uid).in_(run_uids)),
            ).all(),
        )
        found_uids = {run.run_uid for run in runs}
        missing = [uid for uid in run_uids if uid not in found_uids]
        if missing:
            raise RunNotFoundError(
                f"Unknown run_uid(s): {', '.join(missing)}",
            )

        final_sq = _final_metric_subquery(metric_name)
        rows = session.execute(
            select(final_sq.c.run_id, final_sq.c.value),
        ).all()
        finals: dict[int, float] = {row[0]: row[1] for row in rows}

    # Preserve the caller-supplied uid set; sort by metric value descending,
    # with runs missing the metric pinned to the bottom.
    runs_by_uid = {run.run_uid: run for run in runs}
    ordered = sorted(
        run_uids,
        key=lambda uid: (
            runs_by_uid[uid].id not in finals,
            -(finals.get(cast(int, runs_by_uid[uid].id), 0.0)),
        ),
    )

    header = f"| run_uid  | recipe | hyperparameters | {metric_name} |"
    separator = "| -------- | ------ | --------------- | ----------- |"
    lines = [header, separator]
    for uid in ordered:
        run = runs_by_uid[uid]
        run_id = cast(int, run.id)
        value_cell = f"{finals[run_id]}" if run_id in finals else "n/a"
        hp_cell = json.dumps(run.hyperparameters, separators=(",", ":"))
        lines.append(
            f"| {uid[:8]} | {run.recipe} | {hp_cell} | {value_cell} |",
        )
    return "\n".join(lines)


def best_run(
    metric_name: str,
    direction: Literal["max", "min"] = "max",
    filters: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return the run dict with the best final value of ``metric_name``.

    Args:
        metric_name: Metric to score on (e.g. ``"accuracy"``, ``"loss"``).
        direction: ``"max"`` selects the highest final value, ``"min"`` the
            lowest. Defaults to ``"max"``.
        filters: Optional ``{field: value}`` dict narrowing the candidate
            set. Supported fields: ``recipe``, ``model_base``, ``dataset``,
            ``status``. Multiple filters are AND-combined. Unknown fields
            are ignored.

    Returns:
        A dict with the same shape as a ``list_runs`` entry, or ``None``
        when the database is empty, no run matches the filters, or no
        candidate run has any recorded value for ``metric_name``. The
        function never raises on missing data; the caller checks for
        ``None``.
    """
    engine = current_engine()
    with get_session(engine) as session:
        statement = select(Run)
        for field, value in (filters or {}).items():
            if field not in _RUN_FILTER_FIELDS:
                continue
            statement = statement.where(getattr(Run, field) == value)
        candidates = list(session.scalars(statement).all())
        if not candidates:
            return None

        final_sq = _final_metric_subquery(metric_name)
        candidate_ids = [cast(int, run.id) for run in candidates]
        rows = session.execute(
            select(final_sq.c.run_id, final_sq.c.value).where(
                final_sq.c.run_id.in_(candidate_ids),
            ),
        ).all()
        if not rows:
            return None

        if direction == "max":
            winner_id, _ = max(rows, key=lambda row: row[1])
        else:
            winner_id, _ = min(rows, key=lambda row: row[1])

        winner = next(run for run in candidates if run.id == winner_id)
        return _run_to_dict(winner)


__all__ = [
    "BEST_RUN_DESCRIPTION",
    "COMPARE_RUNS_DESCRIPTION",
    "best_run",
    "compare_runs",
]
