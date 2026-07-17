#!/usr/bin/env python3
"""Launch Codex CLI or Claude Code through one trusted evaluation adapter."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from gauntletlib.core.jsonio import canonical_json, pretty_json
from gauntletlib.core.jsonio import read_json as _read_json


SCHEMA_VERSION = 1
HARNESS_KINDS = ("codex-cli", "claude-code")
EQUIVALENCE_DIMENSIONS = (
    "single-agent",
    "custom-profile",
    "nested-agent",
    "concurrent-lanes",
    "resume-interrupt",
    "permission",
    "pty",
    "timeout",
    "artifact",
    "telemetry",
    "failure",
)
SAFE_BASE_ENV = {"HOME", "LANG", "LC_ALL", "PATH", "SYSTEMROOT", "TEMP", "TMP", "TMPDIR"}
SECRET_MARKERS = ("KEY", "PASSWORD", "SECRET", "TOKEN", "CREDENTIAL")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
HEX = set("0123456789abcdef")
MAX_EVENT_BYTES = 10 * 1024 * 1024


class HarnessError(Exception):
    pass


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode()).hexdigest()


def tree_digest(root: Path) -> str:
    """Match eval-task.py's canonical names, modes, and contents digest."""
    reject_symlinks(root)
    root = root.resolve()
    records: list[bytes] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            records.append(f"d\0{relative}\0".encode())
        elif path.is_file():
            contents = path.read_bytes()
            mode = path.stat().st_mode & 0o777
            records.append(f"f\0{relative}\0{mode:o}\0{len(contents)}\0".encode() + contents)
        else:
            raise HarnessError(f"unsupported starting-tree entry: {relative}")
    return "sha256:" + hashlib.sha256(b"".join(records)).hexdigest()


def read_json(path: Path, label: str) -> Any:
    try:
        return _read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        raise HarnessError(f"cannot read {label} {path}: {exc}") from exc


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HarnessError(f"{label} must be an object")
    return value


def require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HarnessError(f"{label} must be a non-empty string")
    return value.strip()


def require_command(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item for item in value):
        raise HarnessError(f"{label} must be a non-empty string list")
    return list(value)


def require_absolute(value: Any, label: str, *, directory: bool | None = None) -> Path:
    path = Path(require_string(value, label))
    if not path.is_absolute():
        raise HarnessError(f"{label} must be absolute")
    if directory is True and not path.is_dir():
        raise HarnessError(f"{label} must be an existing directory")
    if directory is False and not path.is_file():
        raise HarnessError(f"{label} must be an existing file")
    return path


