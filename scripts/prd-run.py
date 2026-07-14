#!/usr/bin/env python3
"""Deterministic, disk-backed execution runs for multi-agent PRD delivery.

The CLI is deliberately stdlib-only.  A parent agent is the sole writer; child
agents receive materialized bundles and return receipts for the parent to record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


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
RELEASE_STAGES = ("integration", "deployment", "production-verification")
ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]{0,63}$")
PROTOCOL_VERSION = 1


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


def require_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise RunError(f"{label} must match {ID_RE.pattern}")
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
    if not isinstance(source_areas, dict) or not source_areas:
        raise RunError("scope_areas must be a non-empty object")
    if not isinstance(cohorts, dict) or not cohorts:
        raise RunError("cohorts must be a non-empty object")
    if not isinstance(tickets, list) or not tickets:
        raise RunError("tickets must be a non-empty list")
    if not isinstance(shared, dict):
        raise RunError("shared_context must be an object")

    scope_out: dict[str, str] = {}
    for scope_id in sorted(source_areas):
        require_id(scope_id, "scope area ID")
        scope_out[scope_id] = require_string(source_areas[scope_id], f"scope area {scope_id}")

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
        ticket_out.append({
            "acceptance": string_list(item.get("acceptance"), f"ticket {ticket_id}.acceptance", allow_empty=False),
            "ask_parent_policy": require_string(item.get("ask_parent_policy"), f"ticket {ticket_id}.ask_parent_policy"),
            "cohort_id": cohort_id,
            "constraints": string_list(item.get("constraints", []), f"ticket {ticket_id}.constraints"),
            "dependencies": sorted(string_list(item.get("dependencies", []), f"ticket {ticket_id}.dependencies")),
            "epic_id": require_id(item.get("epic_id"), f"ticket {ticket_id}.epic_id"),
            "id": ticket_id,
            "objective": require_string(item.get("objective"), f"ticket {ticket_id}.objective"),
            "ownership": sorted(string_list(item.get("ownership"), f"ticket {ticket_id}.ownership", allow_empty=False)),
            "proof": {
                "claim": claim,
                "non_effects": string_list(proof.get("non_effects", []), f"ticket {ticket_id}.proof.non_effects"),
                "oracle": oracle,
                "wrong_case": wrong_case,
            },
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
    if verify_source:
        lock = read_json(run / "source-lock.json")
        if lock.get("source_path") != manifest["source"]["path"] or lock.get("source_sha256") != manifest["source"]["sha256"]:
            raise RunError("source lock and manifest disagree")
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
    manifest["event_sequence"] = sequence


def write_resume(run: Path, manifest: dict[str, Any]) -> None:
    active = [ticket_id for ticket_id, item in sorted(manifest.get("tickets", {}).items()) if item["status"] not in ("integrated", "invalidated")]
    blocked = [ticket_id for ticket_id in active if manifest["tickets"][ticket_id]["status"] in ("blocked", "waiting")]
    lines = [
        "# Execution resume",
        "",
        f"State: {manifest['state']}",
        f"Source SHA-256: {manifest['source']['sha256']}",
        f"Graph SHA-256: {manifest.get('graph_sha256', 'not compiled')}",
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
    run = root / args.run_id
    if run.exists():
        raise RunError(f"run already exists: {run}")
    for directory in ("tickets", "receipts", "evidence", "cohorts", "release", "shared-context"):
        (run / directory).mkdir(parents=True, exist_ok=False)
    source_hash = sha_file(source)
    lock = {"source_path": str(source), "source_sha256": source_hash, "scope_hashes": {}}
    manifest = {
        "cohorts": {}, "event_sequence": 0, "graph_sha256": None,
        "ownership": {
            "children": ["assigned code worktree", "receipt input", "named evidence"],
            "parent": ["source-lock.json", "manifest.json", "resume.md", "events.jsonl", "cohorts/", "release/"],
        },
        "protocol_version": PROTOCOL_VERSION, "release": {}, "run_id": args.run_id, "shared_context": {},
        "source": {"path": str(source), "sha256": source_hash}, "state": "discussing", "tickets": {},
    }
    atomic_json(run / "source-lock.json", lock)
    atomic_text(run / "events.jsonl", "")
    atomic_text(run / "shared-context" / "global-v1.md", "# Global context\n\nNot compiled.\n")
    for stage in RELEASE_STAGES:
        atomic_text(run / "release" / f"{stage}.md", f"# {stage.replace('-', ' ').title()}\n\nNot recorded.\n")
    event(run, manifest, "run_initialized", {"source_sha256": source_hash})
    save_manifest(run, manifest)
    print(run)


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
    if target == "prd_verified" and manifest["release"].get("integration", {}).get("result") != "pass":
        raise RunError("integration verification has not passed")
    if target == "deployed" and manifest["release"].get("deployment", {}).get("result") != "pass":
        raise RunError("deployment verification has not passed")
    if target in ("production_verified", "complete") and manifest["release"].get("production-verification", {}).get("result") != "pass":
        raise RunError("production verification has not passed")
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
    scope_hashes = {key: object_hash(value) for key, value in graph["scope_areas"].items()}
    tickets: dict[str, Any] = {}
    for ticket in graph["tickets"]:
        path = run / "tickets" / f"{ticket['id']}.r1.md"
        atomic_text(path, render_ticket(ticket, 1))
        tickets[ticket["id"]] = ticket_entry(ticket, 1, path, scope_hashes)
    global_context = "# Global context\n\n" + graph["shared_context"]["global"].strip() + "\n"
    atomic_text(run / "shared-context" / "global-v1.md", global_context)
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
    lock = read_json(run / "source-lock.json")
    lock["scope_hashes"] = scope_hashes
    atomic_json(run / "source-lock.json", lock)
    atomic_json(run / "ticket-graph.json", graph)
    event(run, manifest, "graph_compiled", {"graph_sha256": manifest["graph_sha256"], "tickets": sorted(tickets)})
    save_manifest(run, manifest)


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
    if args.attempt < 1:
        raise RunError("attempt must be positive")
    if retry and args.attempt <= item["lease"]["attempt"]:
        raise RunError("retry attempt must exceed the previous lease attempt")
    item["lease"] = {"agent": agent, "attempt": args.attempt}
    item["status"] = "dispatched"
    event(run, manifest, "ticket_claimed", {"agent": agent, "attempt": args.attempt, "revision": item["revision"], "ticket": args.ticket})
    save_manifest(run, manifest)


def dependency_receipts(run: Path, manifest: dict[str, Any], item: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for dependency in item["dependencies"]:
        dep = manifest["tickets"][dependency]
        path = run / "receipts" / f"{dependency}.r{dep['revision']}.json"
        if dep["status"] != "integrated" or not path.is_file():
            raise RunError(f"dependency {dependency} is not integrated")
        receipt = read_json(path)
        output.append({"evidence": receipt["evidence"], "outputs": receipt["outputs"], "summary": receipt["summary"], "ticket": dependency})
    return output


def cmd_materialize(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    item = get_ticket(manifest, args.ticket)
    if item["status"] not in ("ready", "dispatched"):
        raise RunError(f"ticket {args.ticket} cannot be materialized while {item['status']}")
    ticket_text = (run / item["ticket_file"]).read_text().rstrip()
    cohort_id = item["cohort_id"]
    cohort_path = run / manifest["shared_context"]["cohorts"][cohort_id]
    dependencies = dependency_receipts(run, manifest, item)
    dependency_text = pretty_json(dependencies).rstrip() if dependencies else "[]"
    bundle = (
        "# Gauntlet child execution bundle\n\n"
        "Protocol: prd-run/v1\n"
        "Use only this bundle, the named relevant source files, and direct tool observations.\n"
        "Do not read the PRD, manifest, event log, or unrelated tickets and receipts.\n"
        "Work only within ticket ownership. Return the requested compact receipt inputs to the parent.\n\n"
        f"{(run / manifest['shared_context']['global']).read_text().rstrip()}\n\n"
        f"{cohort_path.read_text().rstrip()}\n\n"
        "# Dependency contracts\n\n"
        f"{dependency_text}\n\n"
        "# Assigned ticket (variable context follows)\n\n"
        f"{ticket_text}\n"
    )
    if args.output:
        atomic_text(Path(args.output), bundle)
    else:
        sys.stdout.write(bundle)


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
    if receipt["status"] == "complete":
        for ref in receipt["evidence"]:
            evidence_path = Path(ref) if Path(ref).is_absolute() else run / ref
            try:
                evidence_path.resolve().relative_to(run)
            except ValueError as exc:
                raise RunError(f"evidence must be inside the run: {ref}") from exc
            if not evidence_path.is_file() or not evidence_path.read_text().strip():
                raise RunError(f"evidence does not exist or is empty: {ref}")
    path = run / "receipts" / f"{args.ticket}.r{item['revision']}.json"
    if path.exists():
        raise RunError(f"receipt already recorded for {args.ticket} revision {item['revision']}")
    atomic_json(path, receipt)
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
    evidence = Path(args.evidence)
    try:
        relative = evidence.resolve().relative_to(run)
    except ValueError as exc:
        raise RunError("ticket integration evidence must be inside the run") from exc
    if not evidence.is_file() or not evidence.read_text().strip():
        raise RunError("ticket integration evidence must exist and be non-empty")
    receipt_path = run / "receipts" / f"{args.ticket}.r{item['revision']}.json"
    child_evidence = set(read_json(receipt_path).get("evidence", []))
    if str(relative) in child_evidence:
        raise RunError("parent integration evidence must be distinct from child-reported evidence")
    item["integration_verification"] = {
        "evidence": str(relative),
        "summary": require_string(args.summary, "integration summary"),
    }
    item["status"] = "integrated"
    item["lease"] = None
    refresh_readiness(manifest)
    event(run, manifest, "ticket_integrated", {"evidence": str(relative), "revision": item["revision"], "ticket": args.ticket})
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
    evidence = Path(args.evidence)
    try:
        relative = evidence.resolve().relative_to(run)
    except ValueError as exc:
        raise RunError("cohort evidence must be inside the run") from exc
    if not evidence.is_file() or not evidence.read_text().strip():
        raise RunError("cohort evidence must exist and be non-empty")
    cohort["result"] = args.result
    cohort["evidence"] = str(relative)
    atomic_text(run / "cohorts" / f"{args.cohort.lower()}.md", evidence.read_text())
    event(run, manifest, "cohort_verified", {"cohort": args.cohort, "result": args.result})
    save_manifest(run, manifest)


def cmd_record_release(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    stage = args.stage
    allowed_states = {
        "integration": ("cohort_verified",),
        "deployment": ("merged",),
        "production-verification": ("deployed",),
    }
    require_state(manifest, allowed_states[stage])
    evidence = require_string(args.evidence, "evidence")
    summary = require_string(args.summary, "summary")
    manifest["release"][stage] = {"evidence": evidence, "result": args.result, "summary": summary}
    report = f"# {stage.replace('-', ' ').title()}\n\nResult: {args.result}\n\nSummary: {summary}\n\nEvidence: {evidence}\n"
    atomic_text(run / "release" / f"{stage}.md", report)
    event(run, manifest, "release_stage_recorded", {"result": args.result, "stage": stage})
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
    new_scope_hashes = {key: object_hash(value) for key, value in graph["scope_areas"].items()}
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
    impacted.update(ticket_id for ticket_id, item in new_by_id.items() if item["cohort_id"] in changed_cohort_contexts)
    changed = True
    while changed:
        changed = False
        for ticket_id, item in new_by_id.items():
            if ticket_id not in impacted and impacted.intersection(item["dependencies"]):
                impacted.add(ticket_id)
                changed = True
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
    lock = {"source_path": str(source), "source_sha256": sha_file(source), "scope_hashes": new_scope_hashes}
    manifest["source"] = {"path": str(source), "sha256": lock["source_sha256"]}
    manifest["graph_sha256"] = object_hash(graph)
    manifest["cohorts"] = {key: {"result": None, **graph["cohorts"][key]} for key in sorted(graph["cohorts"])}
    atomic_json(run / "source-lock.json", lock)
    atomic_json(run / "ticket-graph.json", graph)
    event(run, manifest, "source_reconciled", {"changed_scopes": sorted(changed_scopes), "invalidated_tickets": sorted(impacted)})
    save_manifest(run, manifest)
    print(pretty_json({"changed_scopes": sorted(changed_scopes), "invalidated_tickets": sorted(impacted)}), end="")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--executions", required=True); init.add_argument("--run-id", required=True); init.add_argument("--source", required=True); init.set_defaults(func=cmd_init)
    transition = commands.add_parser("transition")
    transition.add_argument("--run", required=True); transition.add_argument("--to", required=True); transition.set_defaults(func=cmd_transition)
    compile_cmd = commands.add_parser("compile")
    compile_cmd.add_argument("--run", required=True); compile_cmd.add_argument("--graph", required=True); compile_cmd.set_defaults(func=cmd_compile)
    claim = commands.add_parser("claim")
    claim.add_argument("--run", required=True); claim.add_argument("--ticket", required=True); claim.add_argument("--agent", required=True); claim.add_argument("--attempt", required=True, type=int); claim.set_defaults(func=cmd_claim)
    materialize = commands.add_parser("materialize-ticket")
    materialize.add_argument("--run", required=True); materialize.add_argument("--ticket", required=True); materialize.add_argument("--output"); materialize.set_defaults(func=cmd_materialize)
    receipt = commands.add_parser("record-receipt")
    receipt.add_argument("--run", required=True); receipt.add_argument("--ticket", required=True); receipt.add_argument("--receipt", required=True); receipt.set_defaults(func=cmd_receipt)
    integrate = commands.add_parser("integrate")
    integrate.add_argument("--run", required=True); integrate.add_argument("--ticket", required=True); integrate.add_argument("--evidence", required=True); integrate.add_argument("--summary", required=True); integrate.set_defaults(func=cmd_integrate)
    cohort = commands.add_parser("verify-cohort")
    cohort.add_argument("--run", required=True); cohort.add_argument("--cohort", required=True); cohort.add_argument("--result", required=True, choices=("pass", "fail")); cohort.add_argument("--evidence", required=True); cohort.set_defaults(func=cmd_verify_cohort)
    release = commands.add_parser("record-release")
    release.add_argument("--run", required=True); release.add_argument("--stage", required=True, choices=RELEASE_STAGES); release.add_argument("--result", required=True, choices=("pass", "fail")); release.add_argument("--summary", required=True); release.add_argument("--evidence", required=True); release.set_defaults(func=cmd_record_release)
    reconcile = commands.add_parser("reconcile")
    reconcile.add_argument("--run", required=True); reconcile.add_argument("--source", required=True); reconcile.add_argument("--graph", required=True); reconcile.set_defaults(func=cmd_reconcile)
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        args.func(args)
        return 0
    except RunError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
