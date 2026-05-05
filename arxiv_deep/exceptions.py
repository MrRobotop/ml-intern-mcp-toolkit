"""Typed exceptions raised by the arxiv-deep MCP server.

All exceptions inherit from :class:`ArxivDeepError` so callers can catch the
whole family with a single ``except`` clause. Each subclass corresponds to a
distinct failure mode that the calling agent should be able to react to:

* :class:`InvalidArxivIdError` for malformed arxiv identifiers (caller bug).
* :class:`ArxivFetchError` for network or upstream arxiv failures (transient).
* :class:`FigureExtractionError` for PDF parsing failures (corrupt input).
* :class:`CodeFinderError` for failures while resolving reference code links.

FastMCP wraps any unhandled tool exception in ``ToolError`` and surfaces the
chained message to the client, so raising these typed errors keeps the agent's
view actionable.
"""

from __future__ import annotations


class ArxivDeepError(Exception):
    """Base class for every error raised by the arxiv-deep package."""


class InvalidArxivIdError(ArxivDeepError):
    """Raised when an arxiv identifier cannot be parsed or normalised."""


class ArxivFetchError(ArxivDeepError):
    """Raised when fetching paper metadata or the PDF fails."""


class FigureExtractionError(ArxivDeepError):
    """Raised when figure extraction from a paper PDF fails."""


class CodeFinderError(ArxivDeepError):
    """Raised when discovering or validating reference code links fails."""


__all__ = [
    "ArxivDeepError",
    "ArxivFetchError",
    "CodeFinderError",
    "FigureExtractionError",
    "InvalidArxivIdError",
]
