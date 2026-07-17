#!/usr/bin/env python3
"""Admit and run digest-pinned evaluation tasks with hidden verifiers.

The controller is stdlib-only. Visible task metadata contains verifier identity
and digests, while verifier adapters, fixtures, and reference solutions remain
in a separate directory supplied only to the trusted evaluation process.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from gauntletlib.core.fsio import atomic_write_synced_json as atomic_json
from gauntletlib.core.hashing import sha256_bytes as sha_bytes
from gauntletlib.core.jsonio import canonical_json, pretty_json
from gauntletlib.core.jsonio import read_json as _read_json


SCHEMA_VERSION = 1
SHA256_RE = re.compile(r"^sha256:([0-9a-f]{64})$")
ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
CORE_SLOT_RE = re.compile(r"^CORE-(?:0[1-9]|1[0-2])$")
OUTCOMES = ("pass", "implementation_failure", "infrastructure_invalid")


class EvalTaskError(Exception):
    """A deterministic admission, integrity, liveness, or adapter failure."""

    def __init__(self, message: str, *, kind: str = "invalid") -> None:
        super().__init__(message)
        self.kind = kind


def read_json(path: Path, label: str) -> Any:
    try:
        return _read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        raise EvalTaskError(f"cannot read {label} {path}: {exc}", kind="integrity") from exc


def tree_digest(root: Path) -> str:
    """Hash names, modes, and contents without following symlinks."""
    root = root.resolve()
    if not root.is_dir():
        raise EvalTaskError(f"directory does not exist: {root}", kind="integrity")
    records: list[bytes] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise EvalTaskError(f"symlinks are not allowed in immutable bundles: {relative}", kind="integrity")
        if path.is_dir():
            records.append(f"d\0{relative}\0".encode())
        elif path.is_file():
            mode = path.stat().st_mode & 0o777
            records.append(f"f\0{relative}\0{mode:o}\0{len(path.read_bytes())}\0".encode() + path.read_bytes())
        else:
            raise EvalTaskError(f"unsupported bundle entry: {relative}", kind="integrity")
    return sha_bytes(b"".join(records))


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvalTaskError(f"{label} must be an object")
    return value


def require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvalTaskError(f"{label} must be a non-empty string")
    return value.strip()


def require_digest(value: Any, label: str) -> str:
    digest = require_string(value, label).lower()
    if not SHA256_RE.fullmatch(digest):
        raise EvalTaskError(f"{label} must be a full sha256 digest")
    return digest


def separate_roots(first: Path, second: Path, first_label: str, second_label: str) -> None:
    first = first.resolve()
    second = second.resolve()
    if first == second or first in second.parents or second in first.parents:
        raise EvalTaskError(f"{first_label} and {second_label} must be separate directory trees", kind="isolation")


def resolve_inside(root: Path, relative: Any, label: str) -> Path:
    raw = require_string(relative, label)
    path = (root / raw).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise EvalTaskError(f"{label} escapes the hidden verifier bundle", kind="isolation") from exc
    if not path.exists():
        raise EvalTaskError(f"{label} does not exist: {raw}", kind="integrity")
    return path


def load_contract(task_root: Path, verifier_root: Path) -> dict[str, Any]:
    task_root = task_root.resolve()
    verifier_root = verifier_root.resolve()
    separate_roots(task_root, verifier_root, "task", "verifier")
    task = require_object(read_json(task_root / "task.json", "task manifest"), "task manifest")
    verifier = require_object(read_json(verifier_root / "verifier.json", "verifier manifest"), "verifier manifest")

    if task.get("schema_version") != SCHEMA_VERSION or verifier.get("schema_version") != SCHEMA_VERSION:
        raise EvalTaskError(f"task and verifier schema_version must be {SCHEMA_VERSION}")
    task_id = require_string(task.get("task_id"), "task_id")
    if not ID_RE.fullmatch(task_id):
        raise EvalTaskError(f"task_id must match {ID_RE.pattern}")
    if not isinstance(task.get("task_version"), int) or isinstance(task.get("task_version"), bool) or task["task_version"] < 1:
        raise EvalTaskError("task_version must be a positive integer")
    slot = require_string(task.get("slot"), "slot")
    if slot != "development":
        if CORE_SLOT_RE.fullmatch(slot):
            raise EvalTaskError(f"{slot} is reserved and undefined; core tasks cannot be admitted yet")
        raise EvalTaskError("slot must be development while the core study slots remain sealed")

    public_verifier = require_object(task.get("verifier"), "task.verifier")
    verifier_id = require_string(public_verifier.get("id"), "task.verifier.id")
    if verifier_id != require_string(verifier.get("verifier_id"), "verifier.verifier_id"):
        raise EvalTaskError("visible and hidden verifier IDs disagree", kind="integrity")
    if task_id != require_string(verifier.get("task_id"), "verifier.task_id"):
        raise EvalTaskError("visible task and hidden verifier task IDs disagree", kind="integrity")

    if verifier.get("mode") != "isolated":
        raise EvalTaskError("verifier mode must be isolated; shared verifier mode is forbidden", kind="isolation")
    if verifier.get("mutable") is not False:
        raise EvalTaskError("verifier image must declare mutable=false", kind="integrity")
    image_digest = require_digest(verifier.get("image_digest"), "verifier.image_digest")
    if image_digest != require_digest(public_verifier.get("image_digest"), "task.verifier.image_digest"):
        raise EvalTaskError("visible and hidden verifier image digests disagree", kind="integrity")

    actual_bundle_digest = tree_digest(verifier_root)
    expected_bundle_digest = require_digest(public_verifier.get("bundle_sha256"), "task.verifier.bundle_sha256")
    if actual_bundle_digest != expected_bundle_digest.removeprefix("sha256:"):
        raise EvalTaskError("hidden verifier bundle does not match its pinned digest", kind="integrity")

    adapter = require_object(verifier.get("adapter"), "verifier.adapter")
    if adapter.get("kind") != "command-v1":
        raise EvalTaskError("verifier.adapter.kind must be command-v1")
    command = adapter.get("command")
    if not isinstance(command, list) or not command or any(not isinstance(item, str) or not item for item in command):
        raise EvalTaskError("verifier.adapter.command must be a non-empty string list")

    cases = require_object(verifier.get("cases"), "verifier.cases")
    for required in ("starting_state", "reference_solution", "regressions", "wrong_solutions"):
        if required not in cases:
            raise EvalTaskError(f"verifier.cases.{required} is required")
    if not isinstance(cases["regressions"], list) or not cases["regressions"]:
        raise EvalTaskError("verifier.cases.regressions must be non-empty")
    if not isinstance(cases["wrong_solutions"], list) or not cases["wrong_solutions"]:
        raise EvalTaskError("verifier.cases.wrong_solutions must be non-empty")
    require_object(verifier.get("liveness"), "verifier.liveness")

    return {
        "adapter": command,
        "bundle_digest": actual_bundle_digest,
        "image_digest": image_digest,
        "task": task,
        "task_digest": tree_digest(task_root),
        "task_id": task_id,
        "task_root": task_root,
        "verifier": verifier,
        "verifier_root": verifier_root,
    }


def adapter_environment(runtime_env: dict[str, str] | None = None) -> dict[str, str]:
    allowed = {"PATH", "SYSTEMROOT", "TMPDIR", "TEMP", "TMP"}
    environment = {key: value for key, value in os.environ.items() if key in allowed}
    for key, value in (runtime_env or {}).items():
        if not isinstance(key, str) or not key.startswith("GAUNTLET_EVAL_") or not isinstance(value, str):
            raise EvalTaskError("runtime environment keys must use the GAUNTLET_EVAL_ prefix")
        environment[key] = value
    return environment


def run_adapter(contract: dict[str, Any], request: dict[str, Any], runtime_env: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            contract["adapter"],
            cwd=contract["verifier_root"],
            env=adapter_environment(runtime_env),
            input=canonical_json(request) + "\n",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EvalTaskError(f"verifier adapter could not run: {exc}", kind="adapter") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip()[:500]
        raise EvalTaskError(f"verifier adapter failed with exit {completed.returncode}: {detail}", kind="adapter")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise EvalTaskError("verifier adapter did not return one JSON result", kind="adapter") from exc
    if not isinstance(result, dict) or not isinstance(result.get("passed"), bool):
        raise EvalTaskError("verifier adapter result must contain boolean passed", kind="adapter")
    return result


def case_request(contract: dict[str, Any], raw: Any, label: str) -> tuple[dict[str, Any], bool]:
    case = require_object(raw, label)
    candidate = resolve_inside(contract["verifier_root"], case.get("path"), f"{label}.path")
    expected = case.get("expected")
    if not isinstance(expected, bool):
        raise EvalTaskError(f"{label}.expected must be boolean")
    return {"candidate": str(candidate), "op": "score", "task_id": contract["task_id"]}, expected


def immutable_cases(contract: dict[str, Any]) -> list[tuple[str, dict[str, Any], bool]]:
    cases = contract["verifier"]["cases"]
    output: list[tuple[str, dict[str, Any], bool]] = []
    for name in ("starting_state", "reference_solution"):
        request, expected = case_request(contract, cases[name], f"verifier.cases.{name}")
        output.append((name, request, expected))
    for group in ("regressions", "wrong_solutions"):
        for index, raw in enumerate(cases[group]):
            request, expected = case_request(contract, raw, f"verifier.cases.{group}[{index}]")
            output.append((f"{group}[{index}]", request, expected))
    return output


def run_immutable_checks(contract: dict[str, Any], runtime_env: dict[str, str] | None = None) -> list[dict[str, Any]]:
    observations = []
    expectations = {"starting_state": False, "reference_solution": True}
    for name, request, expected in immutable_cases(contract):
        if name in expectations and expected is not expectations[name]:
            raise EvalTaskError(f"{name} must expect {str(expectations[name]).lower()}")
        if name.startswith(("regressions", "wrong_solutions")) and expected is not False:
            raise EvalTaskError(f"{name} must be a failing negative control")
        result = run_adapter(contract, request, runtime_env)
        observations.append({"case": name, "expected": expected, "observed": result["passed"]})
        if result["passed"] is not expected:
            raise EvalTaskError(
                f"immutable oracle case {name} expected {str(expected).lower()} but observed {str(result['passed']).lower()}",
                kind="oracle",
            )
    if tree_digest(contract["verifier_root"]) != contract["bundle_digest"]:
        raise EvalTaskError("verifier bundle mutated while immutable checks ran", kind="integrity")
    return observations


def cache_key(contract: dict[str, Any]) -> str:
    return sha_bytes(canonical_json({
        "bundle_digest": contract["bundle_digest"],
        "image_digest": contract["image_digest"],
        "schema_version": SCHEMA_VERSION,
        "task_digest": contract["task_digest"],
    }).encode())


def read_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"immutable_checks": {}, "schema_version": SCHEMA_VERSION}
    raw = read_json(path, "immutable-check cache")
    if not isinstance(raw, dict) or raw.get("schema_version") != SCHEMA_VERSION or not isinstance(raw.get("immutable_checks"), dict):
        raise EvalTaskError("immutable-check cache has an invalid schema", kind="integrity")
    return raw


def immutable_preflight(contract: dict[str, Any], cache_path: Path, runtime_env: dict[str, str] | None = None) -> dict[str, Any]:
    cache = read_cache(cache_path)
    key = cache_key(contract)
    expected_record = {
        "bundle_digest": contract["bundle_digest"],
        "image_digest": contract["image_digest"],
        "passed": True,
        "task_digest": contract["task_digest"],
    }
    hit = cache["immutable_checks"].get(key) == expected_record
    observations: list[dict[str, Any]] = []
    if not hit:
        observations = run_immutable_checks(contract, runtime_env)
        cache["immutable_checks"][key] = expected_record
        atomic_json(cache_path, cache)
    return {"cache_key": key, "immutable_cache_hit": hit, "observations": observations}


def liveness_probe(contract: dict[str, Any], runtime_env: dict[str, str] | None = None) -> dict[str, Any]:
    liveness = contract["verifier"]["liveness"]
    probe = require_string(liveness.get("probe"), "verifier.liveness.probe")
    result = run_adapter(contract, {"op": "liveness", "probe": probe, "task_id": contract["task_id"]}, runtime_env)
    if not result["passed"]:
        raise EvalTaskError("current verifier liveness probe failed", kind="liveness")
    if tree_digest(contract["verifier_root"]) != contract["bundle_digest"]:
        raise EvalTaskError("verifier bundle mutated while the liveness probe ran", kind="integrity")
    return {"probe": probe, "passed": True}


def quarantine(state_path: Path, task_id: str | None, error: EvalTaskError) -> None:
    atomic_json(state_path, {
        "reason": str(error),
        "reason_kind": error.kind,
        "schema_version": SCHEMA_VERSION,
        "status": "quarantined",
        "task_id": task_id,
    })


def admit(
    task_root: Path,
    verifier_root: Path,
    state_path: Path,
    cache_path: Path,
    runtime_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    task_id: str | None = None
    try:
        contract = load_contract(task_root, verifier_root)
        task_id = contract["task_id"]
        immutable = immutable_preflight(contract, cache_path, runtime_env)
        liveness = liveness_probe(contract, runtime_env)
        state = {
            "bundle_digest": contract["bundle_digest"],
            "image_digest": contract["image_digest"],
            "schema_version": SCHEMA_VERSION,
            "status": "admitted",
            "task_digest": contract["task_digest"],
            "task_id": task_id,
        }
        atomic_json(state_path, state)
        return {"immutable": immutable, "liveness": liveness, **state}
    except EvalTaskError as exc:
        quarantine(state_path, task_id, exc)
        raise


def require_admitted(contract: dict[str, Any], state_path: Path) -> None:
    state = read_json(state_path, "admission state")
    if not isinstance(state, dict) or state.get("schema_version") != SCHEMA_VERSION or state.get("status") != "admitted":
        raise EvalTaskError("task is not admitted", kind="quarantine")
    expected = {
        "bundle_digest": contract["bundle_digest"],
        "image_digest": contract["image_digest"],
        "task_digest": contract["task_digest"],
        "task_id": contract["task_id"],
    }
    for key, value in expected.items():
        if state.get(key) != value:
            raise EvalTaskError(f"admitted {key} no longer matches current task state", kind="integrity")


def preflight(
    task_root: Path,
    verifier_root: Path,
    state_path: Path,
    cache_path: Path,
    runtime_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    task_id: str | None = None
    try:
        contract = load_contract(task_root, verifier_root)
        task_id = contract["task_id"]
        require_admitted(contract, state_path)
        immutable = immutable_preflight(contract, cache_path, runtime_env)
        liveness = liveness_probe(contract, runtime_env)
        return {"immutable": immutable, "liveness": liveness, "status": "ready", "task_id": task_id}
    except EvalTaskError as exc:
        quarantine(state_path, task_id, exc)
        raise


def score(
    task_root: Path,
    verifier_root: Path,
    candidate: Path,
    state_path: Path,
    cache_path: Path,
    runtime_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    result = preflight(task_root, verifier_root, state_path, cache_path, runtime_env)
    contract = load_contract(task_root, verifier_root)
    candidate = candidate.resolve()
    if not candidate.exists():
        raise EvalTaskError(f"candidate does not exist: {candidate}")
    separate_roots(candidate, contract["verifier_root"], "candidate", "verifier")
    observed = run_adapter(contract, {"candidate": str(candidate), "op": "score", "task_id": contract["task_id"]}, runtime_env)
    outcome = "pass" if observed["passed"] else "implementation_failure"
    return {"outcome": outcome, "preflight": result, "task_id": contract["task_id"]}


def classify_retry(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, list) or not raw:
        raise EvalTaskError("attempts must be a non-empty list")
    outcomes = []
    ignored_triage = []
    for index, item in enumerate(raw):
        attempt = require_object(item, f"attempts[{index}]")
        outcome = attempt.get("outcome")
        if outcome not in OUTCOMES:
            raise EvalTaskError(f"attempts[{index}].outcome must be one of {', '.join(OUTCOMES)}")
        outcomes.append(outcome)
        triage = attempt.get("failure_only_triage")
        if outcome == "implementation_failure" and isinstance(triage, dict) and triage.get("requested_outcome") == "infrastructure_invalid":
            ignored_triage.append(index)
    if "pass" in outcomes:
        classification = "pass"
        retry = False
    elif all(item == "infrastructure_invalid" for item in outcomes):
        classification = "infrastructure_invalid"
        retry = True
    else:
        classification = "implementation_failure"
        retry = False
    return {"classification": classification, "ignored_failure_only_triage": ignored_triage, "retry": retry}


def runtime_env_args(values: list[str]) -> dict[str, str]:
    output = {}
    for value in values:
        if "=" not in value:
            raise EvalTaskError("--runtime-env values must be NAME=VALUE")
        key, item = value.split("=", 1)
        output[key] = item
    return output


def common(command: argparse.ArgumentParser, *, candidate: bool = False) -> None:
    command.add_argument("--task", required=True, type=Path)
    command.add_argument("--verifier", required=True, type=Path)
    command.add_argument("--state", required=True, type=Path)
    command.add_argument("--cache", required=True, type=Path)
    command.add_argument("--runtime-env", action="append", default=[])
    if candidate:
        command.add_argument("--candidate", required=True, type=Path)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    admit_cmd = commands.add_parser("admit")
    common(admit_cmd)
    preflight_cmd = commands.add_parser("preflight")
    common(preflight_cmd)
    score_cmd = commands.add_parser("score")
    common(score_cmd, candidate=True)
    classify_cmd = commands.add_parser("classify-retry")
    classify_cmd.add_argument("--attempts", required=True, type=Path)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "classify-retry":
            result = classify_retry(read_json(args.attempts, "attempts"))
        else:
            environment = runtime_env_args(args.runtime_env)
            positional = (args.task, args.verifier, args.state, args.cache)
            if args.command == "admit":
                result = admit(*positional, environment)
            elif args.command == "preflight":
                result = preflight(*positional, environment)
            else:
                result = score(args.task, args.verifier, args.candidate, args.state, args.cache, environment)
        print(pretty_json(result), end="")
        return 0
    except EvalTaskError as exc:
        print(pretty_json({"error": str(exc), "kind": exc.kind, "status": "failed"}), end="", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
