#!/usr/bin/env python3
"""Run condition-blind paired development evaluations and report estimands."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import signal
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

from gauntletlib.core.fsio import atomic_write_synced_json as atomic_json
from gauntletlib.core.jsonio import canonical_json, pretty_json
from gauntletlib.core.jsonio import read_json as _read_json


SCHEMA_VERSION = 1
DIMENSIONS = (
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
ADAPTER_KINDS = ("native", "wrapped", "mastra", "harbor")
HARNESS_CELL_FIELDS = (
    "harness", "harness_version", "model", "reasoning_effort", "permission_mode", "resource_profile"
)
CACHE_STATES = ("cold", "steady")
ROLES = ("baseline", "total-package", "ablation")
HEX = set("0123456789abcdef")
MAX_ADAPTER_BYTES = 10 * 1024 * 1024


class EvalRunError(Exception):
    pass


class AdapterFailure(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def full_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71 or any(c not in HEX for c in value[7:]):
        raise EvalRunError(f"{label} must be a full lowercase sha256 digest")
    return value


def read_json(path: Path, label: str) -> Any:
    try:
        return _read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        raise EvalRunError(f"cannot read {label} {path}: {exc}") from exc


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvalRunError(f"{label} must be an object")
    return value


def require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvalRunError(f"{label} must be a non-empty string")
    return value.strip()


def command_digest(command: list[str]) -> str:
    return "sha256:" + digest(command)


def plan_digest(plan: dict[str, Any]) -> str:
    return "sha256:" + digest(plan)


def validate_command(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item for item in value):
        raise EvalRunError(f"{label} must be a non-empty string list")
    return value


def validate_core_registry(raw: Any) -> None:
    registry = require_object(raw, "core registry")
    expected = [{"slot": f"CORE-{index:02d}", "status": "reserved-undefined"} for index in range(1, 13)]
    if registry.get("schema_version") != SCHEMA_VERSION or registry.get("slots") != expected:
        raise EvalRunError("core registry must contain exactly twelve ordered reserved-undefined slots")


def contains_gauntlet_artifact(value: Any) -> bool:
    return "gauntlet" in canonical_json(value).casefold()


def validate_equivalence_record(proof: Any, adapter_id: str) -> dict[str, Any]:
    proof = require_object(proof, f"adapter {adapter_id}.equivalence")
    if proof.get("schema_version") != SCHEMA_VERSION:
        raise EvalRunError(f"adapter {adapter_id} equivalence schema_version must be 1")
    if proof.get("status") != "pass" or proof.get("dimensions") != list(DIMENSIONS) or proof.get("mismatches") != []:
        raise EvalRunError(f"adapter {adapter_id} requires passing A/A equivalence for every dimension")
    comparisons = proof.get("comparisons")
    if not isinstance(comparisons, list) or len(comparisons) != len(DIMENSIONS):
        raise EvalRunError(f"adapter {adapter_id} equivalence requires complete comparison evidence")
    for dimension, raw_comparison in zip(DIMENSIONS, comparisons):
        comparison = require_object(raw_comparison, f"adapter {adapter_id} equivalence comparison {dimension}")
        if set(comparison) != {"dimension", "native", "passed", "wrapped"}:
            raise EvalRunError(f"adapter {adapter_id} equivalence comparison {dimension} has invalid fields")
        native = require_object(comparison.get("native"), f"adapter {adapter_id} equivalence native {dimension}")
        wrapped = require_object(comparison.get("wrapped"), f"adapter {adapter_id} equivalence wrapped {dimension}")
        if (
            comparison.get("dimension") != dimension
            or comparison.get("passed") is not True
            or native != wrapped
            or native.get("dimension") != dimension
            or "observation" not in native
        ):
            raise EvalRunError(f"adapter {adapter_id} equivalence comparison {dimension} did not pass")
    expected_suite_digest = "sha256:" + digest(comparisons)
    if proof.get("suite_digest") != expected_suite_digest:
        raise EvalRunError(f"adapter {adapter_id} equivalence suite digest does not match its comparisons")
    return proof


validate_conformance_record = validate_equivalence_record


def validate_adapters(raw: Any, used: set[str]) -> dict[str, dict[str, Any]]:
    registry = require_object(raw, "adapter registry")
    if registry.get("schema_version") != SCHEMA_VERSION:
        raise EvalRunError("adapter registry schema_version must be 1")
    adapters = require_object(registry.get("adapters"), "adapter registry.adapters")
    native_adapters = {}
    for key, item in adapters.items():
        if isinstance(item, dict) and item.get("kind") == "native":
            native_command = validate_command(item.get("command"), f"adapter {key}.command")
            native_adapters[command_digest(native_command)] = {
                "command": native_command,
                "timeout_seconds": item.get("timeout_seconds", 30),
            }
    output = {}
    for adapter_id in sorted(used):
        item = require_object(adapters.get(adapter_id), f"adapter {adapter_id}")
        kind = item.get("kind")
        if kind not in ADAPTER_KINDS:
            raise EvalRunError(f"adapter {adapter_id}.kind must be one of {', '.join(ADAPTER_KINDS)}")
        command = validate_command(item.get("command"), f"adapter {adapter_id}.command")
        timeout = item.get("timeout_seconds", 30)
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 300:
            raise EvalRunError(f"adapter {adapter_id}.timeout_seconds must be from 0 to 300")
        if kind != "native":
            if "equivalence" in item and "conformance" in item:
                raise EvalRunError(f"adapter {adapter_id} cannot declare both equivalence and legacy conformance")
            raw_proof = item.get("equivalence", item.get("conformance"))
            if not isinstance(raw_proof, dict):
                raise EvalRunError(f"adapter {adapter_id} requires passing A/A equivalence for every dimension")
            proof = validate_equivalence_record(raw_proof, adapter_id)
            if proof.get("wrapped_command_digest") != command_digest(command):
                raise EvalRunError(f"adapter {adapter_id} equivalence does not match its command")
            native_adapter = native_adapters.get(proof.get("native_command_digest"))
            if native_adapter is None:
                raise EvalRunError(f"adapter {adapter_id} equivalence does not match a registered native adapter")
            live_timeout = min(float(timeout), float(native_adapter["timeout_seconds"]))
            live_proof = adapter_equivalence(native_adapter["command"], command, live_timeout)
            if live_proof.get("status") != "pass" or live_proof.get("suite_digest") != proof.get("suite_digest"):
                raise EvalRunError(f"adapter {adapter_id} failed live A/A equivalence at plan admission")
        cell = item.get("harness_cell")
        if cell is not None:
            cell = require_object(cell, f"adapter {adapter_id}.harness_cell")
            if set(cell) != set(HARNESS_CELL_FIELDS):
                raise EvalRunError(f"adapter {adapter_id}.harness_cell must contain exactly {', '.join(HARNESS_CELL_FIELDS)}")
            for field in HARNESS_CELL_FIELDS:
                if field == "reasoning_effort" and cell[field] is None:
                    continue
                require_string(cell[field], f"adapter {adapter_id}.harness_cell.{field}")
        output[adapter_id] = {**item, "command": command, "harness_cell": cell, "timeout_seconds": float(timeout)}
    return output


def validate_plan(raw: Any, core_registry: Any, adapter_registry: Any) -> dict[str, Any]:
    validate_core_registry(core_registry)
    plan = require_object(raw, "plan")
    if plan.get("schema_version") != SCHEMA_VERSION:
        raise EvalRunError("plan schema_version must be 1")
    study_id = require_string(plan.get("study_id"), "study_id")
    repetitions = plan.get("repetitions")
    if not isinstance(repetitions, int) or isinstance(repetitions, bool) or not 1 <= repetitions <= 100:
        raise EvalRunError("repetitions must be an integer from 1 to 100")
    if plan.get("cache_states") != list(CACHE_STATES):
        raise EvalRunError("cache_states must be exactly cold then steady")
    tasks = plan.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise EvalRunError("tasks must be a non-empty list")
    normalized_tasks = []
    seen_tasks = set()
    for index, raw_task in enumerate(tasks):
        task = require_object(raw_task, f"tasks[{index}]")
        task_id = require_string(task.get("task_id"), f"tasks[{index}].task_id")
        if task_id in seen_tasks:
            raise EvalRunError(f"duplicate task {task_id}")
        seen_tasks.add(task_id)
        if task.get("slot") != "development":
            raise EvalRunError("core slots are sealed; only development tasks may run")
        version = task.get("task_version")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise EvalRunError(f"tasks[{index}].task_version must be positive")
        normalized_tasks.append({
            "slot": "development", "state_digest": full_digest(task.get("state_digest"), f"tasks[{index}].state_digest"),
            "task_id": task_id, "task_version": version,
        })
    conditions = plan.get("conditions")
    if not isinstance(conditions, list) or len(conditions) < 2:
        raise EvalRunError("conditions must contain baseline and total-package")
    normalized_conditions = []
    seen_conditions = set()
    role_counts = {role: 0 for role in ROLES}
    components = set()
    for index, raw_condition in enumerate(conditions):
        condition = require_object(raw_condition, f"conditions[{index}]")
        condition_id = require_string(condition.get("condition_id"), f"conditions[{index}].condition_id")
        if condition_id in seen_conditions:
            raise EvalRunError(f"duplicate condition {condition_id}")
        seen_conditions.add(condition_id)
        role = condition.get("role")
        if role not in ROLES:
            raise EvalRunError(f"conditions[{index}].role is invalid")
        role_counts[role] += 1
        package = require_object(condition.get("package"), f"conditions[{index}].package")
        component = None
        if role == "baseline" and contains_gauntlet_artifact(package):
            raise EvalRunError("baseline package cannot contain Gauntlet artifacts")
        if role == "ablation":
            component = require_string(condition.get("component"), f"conditions[{index}].component")
            if component in components:
                raise EvalRunError(f"duplicate ablation component {component}")
            components.add(component)
        normalized_conditions.append({
            "adapter": require_string(condition.get("adapter"), f"conditions[{index}].adapter"),
            "component": component, "condition_id": condition_id, "package": package, "package_digest": "sha256:" + digest(package),
            "role": role,
        })
    if role_counts["baseline"] != 1 or role_counts["total-package"] != 1:
        raise EvalRunError("plan requires exactly one baseline and one total-package condition")
    used = {item["adapter"] for item in normalized_conditions}
    adapters = validate_adapters(adapter_registry, used)
    cells = [adapters[item["adapter"]].get("harness_cell") for item in normalized_conditions]
    if any(cell is not None for cell in cells):
        if any(cell is None for cell in cells) or any(cell != cells[0] for cell in cells[1:]):
            raise EvalRunError(
                "every condition in one paired plan must use the same harness version, model, effort, permission, and resource cell"
            )
    return {
        "adapters": adapters, "cache_states": list(CACHE_STATES), "conditions": normalized_conditions,
        "repetitions": repetitions, "schema_version": SCHEMA_VERSION, "study_id": study_id, "tasks": normalized_tasks,
    }


def adapter_environment() -> dict[str, str]:
    allowed = {
        "OPENAI_API_KEY",
        "PATH", "SYSTEMROOT", "TMPDIR", "TEMP", "TMP",
    }
    return {key: value for key, value in os.environ.items() if key in allowed}


def run_process(command: list[str], request: dict[str, Any], timeout: float) -> dict[str, Any]:
    try:
        process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env=adapter_environment(), start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(input=canonical_json(request) + "\n", timeout=timeout)
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
        completed = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    except subprocess.TimeoutExpired as exc:
        raise AdapterFailure("timeout", "adapter timed out") from exc
    except OSError as exc:
        raise AdapterFailure("adapter-error", f"adapter could not start: {exc}") from exc
    if completed.returncode != 0:
        raise AdapterFailure("adapter-error", f"adapter exited {completed.returncode}: {completed.stderr.strip()[:300]}")
    if len(completed.stdout.encode()) + len(completed.stderr.encode()) > MAX_ADAPTER_BYTES:
        raise AdapterFailure("malformed-response", "adapter response exceeds the bounded controller limit")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AdapterFailure("malformed-response", "adapter returned malformed JSON") from exc
    if not isinstance(result, dict):
        raise AdapterFailure("malformed-response", "adapter result must be an object")
    return result


def invoke_execution(adapter: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    result = run_process(adapter["command"], request, adapter["timeout_seconds"])
    allowed = {"artifacts", "metrics", "outcome", "telemetry"}
    if set(result) - allowed:
        raise AdapterFailure("canonical-state-override", "adapter attempted to add canonical state fields")
    if result.get("outcome") not in ("pass", "implementation_failure"):
        raise AdapterFailure("malformed-response", "adapter outcome must be pass or implementation_failure")
    metrics = result.get("metrics", {})
    if not isinstance(metrics, dict) or any(
        not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value)
        for value in metrics.values()
    ):
        raise AdapterFailure("malformed-response", "adapter metrics must be numeric")
    artifacts = result.get("artifacts", [])
    if not isinstance(artifacts, list) or any(
        not isinstance(value, str) or not value or len(value) > 512 or Path(value).is_absolute() or ".." in Path(value).parts
        for value in artifacts
    ):
        raise AdapterFailure("malformed-response", "adapter artifacts must be safe bounded relative references")
    telemetry = result.get("telemetry", {})
    if not isinstance(telemetry, dict):
        raise AdapterFailure("malformed-response", "adapter telemetry must be an object")
    return {"artifacts": artifacts, "metrics": metrics, "outcome": result["outcome"], "telemetry": telemetry}


def equivalence_request(dimension: str) -> dict[str, Any]:
    fixtures = {
        "single-agent": {"expected_sessions": 1, "prompt": "return the fixture marker"},
        "custom-profile": {"profile": "fixture-profile", "selector": "explicit"},
        "nested-agent": {"children": ["child-a", "child-b"], "depth": 2},
        "concurrent-lanes": {"lanes": ["lane-a", "lane-b"], "minimum_overlap": True},
        "resume-interrupt": {"checkpoint": "fixture-checkpoint", "interrupt_after": 1},
        "permission": {"network": False, "sandbox": "read-only"},
        "pty": {"stdin": "fixture-input", "terminal": True},
        "timeout": {"timeout_ms": 250},
        "artifact": {"required": ["result.json"]},
        "telemetry": {"fields": ["duration_ms", "tokens"]},
        "failure": {"expected_exit": "nonzero", "reason": "fixture-failure"},
    }
    return {"dimension": dimension, "fixture": fixtures[dimension], "op": "conformance", "schema_version": SCHEMA_VERSION}


def adapter_equivalence(native: list[str], wrapped: list[str], timeout: float = 30) -> dict[str, Any]:
    native = validate_command(native, "native command")
    wrapped = validate_command(wrapped, "wrapped command")
    comparisons = []
    mismatches = []
    for dimension in DIMENSIONS:
        request = equivalence_request(dimension)
        try:
            left = run_process(native, request, timeout)
            right = run_process(wrapped, request, timeout)
            passed = left == right and left.get("dimension") == dimension and "observation" in left
        except AdapterFailure as exc:
            left = {"error": exc.code}; right = {"error": exc.code}; passed = False
        comparisons.append({"dimension": dimension, "native": left, "passed": passed, "wrapped": right})
        if not passed:
            mismatches.append(dimension)
    record = {
        "dimensions": list(DIMENSIONS), "mismatches": mismatches,
        "native_command_digest": command_digest(native), "schema_version": SCHEMA_VERSION,
        "status": "pass" if not mismatches else "fail", "wrapped_command_digest": command_digest(wrapped),
    }
    record["suite_digest"] = "sha256:" + digest(comparisons)
    record["comparisons"] = comparisons
    return record


conformance_request = equivalence_request
conformance = adapter_equivalence


def identity(condition: dict[str, Any]) -> str:
    return condition["role"] if condition["role"] != "ablation" else f"ablation:{condition['component']}"


def execution_request(
    task: dict[str, Any], condition: dict[str, Any], repetition: int, cache_state: str, execution_id: str
) -> dict[str, Any]:
    return {
        "cache_state": cache_state, "condition_token": condition["package_digest"], "op": "execute",
        "execution_id": execution_id, "package": condition["package"], "repetition": repetition, "schema_version": SCHEMA_VERSION,
        "state_digest": task["state_digest"], "task_id": task["task_id"], "task_version": task["task_version"],
    }


def execute(plan_raw: Any, core_raw: Any, adapters_raw: Any, output: Path | None = None) -> dict[str, Any]:
    plan = validate_plan(plan_raw, core_raw, adapters_raw)
    raw_plan = require_object(plan_raw, "plan")
    state = {
        "intention_to_run": [], "plan_digest": plan_digest(raw_plan),
        "replays": [], "schema_version": SCHEMA_VERSION, "study_id": plan["study_id"],
    }
    for task_index, task in enumerate(plan["tasks"]):
        for repetition in range(1, plan["repetitions"] + 1):
            for cache_index, cache_state in enumerate(plan["cache_states"]):
                pair_id = digest([plan["study_id"], task["task_id"], task["task_version"], repetition, cache_state])[:24]
                conditions = list(plan["conditions"])
                shift = (task_index + repetition + cache_index) % len(conditions)
                conditions = conditions[shift:] + conditions[:shift]
                for order_index, condition in enumerate(conditions):
                    execution_id = digest([pair_id, identity(condition), condition["package_digest"]])[:24]
                    record = {
                        "attempt": 1, "cache_state": cache_state, "condition_id": condition["condition_id"],
                        "condition_identity": identity(condition), "condition_package_digest": condition["package_digest"],
                        "execution_id": execution_id, "order_index": order_index, "outcome": "launched", "pair_id": pair_id,
                        "repetition": repetition, "state_digest": task["state_digest"], "task_id": task["task_id"],
                        "task_version": task["task_version"],
                    }
                    state["intention_to_run"].append(record)
                    if output:
                        atomic_json(output, state)
                    try:
                        observed = invoke_execution(
                            plan["adapters"][condition["adapter"]],
                            execution_request(task, condition, repetition, cache_state, execution_id),
                        )
                        record.update(observed)
                    except AdapterFailure as exc:
                        record.update({
                            "invalidity": {
                                "code": exc.code,
                                "condition_blind": True,
                                "retryable": exc.code in ("adapter-error", "timeout"),
                            },
                            "outcome": "infrastructure_invalid",
                        })
                    if output:
                        atomic_json(output, state)
    return state


def replay(plan_raw: Any, core_raw: Any, adapters_raw: Any, run_raw: Any, output: Path | None = None) -> dict[str, Any]:
    plan = validate_plan(plan_raw, core_raw, adapters_raw)
    run = require_object(run_raw, "run")
    state = json.loads(json.dumps(run))
    if state.get("schema_version") != SCHEMA_VERSION or not isinstance(state.get("intention_to_run"), list):
        raise EvalRunError("run has an invalid schema")
    if state.get("study_id") != plan["study_id"]:
        raise EvalRunError("run does not match the supplied study")
    tasks = {item["task_id"]: item for item in plan["tasks"]}
    conditions = {identity(item): item for item in plan["conditions"]}
    replayed = {item.get("replay_of") for item in state.get("replays", [])}
    state.setdefault("replays", [])
    for original in state["intention_to_run"]:
        if original.get("outcome") != "infrastructure_invalid" or not original.get("invalidity", {}).get("retryable"):
            continue
        if original["execution_id"] in replayed:
            continue
        task = tasks.get(original.get("task_id"))
        condition = conditions.get(original.get("condition_identity"))
        record = {"attempt": 2, "replay_of": original["execution_id"]}
        if not task or not condition or task["state_digest"] != original.get("state_digest") or condition["package_digest"] != original.get("condition_package_digest"):
            record.update({"outcome": "not_run", "reason": "state_or_package_mismatch"})
        else:
            request = execution_request(
                task, condition, original["repetition"], original["cache_state"], f"{original['execution_id']}-replay-2"
            )
            try:
                observed = invoke_execution(plan["adapters"][condition["adapter"]], request)
                record.update(observed)
            except AdapterFailure as exc:
                record.update({
                    "invalidity": {
                        "code": exc.code,
                        "condition_blind": True,
                        "retryable": exc.code in ("adapter-error", "timeout"),
                    },
                    "outcome": "infrastructure_invalid",
                })
        state["replays"].append(record)
        if output:
            atomic_json(output, state)
    return state


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def nested_estimate(pairs: list[tuple[dict[str, Any], dict[str, Any]]], metric) -> dict[str, Any]:
    by_task: dict[str, list[float]] = {}
    for baseline, comparison in pairs:
        value = metric(baseline, comparison)
        if value is not None:
            by_task.setdefault(baseline["task_id"], []).append(value)
    task_effects = {key: mean(values) for key, values in sorted(by_task.items())}
    values = list(task_effects.values())
    standard_error = statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else None
    return {
        "estimate": mean(values), "repetition_count": sum(len(item) for item in by_task.values()),
        "standard_error_across_tasks": standard_error, "task_count": len(values), "task_effects": task_effects,
    }


def report(plan_raw: Any, run_raw: Any) -> dict[str, Any]:
    plan = require_object(plan_raw, "plan")
    run = require_object(run_raw, "run")
    if plan.get("schema_version") != SCHEMA_VERSION:
        raise EvalRunError("plan schema_version must be 1")
    study_id = require_string(plan.get("study_id"), "study_id")
    if run.get("schema_version") != SCHEMA_VERSION:
        raise EvalRunError("run has an invalid schema")
    if run.get("study_id") != study_id or run.get("plan_digest") != plan_digest(plan):
        raise EvalRunError("run does not match the supplied study plan")
    records = run.get("intention_to_run")
    if not isinstance(records, list):
        raise EvalRunError("run.intention_to_run must be a list")
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    invalidity: dict[str, int] = {}
    for record in records:
        grouped.setdefault(record["pair_id"], {})[record["condition_identity"]] = record
        if record.get("outcome") == "infrastructure_invalid":
            key = f"{record['condition_identity']}:{record['invalidity']['code']}"
            invalidity[key] = invalidity.get(key, 0) + 1
    total_pairs = []
    ablation_pairs: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for conditions in grouped.values():
        if "baseline" in conditions and "total-package" in conditions:
            total_pairs.append((conditions["baseline"], conditions["total-package"]))
        for key, value in conditions.items():
            if key.startswith("ablation:") and "total-package" in conditions:
                ablation_pairs.setdefault(key.removeprefix("ablation:"), []).append((value, conditions["total-package"]))
    correctness = lambda left, right: float(right.get("outcome") == "pass") - float(left.get("outcome") == "pass")
    efficiency = lambda left, right: (
        right.get("metrics", {}).get("duration_ms") - left.get("metrics", {}).get("duration_ms")
        if left.get("outcome") == right.get("outcome") == "pass"
        and isinstance(left.get("metrics", {}).get("duration_ms"), (int, float))
        and isinstance(right.get("metrics", {}).get("duration_ms"), (int, float)) else None
    )
    cache_reports = {}
    for cache_state in CACHE_STATES:
        selected = [pair for pair in total_pairs if pair[0]["cache_state"] == cache_state]
        cache_reports[cache_state] = {
            "correctness_itt": nested_estimate(selected, correctness),
            "correctness_conditional_efficiency_ms": nested_estimate(selected, efficiency),
        }
    component_reports = {}
    for component, pairs in sorted(ablation_pairs.items()):
        component_reports[component] = {
            "correctness_contribution": nested_estimate(pairs, correctness),
            "decision_scope": "matching-ablation-only",
        }
    return {
        "cache_behavior": cache_reports,
        "component_estimands": component_reports,
        "component_policy": "matching-ablations-required" if component_reports else "undecidable_without_matching_ablations",
        "invalidity_records": dict(sorted(invalidity.items())),
        "nested_repetitions": {"launched_execution_count": len(records), "task_generalization_count": len({item["task_id"] for item in records})},
        "replay_records": {"count": len(run.get("replays", [])), "substituted_for_originals": False},
        "schema_version": SCHEMA_VERSION,
        "total_package_estimand": nested_estimate(total_pairs, correctness),
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("execute", "replay"):
        item = commands.add_parser(name)
        item.add_argument("--plan", required=True, type=Path); item.add_argument("--adapters", required=True, type=Path)
        item.add_argument("--core-registry", required=True, type=Path); item.add_argument("--output", required=True, type=Path)
        if name == "replay":
            item.add_argument("--run", required=True, type=Path)
    report_cmd = commands.add_parser("report")
    report_cmd.add_argument("--plan", required=True, type=Path); report_cmd.add_argument("--run", required=True, type=Path)
    report_cmd.add_argument("--output", type=Path)
    for name in ("adapter-equivalence", "conformance"):
        conform = commands.add_parser(name)
        conform.add_argument("--native-command", required=True, type=Path); conform.add_argument("--wrapped-command", required=True, type=Path)
        conform.add_argument("--output", type=Path)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command in ("adapter-equivalence", "conformance"):
            result = adapter_equivalence(
                read_json(args.native_command, "native command"), read_json(args.wrapped_command, "wrapped command")
            )
        elif args.command == "report":
            result = report(read_json(args.plan, "plan"), read_json(args.run, "run"))
        else:
            plan = read_json(args.plan, "plan"); core = read_json(args.core_registry, "core registry")
            adapters = read_json(args.adapters, "adapter registry")
            if args.command == "execute":
                if args.output.exists():
                    raise EvalRunError("output already exists; selective rerun is forbidden")
                result = execute(plan, core, adapters, args.output)
            else:
                result = replay(plan, core, adapters, read_json(args.run, "run"), args.output)
        if getattr(args, "output", None):
            atomic_json(args.output, result)
        else:
            print(pretty_json(result), end="")
        return 0
    except EvalRunError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
