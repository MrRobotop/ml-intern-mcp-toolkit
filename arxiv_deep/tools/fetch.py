"""``fetch_paper`` MCP tool implementation.

Downloads the PDF for an arxiv paper, extracts its full text via PyMuPDF, and
returns a structured dict combining metadata from the arxiv API with the
extracted body text. PDFs are cached on disk under
``$ARXIV_DEEP_CACHE_DIR/pdfs/<arxiv_id>.pdf`` (defaulting to
``~/.cache/arxiv-deep/pdfs/``) so repeat calls within or across sessions are
cheap.

The module exposes two private hooks, :func:`_download_pdf` and
:func:`_fetch_metadata`, that the test suite monkey-patches to keep tests
hermetic. The public surface is :func:`fetch_paper` plus
:data:`FETCH_PAPER_DESCRIPTION`, which is the agent-facing tool description
registered on the MCP server.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import arxiv
import pymupdf

from arxiv_deep.exceptions import ArxivFetchError, InvalidArxivIdError

logger = logging.getLogger(__name__)

_CANONICAL_ID_RE = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")
_ARXIV_PREFIX_RE = re.compile(r"^arxiv:", re.IGNORECASE)
_ABS_OR_PDF_URL_RE = re.compile(
    r"^https?://arxiv\.org/(?:abs|pdf)/(?P<id>[^/?#]+?)(?:\.pdf)?/?$",
    re.IGNORECASE,
)


def _cache_root() -> Path:
    """Return the on-disk cache root for arxiv-deep.

    Honours the ``ARXIV_DEEP_CACHE_DIR`` environment variable (used by tests
    via the ``tmp_cache_dir`` fixture); otherwise falls back to
    ``~/.cache/arxiv-deep/``.
    """
    override = os.environ.get("ARXIV_DEEP_CACHE_DIR")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "arxiv-deep"


def _pdf_cache_path(arxiv_id: str) -> Path:
    """Return the cache path for the PDF of ``arxiv_id``."""
    return _cache_root() / "pdfs" / f"{arxiv_id}.pdf"


def _normalise_id(raw: str) -> str:
    """Normalise a user-supplied arxiv reference to a bare arxiv id.

    Accepts the bare id (``2305.14314``), the prefixed form
    (``arXiv:2305.14314``), or an abs/pdf URL
    (``https://arxiv.org/abs/2305.14314``). Versioned ids such as
    ``2305.14314v2`` are preserved.

    Raises:
        InvalidArxivIdError: if the input cannot be reduced to a valid id.
    """
    candidate = raw.strip()
    candidate = _ARXIV_PREFIX_RE.sub("", candidate)
    url_match = _ABS_OR_PDF_URL_RE.match(candidate)
    if url_match:
        candidate = url_match.group("id")
    if not _CANONICAL_ID_RE.match(candidate):
        raise InvalidArxivIdError(f"Not a valid arxiv id: {raw!r}")
    return candidate


def _arxiv_result(arxiv_id: str) -> arxiv.Result:
    """Fetch the single arxiv ``Result`` matching ``arxiv_id``.

    Centralised so both the metadata fetcher and the PDF downloader hit the
    upstream once each rather than twice.
    """
    try:
        client = arxiv.Client()
        return next(client.results(arxiv.Search(id_list=[arxiv_id])))
    except StopIteration as exc:
        raise ArxivFetchError(f"No arxiv result for id {arxiv_id!r}") from exc
    except Exception as exc:  # network / parser failures from the arxiv lib
        raise ArxivFetchError(f"arxiv lookup failed for {arxiv_id!r}: {exc}") from exc


def _download_pdf(arxiv_id: str, dest: Path) -> None:
    """Download the PDF for ``arxiv_id`` to ``dest``.

    Hook target: tests monkey-patch this to copy a fixture PDF rather than
    hitting the network.
    """
    result = _arxiv_result(arxiv_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        result.download_pdf(dirpath=str(dest.parent), filename=dest.name)
    except Exception as exc:
        raise ArxivFetchError(f"PDF download failed for {arxiv_id!r}: {exc}") from exc


def _fetch_metadata(arxiv_id: str) -> dict[str, Any]:
    """Return the structured metadata fields for ``arxiv_id``.

    Hook target: tests monkey-patch this with a canned payload.
    """
    result = _arxiv_result(arxiv_id)
    return {
        "title": result.title,
        "authors": [author.name for author in result.authors],
        "abstract": result.summary,
        "published_date": result.published.date().isoformat(),
        "categories": list(result.categories),
    }


def _extract_full_text(pdf_path: Path) -> str:
    """Extract the concatenated full text of ``pdf_path`` via PyMuPDF.

    Pages are joined with a single newline; the structure preserves enough
    layout for downstream regex-based extractors (used by
    ``implementation_brief``) without imposing any reflow heuristic.
    """
    try:
        doc = pymupdf.open(str(pdf_path))
    except Exception as exc:
        raise ArxivFetchError(f"Could not open PDF at {pdf_path}: {exc}") from exc
    try:
        pages = [page.get_text() for page in doc]
    finally:
        doc.close()
    return "\n".join(pages)


FETCH_PAPER_DESCRIPTION = (
    "Fetches the title, authors, abstract, full body text, publication date, "
    "and arxiv categories for a paper given its arxiv ID. Accepts the bare ID "
    "(e.g. '2305.14314'), the 'arXiv:<id>' form, or a full arxiv abs/pdf URL. "
    "Always call this before any other arxiv-deep tool when working with a "
    "new paper. Returns a dict with keys: title, authors, abstract, full_text, "
    "published_date, categories. The PDF is cached on disk so repeat calls "
    "within or across sessions are cheap."
)


def fetch_paper(arxiv_id: str) -> dict[str, Any]:
    """Fetch metadata and full body text for an arxiv paper.

    Args:
        arxiv_id: A bare arxiv id, an ``arXiv:<id>`` reference, or an
            ``https://arxiv.org/abs/<id>`` URL. Versioned ids (``...v2``) are
            preserved.

    Returns:
        A dict with keys ``title`` (str), ``authors`` (list[str]),
        ``abstract`` (str), ``full_text`` (str), ``published_date`` (str,
        ISO 8601 date), and ``categories`` (list[str]).

    Raises:
        InvalidArxivIdError: if ``arxiv_id`` cannot be parsed.
        ArxivFetchError: if the upstream lookup or PDF download fails.
    """
    canonical = _normalise_id(arxiv_id)
    pdf_path = _pdf_cache_path(canonical)
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        logger.info("Downloading PDF for arxiv id %s", canonical)
        _download_pdf(canonical, pdf_path)
    else:
        logger.debug("PDF cache hit for arxiv id %s at %s", canonical, pdf_path)
    metadata = _fetch_metadata(canonical)
    full_text = _extract_full_text(pdf_path)
    return {**metadata, "full_text": full_text}
