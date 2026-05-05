"""Tests for ``experiment_tracker.tools.compare``.

Pins the contract for ``compare_runs`` and ``best_run``. Each test gets a
private SQLite file via the ``tracker_db`` fixture, mirroring the pattern
in :mod:`tests.experiment_tracker.test_runs`. Runs and metrics are seeded
directly through the ORM so this file does not depend on the
``runs.py`` / ``metrics.py`` tool modules being implemented yet.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from experiment_tracker.db import current_engine, get_session
from experiment_tracker.exceptions import RunNotFoundError
from experiment_tracker.models import Metric, Run
from experiment_tracker.tools.compare import best_run, compare_runs


@pytest.fixture
def tracker_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Per-test SQLite path; overrides EXPERIMENT_TRACKER_DB_PATH."""
    db_path = tmp_path / "runs.db"
    monkeypatch.setenv("EXPERIMENT_TRACKER_DB_PATH", str(db_path))
    return db_path


def _seed_run(
    recipe: str = "lora-r8",
    model_base: str = "m",
    dataset: str = "d",
    status: str = "completed",
    hyperparameters: dict[str, object] | None = None,
    metrics: list[tuple[int, str, float]] | None = None,
) -> str:
    """Insert a Run plus optional Metric rows directly via the ORM.

    Returns the new run's ``run_uid`` for use in assertions.
    """
    with get_session(current_engine()) as session:
        run = Run(
            recipe=recipe,
            model_base=model_base,
            dataset=dataset,
            hyperparameters=hyperparameters or {},
            status=status,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        for step, name, value in metrics or []:
            session.add(Metric(run_id=run.id, step=step, name=name, value=value))
        session.commit()
        return run.run_uid


def _table_rows(markdown: str) -> list[str]:
    """Return the non-blank lines of a Markdown table."""
    return [line for line in markdown.splitlines() if line.strip()]


def _data_rows(markdown: str) -> list[str]:
    """Return body rows of a Markdown table (header + separator stripped)."""
    rows = _table_rows(markdown)
    # Header row plus separator row come first.
    return rows[2:]


def test_compare_runs_returns_header_and_one_row_per_uid(tracker_db: Path) -> None:
    uid_a = _seed_run(metrics=[(1, "accuracy", 0.7), (2, "accuracy", 0.91)])
    uid_b = _seed_run(metrics=[(1, "accuracy", 0.55), (2, "accuracy", 0.6)])

    table = compare_runs([uid_a, uid_b], "accuracy")

    rows = _table_rows(table)
    # Header + separator + 2 data rows.
    assert len(rows) == 4
    assert "run_uid" in rows[0]
    assert "accuracy" in rows[0]


def test_compare_runs_orders_descending_by_metric_value(tracker_db: Path) -> None:
    uid_low = _seed_run(metrics=[(1, "accuracy", 0.10)])
    uid_high = _seed_run(metrics=[(1, "accuracy", 0.95)])
    uid_mid = _seed_run(metrics=[(1, "accuracy", 0.50)])

    table = compare_runs([uid_low, uid_high, uid_mid], "accuracy")
    body = _data_rows(table)

    # Each row begins with the truncated uid; check ordering by index of
    # the truncated uid in the rendered string.
    positions = [
        (body.index(next(r for r in body if uid[:8] in r)), uid)
        for uid in (uid_high, uid_mid, uid_low)
    ]
    assert [pos for pos, _ in positions] == [0, 1, 2]


def test_compare_runs_uses_final_step_value_per_run(tracker_db: Path) -> None:
    # The highest step is the "final" value, not the highest-value step.
    uid_a = _seed_run(metrics=[(1, "loss", 1.0), (5, "loss", 0.2)])
    uid_b = _seed_run(metrics=[(1, "loss", 0.5), (3, "loss", 0.3)])

    table = compare_runs([uid_a, uid_b], "loss")
    body = _data_rows(table)

    # Sorted descending: uid_b (0.3) first, then uid_a (0.2).
    assert uid_b[:8] in body[0]
    assert uid_a[:8] in body[1]


def test_compare_runs_raises_for_unknown_run_uid(tracker_db: Path) -> None:
    uid_real = _seed_run(metrics=[(1, "accuracy", 0.8)])

    with pytest.raises(RunNotFoundError):
        compare_runs([uid_real, "deadbeef" * 4], "accuracy")


def test_compare_runs_missing_metric_renders_na_and_sorts_last(
    tracker_db: Path,
) -> None:
    uid_with = _seed_run(metrics=[(1, "accuracy", 0.4)])
    uid_without = _seed_run(metrics=[(1, "loss", 0.9)])

    table = compare_runs([uid_with, uid_without], "accuracy")
    body = _data_rows(table)

    assert uid_with[:8] in body[0]
    assert uid_without[:8] in body[1]
    assert "n/a" in body[1]


def test_compare_runs_truncates_run_uid_to_eight_chars(tracker_db: Path) -> None:
    uid = _seed_run(metrics=[(1, "accuracy", 0.5)])

    table = compare_runs([uid], "accuracy")
    body = _data_rows(table)

    assert uid[:8] in body[0]
    # The full 32-char uid should not be rendered.
    assert uid not in body[0]


def test_compare_runs_renders_compact_hyperparameters_json(tracker_db: Path) -> None:
    uid = _seed_run(
        hyperparameters={"lr": 0.0002, "rank": 8},
        metrics=[(1, "accuracy", 0.7)],
    )

    table = compare_runs([uid], "accuracy")
    body = _data_rows(table)

    # Compact JSON has no spaces around separators.
    assert '"lr":0.0002' in body[0]
    assert '"rank":8' in body[0]
    assert ", " not in body[0].split("|")[3]  # the hyperparameters cell


def test_best_run_returns_highest_for_max_direction(tracker_db: Path) -> None:
    _seed_run(metrics=[(1, "accuracy", 0.5)])
    uid_best = _seed_run(metrics=[(1, "accuracy", 0.92)])
    _seed_run(metrics=[(1, "accuracy", 0.7)])

    out = best_run("accuracy", direction="max")

    assert out is not None
    assert out["run_uid"] == uid_best


def test_best_run_returns_lowest_for_min_direction(tracker_db: Path) -> None:
    _seed_run(metrics=[(1, "loss", 0.9)])
    uid_best = _seed_run(metrics=[(1, "loss", 0.05)])
    _seed_run(metrics=[(1, "loss", 0.4)])

    out = best_run("loss", direction="min")

    assert out is not None
    assert out["run_uid"] == uid_best


def test_best_run_uses_final_step_value(tracker_db: Path) -> None:
    # uid_a's final accuracy is 0.4; uid_b's final accuracy is 0.8.
    _seed_run(metrics=[(1, "accuracy", 0.99), (2, "accuracy", 0.4)])
    uid_b = _seed_run(metrics=[(1, "accuracy", 0.1), (2, "accuracy", 0.8)])

    out = best_run("accuracy", direction="max")

    assert out is not None
    assert out["run_uid"] == uid_b


def test_best_run_empty_database_returns_none(tracker_db: Path) -> None:
    assert best_run("accuracy") is None


def test_best_run_no_matching_filters_returns_none(tracker_db: Path) -> None:
    _seed_run(recipe="lora-r4", metrics=[(1, "accuracy", 0.8)])

    out = best_run("accuracy", filters={"recipe": "lora-r16"})

    assert out is None


def test_best_run_no_candidate_has_metric_returns_none(tracker_db: Path) -> None:
    _seed_run(metrics=[(1, "loss", 0.5)])
    _seed_run(metrics=[(1, "loss", 0.3)])

    assert best_run("accuracy") is None


def test_best_run_respects_filters(tracker_db: Path) -> None:
    _seed_run(recipe="lora-r4", metrics=[(1, "accuracy", 0.95)])
    uid_target = _seed_run(recipe="lora-r8", metrics=[(1, "accuracy", 0.7)])
    _seed_run(recipe="lora-r8", metrics=[(1, "accuracy", 0.6)])

    out = best_run("accuracy", filters={"recipe": "lora-r8"})

    assert out is not None
    assert out["run_uid"] == uid_target
    assert out["recipe"] == "lora-r8"


def test_best_run_returns_run_dict_shape(tracker_db: Path) -> None:
    uid = _seed_run(
        recipe="lora-r8",
        model_base="Qwen/Qwen3-VL-2B-Instruct",
        dataset="oxford-pets",
        hyperparameters={"lr": 0.0002},
        metrics=[(1, "accuracy", 0.5)],
    )

    out = best_run("accuracy")

    assert out is not None
    assert out["run_uid"] == uid
    assert out["recipe"] == "lora-r8"
    assert out["model_base"] == "Qwen/Qwen3-VL-2B-Instruct"
    assert out["dataset"] == "oxford-pets"
    assert out["hyperparameters"] == {"lr": 0.0002}
    assert out["status"] == "completed"
