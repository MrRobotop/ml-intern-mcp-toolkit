"""``log_artifact`` MCP tool implementation.

Records a single ``(kind, uri)`` pair in the ``artifact`` table for an
existing run. The function resolves the agent-facing ``run_uid`` to the
internal integer ``run_id`` foreign key, raises :class:`RunNotFoundError`
when no run matches, and returns the new ``artifact_id`` so the caller can
correlate writes with downstream reads.

A run may have any number of artifacts of any kind. The schema imposes no
uniqueness constraint, so repeated calls with identical arguments append
new rows.
"""

from __future__ import annotations

from typing import Any

from sqlmodel import select

from experiment_tracker.db import current_engine, get_session
from experiment_tracker.exceptions import RunNotFoundError
from experiment_tracker.models import Artifact, Run

LOG_ARTIFACT_DESCRIPTION = (
    "Records one artifact (model weights, checkpoint, or log file) "
    "produced by an existing run, identified by its run_uid (the opaque "
    "string handle returned by start_run). Call this whenever a "
    "training run materialises an output the agent might want to "
    "reference later, for example after pushing a fine-tuned model to "
    "the Hub or saving an intermediate checkpoint. Inputs: run_uid "
    "(str), kind (str, free-form label such as 'model', 'checkpoint', "
    "or 'log'), uri (str, where the artifact lives, e.g. an hf:// or "
    "file:// URL). Returns a dict with keys logged (bool, always True on "
    "success) and artifact_id (int, the database row id of the newly "
    "inserted artifact). Raises RunNotFoundError if run_uid does not "
    "match any existing run; the agent should call start_run first or "
    "verify the uid via list_runs. Multiple artifacts per run are "
    "allowed; the same (kind, uri) tuple may be logged repeatedly and "
    "each call appends a new row."
)


def log_artifact(run_uid: str, kind: str, uri: str) -> dict[str, Any]:
    """Persist an artifact reference for an existing run.

    Args:
        run_uid: The opaque string handle for the parent run, as returned
            by ``start_run`` and surfaced by ``list_runs``.
        kind: Free-form label categorising the artifact, for example
            ``"model"``, ``"checkpoint"``, or ``"log"``.
        uri: The location of the artifact (Hugging Face Hub URL,
            ``file://`` path, ``s3://`` URI, etc.).

    Returns:
        A dict with two keys: ``logged`` (always ``True`` on success) and
        ``artifact_id`` (the positive integer primary key of the newly
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

        artifact = Artifact(run_id=run.id, kind=kind, uri=uri)
        session.add(artifact)
        session.commit()
        session.refresh(artifact)
        artifact_id = artifact.id

    assert artifact_id is not None  # primary key populated by the commit/refresh
    return {"logged": True, "artifact_id": artifact_id}


__all__ = ["LOG_ARTIFACT_DESCRIPTION", "log_artifact"]
