"""arxiv-deep MCP server package.

Exposes typed exceptions and the package version. The MCP server itself lives
in :mod:`arxiv_deep.server`. This module deliberately performs no I/O or
logging at import time so it remains safe to import from inside MCP tool
handlers and from test fixtures.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from arxiv_deep.exceptions import (
    ArxivDeepError,
    ArxivFetchError,
    CodeFinderError,
    FigureExtractionError,
    InvalidArxivIdError,
)

try:
    __version__: str = version("ml-intern-mcp-toolkit")
except PackageNotFoundError:  # pragma: no cover - editable install edge case
    __version__ = "0.0.0"


__all__ = [
    "ArxivDeepError",
    "ArxivFetchError",
    "CodeFinderError",
    "FigureExtractionError",
    "InvalidArxivIdError",
    "__version__",
]