def validate_manifest(raw: Any) -> dict[str, Any]:
    manifest = require_object(raw, "harness manifest")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise HarnessError("harness manifest schema_version must be 1")
    harness_id = require_string(manifest.get("harness_id"), "harness_id")
    kind = manifest.get("kind")
    if kind not in HARNESS_KINDS:
        raise HarnessError(f"kind must be one of {', '.join(HARNESS_KINDS)}")
    executable = require_command(manifest.get("executable"), "executable")
    if not Path(executable[0]).is_absolute():
        raise HarnessError("executable[0] must be an absolute version-pinned path")
    model = require_string(manifest.get("model"), "model")
    if model == "SET_ME" or "{{" in model:
        raise HarnessError("model must be resolved before use")
    version_pin = require_string(manifest.get("version_pin"), "version_pin")
    permission_mode = require_string(manifest.get("permission_mode"), "permission_mode")
    effort = manifest.get("reasoning_effort")
    if effort is not None:
        effort = require_string(effort, "reasoning_effort")
    max_turns = manifest.get("max_turns")
    if max_turns is not None and (
        not isinstance(max_turns, int) or isinstance(max_turns, bool) or not 1 <= max_turns <= 100
    ):
        raise HarnessError("max_turns must be null or an integer from 1 to 100")
    extra_args = manifest.get("extra_args", [])
    if not isinstance(extra_args, list) or any(not isinstance(item, str) or not item for item in extra_args):
        raise HarnessError("extra_args must be a string list")
    if extra_args:
        raise HarnessError("extra_args are not accepted in schema version 1; add matched typed fields instead")
    inherit_env = manifest.get("inherit_env", [])
    if not isinstance(inherit_env, list) or any(not isinstance(item, str) or not item for item in inherit_env):
        raise HarnessError("inherit_env must be a string list")
    profiles = require_object(manifest.get("profiles"), "profiles")
    if set(profiles) != {"baseline", "treatment"}:
        raise HarnessError("profiles must contain exactly baseline and treatment")
    normalized_profiles = {}
    for profile_name, raw_profile in profiles.items():
        profile = require_object(raw_profile, f"profiles.{profile_name}")
        environment = require_object(profile.get("environment", {}), f"profiles.{profile_name}.environment")
        normalized_environment = {}
        for key, value in environment.items():
            if not isinstance(key, str) or not key or not isinstance(value, str):
                raise HarnessError(f"profiles.{profile_name}.environment must contain string pairs")
            if any(marker in key.upper() for marker in SECRET_MARKERS):
                raise HarnessError(f"profiles.{profile_name}.environment cannot store secret-like values; inherit {key} by name")
            normalized_environment[key] = value
        normalized_profiles[profile_name] = {"environment": normalized_environment}
    home_key = "CODEX_HOME" if kind == "codex-cli" else "CLAUDE_CONFIG_DIR"
    profile_homes = []
    for profile_name in ("baseline", "treatment"):
        value = normalized_profiles[profile_name]["environment"].get(home_key)
        if not isinstance(value, str) or not Path(value).is_absolute() or "{{" in value:
            raise HarnessError(f"profiles.{profile_name}.environment.{home_key} must be a resolved absolute path")
        profile_homes.append(value)
    if profile_homes[0] == profile_homes[1]:
        raise HarnessError(f"baseline and treatment must use different {home_key} paths")
    left_environment = normalized_profiles["baseline"]["environment"]
    right_environment = normalized_profiles["treatment"]["environment"]
    if set(left_environment) != set(right_environment):
        raise HarnessError("baseline and treatment profile environment keys must match")
    for key in left_environment:
        if key in (home_key, "GAUNTLET_EVAL_PROFILE"):
            continue
        if left_environment[key] != right_environment[key]:
            raise HarnessError(f"baseline and treatment environment value for {key} must match")
    capabilities = require_object(manifest.get("capabilities"), "capabilities")
    if set(capabilities) != set(EQUIVALENCE_DIMENSIONS):
        raise HarnessError("capabilities must declare every adapter-equivalence dimension")
    if any(value not in ("required", "unsupported", "not-applicable") for value in capabilities.values()):
        raise HarnessError("capability values must be required, unsupported, or not-applicable")
    if kind == "codex-cli" and permission_mode not in ("read-only", "workspace-write", "danger-full-access"):
        raise HarnessError("Codex permission_mode must be read-only, workspace-write, or danger-full-access")
    if kind == "codex-cli" and max_turns is not None:
        raise HarnessError("Codex max_turns must be null because the direct CLI adapter has no typed turn-cap flag")
    if kind == "claude-code" and permission_mode not in ("default", "acceptEdits", "plan", "bypassPermissions"):
        raise HarnessError("Claude permission_mode must be default, acceptEdits, plan, or bypassPermissions")
    if kind == "claude-code" and effort is not None:
        raise HarnessError("Claude reasoning_effort must be null until the direct CLI adapter has a typed effort flag")
    return {
        "capabilities": dict(sorted(capabilities.items())),
        "executable": executable,
        "extra_args": extra_args,
        "harness_id": harness_id,
        "inherit_env": sorted(set(inherit_env)),
        "kind": kind,
        "max_turns": max_turns,
        "model": model,
        "permission_mode": permission_mode,
        "profiles": normalized_profiles,
        "reasoning_effort": effort,
        "schema_version": SCHEMA_VERSION,
        "version_pin": version_pin,
    }


