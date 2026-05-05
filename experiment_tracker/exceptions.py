"""Typed exceptions raised by the experiment-tracker MCP server.

All exceptions inherit from :class:`ExperimentTrackerError` so callers can
catch the family with one ``except`` clause. FastMCP wraps any unhandled
tool exception in ``ToolError`` and surfaces the chained message to the
client; raising these typed errors keeps the agent's view actionable.
"""

from __future__ import annotations


class ExperimentTrackerError(Exception):
    """Base class for every error raised by the experiment-tracker package."""


class RunNotFoundError(ExperimentTrackerError):
    """Raised when a ``run_uid`` does not match any row in the runs table."""


class MetricLoggingError(ExperimentTrackerError):
    """Raised when a metric write fails for a reason other than a missing run."""


__all__ = [
    "ExperimentTrackerError",
    "MetricLoggingError",
    "RunNotFoundError",
]
