"""Server-shape tests for the arxiv-deep MCP server.

Verifies that ``build_server`` returns a FastMCP instance with every
expected tool registered and that each tool exposes a non-empty input
schema and description. Exercises the registration path that Phase 1's
unit tests skip (those import individual tools directly).
"""

from __future__ import annotations

from arxiv_deep.server import build_server

_EXPECTED_TOOLS = {
    "fetch_paper",
    "extract_figures",
    "find_reference_code",
    "implementation_brief",
}


async def test_build_server_registers_all_phase_1_tools() -> None:
    server = build_server()

    tools = await server.list_tools()
    names = {tool.name for tool in tools}

    assert names == _EXPECTED_TOOLS

    for tool in tools:
        assert tool.description, f"{tool.name} is missing an agent-facing description"
        properties = tool.inputSchema.get("properties", {})
        assert "arxiv_id" in properties, (
            f"{tool.name} input schema must accept arxiv_id, got {list(properties)}"
        )