def validate_task_registry(raw: Any) -> dict[str, dict[str, Any]]:
    registry = require_object(raw, "trusted task registry")
    if registry.get("schema_version") != SCHEMA_VERSION:
        raise HarnessError("trusted task registry schema_version must be 1")
    tasks = require_object(registry.get("tasks"), "trusted task registry.tasks")
    output = {}
    for task_id, raw_task in tasks.items():
        if not isinstance(task_id, str) or not SAFE_ID.fullmatch(task_id):
            raise HarnessError("task IDs must be safe stable identifiers")
        if task_id.startswith("CORE-"):
            raise HarnessError("core tasks remain sealed and cannot enter the harness registry")
        task = require_object(raw_task, f"task {task_id}")
        state_digest = require_string(task.get("state_digest"), f"task {task_id}.state_digest")
        if (
            not state_digest.startswith("sha256:") or len(state_digest) != 71
            or any(character not in HEX for character in state_digest[7:])
        ):
            raise HarnessError(f"task {task_id}.state_digest must be a full sha256 digest")
        artifact_allowlist = task.get("artifact_allowlist", [])
        if not isinstance(artifact_allowlist, list):
            raise HarnessError(f"task {task_id}.artifact_allowlist must be a list")
        output[task_id] = {
            "artifact_allowlist": list(artifact_allowlist),
            "prompt_file": require_absolute(task.get("prompt_file"), f"task {task_id}.prompt_file", directory=False),
            "score_command": require_command(task.get("score_command"), f"task {task_id}.score_command"),
            "starting_tree": require_absolute(task.get("starting_tree"), f"task {task_id}.starting_tree", directory=True),
            "state_digest": state_digest,
        }
        if not Path(output[task_id]["score_command"][0]).is_absolute():
            raise HarnessError(f"task {task_id}.score_command[0] must be absolute")
        if tree_digest(output[task_id]["starting_tree"]) != state_digest:
            raise HarnessError(f"task {task_id}.state_digest does not match its starting tree")
        if any(not isinstance(item, str) or not item or Path(item).is_absolute() or ".." in Path(item).parts for item in output[task_id]["artifact_allowlist"]):
            raise HarnessError(f"task {task_id}.artifact_allowlist must contain safe relative paths")
    return output


def build_command(manifest: dict[str, Any], workspace: Path) -> list[str]:
    command = list(manifest["executable"])
    if manifest["kind"] == "codex-cli":
        command.extend([
            "exec", "--json", "--ephemeral", "--model", manifest["model"],
            "--sandbox", manifest["permission_mode"], "--cd", str(workspace),
        ])
        if manifest["reasoning_effort"]:
            command.extend(["-c", f'model_reasoning_effort="{manifest["reasoning_effort"]}"'])
        command.extend(["-c", 'approval_policy="never"'])
    else:
        command.extend([
            "-p", "--output-format", "stream-json", "--verbose", "--model", manifest["model"],
            "--permission-mode", manifest["permission_mode"],
        ])
        if manifest["max_turns"] is not None:
            command.extend(["--max-turns", str(manifest["max_turns"])])
    command.extend(manifest["extra_args"])
    return command


def runtime_environment(manifest: dict[str, Any], profile: str) -> dict[str, str]:
    allowed = SAFE_BASE_ENV | set(manifest["inherit_env"])
    environment = {key: value for key, value in os.environ.items() if key in allowed}
    environment.update(manifest["profiles"][profile]["environment"])
    return environment


