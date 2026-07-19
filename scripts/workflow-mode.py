#!/usr/bin/env python3
"""Codex hook runtime for a repository's persisted workflow mode."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any


MODE_PATH = Path(".gauntlet") / "workflow-mode"
VALID_MODE_BYTES = {
    "gauntlet": b"gauntlet\n",
    "scratch": b"scratch\n",
}

ADDITIVE_CONTEXT = (
    "This workflow-mode context supplements all applicable AGENTS.md instructions; "
    "continue to follow them and do not replace or ignore them."
)

GAUNTLET_CONTEXT = (
    "Workflow mode: Gauntlet. Follow the applicable Gauntlet workflow for work in "
    "this repository, including the proof required by that workflow. "
    + ADDITIVE_CONTEXT
)

SCRATCH_CONTEXT = (
    "Workflow mode: Scratch. Perform only the work the user explicitly requested. "
    "Do not run tests, linters, builds, smoke checks, or Gauntlet workflow steps "
    "unless the user explicitly requests them for this individual request. If you "
    "make or report changes without verification, explicitly disclose that they "
    "are unverified. The user may opt into Gauntlet steps for an individual request; "
    "treat that opt-in as request-scoped and do not modify .gauntlet/workflow-mode. "
    + ADDITIVE_CONTEXT
)

READ_ONLY_TOOL_VERBS = {
    "fetch",
    "find",
    "finance",
    "get",
    "inspect",
    "list",
    "open",
    "query",
    "read",
    "screenshot",
    "search",
    "sports",
    "stat",
    "time",
    "view",
    "weather",
}
NON_REPOSITORY_WRITE_TOOLS = {
    "request_user_input",
    "wait_agent",
}


def git_root(cwd: object) -> Path | None:
    """Return the active Git root for cwd, ignoring ambient Git overrides."""
    if not isinstance(cwd, str) or not cwd:
        return None

    environment = os.environ.copy()
    for name in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_COMMON_DIR",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
    ):
        environment.pop(name, None)

    try:
        completed = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            env=environment,
        )
    except (OSError, ValueError):
        return None
    if completed.returncode != 0:
        return None

    raw_root = completed.stdout.rstrip(b"\r\n")
    if not raw_root:
        return None
    return Path(os.fsdecode(raw_root)).resolve()


def mode_state(root: Path) -> tuple[str | None, bool]:
    """Return (mode, exists); mode is None unless bytes match exactly."""
    declaration = root / MODE_PATH
    try:
        content = declaration.read_bytes()
    except FileNotFoundError:
        return None, False
    except OSError:
        return None, True

    for mode, expected in VALID_MODE_BYTES.items():
        if content == expected:
            return mode, True
    return None, True


def session_context(mode: str | None, declaration_exists: bool) -> str:
    if mode == "gauntlet":
        return GAUNTLET_CONTEXT
    if mode == "scratch":
        return SCRATCH_CONTEXT

    state = "invalid" if declaration_exists else "missing"
    script = shlex.join([sys.executable, str(Path(__file__).resolve())])
    return (
        f"No valid repository workflow mode is declared; "
        f".gauntlet/workflow-mode is {state}. Before making any local write, ask "
        'exactly: "Which workflow should this repository use by default: Gauntlet '
        'or Scratch?" After the user chooses, use only '
        f"`{script} bootstrap gauntlet` or `{script} bootstrap scratch` to persist "
        "the exact repository-owned declaration. It is intended to be committed and "
        "shared with collaborators. Read-only inspection may continue while waiting. "
        + ADDITIVE_CONTEXT
    )


def session_output(context: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }


def denial_output() -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "Local writes are blocked until this Git repository has a valid "
                "repository workflow mode declaration at .gauntlet/workflow-mode. "
                "Ask the user to choose Gauntlet or Scratch, then use the validated "
                "workflow-mode bootstrap command shown in the SessionStart context."
            ),
        }
    }


def is_read_only_tool(tool_name: object) -> bool:
    if not isinstance(tool_name, str) or not tool_name:
        return False
    normalized = tool_name.casefold()
    if normalized in NON_REPOSITORY_WRITE_TOOLS:
        return True
    leaf = normalized.rsplit("__", 1)[-1]
    verb = leaf.split("_", 1)[0]
    return verb in READ_ONLY_TOOL_VERBS


def is_exact_bootstrap(tool_name: object, tool_input: object) -> bool:
    if tool_name != "Bash" or not isinstance(tool_input, dict):
        return False
    command = tool_input.get("command")
    if not isinstance(command, str):
        return False
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return False
    if len(tokens) != 4:
        return False

    python_name = Path(tokens[0]).name
    if not (
        python_name == "python"
        or python_name == "python3"
        or python_name.startswith("python3.")
    ):
        return False
    try:
        script_matches = Path(tokens[1]).resolve() == Path(__file__).resolve()
    except OSError:
        return False
    return (
        script_matches
        and tokens[2] == "bootstrap"
        and tokens[3] in VALID_MODE_BYTES
    )


def run_hook(payload: object) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    root = git_root(payload.get("cwd"))
    if root is None:
        return None

    event = payload.get("hook_event_name")
    mode, declaration_exists = mode_state(root)
    if event == "SessionStart":
        return session_output(session_context(mode, declaration_exists))
    if event != "PreToolUse" or mode is not None:
        return None

    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if is_exact_bootstrap(tool_name, tool_input) or is_read_only_tool(tool_name):
        return None
    return denial_output()


def bootstrap(mode: str) -> int:
    if mode not in VALID_MODE_BYTES:
        print("mode must be exactly 'gauntlet' or 'scratch'", file=sys.stderr)
        return 2

    root = git_root(os.getcwd())
    if root is None:
        print("workflow mode can only be set inside a Git repository", file=sys.stderr)
        return 2

    directory = root / MODE_PATH.parent
    declaration = root / MODE_PATH
    try:
        if directory.is_symlink() or declaration.is_symlink():
            raise OSError("refusing to write through a symbolic link")
        directory.mkdir(mode=0o755, exist_ok=True)
        if not directory.is_dir() or directory.resolve() != (root / ".gauntlet"):
            raise OSError(".gauntlet is not a repository-local directory")
        declaration.write_bytes(VALID_MODE_BYTES[mode])
    except OSError as error:
        print(f"could not set workflow mode: {error}", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str]) -> int:
    if argv:
        if len(argv) == 2 and argv[0] == "bootstrap":
            return bootstrap(argv[1])
        print("usage: workflow-mode.py bootstrap {gauntlet|scratch}", file=sys.stderr)
        return 2

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0

    output = run_hook(payload)
    if output is not None:
        json.dump(output, sys.stdout, sort_keys=True, separators=(",", ":"))
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
