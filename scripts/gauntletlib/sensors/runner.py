"""Execute selected repository-owned sensors and emit compact handoffs."""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from gauntletlib.core.fsio import atomic_write_synced_json
from gauntletlib.core.jsonio import canonical_json

from .config import load_sensor_config
from .planner import (
    LANGUAGE_BY_SUFFIX,
    PROOF_PHASES,
    SENSOR_IDS,
    SUPPORTED_LANGUAGES,
)


EVIDENCE_SCHEMA = "gauntlet.sensor-evidence/v1"
HANDOFF_SCHEMA = "gauntlet.sensor-handoff/v1"
VERDICT_SCHEMA = "gauntlet.sensor-verdict/v1"
MAX_RAW_LOG_BYTES = 2 * 1024 * 1024
DEFAULT_IGNORED_PREFIXES = (
    ".git/",
    ".gauntlet/",
    "node_modules/",
    "htmlcov/",
)
DEFAULT_IGNORED_NAMES = {
    ".coverage",
    "coverage.json",
    "coverage.xml",
}
DEFAULT_IGNORED_PARTS = {
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}


def _git(project_root: Path, *arguments, check=True):
    result = subprocess.run(
        ["git", *arguments],
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        raise RuntimeError(
            f"git {' '.join(arguments)} failed: "
            + result.stderr.decode("utf-8", errors="replace").strip()
        )
    return result


def _ignored_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return (
        not normalized
        or normalized in DEFAULT_IGNORED_NAMES
        or any(part in DEFAULT_IGNORED_PARTS for part in Path(normalized).parts)
        or any(normalized.startswith(prefix) for prefix in DEFAULT_IGNORED_PREFIXES)
    )


def _status_paths(project_root: Path):
    result = _git(project_root, "status", "--porcelain=v1", "-z")
    parts = result.stdout.decode("utf-8", errors="surrogateescape").split("\0")
    paths = set()
    index = 0
    while index < len(parts):
        record = parts[index]
        index += 1
        if not record:
            continue
        if len(record) < 4:
            continue
        status = record[:2]
        path = record[3:]
        if status[0] in {"R", "C"} or status[1] in {"R", "C"}:
            if index < len(parts) and parts[index]:
                index += 1
        if not _ignored_path(path):
            paths.add(path)
    return paths


def _base_ref(project_root: Path, supplied: Optional[str]):
    candidates = [supplied] if supplied else []
    candidates.extend(["origin/HEAD", "origin/main", "main", "origin/master", "master"])
    head = _git(project_root, "rev-parse", "HEAD").stdout.strip()
    for candidate in candidates:
        if not candidate:
            continue
        resolved = _git(
            project_root,
            "rev-parse",
            "--verify",
            f"{candidate}^{{commit}}",
            check=False,
        )
        if resolved.returncode or resolved.stdout.strip() == head:
            continue
        return candidate
    return None


def discover_changed_paths(
    project_root: Path,
    *,
    supplied_paths=(),
    base_ref: Optional[str] = None,
):
    paths = set(supplied_paths)
    try:
        paths.update(_status_paths(project_root))
        base = _base_ref(project_root, base_ref)
        if base:
            merge_base = _git(project_root, "merge-base", "HEAD", base).stdout.strip()
            changed = _git(
                project_root,
                "diff",
                "--name-only",
                "-z",
                merge_base.decode("ascii"),
                "HEAD",
            )
            paths.update(
                item
                for item in changed.stdout.decode(
                    "utf-8",
                    errors="surrogateescape",
                ).split("\0")
                if item and not _ignored_path(item)
            )
    except RuntimeError:
        paths.update(
            str(path.relative_to(project_root))
            for path in project_root.rglob("*")
            if path.is_file() and not _ignored_path(str(path.relative_to(project_root)))
        )
    return sorted(path for path in paths if not _ignored_path(path))


def _source_fingerprint(
    project_root: Path,
    changed_paths,
    config_sha256,
    proof_phase,
):
    files = []
    for relative in changed_paths:
        path = project_root / relative
        if path.is_file() and not path.is_symlink():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            state = "file"
        elif path.exists():
            digest = None
            state = "other"
        else:
            digest = None
            state = "deleted"
        files.append({"path": relative, "state": state, "sha256": digest})
    head_result = _git(project_root, "rev-parse", "HEAD", check=False)
    head = (
        head_result.stdout.decode("ascii", errors="replace").strip()
        if head_result.returncode == 0
        else None
    )
    value = {
        "head": head,
        "files": files,
        "configSha256": config_sha256,
        "proofPhase": proof_phase,
    }
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _languages(changed_paths):
    return {
        language
        for path in changed_paths
        if (language := LANGUAGE_BY_SUFFIX.get(Path(path).suffix.lower()))
    }


def _is_frontend(path):
    return Path(path).suffix.lower() in {".css", ".html", ".htm", ".jsx", ".tsx"}


def _is_source(path):
    return Path(path).suffix.lower() in LANGUAGE_BY_SUFFIX


def _relevant(sensor, *, changed_paths, languages, workflow_mode, consequences):
    supported = bool(languages & SUPPORTED_LANGUAGES)
    app_surface = any(_is_source(path) for path in changed_paths)
    frontend = any(_is_frontend(path) for path in changed_paths)
    durable = workflow_mode != "scratch"
    if sensor in {"formatter", "type-checker", "linter", "focused-tests", "coverage"}:
        return supported and app_surface
    if sensor in {"complexity", "dead-code-dependency", "jscpd"}:
        return supported and app_surface and durable
    if sensor == "semgrep":
        return supported and app_surface and durable
    if sensor == "gitleaks":
        return bool(changed_paths) and durable
    if sensor in {"browser", "accessibility"}:
        return frontend
    if sensor == "mutation":
        return bool(consequences) and app_surface
    if sensor == "dependency-cruiser":
        return durable and bool(languages & {"javascript", "typescript"})
    raise AssertionError(f"unknown sensor: {sensor}")


def _selected_commands(
    config,
    *,
    project_root,
    changed_paths,
    workflow_mode,
    consequences,
    requested,
    proof_phase,
):
    languages = _languages(changed_paths)
    selected = []
    for sensor in SENSOR_IDS:
        command = config["commands"].get(sensor)
        if not command:
            continue
        if proof_phase not in command["phases"]:
            continue
        if sensor in requested or _relevant(
            sensor,
            changed_paths=changed_paths,
            languages=languages,
            workflow_mode=workflow_mode,
            consequences=consequences,
        ):
            expanded = dict(command)
            argv = []
            for item in command["argv"]:
                if item == "{changed_paths}":
                    argv.extend(changed_paths)
                else:
                    argv.append(
                        item.replace("{project_root}", str(project_root))
                        .replace("{phase}", proof_phase)
                        .replace(
                            "{suite}",
                            "smoke" if proof_phase == "fast" else "full",
                        )
                    )
            expanded["argv"] = argv
            expanded["sensors"] = [sensor]
            selected.append(expanded)

    required_by_sensor = {
        command["sensor"]: command["required"]
        for command in selected
    }
    deduplicated_by_argv = {}
    for command in selected:
        identity = tuple(command["argv"])
        existing = deduplicated_by_argv.get(identity)
        if existing is None:
            deduplicated_by_argv[identity] = command
            continue
        existing["sensors"].extend(command["sensors"])
        existing["required"] = existing["required"] or command["required"]
        existing["covers"] = sorted(set(existing["covers"]) | set(command["covers"]))
        existing["timeoutSeconds"] = min(
            existing["timeoutSeconds"],
            command["timeoutSeconds"],
        )

    deduplicated = list(deduplicated_by_argv.values())
    covered = {
        covered_sensor
        for command in deduplicated
        for covered_sensor in command["covers"]
    }
    result = []
    for command in deduplicated:
        command["required"] = command["required"] or any(
            required_by_sensor.get(sensor, False)
            for sensor in command["covers"]
        )
        command["sensors"] = [
            sensor for sensor in command["sensors"] if sensor not in covered
        ]
        if not command["sensors"]:
            continue
        command["sensor"] = command["sensors"][0]
        result.append(command)
    return result


def _git_evidence_root(project_root: Path):
    result = _git(
        project_root,
        "rev-parse",
        "--git-path",
        "gauntlet-sensors",
        check=False,
    )
    if result.returncode == 0:
        value = result.stdout.decode("utf-8", errors="replace").strip()
        path = Path(value)
        return path if path.is_absolute() else (project_root / path).resolve()
    return project_root / ".gauntlet" / "sensors"


def _public_evidence_ref(project_root: Path, evidence_path: Path):
    root = _git_evidence_root(project_root)
    try:
        relative = evidence_path.relative_to(root).as_posix()
    except ValueError:
        return str(evidence_path)
    return f"git:gauntlet-sensors/{relative}"


def _tool_identity(argv, cwd, env):
    result = subprocess.run(
        [argv[0], "--version"],
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=5,
    )
    output = " ".join(result.stdout.strip().split())
    return {
        "executable": argv[0],
        "version": output[:240] if output else "unavailable",
    }


def _bounded_environment():
    allowed = {
        "CI",
        "HOME",
        "LANG",
        "LC_ALL",
        "PATH",
        "SHELL",
        "TMPDIR",
        "UV_CACHE_DIR",
        "XDG_CACHE_HOME",
    }
    env = {key: value for key, value in os.environ.items() if key in allowed}
    agent_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    sensor_bin = agent_home / "gauntlet-tools" / "current" / "bin"
    if sensor_bin.is_dir():
        env["PATH"] = f"{sensor_bin}{os.pathsep}{env.get('PATH', '')}"
    return env


def _failure_summary(*, unavailable, timed_out, exit_code, timeout_seconds):
    if unavailable:
        return "Executable unavailable; inspect the referenced raw log."
    if timed_out:
        return (
            f"Timed out after {timeout_seconds} seconds; "
            "inspect the referenced raw log."
        )
    return f"Exited with code {exit_code}; inspect the referenced raw log."


def _hash_file(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _drain_bounded_output(stream, path: Path):
    marker = b"\n[Gauntlet truncated raw sensor output]\n"
    prefix_limit = MAX_RAW_LOG_BYTES // 2
    suffix_limit = MAX_RAW_LOG_BYTES - prefix_limit - len(marker)
    prefix = bytearray()
    suffix = bytearray()
    total = 0
    while chunk := stream.read(64 * 1024):
        total += len(chunk)
        prefix_room = prefix_limit - len(prefix)
        if prefix_room:
            prefix.extend(chunk[:prefix_room])
            chunk = chunk[prefix_room:]
        if chunk:
            suffix.extend(chunk)
            if len(suffix) > suffix_limit:
                del suffix[: len(suffix) - suffix_limit]
    content = (
        bytes(prefix + suffix)
        if total <= MAX_RAW_LOG_BYTES
        else bytes(prefix) + marker + bytes(suffix)
    )
    path.write_bytes(content)


def _run_bounded(command, *, project_root, env, log_path):
    process = subprocess.Popen(
        command["argv"],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    drain = threading.Thread(
        target=_drain_bounded_output,
        args=(process.stdout, log_path),
        daemon=True,
    )
    drain.start()
    timed_out = False
    try:
        exit_code = process.wait(timeout=command["timeoutSeconds"])
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        exit_code = process.wait()
    drain.join()
    if process.stdout is not None:
        process.stdout.close()
    return exit_code, timed_out


def _execute(command, *, project_root, logs_dir, env):
    sensor = command["sensor"]
    log_path = logs_dir / f"{sensor}.log"
    started = time.monotonic()
    timed_out = False
    unavailable = False
    exit_code = None
    try:
        tool = _tool_identity(command["argv"], project_root, env)
        exit_code, timed_out = _run_bounded(
            command,
            project_root=project_root,
            env=env,
            log_path=log_path,
        )
    except FileNotFoundError:
        unavailable = True
        tool = {"executable": command["argv"][0], "version": "unavailable"}
        log_path.write_text("Executable was not found.\n", encoding="utf-8")
    except subprocess.TimeoutExpired:
        timed_out = True
        tool = {"executable": command["argv"][0], "version": "unavailable"}
        with log_path.open("ab") as output:
            output.write(b"\nGauntlet stopped this sensor after its timeout.\n")
    except (OSError, subprocess.SubprocessError) as error:
        unavailable = True
        tool = {"executable": command["argv"][0], "version": "unavailable"}
        log_path.write_text(f"Sensor could not start: {error}\n", encoding="utf-8")

    duration_ms = round((time.monotonic() - started) * 1000)
    if unavailable:
        result_name = "unavailable"
    elif timed_out:
        result_name = "fail"
    else:
        result_name = "pass" if exit_code == 0 else "fail"
    summary = (
        "Passed."
        if result_name == "pass"
        else _failure_summary(
            unavailable=unavailable,
            timed_out=timed_out,
            exit_code=exit_code,
            timeout_seconds=command["timeoutSeconds"],
        )
    )
    return {
        "sensor": sensor,
        "sensors": command["sensors"],
        "result": result_name,
        "required": command["required"],
        "argv": command["argv"],
        "cwd": str(project_root),
        "exitCode": exit_code,
        "timedOut": timed_out,
        "durationMs": duration_ms,
        "tool": tool,
        "summary": summary,
        "rawLogRef": f"logs/{log_path.name}",
        "rawOutputSha256": _hash_file(log_path),
    }


def _print_handoff(payload, as_json):
    if as_json:
        print(json.dumps(payload, indent=2))
        return
    print(
        f"Sensors: {payload['status']} "
        f"({payload['counts']['passed']} passed, "
        f"{payload['counts']['attention']} need attention)"
    )
    for finding in payload["attention"]:
        print(
            f"- {finding['sensor']}: {finding['result']} — "
            f"{finding['summary']} ({finding['rawLogRef']})"
        )


def command_run(args):
    project_root = args.project_root.expanduser().resolve()
    if not project_root.is_dir():
        raise RuntimeError(f"project root is not a directory: {project_root}")
    config = load_sensor_config(project_root, args.config)
    proof_phase = getattr(args, "phase", None) or "integrated"
    changed_paths = discover_changed_paths(
        project_root,
        supplied_paths=args.changed_path,
        base_ref=args.base_ref,
    )
    source_fingerprint = _source_fingerprint(
        project_root,
        changed_paths,
        config["sha256"],
        proof_phase,
    )
    commands = _selected_commands(
        config,
        project_root=project_root,
        changed_paths=changed_paths,
        workflow_mode=args.workflow_mode,
        consequences=set(args.consequence),
        requested=set(args.request_sensor),
        proof_phase=proof_phase,
    )
    plan_value = {
        "workflowMode": args.workflow_mode,
        "proofPhase": proof_phase,
        "changedPaths": changed_paths,
        "sourceFingerprint": source_fingerprint,
        "commands": commands,
    }
    plan_fingerprint = hashlib.sha256(
        canonical_json(plan_value).encode("utf-8")
    ).hexdigest()
    run_id = f"{int(time.time())}-{plan_fingerprint[:12]}"
    run_root = _git_evidence_root(project_root) / run_id
    logs_dir = run_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=False)
    env = _bounded_environment()
    results = [
        _execute(
            command,
            project_root=project_root,
            logs_dir=logs_dir,
            env=env,
        )
        for command in commands
    ]
    blocking = [
        result
        for result in results
        if result["required"] and result["result"] != "pass"
    ]
    evidence_path = run_root / "evidence.json"
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "projectRoot": str(project_root),
        "workflowMode": args.workflow_mode,
        "proofPhase": proof_phase,
        "baseRef": args.base_ref,
        "suppliedChangedPaths": sorted(set(args.changed_path)),
        "consequences": sorted(set(args.consequence)),
        "requestedSensors": sorted(set(args.request_sensor)),
        "changedPaths": changed_paths,
        "configPath": str(config["path"]),
        "configSha256": config["sha256"],
        "sourceFingerprint": source_fingerprint,
        "planFingerprint": plan_fingerprint,
        "results": results,
        "verdict": "fail" if blocking else "pass",
    }
    atomic_write_synced_json(evidence_path, evidence)
    public_ref = _public_evidence_ref(project_root, evidence_path)
    attention = [
        {
            "sensor": result["sensor"],
            "sensors": result["sensors"],
            "result": result["result"],
            "summary": result["summary"],
            "rawLogRef": f"{public_ref.rsplit('/', 1)[0]}/{result['rawLogRef']}",
        }
        for result in results
        if result["result"] != "pass"
    ]
    passed = [
        sensor
        for result in results
        if result["result"] == "pass"
        for sensor in result["sensors"]
    ]
    handoff = {
        "schema": HANDOFF_SCHEMA,
        "status": "fail" if blocking else "pass",
        "proofPhase": proof_phase,
        "sourceFingerprint": source_fingerprint,
        "passed": passed,
        "attention": attention,
        "counts": {
            "selected": len(results),
            "passed": len(passed),
            "attention": len(attention),
        },
        "evidenceRef": public_ref,
    }
    _print_handoff(handoff, args.json)
    return 1 if blocking else 0


def _resolve_evidence(project_root: Path, supplied: Path):
    value = str(supplied)
    if value.startswith("git:gauntlet-sensors/"):
        relative = value.removeprefix("git:gauntlet-sensors/")
        resolved = (_git_evidence_root(project_root) / relative).resolve()
    else:
        resolved = supplied.expanduser().resolve()
    evidence_root = _git_evidence_root(project_root).resolve()
    try:
        resolved.relative_to(evidence_root)
    except ValueError as error:
        raise RuntimeError(
            "sensor evidence must be inside Gauntlet's Git-private evidence directory"
        ) from error
    if resolved.name != "evidence.json":
        raise RuntimeError("sensor evidence must reference a generated evidence.json")
    return resolved


def _evidence_results_match(
    evidence_path: Path,
    project_root: Path,
    expected_commands,
    results,
):
    if not isinstance(results, list) or len(results) != len(expected_commands):
        return False
    for expected, result in zip(expected_commands, results):
        if not isinstance(result, dict):
            return False
        for field in ("sensor", "sensors", "required", "argv"):
            if result.get(field) != expected.get(field):
                return False
        if result.get("cwd") != str(project_root):
            return False
        outcome = result.get("result")
        if outcome not in {"pass", "fail", "not-run", "unavailable"}:
            return False
        if outcome == "pass" and result.get("exitCode") != 0:
            return False
        raw_ref = result.get("rawLogRef")
        raw_sha256 = result.get("rawOutputSha256")
        if not isinstance(raw_ref, str) or not isinstance(raw_sha256, str):
            return False
        raw_path = (evidence_path.parent / raw_ref).resolve()
        try:
            raw_path.relative_to(evidence_path.parent.resolve())
        except ValueError:
            return False
        if not raw_path.is_file() or _hash_file(raw_path) != raw_sha256:
            return False
    return True


def command_verify(args):
    project_root = args.project_root.expanduser().resolve()
    evidence_path = _resolve_evidence(project_root, args.evidence)
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"sensor evidence could not be read: {error}") from error
    if not isinstance(evidence, dict) or evidence.get("schema") != EVIDENCE_SCHEMA:
        raise RuntimeError(f"sensor evidence schema must be {EVIDENCE_SCHEMA}")
    if evidence.get("projectRoot") != str(project_root):
        raise RuntimeError("sensor evidence belongs to a different project root")
    workflow_mode = evidence.get("workflowMode")
    if workflow_mode not in {"scratch", "research", "patch", "feature", "release"}:
        raise RuntimeError("sensor evidence has an invalid workflow mode")
    evidence_phase = evidence.get("proofPhase", "integrated")
    if evidence_phase not in PROOF_PHASES:
        raise RuntimeError("sensor evidence has an invalid proof phase")
    requested_phase = getattr(args, "phase", None) or "integrated"
    phase_mismatch = evidence_phase != requested_phase
    sequence_fields = (
        "suppliedChangedPaths",
        "consequences",
        "requestedSensors",
        "changedPaths",
    )
    if any(
        not isinstance(evidence.get(field), list)
        or any(not isinstance(item, str) for item in evidence[field])
        for field in sequence_fields
    ):
        raise RuntimeError("sensor evidence has invalid planning inputs")
    config_path = evidence.get("configPath")
    if not isinstance(config_path, str):
        raise RuntimeError("sensor evidence has an invalid config path")
    current_config = load_sensor_config(project_root, Path(config_path))
    current_paths = discover_changed_paths(
        project_root,
        supplied_paths=evidence["suppliedChangedPaths"],
        base_ref=evidence.get("baseRef"),
    )
    current_fingerprint = _source_fingerprint(
        project_root,
        current_paths,
        current_config["sha256"],
        requested_phase,
    )
    stale = (
        current_paths != evidence["changedPaths"]
        or current_fingerprint != evidence.get("sourceFingerprint")
    )
    expected_commands = _selected_commands(
        current_config,
        project_root=project_root,
        changed_paths=current_paths,
        workflow_mode=workflow_mode,
        consequences=set(evidence["consequences"]),
        requested=set(evidence["requestedSensors"]),
        proof_phase=requested_phase,
    )
    plan_value = {
        "workflowMode": workflow_mode,
        "proofPhase": requested_phase,
        "changedPaths": current_paths,
        "sourceFingerprint": current_fingerprint,
        "commands": expected_commands,
    }
    expected_plan_fingerprint = hashlib.sha256(
        canonical_json(plan_value).encode("utf-8")
    ).hexdigest()
    results = evidence.get("results")
    complete = (
        expected_plan_fingerprint == evidence.get("planFingerprint")
        and _evidence_results_match(
            evidence_path,
            project_root,
            expected_commands,
            results,
        )
    )
    blocking = [
        result
        for result in results
        if result.get("required") and result.get("result") != "pass"
    ] if isinstance(results, list) else [None]
    valid = (
        not stale
        and not phase_mismatch
        and complete
        and not blocking
        and evidence.get("verdict") == "pass"
    )
    if valid:
        reason = "Current source matches passing sensor evidence."
    elif phase_mismatch:
        reason = "Sensor evidence proof phase does not match the requested phase."
    elif stale:
        reason = "Sensor evidence is stale for the current source."
    elif not complete:
        reason = "Sensor evidence is incomplete or does not match the selected commands."
    else:
        reason = "Required sensor evidence did not pass."
    payload = {
        "schema": VERDICT_SCHEMA,
        "status": "pass" if valid else "fail",
        "reason": reason,
        "sourceFingerprint": current_fingerprint,
        "evidenceRef": _public_evidence_ref(project_root, evidence_path),
    }
    print(json.dumps(payload, indent=2) if args.json else payload["reason"])
    return 0 if valid else 1
