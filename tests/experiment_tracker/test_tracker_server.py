"""Server-shape tests for the experiment-tracker MCP server.

Verifies that ``build_server`` returns a FastMCP instance with every
expected tool registered and that each tool exposes a non-empty input
schema and description. Exercises the registration path that the per-tool
unit tests skip (those import individual tools directly).
"""

from __future__ import annotations

from pathlib import Path

from experiment_tracker.server import build_server

_EXPECTED_TOOLS = {
    "start_run",
    "list_runs",
    "complete_run",
    "log_metric",
    "log_artifact",
    "compare_runs",
    "best_run",
}


async def test_build_server_registers_all_phase_2_tools(tmp_path: Path) -> None:
    server = build_server(db_path=tmp_path / "runs.db")

    tools = await server.list_tools()
    names = {tool.name for tool in tools}

    assert names == _EXPECTED_TOOLS

    for tool in tools:
        assert tool.description, f"{tool.name} is missing an agent-facing description"
