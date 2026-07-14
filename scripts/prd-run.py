#!/usr/bin/env python3
"""Deterministic, disk-backed execution runs for multi-agent PRD delivery.

The CLI is deliberately stdlib-only.  A parent agent is the sole writer; child
agents receive materialized bundles and return receipts for the parent to record.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from generated_context import ContextError, render_manifest


STATES = (
    "discussing",
    "accepted",
    "compiled",
    "executing",
    "integrating",
    "cohort_verified",
    "prd_verified",
    "merged",
    "deployed",
    "production_verified",
    "complete",
)
RELEASE_STAGES = ("deployment", "production-verification")
RELEASE_APPLICABILITY = ("merge", "deployment", "production-verification")
ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]{0,63}$")
BRANCH_RE = re.compile(r"^(?!/)(?!-)(?!.*(?:\.\.|//|@\{|[ ~^:?*\[\\]))[A-Za-z0-9._/@-]{1,255}(?<![/.])$")
LANE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
PROTOCOL_VERSION = 1
INTEGRATION_MODE = "parent-branch"
PR_STRATEGY = "one-final-pr-per-run"


class RunError(Exception):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def object_hash(value: Any) -> str:
    return sha_bytes(canonical_json(value).encode())


def source_contract(path: Path, requested_targets: list[str]) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    target_match = re.search(r"^Implementation target:\s*(.+?)\s*$", text, re.MULTILINE)
    if not target_match:
        raise RunError("PRD must declare Implementation target")
    declared = sorted(set(re.findall(r"\b[A-Z][A-Z0-9_-]{1,63}\b", target_match.group(1))))
    requested = sorted({require_id(item, "target Epic ID") for item in requested_targets})
    if not requested or declared != requested:
        raise RunError(f"requested targets {requested} do not match PRD Implementation target {declared}")
    epic_matches = list(re.finditer(r"^## Epic ([A-Z][A-Z0-9_-]{0,63}):[^\n]*$", text, re.MULTILINE))
    epic_sections: dict[str, str] = {}
    scope_hashes: dict[str, str] = {}
    for index, match in enumerate(epic_matches):
        epic_id = match.group(1)
        if epic_id in epic_sections:
            raise RunError(f"duplicate Epic ID in PRD: {epic_id}")
        section = text[match.start() : epic_matches[index + 1].start() if index + 1 < len(epic_matches) else len(text)]
        epic_sections[epic_id] = section
        if epic_id in requested and not re.search(r"^Epic status:\s*Accepted\s*$", section, re.MULTILINE | re.IGNORECASE):
            raise RunError(f"target Epic {epic_id} is not Accepted")
        if epic_id in requested:
            heading_matches = list(re.finditer(r"^### ([^\n]+)$", section, re.MULTILINE))
            scope_chunks: list[tuple[str, int, int, str]] = []
            for heading_index, heading in enumerate(heading_matches):
                scope_match = re.fullmatch(r"Scope Area ([A-Z][A-Z0-9_-]{0,63}):.+", heading.group(1))
                if not scope_match:
                    continue
                scope_id = scope_match.group(1)
                if scope_id in scope_hashes or any(existing[0] == scope_id for existing in scope_chunks):
                    raise RunError(f"duplicate Scope Area ID in PRD: {scope_id}")
                if not scope_id.startswith(f"{epic_id}-"):
                    raise RunError(f"Scope Area {scope_id} must belong to target Epic {epic_id}")
                end = heading_matches[heading_index + 1].start() if heading_index + 1 < len(heading_matches) else len(section)
                scope_chunks.append((scope_id, heading.start(), end, section[heading.start():end]))
            common_parts = []
            cursor = 0
            for _, start, end, _ in scope_chunks:
                common_parts.append(section[cursor:start]); cursor = end
            common_parts.append(section[cursor:])
            common = "".join(common_parts)
            for scope_id, _, _, scope_text in scope_chunks:
                scope_hashes[scope_id] = object_hash({"epic_common": common, "scope": scope_text})
    missing = set(requested) - set(epic_sections)
    if missing:
        raise RunError(f"target Epics are missing from the PRD: {sorted(missing)}")
    if not scope_hashes:
        raise RunError("Implementation target must define searchable '### Scope Area <ID>: <Responsibility>' sections")
    return {"epic_ids": requested, "scope_hashes": dict(sorted(scope_hashes.items()))}


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RunError(f"cannot read JSON {path}: {exc}") from exc


def atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, pretty_json(value))


def relative_run_path(run: Path, path: Path, label: str) -> tuple[Path, str]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(run)
    except ValueError as exc:
        raise RunError(f"{label} must be inside the run") from exc
    if not resolved.is_file() or not resolved.read_text().strip():
        raise RunError(f"{label} must exist and be non-empty")
    return resolved, relative.as_posix()


def proof_path(run: Path, path: Path, label: str, *, name_prefix=None) -> tuple[Path, str]:
    resolved, relative = relative_run_path(run, path, label)
    parts = Path(relative).parts
    if not parts or parts[0] != "evidence":
        raise RunError(f"{label} must be under the run evidence directory")
    if name_prefix and not Path(relative).name.startswith(name_prefix):
        raise RunError(f"{label} must use the lease-specific prefix {name_prefix}")
    return resolved, relative


def pin_artifact(run: Path, manifest: dict[str, Any], path: Path) -> str:
    resolved, relative = relative_run_path(run, path, "pinned artifact")
    manifest.setdefault("artifact_hashes", {})[relative] = sha_file(resolved)
    return relative


def verify_pinned_artifacts(run: Path, manifest: dict[str, Any]) -> None:
    for relative, expected in manifest.get("artifact_hashes", {}).items():
        path = run / relative
        if not path.is_file() or sha_file(path) != expected:
            raise RunError(f"pinned execution artifact changed or disappeared: {relative}")


def recover_event_journal(run: Path) -> None:
    """Keep the journal at the exact prefix committed by manifest.event_sequence."""

    manifest_path = run / "manifest.json"
    journal_path = run / "events.jsonl"
    if not manifest_path.is_file() or not journal_path.is_file():
        return
    manifest = read_json(manifest_path)
    expected = manifest.get("event_sequence", 0)
    if not isinstance(expected, int) or isinstance(expected, bool) or expected < 0:
        raise RunError("manifest event_sequence must be a non-negative integer")
    data = journal_path.read_bytes()
    committed: list[bytes] = []
    for line in data.splitlines(keepends=True):
        if not line.endswith(b"\n") or len(committed) == expected:
            break
        try:
            record = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RunError("event journal is corrupt before the committed boundary") from exc
        sequence = len(committed) + 1
        if not isinstance(record, dict) or record.get("sequence") != sequence:
            raise RunError(f"event journal sequence {sequence} is missing or out of order")
        committed.append(line)
    if len(committed) != expected:
        raise RunError(f"event journal has {len(committed)} valid committed events; manifest requires {expected}")
    canonical_prefix = b"".join(committed)
    if data != canonical_prefix:
        atomic_text(journal_path, canonical_prefix.decode("utf-8"))


def recover_transactions(run: Path) -> None:
    for name in ("compile", "reconcile"):
        temporary = run / f".{name}-backup.tmp"
        if temporary.exists():
            shutil.rmtree(temporary)
        backup = run / f".{name}-backup"
        if not backup.is_dir():
            continue
        journal = read_json(backup / "journal.json")
        try:
            current_generation = int(read_json(run / "manifest.json").get("generation", 0))
        except RunError:
            current_generation = -1
        if current_generation > journal["base_generation"]:
            shutil.rmtree(backup)
            continue
        for relative in journal["restore"]:
            saved = backup / "files" / relative
            destination = run / relative
            if destination.is_dir():
                shutil.rmtree(destination)
            elif destination.exists():
                destination.unlink()
            if saved.is_dir():
                shutil.copytree(saved, destination)
            elif saved.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(saved, destination)
        for relative in journal["remove"]:
            destination = run / relative
            if destination.is_dir():
                shutil.rmtree(destination)
            elif destination.exists():
                destination.unlink()
        shutil.rmtree(backup)


def begin_transaction_backup(run: Path, name: str, restore: list[str], remove: list[str]) -> tuple[Path, int]:
    backup = run / f".{name}-backup"
    temporary = run / f".{name}-backup.tmp"
    if backup.exists() or temporary.exists():
        raise RunError(f"a {name} recovery journal already exists")
    base_generation = int(read_json(run / "manifest.json").get("generation", 0))
    (temporary / "files").mkdir(parents=True)
    for relative in restore:
        source = run / relative
        destination = temporary / "files" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination)
        elif source.is_file():
            shutil.copy2(source, destination)
    atomic_json(temporary / "journal.json", {"base_generation": base_generation, "remove": remove, "restore": restore})
    os.replace(temporary, backup)
    return backup, base_generation


def require_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise RunError(f"{label} must match {ID_RE.pattern}")
    return value


def require_branch(value: Any, label: str) -> str:
    if not isinstance(value, str) or not BRANCH_RE.fullmatch(value) or value in {"main", "master"}:
        raise RunError(f"{label} must be a valid non-default Git branch")
    return value


def require_lane(value: Any, label: str = "lane") -> str:
    if not isinstance(value, str) or not LANE_RE.fullmatch(value):
        raise RunError(f"{label} must match {LANE_RE.pattern}")
    return value


def require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RunError(f"{label} must be a non-empty string")
    return value.strip()


def string_list(value: Any, label: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise RunError(f"{label} must be a{' non-empty' if not allow_empty else ''} list")
    result = []
    for index, item in enumerate(value):
        result.append(require_string(item, f"{label}[{index}]"))
    return result


def normalize_graph(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise RunError("ticket graph version must be 1")
    source_areas = raw.get("scope_areas")
    cohorts = raw.get("cohorts")
    tickets = raw.get("tickets")
    shared = raw.get("shared_context", {})
    if not isinstance(source_areas, list) or not source_areas:
        raise RunError("scope_areas must be a non-empty list of locked PRD IDs")
    if not isinstance(cohorts, dict) or not cohorts:
        raise RunError("cohorts must be a non-empty object")
    if not isinstance(tickets, list) or not tickets:
        raise RunError("tickets must be a non-empty list")
    if not isinstance(shared, dict):
        raise RunError("shared_context must be an object")

    scope_out: list[str] = []
    for scope_id in sorted(source_areas):
        require_id(scope_id, "scope area ID")
        if scope_id in scope_out:
            raise RunError(f"duplicate scope area ID: {scope_id}")
        scope_out.append(scope_id)

    cohort_out: dict[str, Any] = {}
    for cohort_id in sorted(cohorts):
        require_id(cohort_id, "cohort ID")
        item = cohorts[cohort_id]
        if not isinstance(item, dict):
            raise RunError(f"cohort {cohort_id} must be an object")
        cohort_out[cohort_id] = {
            "invariant": require_string(item.get("invariant"), f"cohort {cohort_id}.invariant"),
            "ticket_ids": sorted(string_list(item.get("ticket_ids"), f"cohort {cohort_id}.ticket_ids", allow_empty=False)),
        }

    ticket_out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in tickets:
        if not isinstance(item, dict):
            raise RunError("each ticket must be an object")
        ticket_id = require_id(item.get("id"), "ticket ID")
        if ticket_id in seen:
            raise RunError(f"duplicate ticket {ticket_id}")
        seen.add(ticket_id)
        scopes = sorted(string_list(item.get("scope_area_ids"), f"ticket {ticket_id}.scope_area_ids", allow_empty=False))
        unknown_scopes = set(scopes) - set(scope_out)
        if unknown_scopes:
            raise RunError(f"ticket {ticket_id} has unknown scope areas: {sorted(unknown_scopes)}")
        cohort_id = require_id(item.get("cohort_id"), f"ticket {ticket_id}.cohort_id")
        if cohort_id not in cohort_out:
            raise RunError(f"ticket {ticket_id} has unknown cohort {cohort_id}")
        proof = item.get("proof")
        if not isinstance(proof, dict):
            raise RunError(f"ticket {ticket_id}.proof must be an object")
        claim = require_string(proof.get("claim"), f"ticket {ticket_id}.proof.claim")
        oracle = require_string(proof.get("oracle"), f"ticket {ticket_id}.proof.oracle")
        wrong_case = require_string(proof.get("wrong_case"), f"ticket {ticket_id}.proof.wrong_case")
        if object_hash(oracle.casefold()) == object_hash(wrong_case.casefold()):
            raise RunError(f"ticket {ticket_id} proof oracle and wrong_case must differ")
        kind = item.get("kind", "implementation")
        if kind not in ("implementation", "verification"):
            raise RunError(f"ticket {ticket_id}.kind must be implementation or verification")
        priority = item.get("priority", 100)
        if not isinstance(priority, int) or isinstance(priority, bool) or not 0 <= priority <= 999:
            raise RunError(f"ticket {ticket_id}.priority must be an integer from 0 to 999")
        interface_first = item.get("interface_first", False)
        if not isinstance(interface_first, bool):
            raise RunError(f"ticket {ticket_id}.interface_first must be boolean")
        ticket_out.append({
            "acceptance": string_list(item.get("acceptance"), f"ticket {ticket_id}.acceptance", allow_empty=False),
            "ask_parent_policy": require_string(item.get("ask_parent_policy"), f"ticket {ticket_id}.ask_parent_policy"),
            "cohort_id": cohort_id,
            "constraints": string_list(item.get("constraints", []), f"ticket {ticket_id}.constraints"),
            "dependencies": sorted(string_list(item.get("dependencies", []), f"ticket {ticket_id}.dependencies")),
            "epic_id": require_id(item.get("epic_id"), f"ticket {ticket_id}.epic_id"),
            "id": ticket_id,
            "affinity": sorted(string_list(item.get("affinity", []), f"ticket {ticket_id}.affinity")),
            "interface_first": interface_first,
            "kind": kind,
            "objective": require_string(item.get("objective"), f"ticket {ticket_id}.objective"),
            "ownership": sorted(string_list(item.get("ownership"), f"ticket {ticket_id}.ownership", allow_empty=False)),
            "proof": {
                "claim": claim,
                "non_effects": string_list(proof.get("non_effects", []), f"ticket {ticket_id}.proof.non_effects"),
                "oracle": oracle,
                "wrong_case": wrong_case,
            },
            "priority": priority,
            "return_contract": require_string(item.get("return_contract"), f"ticket {ticket_id}.return_contract"),
            "scope_area_ids": scopes,
            "source_files": sorted(string_list(item.get("source_files", []), f"ticket {ticket_id}.source_files")),
            "title": require_string(item.get("title"), f"ticket {ticket_id}.title"),
        })
    ticket_out.sort(key=lambda item: item["id"])
    ticket_ids = {item["id"] for item in ticket_out}
    for ticket in ticket_out:
        unknown = set(ticket["dependencies"]) - ticket_ids
        if unknown:
            raise RunError(f"ticket {ticket['id']} has unknown dependencies: {sorted(unknown)}")
        if ticket["id"] in ticket["dependencies"]:
            raise RunError(f"ticket {ticket['id']} cannot depend on itself")
    for cohort_id, cohort in cohort_out.items():
        listed = set(cohort["ticket_ids"])
        actual = {item["id"] for item in ticket_out if item["cohort_id"] == cohort_id}
        if listed != actual:
            raise RunError(f"cohort {cohort_id} ticket_ids do not match assigned tickets")
    detect_cycles(ticket_out)

    cohort_context = shared.get("cohorts", {})
    if not isinstance(cohort_context, dict):
        raise RunError("shared_context.cohorts must be an object")
    return {
        "cohorts": cohort_out,
        "scope_areas": scope_out,
        "shared_context": {
            "cohorts": {key: require_string(cohort_context[key], f"shared context {key}") for key in sorted(cohort_context)},
            "global": require_string(shared.get("global"), "shared_context.global"),
        },
        "tickets": ticket_out,
        "version": 1,
    }


def detect_cycles(tickets: list[dict[str, Any]]) -> None:
    dependencies = {item["id"]: item["dependencies"] for item in tickets}
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(ticket_id: str) -> None:
        if ticket_id in visiting:
            raise RunError(f"dependency cycle includes {ticket_id}")
        if ticket_id in visited:
            return
        visiting.add(ticket_id)
        for dependency in dependencies[ticket_id]:
            visit(dependency)
        visiting.remove(ticket_id)
        visited.add(ticket_id)
    for ticket_id in sorted(dependencies):
        visit(ticket_id)


def run_path(value: str) -> Path:
    path = Path(value).resolve()
    if not (path / "manifest.json").is_file():
        raise RunError(f"not an execution run: {path}")
    return path


def load_manifest(run: Path, *, verify_source: bool = True) -> dict[str, Any]:
    manifest = read_json(run / "manifest.json")
    if not isinstance(manifest, dict) or manifest.get("protocol_version") != PROTOCOL_VERSION:
        raise RunError("unsupported or invalid manifest")
    verify_ticket_revisions(run, manifest)
    verify_pinned_artifacts(run, manifest)
    if manifest.get("graph_sha256") is not None:
        graph_path = run / "ticket-graph.json"
        if not graph_path.is_file() or object_hash(read_json(graph_path)) != manifest["graph_sha256"]:
            raise RunError("normalized Ticket Graph changed or disappeared")
    lock = read_json(run / "source-lock.json")
    if sha_file(run / "source-lock.json") != manifest.get("source_lock_sha256"):
        raise RunError("source lock changed outside the controller")
    if lock.get("source_path") != manifest["source"]["path"] or lock.get("source_sha256") != manifest["source"]["sha256"]:
        raise RunError("source lock and manifest disagree")
    if verify_source:
        source = Path(manifest["source"]["path"])
        if not source.is_file() or sha_file(source) != manifest["source"]["sha256"]:
            raise RunError("locked PRD changed; reconcile the source before continuing")
    return manifest


def save_manifest(run: Path, manifest: dict[str, Any]) -> None:
    atomic_json(run / "manifest.json", manifest)
    write_resume(run, manifest)


def event(run: Path, manifest: dict[str, Any], action: str, payload: dict[str, Any]) -> None:
    sequence = int(manifest.get("event_sequence", 0)) + 1
    record = {"action": action, "payload": payload, "sequence": sequence}
    data = canonical_json(record) + "\n"
    fd = os.open(run / "events.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, data.encode())
        os.fsync(fd)
    finally:
        os.close(fd)
    if os.environ.get("PRD_RUN_FAIL_EVENT_AFTER") == action:
        raise RunError(f"injected event interruption after {action}")
    manifest["event_sequence"] = sequence


def write_resume(run: Path, manifest: dict[str, Any]) -> None:
    active = [ticket_id for ticket_id, item in sorted(manifest.get("tickets", {}).items()) if item["status"] not in ("integrated", "invalidated")]
    blocked = [ticket_id for ticket_id in active if manifest["tickets"][ticket_id]["status"] in ("blocked", "waiting")]
    integration = manifest.get("integration", {})
    lines = [
        "# Execution resume",
        "",
        f"State: {manifest['state']}",
        f"Source SHA-256: {manifest['source']['sha256']}",
        f"Graph SHA-256: {manifest.get('graph_sha256', 'not compiled')}",
        f"Integration branch: {integration.get('branch', 'not recorded')}",
        f"PR strategy: {integration.get('pr_strategy', 'not recorded')}",
        "",
        "## Active tickets",
        "",
        *(f"- {item}" for item in active),
        "",
        "## Blocked tickets",
        "",
        *(f"- {item}" for item in blocked),
        "",
    ]
    atomic_text(run / "resume.md", "\n".join(lines))


def render_ticket(ticket: dict[str, Any], revision: int) -> str:
    def bullets(values: list[str]) -> str:
        return "\n".join(f"- {value}" for value in values) if values else "- None"
    proof = ticket["proof"]
    return f"""# Ticket {ticket['id']}: {ticket['title']}

