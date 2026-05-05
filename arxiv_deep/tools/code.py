"""``find_reference_code`` MCP tool implementation.

Scrapes ``github.com`` URLs out of an arxiv paper's full body text, extracts a
short context window around each occurrence, and validates each unique URL by
issuing an asynchronous HTTP ``HEAD`` request. Validation failures (rate
limits, timeouts, DNS errors) are downgraded to ``validated=False`` and
surfaced through warning logs rather than raising, so the calling agent
always receives a complete list of candidate links.

The module exposes :func:`find_reference_code` and the agent-facing
:data:`FIND_REFERENCE_CODE_DESCRIPTION` constant. It calls
:func:`arxiv_deep.tools.fetch.fetch_paper` internally to obtain the full text;
that call carries the same caching guarantees as ``fetch_paper`` itself.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx

from arxiv_deep.tools.fetch import fetch_paper

logger = logging.getLogger(__name__)

_GITHUB_URL_RE = re.compile(r"https?://github\.com/[\w.-]+/[\w.-]+")
_CONTEXT_WINDOW = 200
_HEAD_TIMEOUT_SECONDS = 5.0


FIND_REFERENCE_CODE_DESCRIPTION = (
    "Scans the full text of an arxiv paper for github.com URLs and reports "
    "each unique URL together with surrounding context and a reachability "
    "flag. Call this after fetch_paper to discover the official code "
    "implementations the authors link to (the agent should prefer these over "
    "third-party reimplementations). Returns a list of dicts, each with keys: "
    "url (str, the canonical GitHub URL), context (str, roughly 200 "
    "characters of paper text surrounding the URL), and validated (bool, True "
    "iff an HTTP HEAD against the URL returned a 2xx response within 5 "
    "seconds). URLs are de-duplicated case-sensitively and preserved in the "
    "order they first appear in the paper. The tool never raises for "
    "individual URL failures; it sets validated=False and logs a warning "
    "instead, so the agent can still surface unreachable links to the user."
)


def _extract_url_occurrences(full_text: str) -> list[tuple[str, str]]:
    """Return ``(url, context)`` pairs in order of first occurrence.

    Args:
        full_text: The body text of the paper as returned by
            :func:`arxiv_deep.tools.fetch.fetch_paper`.

    Returns:
        A list of ``(url, context)`` pairs. Each ``context`` is a slice of
        ``full_text`` of up to roughly ``2 * _CONTEXT_WINDOW`` characters
        centred on the URL match. Duplicate URLs are removed, keeping the
        context of the first occurrence.
    """
    seen: dict[str, str] = {}
    for match in _GITHUB_URL_RE.finditer(full_text):
        url = match.group(0)
        if url in seen:
            continue
        start = max(0, match.start() - _CONTEXT_WINDOW)
        end = min(len(full_text), match.end() + _CONTEXT_WINDOW)
        seen[url] = full_text[start:end]
    return list(seen.items())


def _has_rate_limit_header(response: httpx.Response) -> bool:
    """Return True if any ``X-RateLimit-*`` header is present on ``response``."""
    return any(name.lower().startswith("x-ratelimit-") for name in response.headers)


async def _validate_url(client: httpx.AsyncClient, url: str) -> bool:
    """Issue a ``HEAD`` against ``url`` and return whether it is reachable.

    Args:
        client: A shared :class:`httpx.AsyncClient` used to pool connections
            across all URLs validated in a single call.
        url: The GitHub URL to probe.

    Returns:
        True if the response status code is in the 2xx range. False on any
        non-2xx response, on rate-limited 403s (identified by the presence of
        an ``X-RateLimit-*`` header), or on any transport-level exception.
        This function never raises.
    """
    try:
        response = await client.head(url, follow_redirects=True)
    except httpx.HTTPError as exc:
        logger.warning("HEAD request failed for %s: %s", url, exc)
        return False

    if response.status_code == 403 and _has_rate_limit_header(response):
        logger.warning("GitHub rate limit hit while validating %s; marking unvalidated", url)
        return False

    return 200 <= response.status_code < 300


async def find_reference_code(arxiv_id: str) -> list[dict[str, Any]]:
    """Find and validate the GitHub URLs cited inside an arxiv paper.

    Fetches the paper via :func:`arxiv_deep.tools.fetch.fetch_paper`, scrapes
    every ``github.com`` URL out of its body text, and probes each unique URL
    with an asynchronous ``HEAD`` request to flag reachable links. URL
    validations run concurrently against a single
    :class:`httpx.AsyncClient` so connection pooling stays effective.

    Args:
        arxiv_id: A bare arxiv id, an ``arXiv:<id>`` reference, or an
            ``https://arxiv.org/abs/<id>`` URL. Forwarded to ``fetch_paper``
            unchanged.

    Returns:
        A list of dicts, one per unique URL, in the order URLs first appear
        in the paper. Each dict has keys ``url`` (str), ``context`` (str,
        up to roughly 400 characters of surrounding paper text), and
        ``validated`` (bool).

    Raises:
        InvalidArxivIdError: propagated from ``fetch_paper`` if ``arxiv_id``
            cannot be parsed.
        ArxivFetchError: propagated from ``fetch_paper`` on upstream failure.
    """
    paper = fetch_paper(arxiv_id)
    full_text: str = paper["full_text"]

    occurrences = _extract_url_occurrences(full_text)
    if not occurrences:
        return []

    async with httpx.AsyncClient(timeout=_HEAD_TIMEOUT_SECONDS) as client:
        validations = await asyncio.gather(*(_validate_url(client, url) for url, _ in occurrences))

    return [
        {"url": url, "context": context, "validated": validated}
        for (url, context), validated in zip(occurrences, validations, strict=True)
    ]
