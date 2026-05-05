"""Tests for ``arxiv_deep.tools.code.find_reference_code``.

These tests pin the contract for the tool before it exists. Per
``PROMPTS.md`` Phase 1.7,
``find_reference_code(arxiv_id: str) -> list[dict[str, Any]]`` must scrape
GitHub URLs from the paper full text returned by ``fetch_paper`` and return
one dict per unique URL with keys ``url``, ``context``, and ``validated``.

Network-touching helpers in ``arxiv_deep.tools.fetch`` are monkey-patched the
same way ``test_fetch_paper`` does it so the suite stays offline-deterministic.
GitHub HEAD validation is intercepted via the ``mock_github_validator``
respx fixture from ``tests/conftest.py``.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from arxiv_deep.tools.code import find_reference_code

_GITHUB_URL_RE = re.compile(r"https?://github\.com/[\w.-]+/[\w.-]+")

_QLORA_METADATA: dict[str, Any] = {
    "title": "QLoRA: Efficient Finetuning of Quantized LLMs",
    "authors": ["Tim Dettmers"],
    "abstract": "QLoRA abstract.",
    "published_date": "2023-05-23",
    "categories": ["cs.LG"],
}


def _install_qlora_doubles(
    monkeypatch: pytest.MonkeyPatch,
    qlora_pdf_path: Path,
) -> None:
    """Patch ``fetch._download_pdf`` and ``fetch._fetch_metadata``.

    Mirrors the helper used by ``test_fetch_paper`` so ``fetch_paper`` returns
    the real QLoRA full text without touching the network.
    """
    from arxiv_deep.tools import fetch as fetch_mod

    def _fake_download(arxiv_id: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(qlora_pdf_path, dest)

    def _fake_metadata(arxiv_id: str) -> dict[str, Any]:
        return dict(_QLORA_METADATA)

    monkeypatch.setattr(fetch_mod, "_download_pdf", _fake_download)
    monkeypatch.setattr(fetch_mod, "_fetch_metadata", _fake_metadata)


def _stub_fetch_paper(
    monkeypatch: pytest.MonkeyPatch,
    full_text: str,
) -> None:
    """Replace the ``fetch_paper`` symbol imported inside ``code.py``.

    The ``find_reference_code`` implementation calls ``fetch_paper`` from
    ``arxiv_deep.tools.code``'s namespace, so patching that attribute lets a
    test feed an arbitrary ``full_text`` payload.
    """
    from arxiv_deep.tools import code as code_mod

    def _fake_fetch_paper(arxiv_id: str) -> dict[str, Any]:
        return {**_QLORA_METADATA, "full_text": full_text}

    monkeypatch.setattr(code_mod, "fetch_paper", _fake_fetch_paper)


async def test_qlora_fixture_yields_at_least_one_github_url(
    qlora_pdf_path: Path,
    tmp_cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_github_validator: respx.MockRouter,
) -> None:
    _install_qlora_doubles(monkeypatch, qlora_pdf_path)

    results = await find_reference_code("2305.14314")

    assert results, "QLoRA paper should contain at least one github.com URL"
    assert all(isinstance(item, dict) for item in results)
    assert all({"url", "context", "validated"} <= set(item.keys()) for item in results)


async def test_all_returned_urls_match_github_pattern(
    qlora_pdf_path: Path,
    tmp_cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_github_validator: respx.MockRouter,
) -> None:
    _install_qlora_doubles(monkeypatch, qlora_pdf_path)

    results = await find_reference_code("2305.14314")

    for item in results:
        url = item["url"]
        assert _GITHUB_URL_RE.match(url), f"URL {url!r} does not match GitHub pattern"


@pytest.mark.network
@pytest.mark.skipif(
    not os.getenv("ARXIV_DEEP_RUN_NETWORK_TESTS"),
    reason="Network tests gated behind ARXIV_DEEP_RUN_NETWORK_TESTS=1",
)
async def test_live_validation_against_real_github(
    qlora_pdf_path: Path,
    tmp_cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_qlora_doubles(monkeypatch, qlora_pdf_path)

    results = await find_reference_code("2305.14314")

    assert any(item["validated"] for item in results), (
        "At least one QLoRA reference URL should resolve over the network"
    )


async def test_paper_with_no_github_urls_returns_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_fetch_paper(monkeypatch, "This paper has no code links at all.")

    results = await find_reference_code("2305.14314")

    assert results == []


async def test_rate_limited_github_url_marked_unvalidated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_url = "https://github.com/example/rate-limited"
    _stub_fetch_paper(
        monkeypatch,
        f"See the implementation at {target_url} for details.",
    )

    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.head(target_url).mock(
            return_value=httpx.Response(
                403,
                headers={"X-RateLimit-Remaining": "0"},
            )
        )
        results = await find_reference_code("2305.14314")

    assert len(results) == 1
    assert results[0]["url"] == target_url
    assert results[0]["validated"] is False


async def test_connection_error_marks_url_unvalidated_and_warns(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    target_url = "https://github.com/example/unreachable"
    _stub_fetch_paper(
        monkeypatch,
        f"Code is at {target_url} (please check it out).",
    )

    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.head(target_url).mock(side_effect=httpx.ConnectError("boom"))
        with caplog.at_level(logging.WARNING, logger="arxiv_deep.tools.code"):
            results = await find_reference_code("2305.14314")

    assert len(results) == 1
    assert results[0]["url"] == target_url
    assert results[0]["validated"] is False
    assert any("unreachable" in record.message for record in caplog.records), (
        f"Expected a warning mentioning the URL; got: {[r.message for r in caplog.records]}"
    )


async def test_duplicate_urls_collapsed_to_first_occurrence(
    monkeypatch: pytest.MonkeyPatch,
    mock_github_validator: respx.MockRouter,
) -> None:
    repeated = "https://github.com/example/repo"
    _stub_fetch_paper(
        monkeypatch,
        f"First mention {repeated} and a second mention {repeated} later on.",
    )

    results = await find_reference_code("2305.14314")

    urls = [item["url"] for item in results]
    assert urls.count(repeated) == 1
    assert len(results) == 1
