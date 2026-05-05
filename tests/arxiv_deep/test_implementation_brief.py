"""Tests for ``arxiv_deep.tools.brief.implementation_brief``.

The tool is intentionally heuristic: it does no LLM calls and is fuzzy by
design. These tests therefore assert *structure* rather than exact content,
mirroring the contract in ``PROMPTS.md`` Phase 1.9.

Hermetic setup follows the pattern established by
``tests/arxiv_deep/test_fetch_paper.py``: monkey-patch ``_download_pdf`` and
``_fetch_metadata`` to serve from the cached QLoRA fixture, and use the
``mock_github_validator`` fixture so the embedded ``find_reference_code``
call does not touch the live network.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
import respx

from arxiv_deep.tools.brief import implementation_brief

_QLORA_METADATA: dict[str, Any] = {
    "title": "QLoRA: Efficient Finetuning of Quantized LLMs",
    "authors": ["Tim Dettmers", "Artidoro Pagnoni", "Ari Holtzman", "Luke Zettlemoyer"],
    "abstract": (
        "We present QLoRA, an efficient finetuning approach that reduces "
        "memory usage enough to finetune a 65B parameter model on a single "
        "48GB GPU while preserving full 16-bit finetuning task performance. "
        "QLoRA backpropagates gradients through a frozen, 4-bit quantized "
        "pretrained language model into Low Rank Adapters (LoRA)."
    ),
    "published_date": "2023-05-23",
    "categories": ["cs.LG"],
}


def _install_doubles(monkeypatch: pytest.MonkeyPatch, qlora_pdf_path: Path) -> None:
    """Patch the network-touching helpers in ``arxiv_deep.tools.fetch``."""
    from arxiv_deep.tools import fetch as fetch_mod

    def _fake_download(arxiv_id: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(qlora_pdf_path, dest)

    def _fake_metadata(arxiv_id: str) -> dict[str, Any]:
        return dict(_QLORA_METADATA)

    monkeypatch.setattr(fetch_mod, "_download_pdf", _fake_download)
    monkeypatch.setattr(fetch_mod, "_fetch_metadata", _fake_metadata)


async def test_brief_has_all_contract_keys(
    qlora_pdf_path: Path,
    tmp_cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_github_validator: respx.MockRouter,
) -> None:
    _install_doubles(monkeypatch, qlora_pdf_path)

    brief = await implementation_brief("2305.14314")

    expected_keys = {
        "title",
        "core_method",
        "architecture",
        "hyperparameters",
        "dataset",
        "eval_protocol",
        "reference_implementations",
    }
    assert expected_keys <= set(brief.keys())


async def test_brief_title_round_trips_from_metadata(
    qlora_pdf_path: Path,
    tmp_cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_github_validator: respx.MockRouter,
) -> None:
    _install_doubles(monkeypatch, qlora_pdf_path)

    brief = await implementation_brief("2305.14314")

    assert brief["title"] == _QLORA_METADATA["title"]


async def test_brief_architecture_is_non_empty_list_of_strings(
    qlora_pdf_path: Path,
    tmp_cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_github_validator: respx.MockRouter,
) -> None:
    _install_doubles(monkeypatch, qlora_pdf_path)

    brief = await implementation_brief("2305.14314")

    arch = brief["architecture"]
    assert isinstance(arch, list)
    assert arch, "architecture should detect at least one component for QLoRA"
    assert all(isinstance(item, str) and item for item in arch)


async def test_brief_has_at_least_one_hyperparameter(
    qlora_pdf_path: Path,
    tmp_cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_github_validator: respx.MockRouter,
) -> None:
    _install_doubles(monkeypatch, qlora_pdf_path)

    brief = await implementation_brief("2305.14314")

    hp = brief["hyperparameters"]
    assert isinstance(hp, dict)
    assert hp, "hyperparameter heuristics should surface at least one value for QLoRA"
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in hp.items())


async def test_brief_has_at_least_one_reference_implementation(
    qlora_pdf_path: Path,
    tmp_cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_github_validator: respx.MockRouter,
) -> None:
    _install_doubles(monkeypatch, qlora_pdf_path)

    brief = await implementation_brief("2305.14314")

    refs = brief["reference_implementations"]
    assert isinstance(refs, list)
    assert refs, "QLoRA paper cites at least one github repository"
    assert all("url" in entry and "validated" in entry for entry in refs)


async def test_brief_dataset_is_list_eval_protocol_is_str_core_method_is_str(
    qlora_pdf_path: Path,
    tmp_cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_github_validator: respx.MockRouter,
) -> None:
    _install_doubles(monkeypatch, qlora_pdf_path)

    brief = await implementation_brief("2305.14314")

    assert isinstance(brief["dataset"], list)
    assert all(isinstance(d, str) for d in brief["dataset"])
    assert isinstance(brief["eval_protocol"], str)
    assert isinstance(brief["core_method"], str)
    assert brief["core_method"], "core_method should at least include the abstract opener"
