"""Tests for ``arxiv_deep.tools.figures.extract_figures``.

These tests pin the contract for the ``extract_figures`` tool. Per
``PROMPTS.md`` Phase 1.6, ``extract_figures(arxiv_id: str) -> list[dict]``
must yield one dict per extracted figure with keys ``page_number`` (int,
1-indexed), ``caption`` (str, may be empty), and ``image_path`` (str,
absolute path to a PNG on disk).

The suite reuses the ``_download_pdf`` hook on ``arxiv_deep.tools.fetch``
so figure extraction can resolve the cached PDF without touching the
network. Captures of the QLoRA fixture power every assertion.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from arxiv_deep.tools.figures import extract_figures

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _install_pdf_double(
    monkeypatch: pytest.MonkeyPatch,
    qlora_pdf_path: Path,
) -> None:
    """Patch ``_download_pdf`` to copy the QLoRA fixture into the cache.

    ``extract_figures`` reuses the same caching helpers as ``fetch_paper``;
    monkey-patching the downloader keeps the test offline-deterministic
    while exercising the production cache path.
    """
    from arxiv_deep.tools import fetch as fetch_mod

    def _fake_download(arxiv_id: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(qlora_pdf_path, dest)

    monkeypatch.setattr(fetch_mod, "_download_pdf", _fake_download)


def test_qlora_returns_at_least_three_figures(
    qlora_pdf_path: Path,
    tmp_cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_pdf_double(monkeypatch, qlora_pdf_path)

    figures = extract_figures("2305.14314")

    assert len(figures) >= 3, f"QLoRA paper should yield at least 3 figures; got {len(figures)}."


def test_at_least_one_figure_has_non_empty_caption(
    qlora_pdf_path: Path,
    tmp_cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_pdf_double(monkeypatch, qlora_pdf_path)

    figures = extract_figures("2305.14314")

    assert any(fig["caption"].strip() for fig in figures), (
        "Expected at least one figure to carry a non-empty caption."
    )


def test_every_image_path_exists_and_is_png(
    qlora_pdf_path: Path,
    tmp_cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_pdf_double(monkeypatch, qlora_pdf_path)

    figures = extract_figures("2305.14314")

    assert figures, "Expected at least one figure to validate."
    for fig in figures:
        path = Path(fig["image_path"])
        assert path.is_absolute(), f"image_path must be absolute: {path}"
        assert path.exists(), f"image_path does not exist on disk: {path}"
        with path.open("rb") as fh:
            header = fh.read(len(_PNG_MAGIC))
        assert header == _PNG_MAGIC, (
            f"File at {path} does not start with PNG magic bytes; got {header!r}."
        )


def test_all_page_numbers_are_positive(
    qlora_pdf_path: Path,
    tmp_cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_pdf_double(monkeypatch, qlora_pdf_path)

    figures = extract_figures("2305.14314")

    assert figures, "Expected at least one figure to validate."
    for fig in figures:
        assert isinstance(fig["page_number"], int)
        assert fig["page_number"] >= 1, (
            f"page_number must be 1-indexed and positive: {fig['page_number']}"
        )


def test_repeated_call_reuses_cached_images(
    qlora_pdf_path: Path,
    tmp_cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_pdf_double(monkeypatch, qlora_pdf_path)

    first = extract_figures("2305.14314")
    assert first, "Expected at least one figure on first call."
    mtimes = {fig["image_path"]: os.stat(fig["image_path"]).st_mtime_ns for fig in first}

    second = extract_figures("2305.14314")
    assert len(second) == len(first), (
        "Cached call should produce the same number of figures as the first."
    )
    for fig in second:
        path = fig["image_path"]
        assert path in mtimes, f"Unexpected new image path on cached call: {path}"
        assert os.stat(path).st_mtime_ns == mtimes[path], (
            f"Cached image at {path} was rewritten on the second call."
        )
