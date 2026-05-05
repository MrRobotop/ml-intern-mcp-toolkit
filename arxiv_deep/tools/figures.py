"""``extract_figures`` MCP tool implementation.

Walks the cached PDF for an arxiv paper page-by-page and produces one PNG
per detected figure. Two extraction paths cooperate:

* PyMuPDF's :meth:`Page.get_images` finds raster figures embedded as
  XObjects and writes them via :class:`pymupdf.Pixmap`.
* Pages that contain a ``Figure N:`` caption line but do not surface a
  raster image (a common pattern for arxiv papers that ship line-art
  figures as vector PDF objects, including QLoRA's bar-chart figures)
  are rendered to PNG at 200 DPI as a fallback so vector-only figures
  are still surfaced to the agent.

Each detected figure is paired with the most plausible caption found on
the same page: the heuristic looks for a line beginning ``Figure N:`` or
``Figure N.`` and concatenates that line with the line immediately
following.

Cached PNGs land under
``$ARXIV_DEEP_CACHE_DIR/figures/<arxiv_id>/figure_<n>.png`` and are
reused across calls. The PDF itself comes through
:func:`arxiv_deep.tools.fetch._download_pdf` so this tool benefits from
the same hermetic test hooks as ``fetch_paper``.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pymupdf

from arxiv_deep.exceptions import FigureExtractionError
from arxiv_deep.tools.fetch import _cache_root, _download_pdf, _normalise_id, _pdf_cache_path

logger = logging.getLogger(__name__)

_FIGURE_CAPTION_RE = re.compile(r"^Figure\s+\d+[:.]")
_FALLBACK_RENDER_DPI = 200


def _figures_cache_dir(arxiv_id: str) -> Path:
    """Return the per-paper directory that holds extracted figure PNGs."""
    return _cache_root() / "figures" / arxiv_id


def _figure_image_path(arxiv_id: str, index: int) -> Path:
    """Return the cache path for the ``index``-th extracted figure (1-indexed)."""
    return _figures_cache_dir(arxiv_id) / f"figure_{index}.png"


def _ensure_pdf_cached(arxiv_id: str) -> Path:
    """Ensure the PDF for ``arxiv_id`` is on disk, downloading if needed.

    Mirrors the cache-then-download pattern from ``fetch_paper`` so a single
    on-disk PDF backs both tools.
    """
    pdf_path = _pdf_cache_path(arxiv_id)
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        logger.info("Downloading PDF for arxiv id %s", arxiv_id)
        _download_pdf(arxiv_id, pdf_path)
    return pdf_path


def _find_caption(page_text: str) -> str:
    """Return a figure caption pulled from ``page_text``.

    Scans for the first line matching ``^Figure\\s+\\d+[:.]`` and concatenates
    it with the following line (when present), separated by a single space.
    Returns an empty string when no candidate line is found.
    """
    lines = page_text.splitlines()
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if _FIGURE_CAPTION_RE.match(line):
            tail = lines[idx + 1].strip() if idx + 1 < len(lines) else ""
            if tail:
                return f"{line} {tail}"
            return line
    return ""


def _save_raster_image(doc: pymupdf.Document, xref: int, dest: Path) -> None:
    """Write the raster image identified by ``xref`` to ``dest`` as a PNG.

    CMYK and other multi-channel pixmaps are converted to RGB before
    writing because PNG cannot encode CMYK directly.
    """
    pixmap = pymupdf.Pixmap(doc, xref)
    if pixmap.n - pixmap.alpha >= 4:
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pixmap)
    pixmap.save(str(dest))


def _render_page(page: pymupdf.Page, dest: Path) -> None:
    """Rasterise an entire PDF page to PNG at :data:`_FALLBACK_RENDER_DPI`."""
    matrix = pymupdf.Matrix(_FALLBACK_RENDER_DPI / 72, _FALLBACK_RENDER_DPI / 72)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    pixmap.save(str(dest))


EXTRACT_FIGURES_DESCRIPTION = (
    "Extracts every figure from an arxiv paper PDF and returns one entry "
    "per figure. Accepts the bare arxiv ID (e.g. '2305.14314'), the "
    "'arXiv:<id>' form, or a full arxiv abs/pdf URL. Call this when the "
    "user wants to inspect, summarise, or reason about figures from a "
    "paper, after fetch_paper has confirmed the paper is available. "
    "Raster figures (embedded JPEG/PNG XObjects) are extracted directly; "
    "pages whose captions reference a figure but contain only vector "
    "graphics are rendered to PNG so vector figures are still surfaced. "
    "Returns a list of dicts, each with keys: page_number (int, "
    "1-indexed), caption (str, the 'Figure N:' line plus the following "
    "line; may be empty when no caption is detected), image_path (str, "
    "absolute path to a PNG on disk). Extracted PNGs are cached on disk "
    "so repeat calls for the same paper are cheap."
)


def extract_figures(arxiv_id: str) -> list[dict[str, Any]]:
    """Extract figures from an arxiv paper PDF and cache them as PNGs.

    Args:
        arxiv_id: A bare arxiv id, an ``arXiv:<id>`` reference, or an
            ``https://arxiv.org/abs/<id>`` URL. Versioned ids (``...v2``)
            are preserved.

    Returns:
        A list of dicts, one per extracted figure, in document order. Each
        dict has keys ``page_number`` (int, 1-indexed), ``caption`` (str,
        possibly empty), and ``image_path`` (str, absolute path to a PNG
        on disk).

    Raises:
        InvalidArxivIdError: if ``arxiv_id`` cannot be parsed.
        ArxivFetchError: if the PDF download fails.
        FigureExtractionError: if PyMuPDF cannot open or read the cached PDF.
    """
    canonical = _normalise_id(arxiv_id)
    pdf_path = _ensure_pdf_cached(canonical)
    figures_dir = _figures_cache_dir(canonical)
    figures_dir.mkdir(parents=True, exist_ok=True)

    try:
        doc = pymupdf.open(str(pdf_path))
    except Exception as exc:
        raise FigureExtractionError(f"Could not open PDF at {pdf_path}: {exc}") from exc

    results: list[dict[str, Any]] = []
    try:
        figure_index = 0
        for page_index in range(doc.page_count):
            try:
                page = doc.load_page(page_index)
                page_text = page.get_text()
                images = page.get_images(full=True)
            except Exception as exc:
                raise FigureExtractionError(
                    f"Failed to read page {page_index + 1} of {pdf_path}: {exc}"
                ) from exc

            caption = _find_caption(page_text)

            if images:
                for image_info in images:
                    figure_index += 1
                    xref = image_info[0]
                    image_path = _figure_image_path(canonical, figure_index)
                    if not image_path.exists() or image_path.stat().st_size == 0:
                        try:
                            _save_raster_image(doc, xref, image_path)
                        except Exception as exc:
                            raise FigureExtractionError(
                                f"Failed to extract image xref={xref} on page "
                                f"{page_index + 1} of {pdf_path}: {exc}"
                            ) from exc
                    results.append(
                        {
                            "page_number": page_index + 1,
                            "caption": caption,
                            "image_path": str(image_path.resolve()),
                        }
                    )
            elif caption:
                # Vector-only figure: rasterise the whole page so the agent
                # still gets pixels to look at.
                figure_index += 1
                image_path = _figure_image_path(canonical, figure_index)
                if not image_path.exists() or image_path.stat().st_size == 0:
                    try:
                        _render_page(page, image_path)
                    except Exception as exc:
                        raise FigureExtractionError(
                            f"Failed to render vector figure on page "
                            f"{page_index + 1} of {pdf_path}: {exc}"
                        ) from exc
                results.append(
                    {
                        "page_number": page_index + 1,
                        "caption": caption,
                        "image_path": str(image_path.resolve()),
                    }
                )
    finally:
        doc.close()

    return results


__all__ = ["EXTRACT_FIGURES_DESCRIPTION", "extract_figures"]
