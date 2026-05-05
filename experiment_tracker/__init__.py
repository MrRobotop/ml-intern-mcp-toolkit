"""experiment-tracker MCP server package.

Provides typed exceptions, the ORM models, and the FastMCP server entry
point. Public re-exports below let consumers ``from experiment_tracker
import RunNotFoundError`` without reaching into submodules. The exceptions
themselves land in Prompt 2.3 (server skeleton).
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__: str = version("ml-intern-mcp-toolkit")
except PackageNotFoundError:  # pragma: no cover - editable install edge case
    __version__ = "0.0.0"


__all__ = ["__version__"]
