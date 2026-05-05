"""Idempotent downloader for the QLoRA paper PDF used as a test fixture.

The QLoRA paper (arxiv 2305.14314) is the canonical fixture for arxiv-deep
tests. It is downloaded once per machine into ``tests/fixtures/cache/``,
which is gitignored. Re-running this script is a no-op when the cached file
exists and is non-empty.

Run directly:

    python tests/fixtures/download_fixture.py

Or import :func:`download` from :mod:`tests.conftest`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

ARXIV_ID = "2305.14314"
PDF_URL = f"https://arxiv.org/pdf/{ARXIV_ID}.pdf"
FIXTURES_DIR = Path(__file__).resolve().parent
CACHE_DIR = FIXTURES_DIR / "cache"
TARGET = CACHE_DIR / f"{ARXIV_ID}.pdf"

# Bytes; arxiv occasionally returns a stub HTML page when rate-limiting. A real
# PDF for this paper is ~1.5 MB, so anything under 100 KB is treated as failure.
_MIN_PDF_BYTES = 100_000


def download(target: Path = TARGET, url: str = PDF_URL) -> Path:
    """Download the QLoRA PDF if it is missing or truncated.

    Args:
        target: Destination path. Defaults to the shared cache location.
        url: Source URL. Defaults to the arxiv PDF endpoint.

    Returns:
        The path to the cached PDF.

    Raises:
        RuntimeError: If the download succeeds but the resulting file is
            implausibly small (likely a rate-limit HTML stub).
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size >= _MIN_PDF_BYTES:
        return target

    with httpx.stream("GET", url, timeout=60.0, follow_redirects=True) as response:
        response.raise_for_status()
        with target.open("wb") as buf:
            for chunk in response.iter_bytes():
                buf.write(chunk)

    if target.stat().st_size < _MIN_PDF_BYTES:
        raise RuntimeError(
            f"Downloaded file at {target} is only {target.stat().st_size} bytes; "
            "arxiv likely returned a rate-limit page. Retry in a few minutes."
        )
    return target


def _main() -> int:
    path = download()
    size = path.stat().st_size
    sys.stderr.write(f"QLoRA PDF cached at {path} ({size} bytes)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
