"""Minimal arxiv-deep client.

Connects directly to the ``arxiv-deep`` MCP server as an MCP client (no
``ml-intern`` involved), calls ``implementation_brief`` once, and pretty-prints
the result. The point is to demonstrate the toolkit without the full agent in
the loop, which is useful for debugging tool descriptions or for any user who
wants to embed the servers in their own agent harness.

Run from the toolkit root:

    uv run python examples/minimal_arxiv_query.py 2305.14314

Replace ``2305.14314`` with any arxiv id. The script spawns the server as a
subprocess over stdio, drives one tool call, and exits.
"""

from __future__ import annotations

import asyncio
import json
import sys

from arxiv_deep.server import build_server


async def run_minimal_query(arxiv_id: str) -> dict[str, object]:
    """Spawn the arxiv-deep server in-process and call ``implementation_brief``."""
    server = build_server()
    _, structured = await server.call_tool("implementation_brief", {"arxiv_id": arxiv_id})
    if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
        return dict(structured["result"])
    return dict(structured)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    arxiv_id = args[0] if args else "2305.14314"

    brief = asyncio.run(run_minimal_query(arxiv_id))
    print(f"# {brief.get('title', '<no title>')}\n")
    print(f"## Core method\n{brief.get('core_method', '')}\n")
    print("## Architecture\n- " + "\n- ".join(brief.get("architecture", []) or ["<none>"]))
    print()
    print("## Hyperparameters")
    print(json.dumps(brief.get("hyperparameters", {}), indent=2))
    print()
    print("## Datasets")
    print("- " + "\n- ".join(brief.get("dataset", []) or ["<none>"]))
    print()
    print("## Reference implementations")
    for entry in brief.get("reference_implementations", []) or []:
        url = entry.get("url", "<unknown>")
        validated = entry.get("validated", False)
        print(f"- {url}  validated={validated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
