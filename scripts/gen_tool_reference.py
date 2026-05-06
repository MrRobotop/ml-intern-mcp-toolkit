"""Render ``docs/tool_reference.md`` from the live MCP server registrations.

Introspects ``arxiv_deep.server.build_server`` and
``experiment_tracker.server.build_server`` (each invoked with a per-run tmp
DB so we do not touch the user's cache), enumerates every tool, and writes a
deterministic Markdown reference. Idempotent: running the script twice with
no source changes produces identical output.

The generator is wired into ``make docs``; CI does not run it (the rendered
file is committed). To verify the doc is in sync with the code, run the
script locally and ``git diff docs/tool_reference.md``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from arxiv_deep.server import build_server as build_arxiv_server  # noqa: E402
from experiment_tracker.server import (  # noqa: E402
    build_server as build_tracker_server,
)

_HEADER = """# Tool reference

Generated from the live MCP server registrations by
``scripts/gen_tool_reference.py``. Do not edit by hand; run ``make docs`` to
regenerate after modifying any tool definition.

Two servers ship in this toolkit:

| Server | Tools | Source |
|---|---|---|
| ``arxiv-deep`` | paper fetch, figure extraction, code-link discovery, structured implementation brief | [arxiv_deep/](../arxiv_deep) |
| ``experiment-tracker`` | run lifecycle, metric and artifact logging, comparison and winner selection | [experiment_tracker/](../experiment_tracker) |

Tool naming inside ml-intern follows ``fastmcp``'s convention: each tool
appears as ``<server-name>_<tool-name>`` in the agent's registered-tools list,
e.g. ``arxiv-deep_fetch_paper``. The bare names below match the function
exported from each server.
"""


def _format_schema_table(schema: dict[str, object]) -> str:
    """Render an MCP tool input schema as a Markdown table.

    The MCP spec says ``inputSchema`` is JSON Schema, so we walk
    ``properties`` and ``required`` directly. Unknown fields fall through
    untouched into the description column so future schema extensions stay
    visible without code changes here.
    """
    properties = schema.get("properties") or {}
    if not isinstance(properties, dict):
        return "_no input parameters_"
    required = set(schema.get("required") or [])
    if not properties:
        return "_no input parameters_"

    rows = ["| Name | Type | Required | Description |", "|---|---|---|---|"]
    for name, spec in properties.items():
        if not isinstance(spec, dict):
            spec = {}
        kind = spec.get("type") or spec.get("anyOf") or spec.get("oneOf") or "—"
        if isinstance(kind, list):
            kind = " \\| ".join(str(k) for k in kind)
        if isinstance(kind, dict):
            kind = json.dumps(kind, separators=(",", ":"))
        desc = (spec.get("description") or spec.get("title") or "").replace("\n", " ")
        rows.append(
            f"| `{name}` | `{kind}` | {'yes' if name in required else 'no'} | {desc or '—'} |"
        )
    return "\n".join(rows)


def _format_output(tool: object) -> str:
    """Pretty-print the tool's outputSchema as fenced JSON when present."""
    schema = getattr(tool, "outputSchema", None)
    if not schema:
        return "_(no structured output schema; the tool returns text content)_"
    return "```json\n" + json.dumps(schema, indent=2) + "\n```"


def _server_section(server_name: str, tools: list[object]) -> str:
    chunks: list[str] = []
    chunks.append(f"## `{server_name}`\n")
    for tool in sorted(tools, key=lambda t: getattr(t, "name", "")):
        name = getattr(tool, "name", "<unnamed>")
        description = (getattr(tool, "description", "") or "").strip()
        in_schema = getattr(tool, "inputSchema", {}) or {}

        chunks.append(f"### `{name}`\n")
        chunks.append(f"{description}\n")
        chunks.append("**Input parameters**\n")
        chunks.append(_format_schema_table(in_schema) + "\n")
        chunks.append("**Output schema**\n")
        chunks.append(_format_output(tool) + "\n")
        chunks.append(f"**Agent-facing name (under ml-intern)**: ``{server_name}_{name}``\n")
    return "\n".join(chunks)


async def _enumerate_arxiv_deep() -> list[object]:
    server = build_arxiv_server()
    return list(await server.list_tools())


async def _enumerate_tracker(tmp_db: Path) -> list[object]:
    os.environ["EXPERIMENT_TRACKER_DB_PATH"] = str(tmp_db)
    server = build_tracker_server(db_path=tmp_db)
    return list(await server.list_tools())


def render() -> str:
    """Build the full reference Markdown without writing it to disk."""

    async def _gather() -> tuple[list[object], list[object]]:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "doc-gen.db"
            arxiv_tools = await _enumerate_arxiv_deep()
            tracker_tools = await _enumerate_tracker(db_path)
        return arxiv_tools, tracker_tools

    arxiv_tools, tracker_tools = asyncio.run(_gather())
    sections = [
        _HEADER,
        _server_section("arxiv-deep", arxiv_tools),
        _server_section("experiment-tracker", tracker_tools),
    ]
    return "\n".join(sections).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render docs/tool_reference.md")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the rendered output differs from the committed file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "docs" / "tool_reference.md",
        help="Where to write the rendered reference.",
    )
    ns = parser.parse_args(argv)

    rendered = render()

    if ns.check:
        if not ns.output.exists():
            print(f"{ns.output} does not exist; run without --check to create it.")
            return 1
        current = ns.output.read_text(encoding="utf-8")
        if current != rendered:
            print(f"{ns.output} is out of date; rerun scripts/gen_tool_reference.py")
            return 1
        return 0

    ns.output.parent.mkdir(parents=True, exist_ok=True)
    ns.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {ns.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