Revision: {revision}
Epic: {ticket['epic_id']}
Cohort: {ticket['cohort_id']}
Scope areas: {', '.join(ticket['scope_area_ids'])}
Kind: {ticket['kind']}
Priority: {ticket['priority']}
Interface first: {'yes' if ticket['interface_first'] else 'no'}
Affinity: {', '.join(ticket['affinity']) if ticket['affinity'] else 'None'}

## Objective

{ticket['objective']}

## Ownership

{bullets(ticket['ownership'])}

## Dependencies

{bullets(ticket['dependencies'])}

## Constraints

{bullets(ticket['constraints'])}

## Acceptance

{bullets(ticket['acceptance'])}

## Proof contract

Claim: {proof['claim']}

Oracle: {proof['oracle']}

Wrong case: {proof['wrong_case']}

Non-effects:
{bullets(proof['non_effects'])}

## Relevant source files

{bullets(ticket['source_files'])}

## Return contract

{ticket['return_contract']}

## Ask-parent policy

{ticket['ask_parent_policy']}
"""


def render_ticket_graph(graph: dict[str, Any]) -> str:
    lines = ["# Compiled Ticket Graph", ""]
    epic_ids = sorted({item["epic_id"] for item in graph["tickets"]})
    for epic_id in epic_ids:
        lines.extend([f"## Epic {epic_id}", ""])
        for ticket in (item for item in graph["tickets"] if item["epic_id"] == epic_id):
            proof = ticket["proof"]
            fields = [
                ("Objective", ticket["objective"]),
                ("Scope Areas", ", ".join(ticket["scope_area_ids"])),
                ("Ownership", "\n".join(f"- {item}" for item in ticket["ownership"])),
                ("Dependencies", "\n".join(f"- {item}" for item in ticket["dependencies"]) or "None"),
                ("Scheduling", f"Kind: {ticket['kind']}\n\nPriority: {ticket['priority']}\n\nInterface first: {ticket['interface_first']}\n\nAffinity: {', '.join(ticket['affinity']) or 'None'}"),
                ("Constraints And Authority", "\n".join(f"- {item}" for item in ticket["constraints"]) or "None"),
                ("Proof Contract", f"Claim: {proof['claim']}\n\nOracle: {proof['oracle']}\n\nWrong case: {proof['wrong_case']}\n\nNon-effects:\n" + ("\n".join(f"- {item}" for item in proof["non_effects"]) or "- None")),
                ("Return Contract", ticket["return_contract"]),
                ("Ask Parent Policy", ticket["ask_parent_policy"]),
            ]
            lines.extend([f"### Ticket {ticket['id']}: {ticket['title']}", ""])
            for heading, content in fields:
                lines.extend([f"#### {heading}", "", content, ""])
    return "\n".join(lines)


def verify_ticket_revisions(run: Path, manifest: dict[str, Any]) -> None:
    for ticket_id, item in manifest.get("tickets", {}).items():
        history = item.get("revision_history", {str(item["revision"]): {"file": item["ticket_file"], "sha256": item["ticket_sha256"]}})
        for revision, record in history.items():
            path = run / record["file"]
            if not path.is_file() or sha_file(path) != record["sha256"]:
                raise RunError(f"immutable ticket revision changed or disappeared: {ticket_id} r{revision}")


def require_state(manifest: dict[str, Any], allowed: tuple[str, ...]) -> None:
    if manifest["state"] not in allowed:
        raise RunError(f"state {manifest['state']} does not allow this operation; expected {', '.join(allowed)}")


def cmd_init(args: argparse.Namespace) -> None:
    source = Path(args.source).resolve()
    if not source.is_file():
        raise RunError(f"source does not exist: {source}")
    root = Path(args.executions).resolve()
    require_id(args.run_id, "run ID")
    root.mkdir(parents=True, exist_ok=True)
    final_run = root / args.run_id
    if final_run.exists():
        raise RunError(f"run already exists: {final_run}")
    source_info = source_contract(source, args.target)
    integration_branch = require_branch(args.integration_branch or f"run/{args.run_id}", "integration branch")
    stages = sorted(set(item.strip() for item in args.release_stages.split(",") if item.strip()))
    unknown_stages = set(stages) - set(RELEASE_APPLICABILITY)
    if unknown_stages or "merge" not in stages or ("production-verification" in stages and "deployment" not in stages):
        raise RunError("release stages must include merge and production-verification requires deployment")
    run = Path(tempfile.mkdtemp(prefix=f".{args.run_id}.init-", dir=root))
    args._init_temporary = run
    for directory in ("tickets", "receipts", "handoffs", "evidence", "cohorts", "release", "shared-context"):
        (run / directory).mkdir(parents=True, exist_ok=False)
    source_hash = sha_file(source)
    lock = {
        "instruction_version": require_string(args.instruction_version, "instruction version"),
        "release_contract": require_string(args.release_contract, "release contract"),
        "release_stages": stages,
        "source_path": str(source), "source_sha256": source_hash,
        "target_epic_ids": source_info["epic_ids"], "scope_hashes": source_info["scope_hashes"],
    }
    manifest = {
        "artifact_hashes": {}, "cohorts": {}, "event_sequence": 0, "generation": 0, "graph_sha256": None,
        "ownership": {
            "children": ["assigned code worktree", "receipt input", "named evidence"],
            "parent": ["source-lock.json", "manifest.json", "resume.md", "events.jsonl", "cohorts/", "release/"],
        },
        "protocol_version": PROTOCOL_VERSION,
        "integration": {
            "branch": integration_branch,
            "merge_executor": "parent-after-user-authority",
            "mode": INTEGRATION_MODE,
            "pr_strategy": PR_STRATEGY,
        },
        "release": {"applicability": {key: key in stages for key in RELEASE_APPLICABILITY}},
        "run_id": args.run_id, "shared_context": {}, "lanes": {},
        "source": {"path": str(source), "sha256": source_hash}, "state": "discussing", "tickets": {},
    }
    atomic_json(run / "source-lock.json", lock)
    if os.environ.get("PRD_RUN_FAIL_INIT_AFTER") == "source-lock":
        raise RunError("injected initialization interruption after source lock")
    manifest["source_lock_sha256"] = sha_file(run / "source-lock.json")
    atomic_text(run / "events.jsonl", "")
    atomic_text(run / "shared-context" / "global-v1.md", "# Global context\n\nNot compiled.\n")
    for stage in (*RELEASE_STAGES, "merge", "rollback", "prd-verification"):
        atomic_text(run / "release" / f"{stage}.md", f"# {stage.replace('-', ' ').title()}\n\nNot recorded.\n")
    pin_artifact(run, manifest, run / "shared-context" / "global-v1.md")
    event(run, manifest, "run_initialized", {"source_sha256": source_hash})
    save_manifest(run, manifest)
    try:
        os.rename(run, final_run)
    except OSError as exc:
        raise RunError(f"cannot publish execution run {final_run}: {exc}") from exc
    args._init_temporary = None
    print(final_run)


def cmd_transition(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    target = args.to
    if target not in STATES:
        raise RunError(f"unknown state {target}")
    current_index = STATES.index(manifest["state"])
    if current_index + 1 >= len(STATES) or STATES[current_index + 1] != target:
        raise RunError(f"invalid transition {manifest['state']} -> {target}")
    if target == "cohort_verified":
        pending = [key for key, item in manifest["tickets"].items() if item["status"] != "integrated"]
        unverified = [key for key, item in manifest["cohorts"].items() if item.get("result") != "pass"]
        if pending or unverified:
            raise RunError(f"cannot verify cohorts; pending tickets={pending}, unverified cohorts={unverified}")
    if target == "prd_verified" and manifest["release"].get("prd-verification", {}).get("result") != "pass":
        raise RunError("full PRD verification has not passed")
    if target == "merged" and manifest["release"].get("merge", {}).get("result") != "pass":
        raise RunError("exact-main merge verification has not passed")
    if target == "deployed":
        expected = "pass" if manifest["release"]["applicability"]["deployment"] else "skipped"
        if manifest["release"].get("deployment", {}).get("result") != expected:
            raise RunError(f"deployment stage must be {expected}")
    if target in ("production_verified", "complete"):
        expected = "pass" if manifest["release"]["applicability"]["production-verification"] else "skipped"
        if manifest["release"].get("production-verification", {}).get("result") != expected:
            raise RunError(f"production verification stage must be {expected}")
    manifest["state"] = target
    event(run, manifest, "state_transitioned", {"to": target})
    save_manifest(run, manifest)


def ticket_entry(ticket: dict[str, Any], revision: int, path: Path, scope_hashes: dict[str, str]) -> dict[str, Any]:
    digest = sha_file(path)
    return {
        "cohort_id": ticket["cohort_id"], "dependencies": ticket["dependencies"], "lease": None,
        "revision": revision, "scope_area_ids": ticket["scope_area_ids"],
        "scope_hashes": {key: scope_hashes[key] for key in ticket["scope_area_ids"]},
        "revision_history": {str(revision): {"file": f"tickets/{path.name}", "sha256": digest}},
        "status": "ready" if not ticket["dependencies"] else "waiting",
        "ticket_file": f"tickets/{path.name}", "ticket_sha256": digest,
    }


def cmd_compile(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    require_state(manifest, ("accepted",))
    graph = normalize_graph(read_json(Path(args.graph)))
    lock = read_json(run / "source-lock.json")
    graph_epics = {item["epic_id"] for item in graph["tickets"]}
    if graph_epics != set(lock["target_epic_ids"]):
        raise RunError(f"ticket graph Epics {sorted(graph_epics)} do not match locked targets {lock['target_epic_ids']}")
    if set(graph["scope_areas"]) != set(lock["scope_hashes"]):
        raise RunError("ticket graph Scope Areas do not exactly match the locked PRD target")
    referenced_scopes = {scope for item in graph["tickets"] for scope in item["scope_area_ids"]}
    if referenced_scopes != set(lock["scope_hashes"]):
        raise RunError("every locked Scope Area must be owned by at least one Ticket")
    scope_hashes = dict(lock["scope_hashes"])
    backup, base_generation = begin_transaction_backup(
        run, "compile", ["manifest.json", "resume.md", "events.jsonl", "shared-context", "tickets"],
        ["ticket-graph.json", "ticket-graph.md"],
    )
    tickets: dict[str, Any] = {}
    for ticket in graph["tickets"]:
        path = run / "tickets" / f"{ticket['id']}.r1.md"
        atomic_text(path, render_ticket(ticket, 1))
        tickets[ticket["id"]] = ticket_entry(ticket, 1, path, scope_hashes)
    global_context = "# Global context\n\n" + graph["shared_context"]["global"].strip() + "\n"
    atomic_text(run / "shared-context" / "global-v1.md", global_context)
    if os.environ.get("PRD_RUN_FAIL_COMPILE_AFTER") == "global-context":
        raise RunError("injected compile interruption after global context")
    for cohort_id in sorted(graph["cohorts"]):
        context = graph["shared_context"]["cohorts"].get(cohort_id, graph["cohorts"][cohort_id]["invariant"])
        atomic_text(run / "shared-context" / f"{cohort_id.lower()}-v1.md", f"# Cohort {cohort_id} context\n\n{context.strip()}\n")
    manifest["tickets"] = tickets
    manifest["cohorts"] = {key: {"result": None, **graph["cohorts"][key]} for key in sorted(graph["cohorts"])}
    manifest["shared_context"] = {
        "cohorts": {key: f"shared-context/{key.lower()}-v1.md" for key in sorted(graph["cohorts"])},
        "global": "shared-context/global-v1.md",
    }
    manifest["graph_sha256"] = object_hash(graph)
    manifest["state"] = "compiled"
    atomic_json(run / "ticket-graph.json", graph)
    atomic_text(run / "ticket-graph.md", render_ticket_graph(graph))
    pin_artifact(run, manifest, run / "ticket-graph.json")
    pin_artifact(run, manifest, run / "ticket-graph.md")
    pin_artifact(run, manifest, run / manifest["shared_context"]["global"])
    for relative in manifest["shared_context"]["cohorts"].values():
        pin_artifact(run, manifest, run / relative)
    event(run, manifest, "graph_compiled", {"graph_sha256": manifest["graph_sha256"], "tickets": sorted(tickets)})
    manifest["generation"] = base_generation + 1
    save_manifest(run, manifest)
    if os.environ.get("PRD_RUN_FAIL_COMPILE_AFTER") == "manifest":
        raise RunError("injected compile interruption after committed manifest")
    shutil.rmtree(backup)


def get_ticket(manifest: dict[str, Any], ticket_id: str) -> dict[str, Any]:
    if ticket_id not in manifest["tickets"]:
        raise RunError(f"unknown ticket {ticket_id}")
    return manifest["tickets"][ticket_id]


def refresh_readiness(manifest: dict[str, Any]) -> None:
    for ticket_id, item in manifest["tickets"].items():
        if item["status"] == "waiting" and all(manifest["tickets"][dep]["status"] == "integrated" for dep in item["dependencies"]):
            item["status"] = "ready"


def cmd_claim(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    require_state(manifest, ("executing", "integrating"))
    refresh_readiness(manifest)
    item = get_ticket(manifest, args.ticket)
    retry = item["status"] == "blocked" and item["lease"] is not None
    if item["status"] != "ready" and not retry:
        raise RunError(f"ticket {args.ticket} is {item['status']}, not ready")
    agent = require_string(args.agent, "agent")
    active = [ticket_id for ticket_id, other in manifest["tickets"].items() if ticket_id != args.ticket and other["status"] == "dispatched" and (other.get("lease") or {}).get("agent") == agent]
    if active:
        raise RunError(f"agent {agent} already owns active ticket {active[0]}")
    if args.attempt < 1:
        raise RunError("attempt must be positive")
    if retry and args.attempt <= item["lease"]["attempt"]:
        raise RunError("retry attempt must exceed the previous lease attempt")
    item["lease"] = {"agent": agent, "attempt": args.attempt}
    item["status"] = "dispatched"
    event(run, manifest, "ticket_claimed", {"agent": agent, "attempt": args.attempt, "revision": item["revision"], "ticket": args.ticket})
    save_manifest(run, manifest)


def cmd_claim_lane(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    require_state(manifest, ("executing", "integrating"))
    refresh_readiness(manifest)
    lane_id = require_lane(args.lane)
    lanes = manifest.setdefault("lanes", {})
    if lane_id in lanes:
        raise RunError(f"lane {lane_id} already exists")
    ticket_ids = sorted(set(args.ticket))
    if len(ticket_ids) != len(args.ticket):
        raise RunError("lane tickets must be unique")
    if args.attempt < 1:
        raise RunError("attempt must be positive")
    agent = require_string(args.agent, "agent")
    active = [
        ticket_id for ticket_id, item in manifest["tickets"].items()
        if item["status"] == "dispatched" and (item.get("lease") or {}).get("agent") == agent
    ]
    if active:
        raise RunError(f"agent {agent} already owns active ticket {active[0]}")
    graph = read_json(run / "ticket-graph.json")
    graph_by_id = {item["id"]: item for item in graph["tickets"]}
    items = []
    for ticket_id in ticket_ids:
        state = get_ticket(manifest, ticket_id)
        if state["status"] != "ready":
            raise RunError(f"ticket {ticket_id} is {state['status']}, not ready")
        ticket = graph_by_id[ticket_id]
        if args.affinity not in ticket["affinity"]:
            raise RunError(f"ticket {ticket_id} does not declare lane affinity {args.affinity}")
        items.append((ticket_id, state, ticket))
    cohorts = {ticket["cohort_id"] for _, _, ticket in items}
    dependencies = {tuple(ticket["dependencies"]) for _, _, ticket in items}
    if len(cohorts) != 1 or len(dependencies) != 1:
        raise RunError("lane tickets must share one cohort and identical dependency contracts")
    lanes[lane_id] = {
        "affinity": args.affinity,
        "agent": agent,
        "attempt": args.attempt,
        "cohort_id": next(iter(cohorts)),
        "dependencies": list(next(iter(dependencies))),
        "ticket_ids": ticket_ids,
    }
    for ticket_id, state, _ in items:
        state["lease"] = {"agent": agent, "attempt": args.attempt, "lane": lane_id}
        state["status"] = "dispatched"
        event(run, manifest, "ticket_claimed", {
            "agent": agent, "attempt": args.attempt, "lane": lane_id,
            "revision": state["revision"], "ticket": ticket_id,
        })
    event(run, manifest, "lane_claimed", {
        "affinity": args.affinity, "agent": agent, "attempt": args.attempt,
        "lane": lane_id, "tickets": ticket_ids,
    })
    save_manifest(run, manifest)


def cmd_ready(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    require_state(manifest, ("executing", "integrating"))
    refresh_readiness(manifest)
    graph = read_json(run / "ticket-graph.json")
    graph_by_id = {item["id"]: item for item in graph["tickets"]}
    dependents = {ticket_id: set() for ticket_id in graph_by_id}
    for ticket_id, item in graph_by_id.items():
        for dependency in item["dependencies"]:
            dependents[dependency].add(ticket_id)
    def unlocked(ticket_id: str) -> int:
        seen = set()
        stack = list(dependents[ticket_id])
        while stack:
            current = stack.pop()
            if current not in seen:
                seen.add(current); stack.extend(dependents[current])
        return len(seen)
    candidates = []
    for ticket_id, state in manifest["tickets"].items():
        if state["status"] != "ready":
            continue
        ticket = graph_by_id[ticket_id]
        affinity_match = bool(args.affinity and args.affinity in ticket["affinity"])
        candidates.append({
            "affinity_match": affinity_match, "interface_first": ticket["interface_first"],
            "priority": ticket["priority"], "ticket": ticket_id, "unlocks": unlocked(ticket_id),
        })
    candidates.sort(key=lambda item: (not item["affinity_match"], not item["interface_first"], item["priority"], -item["unlocks"], item["ticket"]))
    print(pretty_json(candidates), end="")


def cmd_resume(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    load_manifest(run)
    sys.stdout.write((run / "resume.md").read_text())


def dependency_receipts(run: Path, manifest: dict[str, Any], item: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for dependency in item["dependencies"]:
        dep = manifest["tickets"][dependency]
        path = run / dep.get("receipt_file", "")
        if dep["status"] != "integrated" or not dep.get("receipt_file") or not path.is_file():
            raise RunError(f"dependency {dependency} is not integrated")
        receipt = read_json(path)
        evidence = []
        for reference in receipt["evidence"]:
            candidate = Path(reference)
            if candidate.is_absolute():
                candidate = candidate.resolve().relative_to(run)
            evidence.append(candidate.as_posix())
        output.append({"evidence": evidence, "outputs": receipt["outputs"], "summary": receipt["summary"], "ticket": dependency})
    return output


def materialize_bundle(run: Path, manifest: dict[str, Any], ticket_id: str) -> dict[str, Any]:
    item = get_ticket(manifest, ticket_id)
    if item["status"] != "dispatched" or not item.get("lease"):
        raise RunError(f"ticket {ticket_id} cannot be materialized while {item['status']}")
    cohort_id = item["cohort_id"]
    dependencies = dependency_receipts(run, manifest, item)
    lease = item["lease"]
    stem = f"{ticket_id}.r{item['revision']}.a{lease['attempt']}"
    canonical_bundle = run / "handoffs" / f"{stem}.bundle.md"
    metadata_path = run / "handoffs" / f"{stem}.context.json"
    canonical_relative = str(canonical_bundle.relative_to(run))
    if (
        canonical_bundle.is_file()
        and canonical_relative in manifest.get("artifact_hashes", {})
        and not metadata_path.exists()
    ):
        return {
            "bundle": canonical_relative,
            "content": canonical_bundle.read_text(),
            "metadata": None,
            "stable_prefix_sha256": None,
            "ticket": ticket_id,
        }
    evidence_destination = f"evidence/{stem}.md"
    receipt_destination = f"handoffs/{stem}.receipt.json"
    evidence_absolute = str(run / evidence_destination)
    receipt_absolute = str(run / receipt_destination)
    receipt_schema = pretty_json({
        "agent": lease["agent"], "attempt": lease["attempt"], "changed_paths": [],
        "evidence": [evidence_absolute], "outputs": [], "revision": item["revision"],
        "risks": [], "status": "complete", "summary": "<concise behavioral result>", "ticket": ticket_id,
    }).rstrip()
    handoff = (
        "Protocol: prd-run/v1\n"
        "Use only this bundle, the named relevant source files, and direct tool observations.\n"
        "Do not read the PRD, manifest, event log, or unrelated tickets and receipts.\n"
        "Work only within ticket ownership. Return the requested compact receipt inputs to the parent.\n\n"
        f"Execution run root: `{run}`\n"
        f"Write meaningful raw evidence to `{evidence_absolute}`.\n"
        f"Write the compact receipt JSON to `{receipt_absolute}` using this exact schema:\n\n"
        f"```json\n{receipt_schema}\n```\n"
    )
    handoff_relative = f"handoffs/{stem}.handoff.md"
    atomic_text(run / handoff_relative, handoff)
    dependency_sources = []
    for dependency in dependencies:
        relative = f"handoffs/{stem}.dependency-{dependency['ticket']}.json"
        atomic_json(run / relative, dependency)
        dependency_sources.append({"id": dependency["ticket"], "path": relative, "role": "dependency"})
    graph = read_json(run / "ticket-graph.json")
    ticket = next(value for value in graph["tickets"] if value["id"] == ticket_id)
    context_manifest = {
        "family": "review" if ticket["kind"] == "verification" else "implementation",
        "schema_version": 1,
        "stable_sources": [
            {"id": "global", "path": manifest["shared_context"]["global"], "role": "global"},
            {"id": cohort_id, "path": manifest["shared_context"]["cohorts"][cohort_id], "role": "cohort"},
            *dependency_sources,
        ],
        "template_version": 1,
        "volatile_sources": [
            {"id": ticket_id, "path": item["ticket_file"], "role": "ticket"},
            {"id": f"{ticket_id}.r{item['revision']}.a{lease['attempt']}", "path": handoff_relative, "role": "handoff"},
        ],
    }
    try:
        rendered = render_manifest(
            context_manifest,
            source_root=run,
            template_root=Path(__file__).resolve().parents[1] / "templates" / "generated-context",
        )
    except ContextError as exc:
        raise RunError(f"generated context failed ({exc.code}): {exc}") from exc
    bundle = rendered.prompt.decode("utf-8")
    if canonical_bundle.exists() and canonical_bundle.read_text() != bundle:
        raise RunError("materialized bundle for this lease is immutable")
    if metadata_path.exists() and metadata_path.read_bytes() != rendered.metadata_bytes:
        raise RunError("generated-context metadata for this lease is immutable")
    atomic_text(canonical_bundle, bundle)
    atomic_text(metadata_path, rendered.metadata_bytes.decode("utf-8"))
    for relative in [handoff_relative, *(source["path"] for source in dependency_sources)]:
        pin_artifact(run, manifest, run / relative)
    pin_artifact(run, manifest, canonical_bundle)
    pin_artifact(run, manifest, metadata_path)
    return {
        "bundle": str(canonical_bundle.relative_to(run)),
        "content": bundle,
        "metadata": str(metadata_path.relative_to(run)),
        "stable_prefix_sha256": rendered.metadata["stable_prefix_sha256"],
        "ticket": ticket_id,
    }


def cmd_materialize(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    if args.output:
        output = Path(args.output).resolve()
        try:
            output.relative_to(run)
        except ValueError:
            pass
        else:
            raise RunError("--output cannot overwrite execution-run files; use the canonical handoff bundle")
    result = materialize_bundle(run, manifest, args.ticket)
    save_manifest(run, manifest)
    if args.output:
        atomic_text(Path(args.output), result["content"])
    else:
        sys.stdout.write(result["content"])


def cmd_materialize_lane(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    lane_id = require_lane(args.lane)
    lane = manifest.get("lanes", {}).get(lane_id)
    if not lane:
        raise RunError(f"unknown lane {lane_id}")
    eligible = [
        ticket_id for ticket_id in lane["ticket_ids"]
        if manifest["tickets"][ticket_id]["status"] == "dispatched"
        and (manifest["tickets"][ticket_id].get("lease") or {}).get("lane") == lane_id
    ]
    if not eligible:
        raise RunError(f"lane {lane_id} has no dispatched tickets to materialize")
    results = [materialize_bundle(run, manifest, ticket_id) for ticket_id in eligible]
    save_manifest(run, manifest)
    public = {
        "lane": lane_id,
        "tickets": [{key: value for key, value in item.items() if key != "content"} for item in results],
    }
    print(pretty_json(public), end="")


def validate_receipt(raw: Any, item: dict[str, Any], ticket_id: str, agent: str, attempt: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise RunError("receipt must be an object")
    allowed = {"agent", "attempt", "changed_paths", "evidence", "outputs", "revision", "risks", "status", "summary", "ticket"}
    extra = set(raw) - allowed
    if extra:
        raise RunError(f"receipt has unsupported fields: {sorted(extra)}")
    expected = {"agent": agent, "attempt": attempt, "revision": item["revision"], "ticket": ticket_id}
    for key, value in expected.items():
        if raw.get(key) != value:
            raise RunError(f"receipt {key} does not match active lease")
    if raw.get("status") not in ("complete", "blocked"):
        raise RunError("receipt status must be complete or blocked")
    evidence = string_list(raw.get("evidence"), "receipt.evidence", allow_empty=raw["status"] == "blocked")
    for ref in evidence:
        if ".." in Path(ref).parts:
            raise RunError("evidence references cannot traverse directories")
    receipt = {
        "agent": agent, "attempt": attempt,
        "evidence": sorted(evidence), "outputs": sorted(string_list(raw.get("outputs", []), "receipt.outputs")),
        "revision": item["revision"],
        "status": raw["status"], "summary": require_string(raw.get("summary"), "receipt.summary"), "ticket": ticket_id,
    }
    changed_paths = sorted(string_list(raw.get("changed_paths", []), "receipt.changed_paths"))
    risks = string_list(raw.get("risks", []), "receipt.risks")
    if changed_paths:
        receipt["changed_paths"] = changed_paths
    if risks:
        receipt["risks"] = risks
    return receipt

def cmd_receipt(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    require_state(manifest, ("executing", "integrating"))
    item = get_ticket(manifest, args.ticket)
    if item["status"] != "dispatched" or not item["lease"]:
        raise RunError(f"ticket {args.ticket} has no active lease")
    lease = item["lease"]
    receipt = validate_receipt(read_json(Path(args.receipt)), item, args.ticket, lease["agent"], lease["attempt"])
    validated_evidence = []
    for ref in receipt["evidence"]:
        evidence_path = Path(ref) if Path(ref).is_absolute() else run / ref
        evidence_path, _ = proof_path(
            run, evidence_path, "child evidence",
            name_prefix=f"{args.ticket}.r{item['revision']}.a{lease['attempt']}",
        )
        validated_evidence.append(evidence_path)
    path = run / "receipts" / f"{args.ticket}.r{item['revision']}.a{lease['attempt']}.json"
    if path.exists():
        raise RunError(f"receipt already recorded for {args.ticket} revision {item['revision']}")
    atomic_json(path, receipt)
    pin_artifact(run, manifest, path)
    for evidence_path in validated_evidence:
        pin_artifact(run, manifest, evidence_path)
    item["receipt_file"] = str(path.relative_to(run))
    item["status"] = "completed" if receipt["status"] == "complete" else "blocked"
    event(run, manifest, "receipt_recorded", {"revision": item["revision"], "status": receipt["status"], "ticket": args.ticket})
    save_manifest(run, manifest)


def cmd_integrate(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    require_state(manifest, ("executing", "integrating"))
    item = get_ticket(manifest, args.ticket)
    if item["status"] != "completed":
        raise RunError(f"ticket {args.ticket} is not completed")
    evidence, relative = proof_path(run, Path(args.evidence), "ticket integration evidence")
    receipt_path = run / item.get("receipt_file", "")
    if not item.get("receipt_file") or not receipt_path.is_file():
        raise RunError("ticket has no recorded receipt for the active attempt")
    child_evidence = set(read_json(receipt_path).get("evidence", []))
    child_hashes = {sha_file(run / ref) for ref in child_evidence}
    if relative in child_evidence or sha_file(evidence) in child_hashes:
        raise RunError("parent integration evidence must be distinct in path and content from child-reported evidence")
    item["integration_verification"] = {
        "evidence": relative,
        "summary": require_string(args.summary, "integration summary"),
    }
    pin_artifact(run, manifest, evidence)
    item["status"] = "integrated"
    item["lease"] = None
    refresh_readiness(manifest)
    event(run, manifest, "ticket_integrated", {"evidence": relative, "revision": item["revision"], "ticket": args.ticket})
    save_manifest(run, manifest)


def cmd_verify_cohort(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    require_state(manifest, ("integrating",))
    if args.cohort not in manifest["cohorts"]:
        raise RunError(f"unknown cohort {args.cohort}")
    cohort = manifest["cohorts"][args.cohort]
    pending = [ticket_id for ticket_id in cohort["ticket_ids"] if manifest["tickets"][ticket_id]["status"] != "integrated"]
    if pending:
        raise RunError(f"cohort has pending tickets: {pending}")
    evidence, relative = proof_path(run, Path(args.evidence), "cohort evidence")
    cohort["result"] = args.result
    cohort["evidence"] = relative
    cohort_report = run / "cohorts" / f"{args.cohort.lower()}.md"
    atomic_text(cohort_report, evidence.read_text())
    pin_artifact(run, manifest, evidence)
    pin_artifact(run, manifest, cohort_report)
    event(run, manifest, "cohort_verified", {"cohort": args.cohort, "result": args.result})
    save_manifest(run, manifest)


def cmd_record_release(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    stage = args.stage
    allowed_states = {"deployment": ("merged",), "production-verification": ("deployed",)}
    require_state(manifest, allowed_states[stage])
    evidence = require_string(args.evidence, "evidence")
    summary = require_string(args.summary, "summary")
    applicable = manifest["release"]["applicability"][stage]
    if applicable and args.result == "skipped":
        raise RunError(f"applicable release stage cannot be skipped: {stage}")
    if not applicable and args.result != "skipped":
        raise RunError(f"inapplicable release stage must be recorded as skipped: {stage}")
    previous = manifest["release"].get(stage, {})
    if previous.get("result") == "fail" and args.result == "pass" and manifest["release"].get("rollback", {}).get("result") != "pass":
        raise RunError(f"failed {stage} cannot be replaced with pass until rollback evidence is recorded")
    if stage == "deployment" and applicable and args.result == "pass":
        revision = require_string(args.revision, "deployed revision").lower()
        if revision != manifest["release"].get("merge", {}).get("main_sha"):
            raise RunError("deployment revision must equal the verified merged main SHA")
    else:
        revision = args.revision
    manifest["release"][stage] = {"evidence": evidence, "result": args.result, "summary": summary}
    if revision:
        manifest["release"][stage]["revision"] = revision
    revision_line = f"\nRevision: {revision}\n" if revision else ""
    report = f"# {stage.replace('-', ' ').title()}\n\nResult: {args.result}\n\nSummary: {summary}\n{revision_line}\nEvidence: {evidence}\n"
    atomic_text(run / "release" / f"{stage}.md", report)
    pin_artifact(run, manifest, run / "release" / f"{stage}.md")
    event(run, manifest, "release_stage_recorded", {"result": args.result, "stage": stage})
    save_manifest(run, manifest)


def cmd_verify_prd(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    require_state(manifest, ("cohort_verified",))
    evidence, relative = proof_path(run, Path(args.evidence), "full PRD evidence")
    prior_proof_hashes = set()
    for ticket_id, item in manifest["tickets"].items():
        receipt = run / item.get("receipt_file", "")
        if receipt.is_file():
            for ref in read_json(receipt).get("evidence", []):
                prior_proof_hashes.add(sha_file(Path(ref) if Path(ref).is_absolute() else run / ref))
        integration_ref = item.get("integration_verification", {}).get("evidence")
        if integration_ref:
            prior_proof_hashes.add(sha_file(run / integration_ref))
    for cohort in manifest["cohorts"].values():
        if cohort.get("evidence"):
            prior_proof_hashes.add(sha_file(run / cohort["evidence"]))
    if sha_file(evidence) in prior_proof_hashes:
        raise RunError("full PRD evidence must be independently produced, not copied from earlier proof")
    manifest["release"]["prd-verification"] = {
        "evidence": relative, "result": args.result,
        "summary": require_string(args.summary, "full PRD summary"),
    }
    report = run / "release" / "prd-verification.md"
    atomic_text(report, f"# PRD Verification\n\nResult: {args.result}\n\nSummary: {args.summary}\n\nEvidence: {relative}\n")
    pin_artifact(run, manifest, evidence); pin_artifact(run, manifest, report)
    event(run, manifest, "prd_verified", {"result": args.result})
    save_manifest(run, manifest)


def cmd_record_merge(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    require_state(manifest, ("prd_verified",))
    merged = require_string(args.merged_sha, "merged SHA").lower()
    main = require_string(args.main_sha, "main SHA").lower()
    if not re.fullmatch(r"[0-9a-f]{7,64}", merged) or merged != main:
        raise RunError("merged SHA and verified main SHA must be the same Git object ID")
    integration = manifest.get("integration", {})
    record = {
        "evidence": require_string(args.evidence, "merge evidence"),
        "integration_branch": integration.get("branch"),
        "main_sha": main,
        "merged_sha": merged,
        "pr": require_string(args.pr, "PR reference"),
        "pr_strategy": integration.get("pr_strategy"),
        "result": "pass",
    }
    manifest["release"]["merge"] = record
    report = run / "release" / "merge.md"
    atomic_text(report, f"# Merge\n\nResult: pass\n\nPR: {record['pr']}\n\nIntegration branch: {record['integration_branch'] or 'not recorded'}\n\nPR strategy: {record['pr_strategy'] or 'not recorded'}\n\nMerged SHA: {merged}\n\nVerified main SHA: {main}\n\nEvidence: {record['evidence']}\n")
    pin_artifact(run, manifest, report)
    event(run, manifest, "merge_recorded", {"main_sha": main, "pr": record["pr"]})
    save_manifest(run, manifest)


def cmd_record_rollback(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    record = {
        "action": require_string(args.action, "rollback action"), "evidence": require_string(args.evidence, "rollback evidence"),
        "result": args.result, "trigger": require_string(args.trigger, "rollback trigger"),
    }
    manifest["release"]["rollback"] = record
    report = run / "release" / "rollback.md"
    atomic_text(report, f"# Rollback\n\nResult: {args.result}\n\nTrigger: {record['trigger']}\n\nAction: {record['action']}\n\nEvidence: {record['evidence']}\n")
    pin_artifact(run, manifest, report)
    event(run, manifest, "rollback_recorded", {"result": args.result})
    save_manifest(run, manifest)


def cmd_reconcile(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run, verify_source=False)
    require_state(manifest, ("compiled", "executing", "integrating"))
    source = Path(args.source).resolve()
    if not source.is_file():
        raise RunError(f"source does not exist: {source}")
    graph = normalize_graph(read_json(Path(args.graph)))
    old_graph = read_json(run / "ticket-graph.json")
    old_by_id = {item["id"]: item for item in old_graph["tickets"]}
    new_by_id = {item["id"]: item for item in graph["tickets"]}
    if set(old_by_id) != set(new_by_id):
        raise RunError("reconcile cannot add or remove tickets; compile a new run")
    lock = read_json(run / "source-lock.json")
    source_info = source_contract(source, lock["target_epic_ids"])
    if {item["epic_id"] for item in graph["tickets"]} != set(lock["target_epic_ids"]):
        raise RunError("reconciled graph Epics do not match the locked target")
    if set(graph["scope_areas"]) != set(source_info["scope_hashes"]):
        raise RunError("reconciled graph Scope Areas do not match the PRD target")
    if (
        str(source) == lock["source_path"]
        and sha_file(source) == lock["source_sha256"]
        and object_hash(graph) == manifest["graph_sha256"]
    ):
        print(pretty_json({"changed_scopes": [], "invalidated_tickets": []}), end="")
        return
    new_scope_hashes = source_info["scope_hashes"]
    changed_scopes = {key for key in set(lock["scope_hashes"]) | set(new_scope_hashes) if lock["scope_hashes"].get(key) != new_scope_hashes.get(key)}
    impacted = {ticket_id for ticket_id, item in new_by_id.items() if changed_scopes.intersection(item["scope_area_ids"]) or object_hash(item) != object_hash(old_by_id[ticket_id])}
    old_shared = old_graph["shared_context"]
    new_shared = graph["shared_context"]
    if old_shared["global"] != new_shared["global"]:
        impacted.update(new_by_id)
    changed_cohort_contexts = {
        cohort_id for cohort_id in graph["cohorts"]
        if old_shared["cohorts"].get(cohort_id, old_graph["cohorts"][cohort_id]["invariant"])
        != new_shared["cohorts"].get(cohort_id, graph["cohorts"][cohort_id]["invariant"])
    }
    changed_cohorts = {
        cohort_id for cohort_id in graph["cohorts"]
        if object_hash(old_graph["cohorts"][cohort_id]) != object_hash(graph["cohorts"][cohort_id])
    }
    changed_cohort_contexts.update(changed_cohorts)
    impacted.update(ticket_id for ticket_id, item in new_by_id.items() if item["cohort_id"] in changed_cohort_contexts)
    changed = True
    while changed:
        changed = False
        for ticket_id, item in new_by_id.items():
            if ticket_id not in impacted and impacted.intersection(item["dependencies"]):
                impacted.add(ticket_id)
                changed = True
    backup, base_generation = begin_transaction_backup(
        run, "reconcile",
        ["source-lock.json", "ticket-graph.json", "ticket-graph.md", "manifest.json", "resume.md", "events.jsonl"],
        [],
    )
    for ticket_id in sorted(impacted):
        item = manifest["tickets"][ticket_id]
        history = dict(item.get("revision_history", {}))
        revision = item["revision"] + 1
        path = run / "tickets" / f"{ticket_id}.r{revision}.md"
        atomic_text(path, render_ticket(new_by_id[ticket_id], revision))
        manifest["tickets"][ticket_id] = ticket_entry(new_by_id[ticket_id], revision, path, new_scope_hashes)
        manifest["tickets"][ticket_id]["revision_history"] = {**history, **manifest["tickets"][ticket_id]["revision_history"]}
    if old_shared["global"] != new_shared["global"]:
        current = Path(manifest["shared_context"]["global"])
        version = int(re.search(r"-v(\d+)\.md$", current.name).group(1)) + 1
        relative = Path("shared-context") / f"global-v{version}.md"
        atomic_text(run / relative, "# Global context\n\n" + new_shared["global"].strip() + "\n")
        manifest["shared_context"]["global"] = str(relative)
    for cohort_id in sorted(graph["cohorts"]):
        old_context = old_shared["cohorts"].get(cohort_id, old_graph["cohorts"][cohort_id]["invariant"])
        new_context = new_shared["cohorts"].get(cohort_id, graph["cohorts"][cohort_id]["invariant"])
        if old_context != new_context:
            current = Path(manifest["shared_context"]["cohorts"][cohort_id])
            version = int(re.search(r"-v(\d+)\.md$", current.name).group(1)) + 1
            relative = Path("shared-context") / f"{cohort_id.lower()}-v{version}.md"
            atomic_text(run / relative, f"# Cohort {cohort_id} context\n\n{new_context.strip()}\n")
            manifest["shared_context"]["cohorts"][cohort_id] = str(relative)
    lock = {
        **lock,
        "source_path": str(source), "source_sha256": sha_file(source),
        "target_epic_ids": source_info["epic_ids"], "scope_hashes": new_scope_hashes,
    }
    manifest["source"] = {"path": str(source), "sha256": lock["source_sha256"]}
    manifest["graph_sha256"] = object_hash(graph)
    previous_cohorts = manifest["cohorts"]
    manifest["cohorts"] = {}
    for key in sorted(graph["cohorts"]):
        affected = key in changed_cohort_contexts or bool(set(graph["cohorts"][key]["ticket_ids"]) & impacted)
        preserved = previous_cohorts.get(key, {}) if not affected else {}
        manifest["cohorts"][key] = {**graph["cohorts"][key], "result": preserved.get("result")}
        if preserved.get("evidence"):
            manifest["cohorts"][key]["evidence"] = preserved["evidence"]
    atomic_json(run / "source-lock.json", lock)
    manifest["source_lock_sha256"] = sha_file(run / "source-lock.json")
    if os.environ.get("PRD_RUN_FAIL_RECONCILE_AFTER") == "source-lock":
        raise RunError("injected reconcile interruption after source lock")
    atomic_json(run / "ticket-graph.json", graph)
    atomic_text(run / "ticket-graph.md", render_ticket_graph(graph))
    pin_artifact(run, manifest, run / "ticket-graph.json")
    pin_artifact(run, manifest, run / "ticket-graph.md")
    pin_artifact(run, manifest, run / manifest["shared_context"]["global"])
    for relative in manifest["shared_context"]["cohorts"].values():
        pin_artifact(run, manifest, run / relative)
    event(run, manifest, "source_reconciled", {"changed_scopes": sorted(changed_scopes), "invalidated_tickets": sorted(impacted)})
    manifest["generation"] = base_generation + 1
    save_manifest(run, manifest)
    if os.environ.get("PRD_RUN_FAIL_RECONCILE_AFTER") == "manifest":
        raise RunError("injected reconcile interruption after committed manifest")
    shutil.rmtree(backup)
    print(pretty_json({"changed_scopes": sorted(changed_scopes), "invalidated_tickets": sorted(impacted)}), end="")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--executions", required=True); init.add_argument("--run-id", required=True); init.add_argument("--source", required=True)
    init.add_argument("--target", required=True, action="append"); init.add_argument("--instruction-version", default="prd-run/v1")
    init.add_argument("--release-contract", required=True); init.add_argument("--release-stages", default="merge")
    init.add_argument("--integration-branch")
    init.set_defaults(func=cmd_init)
    transition = commands.add_parser("transition")
    transition.add_argument("--run", required=True); transition.add_argument("--to", required=True); transition.set_defaults(func=cmd_transition)
    compile_cmd = commands.add_parser("compile")
    compile_cmd.add_argument("--run", required=True); compile_cmd.add_argument("--graph", required=True); compile_cmd.set_defaults(func=cmd_compile)
    claim = commands.add_parser("claim")
    claim.add_argument("--run", required=True); claim.add_argument("--ticket", required=True); claim.add_argument("--agent", required=True); claim.add_argument("--attempt", required=True, type=int); claim.set_defaults(func=cmd_claim)
    claim_lane = commands.add_parser("claim-lane")
    claim_lane.add_argument("--run", required=True); claim_lane.add_argument("--lane", required=True); claim_lane.add_argument("--agent", required=True)
    claim_lane.add_argument("--attempt", required=True, type=int); claim_lane.add_argument("--affinity", required=True); claim_lane.add_argument("--ticket", required=True, action="append"); claim_lane.set_defaults(func=cmd_claim_lane)
    ready = commands.add_parser("ready")
    ready.add_argument("--run", required=True); ready.add_argument("--affinity"); ready.set_defaults(func=cmd_ready)
    resume = commands.add_parser("resume")
    resume.add_argument("--run", required=True); resume.set_defaults(func=cmd_resume)
    materialize = commands.add_parser("materialize-ticket")
    materialize.add_argument("--run", required=True); materialize.add_argument("--ticket", required=True); materialize.add_argument("--output"); materialize.set_defaults(func=cmd_materialize)
    materialize_lane = commands.add_parser("materialize-lane")
    materialize_lane.add_argument("--run", required=True); materialize_lane.add_argument("--lane", required=True); materialize_lane.set_defaults(func=cmd_materialize_lane)
    receipt = commands.add_parser("record-receipt")
    receipt.add_argument("--run", required=True); receipt.add_argument("--ticket", required=True); receipt.add_argument("--receipt", required=True); receipt.set_defaults(func=cmd_receipt)
    integrate = commands.add_parser("integrate")
    integrate.add_argument("--run", required=True); integrate.add_argument("--ticket", required=True); integrate.add_argument("--evidence", required=True); integrate.add_argument("--summary", required=True); integrate.set_defaults(func=cmd_integrate)
    cohort = commands.add_parser("verify-cohort")
    cohort.add_argument("--run", required=True); cohort.add_argument("--cohort", required=True); cohort.add_argument("--result", required=True, choices=("pass", "fail")); cohort.add_argument("--evidence", required=True); cohort.set_defaults(func=cmd_verify_cohort)
    verify_prd = commands.add_parser("verify-prd")
    verify_prd.add_argument("--run", required=True); verify_prd.add_argument("--result", required=True, choices=("pass", "fail")); verify_prd.add_argument("--summary", required=True); verify_prd.add_argument("--evidence", required=True); verify_prd.set_defaults(func=cmd_verify_prd)
    merge = commands.add_parser("record-merge")
    merge.add_argument("--run", required=True); merge.add_argument("--pr", required=True); merge.add_argument("--merged-sha", required=True); merge.add_argument("--main-sha", required=True); merge.add_argument("--evidence", required=True); merge.set_defaults(func=cmd_record_merge)
    release = commands.add_parser("record-release")
    release.add_argument("--run", required=True); release.add_argument("--stage", required=True, choices=RELEASE_STAGES); release.add_argument("--result", required=True, choices=("pass", "fail", "skipped")); release.add_argument("--summary", required=True); release.add_argument("--evidence", required=True); release.add_argument("--revision"); release.set_defaults(func=cmd_record_release)
    rollback = commands.add_parser("record-rollback")
    rollback.add_argument("--run", required=True); rollback.add_argument("--trigger", required=True); rollback.add_argument("--action", required=True); rollback.add_argument("--result", required=True, choices=("pass", "fail")); rollback.add_argument("--evidence", required=True); rollback.set_defaults(func=cmd_record_rollback)
    reconcile = commands.add_parser("reconcile")
    reconcile.add_argument("--run", required=True); reconcile.add_argument("--source", required=True); reconcile.add_argument("--graph", required=True); reconcile.set_defaults(func=cmd_reconcile)
    return root


def main() -> int:
    args = None
    try:
        args = parser().parse_args()
        if hasattr(args, "run"):
            run = Path(args.run).resolve()
            if not run.is_dir():
                raise RunError(f"not an execution run: {run}")
            with (run / ".prd-run.lock").open("a+") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                recover_transactions(run)
                recover_event_journal(run)
                args.func(args)
        else:
            args.func(args)
        return 0
    except RunError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        temporary = getattr(args, "_init_temporary", None) if args is not None else None
        if temporary and Path(temporary).exists():
            shutil.rmtree(temporary)


if __name__ == "__main__":
    raise SystemExit(main())
