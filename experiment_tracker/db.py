"""Database engine, schema bootstrap, and session helpers.

Centralises SQLite connection construction so every entry point (server,
tools, tests) gets the same configuration: foreign-key enforcement enabled,
``check_same_thread`` relaxed for FastMCP's anyio threadpool, and the
on-disk path overridable via the ``EXPERIMENT_TRACKER_DB_PATH`` environment
variable.

Importing this module is side-effect free; an engine is only created when
:func:`get_engine` is called.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

import experiment_tracker.models  # noqa: F401 -- registers tables on metadata


def default_db_path() -> Path:
    """Return the on-disk path for the tracker database.

    Honours the ``EXPERIMENT_TRACKER_DB_PATH`` environment variable so tests
    and sandboxed environments can redirect storage; otherwise falls back to
    ``~/.cache/experiment-tracker/runs.db``.
    """
    override = os.environ.get("EXPERIMENT_TRACKER_DB_PATH")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "experiment-tracker" / "runs.db"


def get_engine(db_path: Path | None = None) -> Engine:
    """Build a SQLite engine with experiment-tracker defaults.

    Args:
        db_path: Where to store the SQLite file. ``None`` resolves to
            :func:`default_db_path`. Parent directories are created on
            demand.

    Returns:
        A configured :class:`Engine`. Foreign-key enforcement is wired in
        via a ``connect`` event handler so every connection pulled from the
        pool issues ``PRAGMA foreign_keys = ON``.
    """
    path = db_path or default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    _enable_sqlite_foreign_keys(engine)
    return engine


def init_db(engine: Engine) -> None:
    """Create all tracker tables on ``engine`` if they do not yet exist."""
    SQLModel.metadata.create_all(engine)


@lru_cache(maxsize=8)
def _engine_for_path(path: str) -> Engine:
    """Return a cached engine for ``path``, creating it on first call.

    The cache is keyed on the resolved string path so different DB paths get
    independent engines. Tests get fresh engines per test because each test
    points ``EXPERIMENT_TRACKER_DB_PATH`` at a unique ``tmp_path``.
    """
    engine = get_engine(Path(path))
    init_db(engine)
    return engine


def current_engine() -> Engine:
    """Return the engine bound to the currently-configured database path.

    Resolves the path via :func:`default_db_path` on each call so changes to
    the ``EXPERIMENT_TRACKER_DB_PATH`` environment variable take effect
    without restarting the process. The engine itself is cached per resolved
    path, so repeat calls to this function are cheap.
    """
    return _engine_for_path(str(default_db_path()))


@contextmanager
def get_session(engine: Engine) -> Iterator[Session]:
    """Yield a :class:`Session` bound to ``engine`` and close it on exit.

    Tools that mutate state should call ``session.commit()`` explicitly.
    The context manager only guarantees the session is closed and any
    in-flight transaction is rolled back if not committed.
    """
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """Attach a ``connect`` listener that turns on FK enforcement.

    SQLite ships with foreign-key constraints disabled by default; without
    this hook the schema is a suggestion and orphaned ``Metric`` /
    ``Artifact`` rows would silently land. Idempotent: calling twice on the
    same engine just registers a second listener that does the same thing.
    """

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: Any, _: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()


__all__ = [
    "current_engine",
    "default_db_path",
    "get_engine",
    "get_session",
    "init_db",
]
