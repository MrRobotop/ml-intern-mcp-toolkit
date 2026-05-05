"""Schema and round-trip checks for ``demo/ml_intern_config.json``.

These tests guard the integration contract with the upstream ``ml-intern``
agent. They do *not* require ``ml-intern`` to be installed: instead they
re-implement the ``StdioMCPServer`` schema check via the same library
``fastmcp`` that ``ml-intern`` uses, plus the env-var substitution
semantics that ``agent.config.substitute_env_vars`` implements.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_CONFIG = REPO_ROOT / "demo" / "ml_intern_config.json"


def _substitute_env_vars(obj: Any, env: dict[str, str]) -> Any:
    """Mirror of ``agent.config.substitute_env_vars`` for hermetic tests.

    Supports ``${VAR}`` (required) and ``${VAR:-default}`` (optional with
    fallback). Keeps test independent of the ``ml-intern`` install.
    """
    if isinstance(obj, str):
        pattern = re.compile(r"\$\{([^}:]+)(?::(-)?([^}]*))?\}")

        def replacer(match: re.Match[str]) -> str:
            var_name = match.group(1)
            has_default = match.group(2) is not None
            default_value = match.group(3) if has_default else None
            value = env.get(var_name)
            if value is not None:
                return value
            if has_default:
                return default_value or ""
            raise ValueError(f"required env var {var_name!r} not set")

        return pattern.sub(replacer, obj)
    if isinstance(obj, dict):
        return {k: _substitute_env_vars(v, env) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute_env_vars(item, env) for item in obj]
    return obj


def test_demo_config_is_valid_json() -> None:
    json.loads(DEMO_CONFIG.read_text())


def test_demo_config_declares_both_servers() -> None:
    raw = json.loads(DEMO_CONFIG.read_text())

    assert "mcpServers" in raw
    assert set(raw["mcpServers"].keys()) >= {"arxiv-deep", "experiment-tracker"}


def test_required_env_var_is_required() -> None:
    raw = json.loads(DEMO_CONFIG.read_text())
    raw.pop("_comment", None)

    with pytest.raises(ValueError, match="ML_INTERN_TOOLKIT_PATH"):
        _substitute_env_vars(raw, env={})


def test_optional_env_vars_fall_back_to_empty_string() -> None:
    raw = json.loads(DEMO_CONFIG.read_text())
    raw.pop("_comment", None)

    resolved = _substitute_env_vars(
        raw,
        env={"ML_INTERN_TOOLKIT_PATH": "/abs/path"},
    )

    arxiv_env = resolved["mcpServers"]["arxiv-deep"]["env"]
    tracker_env = resolved["mcpServers"]["experiment-tracker"]["env"]
    assert arxiv_env["ARXIV_DEEP_CACHE_DIR"] == ""
    assert tracker_env["EXPERIMENT_TRACKER_DB_PATH"] == ""


def test_each_server_invokes_a_known_console_script() -> None:
    raw = json.loads(DEMO_CONFIG.read_text())
    expected = {
        "arxiv-deep": "arxiv-deep-server",
        "experiment-tracker": "experiment-tracker-server",
    }

    for server_name, console_script in expected.items():
        entry = raw["mcpServers"][server_name]
        assert entry["command"] == "uv"
        assert entry["args"][-1] == console_script
        assert "${ML_INTERN_TOOLKIT_PATH}" in entry["args"], (
            f"{server_name} args must include the toolkit path placeholder"
        )


def test_fastmcp_can_parse_the_resolved_config() -> None:
    """End-to-end shape check via the same Pydantic models ``ml-intern`` uses.

    Skipped if ``fastmcp`` is not installed in the test env. ``ml-intern``
    pins ``fastmcp>=3.2.0``; ours does not depend on it directly.
    """
    fastmcp_mcp_config = pytest.importorskip("fastmcp.mcp_config")

    raw = json.loads(DEMO_CONFIG.read_text())
    raw.pop("_comment", None)
    resolved = _substitute_env_vars(
        raw,
        env={"ML_INTERN_TOOLKIT_PATH": "/abs/path"},
    )

    for entry in resolved["mcpServers"].values():
        fastmcp_mcp_config.StdioMCPServer.model_validate(entry)