def run_bounded(
    command: list[str], *, timeout: float, input_value: str | None = None, cwd: Path | None = None,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command, stdin=subprocess.PIPE if input_value is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd, env=environment,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(input=input_value, timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            if hasattr(os, "killpg"):
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass
        process.communicate()
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def parse_json_lines(value: str) -> list[dict[str, Any]]:
    events = []
    for number, line in enumerate(value.splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise HarnessError(f"event stream line {number} is not JSON") from exc
        events.append(require_object(item, f"event stream line {number}"))
    if not events:
        raise HarnessError("event stream is empty")
    return events


def numeric_metrics(value: Any, prefix: str = "") -> dict[str, float]:
    output = {}
    if isinstance(value, dict):
        for key, item in value.items():
            name = f"{prefix}_{key}" if prefix else str(key)
            if isinstance(item, (int, float)) and not isinstance(item, bool):
                if not math.isfinite(item):
                    raise HarnessError(f"metric {name} must be finite")
                output[name] = float(item)
            elif isinstance(item, dict):
                output.update(numeric_metrics(item, name))
    return output


def normalize_events(manifest: dict[str, Any], stdout: str) -> dict[str, Any]:
    events = parse_json_lines(stdout)
    metrics: dict[str, float] = {}
    observed_model = None
    observed_permission = None
    session_recorded = False
    tools: list[str] = []
    result_status = "completed"
    if manifest["kind"] == "codex-cli":
        for event in events:
            event_type = event.get("type")
            if event_type == "thread.started" and isinstance(event.get("thread_id"), str):
                session_recorded = True
            if event_type in ("turn.completed", "turn.failed"):
                result_status = "failed" if event_type == "turn.failed" else "completed"
                metrics.update(numeric_metrics(event.get("usage", {})))
            if isinstance(event.get("model"), str):
                observed_model = event["model"]
            if isinstance(event.get("permission_mode"), str):
                observed_permission = event["permission_mode"]
            if isinstance(event.get("tools"), list):
                tools = sorted(str(item) for item in event["tools"])
    else:
        for event in events:
            if event.get("type") == "system" and event.get("subtype") == "init":
                session_recorded = isinstance(event.get("session_id"), str)
                observed_model = event.get("model") if isinstance(event.get("model"), str) else None
                observed_permission = event.get("permissionMode") if isinstance(event.get("permissionMode"), str) else None
                if isinstance(event.get("tools"), list):
                    tools = sorted(str(item) for item in event["tools"])
            if event.get("type") == "result":
                result_status = "failed" if event.get("is_error") else "completed"
                metrics.update(numeric_metrics(event))
    if observed_model is not None and observed_model != manifest["model"]:
        raise HarnessError(
            f'harness reported model {observed_model!r}, expected the pinned model {manifest["model"]!r}'
        )
    if observed_permission is not None and observed_permission != manifest["permission_mode"]:
        raise HarnessError(
            "harness reported a permission mode that differs from the requested manifest"
        )
    return {
        "metrics": dict(sorted(metrics.items())),
        "telemetry": {
            "event_count": len(events),
            "harness": manifest["kind"],
            "model_observed": observed_model,
            "model_requested": manifest["model"],
            "permission_mode_observed": observed_permission,
            "permission_mode_requested": manifest["permission_mode"],
            "reasoning_effort_requested": manifest["reasoning_effort"],
            "result_status": result_status,
            "session_recorded": session_recorded,
            "tool_names": tools,
        },
    }


def probe(manifest: dict[str, Any], timeout: float) -> dict[str, Any]:
    started = time.monotonic()
    try:
        result = run_bounded(
            [*manifest["executable"], "--version"], environment=runtime_environment(manifest, "baseline"),
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "error": type(exc).__name__, "harness_id": manifest["harness_id"], "schema_version": 1}
    version = (result.stdout or result.stderr).strip().splitlines()
    observed = version[0][:300] if version else ""
    return {
        "available": result.returncode == 0 and manifest["version_pin"] in observed,
        "duration_ms": round((time.monotonic() - started) * 1000, 3),
        "exit_code": result.returncode,
        "harness_id": manifest["harness_id"],
        "schema_version": SCHEMA_VERSION,
        "version": observed,
        "version_pin": manifest["version_pin"],
    }


def reject_symlinks(root: Path) -> None:
    if any(path.is_symlink() for path in root.rglob("*")):
        raise HarnessError("starting tree cannot contain symlinks")


def collect_safe_artifacts(candidate: Path, allowlist: list[str]) -> list[str]:
    candidate = candidate.resolve()
    artifacts = []
    for item in allowlist:
        path = candidate / item
        if not path.exists():
            continue
        relative = Path(item)
        if any((candidate / Path(*relative.parts[:index])).is_symlink() for index in range(1, len(relative.parts) + 1)):
            continue
        try:
            path.resolve(strict=True).relative_to(candidate)
        except (OSError, ValueError):
            continue
        if path.is_file():
            artifacts.append(item)
    return sorted(artifacts)


def run_score(command: list[str], task_id: str, candidate: Path, timeout: float) -> str:
    request = {"candidate": str(candidate), "op": "score", "task_id": task_id}
    try:
        result = run_bounded(
            command, input_value=canonical_json(request) + "\n",
            environment={key: value for key, value in os.environ.items() if key in SAFE_BASE_ENV}, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HarnessError(f"score command failed to start: {type(exc).__name__}") from exc
    if result.returncode != 0:
        raise HarnessError(f"score command exited {result.returncode}")
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise HarnessError("score command returned malformed JSON") from exc
    passed = require_object(raw, "score result").get("passed")
    if not isinstance(passed, bool):
        raise HarnessError("score result.passed must be boolean")
    return "pass" if passed else "implementation_failure"


def execute_adapter(
    manifest: dict[str, Any], tasks: dict[str, dict[str, Any]], workspace_root: Path, request: Any, timeout: float
) -> dict[str, Any]:
    request = require_object(request, "adapter request")
    if request.get("op") != "execute":
        raise HarnessError("harness adapter accepts only execute requests")
    task_id = require_string(request.get("task_id"), "task_id")
    task = tasks.get(task_id)
    if task is None:
        raise HarnessError(f"task {task_id} is not in the trusted harness registry")
    if request.get("state_digest") != task["state_digest"]:
        raise HarnessError("request starting state does not match the trusted task registry")
    package = require_object(request.get("package"), "package")
    profile = package.get("profile")
    if profile not in ("baseline", "treatment"):
        raise HarnessError("package.profile must be baseline or treatment")
    execution_id = require_string(request.get("execution_id"), "execution_id")
    if not SAFE_ID.fullmatch(execution_id) or execution_id in (".", ".."):
        raise HarnessError("execution_id must be a safe stable identifier")
    workspace_root = workspace_root.resolve()
    candidate = workspace_root / execution_id
    if candidate.exists():
        raise HarnessError("candidate workspace already exists; selective rerun is forbidden")
    reject_symlinks(task["starting_tree"])
    workspace_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(task["starting_tree"], candidate)
    prompt = task["prompt_file"].read_text(encoding="utf-8")
    environment = runtime_environment(manifest, profile)
    command = build_command(manifest, candidate)
    started = time.monotonic()
    try:
        completed = run_bounded(
            command, input_value=prompt, cwd=candidate, environment=environment, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise HarnessError("harness timed out") from exc
    except OSError as exc:
        raise HarnessError(f"harness could not start: {exc}") from exc
    duration_ms = (time.monotonic() - started) * 1000
    if completed.returncode == 0:
        if len(completed.stdout.encode()) + len(completed.stderr.encode()) > MAX_EVENT_BYTES:
            raise HarnessError("harness event stream exceeds the bounded adapter limit")
        normalized = normalize_events(manifest, completed.stdout)
        outcome = run_score(task["score_command"], task_id, candidate, timeout)
    else:
        normalized = {"metrics": {}, "telemetry": {
            "event_count": 0, "harness": manifest["kind"], "model_observed": None,
            "model_requested": manifest["model"], "permission_mode_observed": None,
            "permission_mode_requested": manifest["permission_mode"],
            "reasoning_effort_requested": manifest["reasoning_effort"], "result_status": "failed",
            "session_recorded": False, "tool_names": [],
        }}
        outcome = "implementation_failure"
    artifacts = collect_safe_artifacts(candidate, task["artifact_allowlist"])
    metrics = {**normalized["metrics"], "duration_ms": duration_ms}
    telemetry = {**normalized["telemetry"], "adapter_manifest_digest": digest(manifest), "cli_exit_code": completed.returncode}
    return {"artifacts": sorted(artifacts), "metrics": metrics, "outcome": outcome, "telemetry": telemetry}


def protocol_observation(request: Any) -> dict[str, Any]:
    request = require_object(request, "adapter-equivalence request")
    if request.get("op") != "conformance":
        raise HarnessError("adapter-equivalence fixture request has an invalid operation")
    dimension = require_string(request.get("dimension"), "dimension")
    if dimension not in EQUIVALENCE_DIMENSIONS:
        raise HarnessError(f"unknown adapter-equivalence dimension {dimension}")
    fixture = require_object(request.get("fixture"), "fixture")
    return {"dimension": dimension, "observation": fixture}


def aa_compare(left: Any, right: Any) -> dict[str, Any]:
    left = require_object(left, "left A/A observation")
    right = require_object(right, "right A/A observation")
    for field in (
        "harness", "harness_version", "model", "reasoning_effort", "permission_mode", "resource_profile"
    ):
        if left.get(field) != right.get(field):
            raise HarnessError(f"A/A requires the same {field}; cross-harness or cross-model runs are separate study blocks")
    left_observations = require_object(left.get("observations"), "left observations")
    right_observations = require_object(right.get("observations"), "right observations")
    if set(left_observations) != set(EQUIVALENCE_DIMENSIONS) or set(right_observations) != set(EQUIVALENCE_DIMENSIONS):
        raise HarnessError("A/A observations must cover every adapter-equivalence dimension")
    comparisons = []
    mismatches = []
    for dimension in EQUIVALENCE_DIMENSIONS:
        passed = left_observations[dimension] == right_observations[dimension]
        comparisons.append({"dimension": dimension, "left": left_observations[dimension], "passed": passed, "right": right_observations[dimension]})
        if not passed:
            mismatches.append(dimension)
    return {
        "comparisons": comparisons,
        "dimensions": list(EQUIVALENCE_DIMENSIONS),
        "left_digest": digest(left),
        "mismatches": mismatches,
        "right_digest": digest(right),
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if not mismatches else "fail",
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--manifest", required=True, type=Path)
    command = commands.add_parser("command")
    command.add_argument("--manifest", required=True, type=Path); command.add_argument("--workspace", required=True, type=Path)
    probe_cmd = commands.add_parser("probe")
    probe_cmd.add_argument("--manifest", required=True, type=Path); probe_cmd.add_argument("--timeout", type=float, default=10)
    normalize = commands.add_parser("normalize")
    normalize.add_argument("--manifest", required=True, type=Path); normalize.add_argument("--events", required=True, type=Path)
    adapter = commands.add_parser("adapter")
    adapter.add_argument("--manifest", required=True, type=Path); adapter.add_argument("--tasks", required=True, type=Path)
    adapter.add_argument("--workspace-root", required=True, type=Path); adapter.add_argument("--timeout", type=float, default=300)
    compare = commands.add_parser("aa-compare")
    compare.add_argument("--left", required=True, type=Path); compare.add_argument("--right", required=True, type=Path)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "aa-compare":
            result = aa_compare(read_json(args.left, "left observation"), read_json(args.right, "right observation"))
        else:
            manifest = validate_manifest(read_json(args.manifest, "harness manifest"))
            if args.command == "validate":
                result = {"manifest_digest": digest(manifest), "status": "pass"}
            elif args.command == "command":
                result = {"argv": build_command(manifest, args.workspace), "stdin": "prompt", "status": "ready"}
            elif args.command == "probe":
                result = probe(manifest, args.timeout)
            elif args.command == "normalize":
                result = normalize_events(manifest, args.events.read_text(encoding="utf-8"))
            else:
                tasks = validate_task_registry(read_json(args.tasks, "trusted task registry"))
                request = json.loads(sys.stdin.read())
                result = (
                    protocol_observation(request)
                    if isinstance(request, dict) and request.get("op") == "conformance"
                    else execute_adapter(manifest, tasks, args.workspace_root, request, args.timeout)
                )
        print(pretty_json(result), end="")
        return 0 if result.get("status") != "fail" else 1
    except (HarnessError, json.JSONDecodeError) as exc:
        print(pretty_json({"error": str(exc), "status": "failed"}), end="", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
