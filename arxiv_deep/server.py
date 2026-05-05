"""arxiv-deep MCP server entry point.

Boots a FastMCP server over stdio. Tools are registered in submodules and
attached here so the registration list stays in one place. The skeleton
deliberately registers no tools yet; later prompts in Phase 1 add
``fetch_paper``, ``extract_figures``, ``find_reference_code``, and
``implementation_brief``.

Stdio gotcha: the MCP wire protocol uses *stdout* for JSON-RPC framing. Any
``print`` to stdout corrupts the stream. This module configures logging to
stderr only and never prints.
"""

from __future__ import annotations

import logging
import sys

from mcp.server.fastmcp import FastMCP

from arxiv_deep import __version__

logger = logging.getLogger("arxiv_deep")


def build_server() -> FastMCP:
    """Construct and return a FastMCP server with all arxiv-deep tools attached.

    Tools are registered here rather than at import time so that tests can
    instantiate fresh server instances without process-global side effects.

    Returns:
        A :class:`FastMCP` server ready to be ``run``.
    """
    server: FastMCP = FastMCP(
        name="arxiv-deep",
        instructions=(
            "Deep arxiv reading tools. Use these when you need full paper text, "
            "figures, linked code, or a structured implementation brief, rather "
            "than just the abstract."
        ),
    )
    return server


def main() -> None:
    """Run the arxiv-deep MCP server on stdio.

    Configures stderr-only logging, builds the server, and runs the stdio
    transport loop. Exits cleanly on KeyboardInterrupt so SIGINT from the
    parent agent does not produce a noisy traceback.
    """
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.info("Starting arxiv-deep MCP server v%s", __version__)
    server = build_server()
    try:
        server.run("stdio")
    except KeyboardInterrupt:  # pragma: no cover - signal-driven path
        logger.info("arxiv-deep MCP server interrupted; shutting down")


if __name__ == "__main__":  # pragma: no cover - exercised via the CLI script
    main()
