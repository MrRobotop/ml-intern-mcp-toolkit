"""``implementation_brief`` MCP tool: a structured paper digest.

This is the synthesis tool. It calls :func:`fetch_paper` and
:func:`find_reference_code` to gather raw material, then runs heuristic
extractors over the abstract and body text to surface the fields a developer
would need to start reproducing the paper. There are intentionally no LLM
calls inside this tool: the calling agent is the reasoner; this tool only
extracts structure.

Heuristics are deliberately fuzzy. Extractors prefer recall over precision
and never block on missing data: every field has a sensible empty-state value
so the agent can decide what to do with whatever is available.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from arxiv_deep.tools.code import find_reference_code
from arxiv_deep.tools.fetch import fetch_paper

logger = logging.getLogger(__name__)


# Vocabulary of canonical architecture / component names. Match is
# case-insensitive over word boundaries; the canonical form (the dict value)
# is what gets surfaced to the agent.
_ARCHITECTURE_VOCAB: dict[str, str] = {
    r"\btransformer(s)?\b": "transformer",
    r"\b(self[- ]?)?attention\b": "attention",
    r"\bencoder(s)?\b": "encoder",
    r"\bdecoder(s)?\b": "decoder",
    r"\bLSTM\b": "LSTM",
    r"\bRNN(s)?\b": "RNN",
    r"\bCNN(s)?\b": "CNN",
    r"\bResNet\b": "ResNet",
    r"\bViT\b|\bvision transformer\b": "vision transformer",
    r"\bBERT\b": "BERT",
    r"\bGPT(-\d)?\b": "GPT",
    r"\bT5\b": "T5",
    r"\bLLaMA\b|\bLlama\b": "LLaMA",
    r"\bMistral\b": "Mistral",
    r"\bQwen\b": "Qwen",
    r"\bCLIP\b": "CLIP",
    r"\bLoRA\b": "LoRA",
    r"\badapter(s)?\b": "adapter",
    r"\bquantiz(ation|e[d]?)\b": "quantization",
    r"\b4[- ]?bit\b": "4-bit",
    r"\b8[- ]?bit\b": "8-bit",
    r"\bNF4\b": "NF4",
    r"\bdouble quantization\b": "double quantization",
    r"\bpaged optimizer(s)?\b": "paged optimizer",
}


# Hyperparameter extractors: each pattern produces ``(name, value)``.
# ``\s*`` allows pretty-printing, the value group is kept narrow so we capture
# numerics rather than swallowing trailing prose.
_HYPERPARAM_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "learning_rate",
        re.compile(
            r"(?:learning[\s-]rate|\blr\b)\s*(?:=|:|of|is)\s*"
            r"([0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)",
            re.IGNORECASE,
        ),
    ),
    (
        "batch_size",
        re.compile(
            r"batch[\s-]size\s*(?:=|:|of|is)\s*([0-9]+)",
            re.IGNORECASE,
        ),
    ),
    (
        "epochs",
        re.compile(
            r"(?:epochs?\s*(?:=|:|of|is)\s*([0-9]+))|(?:([0-9]+)\s+epochs?\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "weight_decay",
        re.compile(
            r"weight[\s-]decay\s*(?:=|:|of|is)\s*"
            r"([0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)",
            re.IGNORECASE,
        ),
    ),
    (
        "dropout",
        re.compile(
            r"dropout\s*(?:=|:|of|is)\s*"
            r"([0-9]+(?:\.[0-9]+)?)",
            re.IGNORECASE,
        ),
    ),
    (
        "lora_rank",
        re.compile(
            r"(?:LoRA\s+r|\brank\s+r|\brank)\s*(?:=|:|of|is)\s*([0-9]+)",
            re.IGNORECASE,
        ),
    ),
    (
        "lora_alpha",
        re.compile(
            r"(?:LoRA\s+)?alpha\s*(?:=|:|of|is)\s*([0-9]+)",
            re.IGNORECASE,
        ),
    ),
    (
        "warmup_steps",
        re.compile(
            r"warmup(?:[\s-]steps)?\s*(?:=|:|of|is)\s*([0-9]+)",
            re.IGNORECASE,
        ),
    ),
]


# Recognised dataset names. Patterns are word-boundaried and case-insensitive.
# Adding a name here makes it discoverable; the canonical form is the value.
_DATASET_VOCAB: dict[str, str] = {
    r"\bImageNet(-\d+k?)?\b": "ImageNet",
    r"\bCOCO\b": "COCO",
    r"\bGLUE\b": "GLUE",
    r"\bSuperGLUE\b": "SuperGLUE",
    r"\bSQuAD\b": "SQuAD",
    r"\bMNIST\b": "MNIST",
    r"\bCIFAR[- ]?10\b": "CIFAR-10",
    r"\bCIFAR[- ]?100\b": "CIFAR-100",
    r"\bOxford[\s-]Pets\b": "Oxford Pets",
    r"\bAlpaca\b": "Alpaca",
    r"\bOpenAssistant\b|\bOASST\b|\bOASST1\b": "OpenAssistant",
    r"\bFLAN(?:[\s-]v?\d?)?\b": "FLAN",
    r"\bWikiText(?:-\d+)?\b": "WikiText",
    r"\bC4\b": "C4",
    r"\bThe Pile\b": "The Pile",
    r"\bCommon\s+Crawl\b": "Common Crawl",
    r"\bMMLU\b": "MMLU",
    r"\bHellaSwag\b": "HellaSwag",
    r"\bBIG[-\s]Bench\b": "BIG-Bench",
    r"\bVicuna\b": "Vicuna",
    r"\bChip2\b": "Chip2",
    r"\bSelf[\s-]Instruct\b": "Self-Instruct",
    r"\bUnnatural Instructions\b": "Unnatural Instructions",
    r"\bLongform\b": "Longform",
    r"\bHH[\s-]RLHF\b": "HH-RLHF",
}


_EVAL_HEADING_RE = re.compile(
    r"^(?:\d+(?:\.\d+)?\s+)?(Evaluation|Experiments|Experimental setup|Results)\b",
    re.MULTILINE | re.IGNORECASE,
)


def _split_sentences(text: str) -> list[str]:
    """Naive sentence splitter on period-space boundaries."""
    parts = re.split(r"(?<=\.)\s+(?=[A-Z0-9])", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _extract_core_method(abstract: str) -> str:
    """Return the first one or two sentences of the abstract.

    Falls back to the first 320 characters if the splitter cannot find a
    sentence boundary.
    """
    sentences = _split_sentences(abstract)
    if not sentences:
        return abstract.strip()[:320]
    head = " ".join(sentences[: 2 if len(sentences) > 1 else 1])
    return head


def _extract_architecture(text: str) -> list[str]:
    """Return canonical names of architecture / component terms found in ``text``.

    The result preserves first-appearance order in the text and is
    de-duplicated by canonical form.
    """
    found: dict[str, int] = {}
    for pattern, canonical in _ARCHITECTURE_VOCAB.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match and canonical not in found:
            found[canonical] = match.start()
    return sorted(found, key=found.__getitem__)


def _extract_hyperparameters(text: str) -> dict[str, str]:
    """Return a dict of detected hyperparameter values.

    The first non-empty match wins per parameter; this favours the abstract
    or early body sections, which usually quote the production value.
    """
    out: dict[str, str] = {}
    for name, pattern in _HYPERPARAM_PATTERNS:
        for match in pattern.finditer(text):
            value = next((g for g in match.groups() if g), None)
            if value:
                out[name] = value
                break
    return out


def _extract_datasets(text: str) -> list[str]:
    """Return canonical names of known datasets found in ``text``."""
    found: dict[str, int] = {}
    for pattern, canonical in _DATASET_VOCAB.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match and canonical not in found:
            found[canonical] = match.start()
    return sorted(found, key=found.__getitem__)


def _extract_eval_protocol(text: str) -> str:
    """Return the first paragraph after an Evaluation/Experiments/Results heading.

    Returns an empty string when no such heading appears in the text.
    """
    match = _EVAL_HEADING_RE.search(text)
    if not match:
        return ""
    start = match.end()
    snippet = text[start : start + 800]
    paragraphs = [p.strip() for p in snippet.split("\n\n") if p.strip()]
    if not paragraphs:
        return snippet.strip()
    return paragraphs[0]


IMPLEMENTATION_BRIEF_DESCRIPTION = (
    "Synthesises a structured implementation brief for an arxiv paper. "
    "Internally calls fetch_paper and find_reference_code, then runs "
    "heuristic regex/keyword extractors over the abstract and body text to "
    "surface fields a developer needs to start reproducing the work. Returns "
    "a dict with keys: title (str), core_method (str, the opening sentences "
    "of the abstract), architecture (list[str], detected components and base "
    "models), hyperparameters (dict[str, str], detected values keyed by "
    "canonical parameter name), dataset (list[str], detected dataset names), "
    "eval_protocol (str, first paragraph after an Evaluation/Experiments/"
    "Results heading; empty if not found), and reference_implementations "
    "(list[dict], the output of find_reference_code). Extraction is fuzzy by "
    "design and prefers recall over precision; treat empty fields as 'unknown' "
    "rather than 'absent from the paper'."
)


async def implementation_brief(arxiv_id: str) -> dict[str, Any]:
    """Build a heuristic implementation brief for an arxiv paper.

    Args:
        arxiv_id: A bare arxiv id, an ``arXiv:<id>`` reference, or an
            ``https://arxiv.org/abs/<id>`` URL. Forwarded unchanged to
            ``fetch_paper`` and ``find_reference_code``.

    Returns:
        A dict with keys ``title``, ``core_method``, ``architecture``,
        ``hyperparameters``, ``dataset``, ``eval_protocol``, and
        ``reference_implementations``. See
        :data:`IMPLEMENTATION_BRIEF_DESCRIPTION` for the exact contract.

    Raises:
        InvalidArxivIdError: propagated from ``fetch_paper``.
        ArxivFetchError: propagated from ``fetch_paper``.
    """
    paper = fetch_paper(arxiv_id)
    references = await find_reference_code(arxiv_id)

    abstract: str = paper["abstract"]
    full_text: str = paper["full_text"]
    haystack = f"{abstract}\n\n{full_text}"

    return {
        "title": paper["title"],
        "core_method": _extract_core_method(abstract),
        "architecture": _extract_architecture(haystack),
        "hyperparameters": _extract_hyperparameters(haystack),
        "dataset": _extract_datasets(haystack),
        "eval_protocol": _extract_eval_protocol(full_text),
        "reference_implementations": references,
    }
