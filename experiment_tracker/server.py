"""experiment-tracker MCP server entry point.

Boots a FastMCP server over stdio. Tools are attached in
:func:`build_server` so tests can instantiate fresh servers without
process-global side effects. The server bootstraps the SQLite database on
first call, creating the parent directory if needed.

Stdio gotcha: the MCP wire protocol uses *stdout* for JSON-RPC framing.
Logging is wired to stderr only and the module avoids ``print`` calls.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from experiment_tracker import __version__
from experiment_tracker.db import default_db_path, get_engine, init_db

logger = logging.getLogger("experiment_tracker")


def build_server(db_path: Path | None = None) -> FastMCP:
    """Construct a FastMCP server with all experiment-tracker tools attached.

    Args:
        db_path: Optional override for the SQLite database file. ``None``
            falls back to :func:`experiment_tracker.db.default_db_path`,
            which itself honours the ``EXPERIMENT_TRACKER_DB_PATH``
            environment variable.

    Returns:
        A :class:`FastMCP` server ready to run.
    """
    engine = get_engine(db_path)
    init_db(engine)

    server: FastMCP = FastMCP(
        name="experiment-tracker",
        instructions=(
            "Persistent log of fine-tuning runs, their metrics, and their "
            "artifacts. Call start_run before training, log_metric and "
            "log_artifact during, complete_run when done, and "
            "compare_runs / best_run to choose between alternatives."
        ),
    )
    return server


def main() -> None:
    """Run the experiment-tracker MCP server on stdio.

    Configures stderr-only logging, builds the server (which bootstraps the
    database), and runs the stdio transport loop. Exits cleanly on
    KeyboardInterrupt so SIGINT from the parent agent does not produce a
    noisy traceback.
    """
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.info("Starting experiment-tracker MCP server v%s", __version__)
    logger.info("Using database at %s", default_db_path())
    server = build_server()
    try:
        server.run("stdio")
    except KeyboardInterrupt:  # pragma: no cover - signal-driven path
        logger.info("experiment-tracker MCP server interrupted; shutting down")


if __name__ == "__main__":  # pragma: no cover - exercised via the CLI script
    main()
