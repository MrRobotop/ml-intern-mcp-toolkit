"""experiment-tracker MCP tools.

Each submodule defines one or more MCP tool functions plus the matching
``<TOOL>_DESCRIPTION`` constants. Tools are wired onto the FastMCP server in
:func:`experiment_tracker.server.build_server`.
"""

from __future__ import annotations
