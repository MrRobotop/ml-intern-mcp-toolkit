"""Shared pytest fixtures for the ml-intern-mcp-toolkit suite.

These fixtures intentionally avoid network or filesystem side effects unless
the test explicitly opts in via the ``qlora_pdf_path`` fixture. The cache
override fixture (:func:`tmp_cache_dir`) sets the ``ARXIV_DEEP_CACHE_DIR``
environment variable; the production code is expected to honour that variable
when computing its on-disk cache root.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx

# The downloader script lives next to this conftest under tests/fixtures/.
# Adding that directory to sys.path lets us import the script without turning
# tests/ into a package (which would interfere with pytest's discovery model).
_FIXTURES_DIR = Path(__file__).parent / "fixtures"
if str(_FIXTURES_DIR) not in sys.path:
    sys.path.insert(0, str(_FIXTURES_DIR))

from download_fixture import download as _download_qlora  # noqa: E402


@pytest.fixture(scope="session")
def qlora_pdf_path() -> Path:
    """Path to the cached QLoRA paper PDF, downloaded on first use.

    Yields the same path for every test that requests it; the underlying
    :func:`tests.fixtures.download_fixture.download` call is idempotent so the
    network is hit at most once per machine.
    """
    return _download_qlora()


@pytest.fixture
def tmp_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Override the arxiv-deep on-disk cache root for a single test.

    Sets ``ARXIV_DEEP_CACHE_DIR`` so that production code reading that
    environment variable falls back to the supplied ``tmp_path`` rather than
    polluting ``~/.cache/arxiv-deep/``.
    """
    monkeypatch.setenv("ARXIV_DEEP_CACHE_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def block_arxiv_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if a test reaches the live arxiv search API.

    Acts as a regression guard against test-isolation bugs where a
    monkey-patch on ``arxiv_deep.tools.fetch._download_pdf`` or
    ``_fetch_metadata`` does not take effect (for example because a
    consumer module bound the name at import time). A test that opts in to
    this fixture will fail with a clear error rather than silently hitting
    the network and racing against arxiv rate limits in CI.
    """
    import arxiv

    def _refuse(self: object, *args: object, **kwargs: object) -> None:
        raise RuntimeError(
            "Live arxiv API call leaked from a test that should be hermetic. "
            "Check that every consumer of arxiv_deep.tools.fetch references "
            "_download_pdf / _fetch_metadata via the fetch module attribute "
            "(not a top-level import) so monkeypatch.setattr propagates."
        )

    monkeypatch.setattr(arxiv.Client, "results", _refuse)


@pytest.fixture
def mock_github_validator() -> Iterator[respx.MockRouter]:
    """Mock all GitHub HEAD requests with a 200 response.

    ``find_reference_code`` issues async HTTPX HEAD requests against any
    ``github.com`` URLs scraped from a paper. In offline test runs we want
    those validations to succeed deterministically; specific tests can
    further override individual routes via the yielded ``respx`` router.
    """
    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.head(url__regex=re.compile(r"https?://github\.com/.+")).mock(
            return_value=httpx.Response(200)
        )
        yield respx_mock
