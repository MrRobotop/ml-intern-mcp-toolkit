"""Torch-free orchestration tests for the demo.

Default CI does not install the ``demo`` optional dependency group, so
these tests must not import ``torch`` / ``transformers`` / ``peft`` at
collection time. Instead they exercise the orchestration surface:

* ``demo/prompts/train_lora_alpaca.txt`` exists and references the env
  vars the orchestrator advertises.
* ``demo/run_demo.sh`` pre-flight rejects missing required env vars and
  invalid ``DEMO_MODE`` values.
* ``demo/scripts/train_local.py`` argparse parses the canonical CLI shape.
* ``demo/scripts/train_hf_jobs.py`` translates ``JobsArgs`` into the right
  ``train_local.py`` flag list and finds the result line in mixed logs.

The end-to-end training path is exercised by an opt-in integration test
gated on ``PYTEST_INTEGRATION=1`` that does load torch.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_DIR = REPO_ROOT / "demo"
RUN_DEMO = DEMO_DIR / "run_demo.sh"
PROMPT_FILE = DEMO_DIR / "prompts" / "train_lora_alpaca.txt"
TRAIN_LOCAL = DEMO_DIR / "scripts" / "train_local.py"
TRAIN_HF_JOBS = DEMO_DIR / "scripts" / "train_hf_jobs.py"


# ---------------------------------------------------------------------------
# Static artefacts
# ---------------------------------------------------------------------------


def test_demo_prompt_exists_and_references_required_env_vars() -> None:
    text = PROMPT_FILE.read_text()
    for token in (
        "ML_INTERN_TOOLKIT_PATH",
        "DEMO_MODEL",
        "DEMO_DATASET",
        "DEMO_QUICK",
        "DEMO_PUSH_TO_ORG",
        "HF_TOKEN",
    ):
        assert token in text, f"prompt should reference {token}"


def test_run_demo_script_is_executable() -> None:
    assert RUN_DEMO.exists()
    assert os.access(RUN_DEMO, os.X_OK), "run_demo.sh must be executable"


# ---------------------------------------------------------------------------
# Bash pre-flight semantics
# ---------------------------------------------------------------------------


def _run_demo(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Execute ``run_demo.sh`` with the given environment, capturing output."""
    base_env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
    }
    base_env.update(env)
    return subprocess.run(
        [str(RUN_DEMO)],
        env=base_env,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )


def test_run_demo_rejects_when_required_env_is_missing(tmp_path: Path) -> None:
    result = _run_demo({})
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "missing required env vars" in combined
    for var in ("ML_INTERN_PATH", "ANTHROPIC_API_KEY", "HF_TOKEN"):
        assert var in combined


