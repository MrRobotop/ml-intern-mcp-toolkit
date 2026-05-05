"""experiment-tracker MCP server package.

Re-exports the typed exception family so callers can ``from
experiment_tracker import RunNotFoundError`` without reaching into
submodules. The MCP server itself lives in :mod:`experiment_tracker.server`
and the SQLModel tables in :mod:`experiment_tracker.models`.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from experiment_tracker.exceptions import (
    ExperimentTrackerError,
    MetricLoggingError,
    RunNotFoundError,
)

try:
    __version__: str = version("ml-intern-mcp-toolkit")
except PackageNotFoundError:  # pragma: no cover - editable install edge case
    __version__ = "0.0.0"


__all__ = [
    "ExperimentTrackerError",
    "MetricLoggingError",
    "RunNotFoundError",
    "__version__",
]
