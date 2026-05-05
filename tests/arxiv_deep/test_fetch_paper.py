"""Tests for ``arxiv_deep.tools.fetch.fetch_paper``.

These tests pin the contract for the tool before it exists. Per
``PROMPTS.md`` Phase 1.4, ``fetch_paper(arxiv_id: str) -> dict`` must return
a dict with keys: ``title`` (str), ``authors`` (list[str]), ``abstract`` (str),
``full_text`` (str), ``published_date`` (str, ISO 8601), ``categories``
(list[str]).

The tests rely on two private hooks in ``arxiv_deep.tools.fetch`` that the
implementation must expose so the suite stays offline-deterministic:

* ``_download_pdf(arxiv_id: str, dest: Path) -> None``
  Writes the paper PDF to ``dest``. Tests monkeypatch it to copy the cached
  QLoRA fixture instead of hitting the network.
* ``_fetch_metadata(arxiv_id: str) -> dict``
  Returns the structured metadata fields. Tests monkeypatch it with a canned
  payload modelled on the real arxiv response.

If the implementation in Prompt 1.5 changes those hook names, the tests
update too; both layers ship in the same commit.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from arxiv_deep.exceptions import InvalidArxivIdError
from arxiv_deep.tools.fetch import fetch_paper

_QLORA_METADATA: dict[str, Any] = {
    "title": "QLoRA: Efficient Finetuning of Quantized LLMs",
    "authors": [
        "Tim Dettmers",
        "Artidoro Pagnoni",
        "Ari Holtzman",
        "Luke Zettlemoyer",
    ],
    "abstract": (
        "We present QLoRA, an efficient finetuning approach that reduces "
        "memory usage enough to finetune a 65B parameter model on a single "
        "48GB GPU while preserving full 16-bit finetuning task performance."
    ),
    "published_date": "2023-05-23",
    "categories": ["cs.LG"],
}


def _install_fixture_doubles(
    monkeypatch: pytest.MonkeyPatch,
    qlora_pdf_path: Path,
    download_calls: list[str] | None = None,
    metadata_calls: list[str] | None = None,
) -> None:
    """Patch the network-touching helpers in ``arxiv_deep.tools.fetch``.

    Installs deterministic doubles for ``_download_pdf`` (copies the cached
    QLoRA fixture) and ``_fetch_metadata`` (returns ``_QLORA_METADATA``).
    Optional list arguments capture the ``arxiv_id`` of each call for
    invocation-count assertions.
    """
    from arxiv_deep.tools import fetch as fetch_mod

    def _fake_download(arxiv_id: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(qlora_pdf_path, dest)
        if download_calls is not None:
            download_calls.append(arxiv_id)

    def _fake_metadata(arxiv_id: str) -> dict[str, Any]:
        if metadata_calls is not None:
            metadata_calls.append(arxiv_id)
        return dict(_QLORA_METADATA)

    monkeypatch.setattr(fetch_mod, "_download_pdf", _fake_download)
    monkeypatch.setattr(fetch_mod, "_fetch_metadata", _fake_metadata)


def test_happy_path_returns_full_structured_payload(
    qlora_pdf_path: Path,
    tmp_cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fixture_doubles(monkeypatch, qlora_pdf_path)

    result = fetch_paper("2305.14314")

    assert set(result.keys()) >= {
        "title",
        "authors",
        "abstract",
        "full_text",
        "published_date",
        "categories",
    }
    assert isinstance(result["title"], str)
    assert isinstance(result["authors"], list) and result["authors"]
    assert all(isinstance(name, str) for name in result["authors"])
    assert isinstance(result["abstract"], str)
    assert isinstance(result["full_text"], str)
    assert isinstance(result["published_date"], str)
    assert isinstance(result["categories"], list)
    assert all(isinstance(cat, str) for cat in result["categories"])

    assert "qlora" in result["title"].lower()
    assert len(result["full_text"]) > 5000


def test_invalid_id_raises_typed_error(tmp_cache_dir: Path) -> None:
    with pytest.raises(InvalidArxivIdError):
        fetch_paper("not-a-real-id")


def test_repeated_call_does_not_redownload(
    qlora_pdf_path: Path,
    tmp_cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    download_calls: list[str] = []
    _install_fixture_doubles(monkeypatch, qlora_pdf_path, download_calls=download_calls)

    fetch_paper("2305.14314")
    fetch_paper("2305.14314")

    assert len(download_calls) == 1, (
        f"PDF should be downloaded once and then served from cache; "
        f"saw {len(download_calls)} calls: {download_calls}"
    )


def test_full_text_contains_paper_specific_phrase(
    qlora_pdf_path: Path,
    tmp_cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fixture_doubles(monkeypatch, qlora_pdf_path)

    result = fetch_paper("2305.14314")

    assert "4-bit" in result["full_text"], (
        "QLoRA paper full text should mention '4-bit'; "
        "either pymupdf extraction is broken or the wrong PDF is cached."
    )


def test_id_normalisation_is_idempotent_across_forms(
    qlora_pdf_path: Path,
    tmp_cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fixture_doubles(monkeypatch, qlora_pdf_path)

    canonical = fetch_paper("2305.14314")
    prefixed = fetch_paper("arXiv:2305.14314")
    abs_url = fetch_paper("https://arxiv.org/abs/2305.14314")

    assert canonical == prefixed == abs_url