def test_run_demo_rejects_when_ml_intern_path_does_not_exist(
    tmp_path: Path,
) -> None:
    result = _run_demo(
        {
            "ML_INTERN_PATH": str(tmp_path / "nope"),
            "ANTHROPIC_API_KEY": "x",
            "HF_TOKEN": "y",
        }
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "does not exist or is not a directory" in combined


def test_run_demo_rejects_invalid_mode(tmp_path: Path) -> None:
    result = _run_demo(
        {
            "ML_INTERN_PATH": str(tmp_path),
            "ANTHROPIC_API_KEY": "x",
            "HF_TOKEN": "y",
            "DEMO_MODE": "satellite",
        }
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "DEMO_MODE must be" in combined


# ---------------------------------------------------------------------------
# train_local.py argparse
# ---------------------------------------------------------------------------


def _load_module(name: str, path: Path) -> object:
    """Load a Python file as a named module, registering it in ``sys.modules``.

    Registration is required so :mod:`dataclasses` can resolve forward
    references during decoration. Without it the loaded module's
    ``__module__`` attribute points at a name that ``sys.modules`` does not
    know about, and ``dataclass`` raises ``AttributeError`` while inspecting
    annotations.
    """
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


def _import_train_local() -> object:
    """Load ``train_local.py`` without triggering torch import.

    The module's top-level imports are stdlib + dataclass + Path; torch only
    enters via ``main`` and the helpers. Importing the module itself is safe
    in environments without the demo extras.
    """
    return _load_module("demo_train_local", TRAIN_LOCAL)


def test_train_local_argparse_minimal_invocation() -> None:
    mod = _import_train_local()
    args = mod._parse_args(  # type: ignore[attr-defined]
        ["--lora-rank", "8", "--output-dir", "/tmp/out", "--run-uid", "deadbeef"]
    )
    assert args.lora_rank == 8
    assert args.output_dir == Path("/tmp/out")
    assert args.run_uid == "deadbeef"
    assert args.quick is False
    assert args.push_to_hub is None


def test_train_local_argparse_quick_and_push() -> None:
    mod = _import_train_local()
    args = mod._parse_args(  # type: ignore[attr-defined]
        [
            "--lora-rank",
            "4",
            "--output-dir",
            "/tmp/out",
            "--run-uid",
            "abc123",
            "--quick",
            "--push-to-hub",
            "user/some-repo",
        ]
    )
    assert args.quick is True
    assert args.push_to_hub == "user/some-repo"


def test_train_local_alpaca_formatter_with_input() -> None:
    mod = _import_train_local()
    rendered = mod._format_alpaca_example(  # type: ignore[attr-defined]
        {
            "instruction": "Translate to French",
            "input": "hello world",
            "output": "bonjour le monde",
        }
    )
    assert "### Instruction:\nTranslate to French" in rendered
    assert "### Input:\nhello world" in rendered
    assert "### Response:\nbonjour le monde" in rendered


def test_train_local_alpaca_formatter_without_input_skips_input_block() -> None:
    mod = _import_train_local()
    rendered = mod._format_alpaca_example(  # type: ignore[attr-defined]
        {"instruction": "Say hi", "input": "", "output": "hi"}
    )
    assert "### Input:" not in rendered
    assert rendered.startswith("### Instruction:\nSay hi")
    assert rendered.endswith("### Response:\nhi")


# ---------------------------------------------------------------------------
# train_hf_jobs.py helpers
# ---------------------------------------------------------------------------


def _import_train_hf_jobs() -> object:
    return _load_module("demo_train_hf_jobs", TRAIN_HF_JOBS)


def test_train_hf_jobs_build_script_args_round_trip() -> None:
    mod = _import_train_hf_jobs()
    args = mod.JobsArgs(  # type: ignore[attr-defined]
        model_base="m/m",
        dataset="d/d",
        lora_rank=16,
        epochs=3,
        lr=1e-4,
        batch_size=4,
        output_dir="/tmp/out",
        run_uid="cafe",
        quick=False,
        push_to_hub="user/repo",
        flavor="cpu-basic",
        timeout="30m",
        script_url="https://example.com/train_local.py",
    )
    flags = mod._build_script_args(args)  # type: ignore[attr-defined]
    assert "--lora-rank" in flags and flags[flags.index("--lora-rank") + 1] == "16"
    assert "--push-to-hub" in flags and flags[flags.index("--push-to-hub") + 1] == "user/repo"
    assert "--quick" not in flags  # quick is False here


def test_train_hf_jobs_build_script_args_quick_appends_flag() -> None:
    mod = _import_train_hf_jobs()
    args = mod.JobsArgs(  # type: ignore[attr-defined]
        model_base="m/m",
        dataset="d/d",
        lora_rank=4,
        epochs=1,
        lr=1e-4,
        batch_size=4,
        output_dir="/tmp/out",
        run_uid="cafe",
        quick=True,
        push_to_hub=None,
        flavor="cpu-basic",
        timeout="10m",
        script_url="x",
    )
    flags = mod._build_script_args(args)  # type: ignore[attr-defined]
    assert "--quick" in flags
    assert "--push-to-hub" not in flags


def test_train_hf_jobs_extract_final_loss_line_matches_run_uid() -> None:
    mod = _import_train_hf_jobs()
    logs = "\n".join(
        [
            "INFO loading base model",
            "step 1 loss=2.5",
            json.dumps({"final_loss": 0.99, "checkpoint_dir": "/tmp/x", "run_uid": "wrong"}),
            "step 2 loss=2.0",
            json.dumps({"final_loss": 0.42, "checkpoint_dir": "/tmp/x", "run_uid": "right"}),
            "INFO done",
        ]
    )
    line = mod._extract_final_loss_line(logs, "right")  # type: ignore[attr-defined]
    payload = json.loads(line)
    assert payload["final_loss"] == 0.42
    assert payload["run_uid"] == "right"


def test_train_hf_jobs_extract_final_loss_line_raises_when_missing() -> None:
    mod = _import_train_hf_jobs()
    with pytest.raises(RuntimeError, match="Could not find the final-loss"):
        mod._extract_final_loss_line(  # type: ignore[attr-defined]
            "junk logs with no json", "any-uid"
        )


# ---------------------------------------------------------------------------
# Integration smoke (opt-in, requires demo extras)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("PYTEST_INTEGRATION"),
    reason="set PYTEST_INTEGRATION=1 to exercise the local training path",
)
def test_train_local_quick_smoke(tmp_path: Path) -> None:
    """Smoke: run train_local.py in quick mode, parse the JSON line.

    This is an explicit opt-in: it downloads the SmolLM2-135M model and a
    slice of the Alpaca dataset, runs one epoch, and asserts the contract
    line ends up on stdout. Requires ``uv sync --extra demo`` and ~1 minute
    on Apple Silicon.
    """
    out_dir = tmp_path / "adapter"
    completed = subprocess.run(
        [
            "uv",
            "run",
            "python",
            str(TRAIN_LOCAL),
            "--lora-rank",
            "4",
            "--output-dir",
            str(out_dir),
            "--run-uid",
            "smokeuid",
            "--quick",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=600,
        check=True,
    )
    last_line = completed.stdout.strip().splitlines()[-1]
    payload = json.loads(last_line)
    assert "final_loss" in payload
    assert payload["run_uid"] == "smokeuid"
    assert Path(payload["checkpoint_dir"]).is_dir()
