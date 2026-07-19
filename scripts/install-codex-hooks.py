#!/usr/bin/env python3
"""Preservation-safe installer for Gauntlet-owned global Codex hooks."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile


OWNERSHIP_MARKER = "Gauntlet repository workflow mode"
HOOK_SPECS = {
    "SessionStart": "startup|resume|clear|compact",
    "PreToolUse": ".*",
}


class HookStateError(ValueError):
    """Existing hook state cannot be changed without risking user-owned hooks."""


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def expected_group(runtime: Path, matcher: str) -> dict:
    command = shlex.join(["python3", str(runtime)])
    return {
        "matcher": matcher,
        "hooks": [
            {
                "type": "command",
                "command": command,
                "async": False,
                "timeout": 10,
                "statusMessage": OWNERSHIP_MARKER,
            }
        ],
    }


def load_payload(path: Path) -> tuple[dict, bytes]:
    if path.is_symlink():
        raise HookStateError(f"Refusing symbolic link for Codex hooks: {path}")
    if not path.exists():
        return {"hooks": {}}, b""
    if not path.is_file():
        raise HookStateError(f"Codex hooks path must be a regular file: {path}")
    data = path.read_bytes()
    try:
        payload = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HookStateError(f"Codex hooks contain malformed JSON at {path}: {error}") from error
    if not isinstance(payload, dict):
        raise HookStateError("Codex hooks top level must be an object")
    if "hooks" not in payload:
        payload["hooks"] = {}
    elif not isinstance(payload["hooks"], dict):
        raise HookStateError("Codex hooks field must be an object")
    return payload, data


def validate_shape(payload: dict) -> None:
    for event, groups in payload["hooks"].items():
        if not isinstance(event, str):
            raise HookStateError("Codex hook event names must be strings")
        if not isinstance(groups, list):
            raise HookStateError(f"Codex hook event {event} must be an array")
        for group_index, group in enumerate(groups):
            if not isinstance(group, dict):
                raise HookStateError(
                    f"Codex hook group {event}[{group_index}] must be an object"
                )
            handlers = group.get("hooks")
            if not isinstance(handlers, list):
                raise HookStateError(
                    f"Codex hook group {event}[{group_index}].hooks must be an array"
                )
            for handler_index, handler in enumerate(handlers):
                if not isinstance(handler, dict):
                    raise HookStateError(
                        f"Codex hook handler {event}[{group_index}][{handler_index}] "
                        "must be an object"
                    )


def owned_locations(payload: dict) -> list[tuple[str, int]]:
    locations = []
    for event, groups in payload["hooks"].items():
        for group_index, group in enumerate(groups):
            markers = sum(
                handler.get("statusMessage") == OWNERSHIP_MARKER
                for handler in group["hooks"]
            )
            if markers:
                if markers != 1:
                    raise HookStateError(
                        f"Codex hooks contain duplicate {OWNERSHIP_MARKER} handlers"
                    )
                locations.append((event, group_index))
    return locations


def inspect_owned(payload: dict, runtime: Path) -> dict[str, int]:
    locations = owned_locations(payload)
    found: dict[str, int] = {}
    for event, group_index in locations:
        if event not in HOOK_SPECS:
            raise HookStateError(
                f"Codex hooks contain a modified {OWNERSHIP_MARKER} group under {event}"
            )
        if event in found:
            raise HookStateError(
                f"Codex hooks contain duplicate {OWNERSHIP_MARKER} groups for {event}"
            )
        expected = expected_group(runtime, HOOK_SPECS[event])
        if payload["hooks"][event][group_index] != expected:
            raise HookStateError(
                f"Codex hooks contain a modified {OWNERSHIP_MARKER} group for {event}"
            )
        found[event] = group_index
    return found


def atomic_write(path: Path, rendered: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def command_check(path: Path, runtime: Path) -> int:
    payload, _ = load_payload(path)
    validate_shape(payload)
    inspect_owned(payload, runtime)
    return 0


def command_apply(path: Path, runtime: Path) -> int:
    payload, data = load_payload(path)
    validate_shape(payload)
    found = inspect_owned(payload, runtime)
    for event, matcher in HOOK_SPECS.items():
        if event in found:
            continue
        payload["hooks"].setdefault(event, []).append(expected_group(runtime, matcher))
    rendered = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if data == rendered:
        return 0
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    atomic_write(path, rendered, mode)
    return 0


def command_verify(path: Path, runtime: Path) -> int:
    payload, _ = load_payload(path)
    validate_shape(payload)
    found = inspect_owned(payload, runtime)
    missing = [event for event in HOOK_SPECS if event not in found]
    if missing:
        fail(f"missing_codex_hook: missing Gauntlet-owned hooks: {', '.join(missing)}")
    return 0


def command_remove(path: Path, runtime: Path) -> int:
    payload, data = load_payload(path)
    validate_shape(payload)
    locations = owned_locations(payload)
    if not locations:
        return 0
    removed = False
    for event, group_index in sorted(locations, reverse=True):
        expected = (
            expected_group(runtime, HOOK_SPECS[event])
            if event in HOOK_SPECS
            else None
        )
        if expected is not None and payload["hooks"][event][group_index] == expected:
            payload["hooks"][event].pop(group_index)
            removed = True
        else:
            print(
                f"Gauntlet installer finding: preserved modified managed Codex hook: "
                f"{event}[{group_index}]",
                file=sys.stderr,
            )
    if not removed:
        return 0
    rendered = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if data == rendered:
        return 0
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    atomic_write(path, rendered, mode)
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=["check", "apply", "verify", "check-remove", "remove"]
    )
    parser.add_argument("--agent-home", required=True)
    parser.add_argument("--runtime", required=True)
    args = parser.parse_args(argv)
    agent_home = Path(args.agent_home).expanduser().absolute()
    runtime = Path(args.runtime).expanduser()
    if not runtime.is_absolute():
        fail("Gauntlet hook runtime path must be absolute")
    path = agent_home / "hooks.json"
    try:
        if args.command == "check":
            return command_check(path, runtime)
        if args.command == "apply":
            return command_apply(path, runtime)
        if args.command == "check-remove":
            payload, _ = load_payload(path)
            validate_shape(payload)
            owned_locations(payload)
            return 0
        if args.command == "remove":
            return command_remove(path, runtime)
        return command_verify(path, runtime)
    except (OSError, HookStateError) as error:
        fail(str(error))
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
