#!/usr/bin/env python3
"""Deterministic, disk-backed execution runs for one accepted Epic.

The CLI is deliberately stdlib-only.  A parent agent is the sole writer; child
agents receive materialized bundles and return receipts for the parent to record.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
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
    "epic_verified",
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
LAUNCH_SCHEMA = "gauntlet.epic-launch.v1"
PROJECT_PR_SCHEMA = "3.0"
INTEGRATION_MODE = "parent-branch"
PR_STRATEGIES = ("single-final-pr", "review-prs-plus-final")
DEFAULT_PR_STRATEGY = "single-final-pr"
AUTHORITY_CAPABILITIES = (
    "push-review-branch",
    "open-review-pr",
    "merge-to-integration",
    "open-final-pr",
    "merge-to-default",
    "deploy-production",
    "verify-production",
    "perform-paid-action",
    "perform-destructive-action",
    "apply-migration",
    "use-credentials",
    "execute-rollback",
)
HIGH_CONSEQUENCE_TRIGGERS = (
    "billing-paid-actions",
    "credentials-auth-permissions",
    "migrations-data-loss",
    "production-authority",
    "destructive-actions",
)
REQUIRED_REVIEW_LENSES = ("authority-security", "failure-recovery", "black-box")
SAFEGUARD_KINDS = ("dry-run-no-mutation", "bounded-live", "rollback-readiness")
TRIGGER_AUTHORITY = {
    "billing-paid-actions": "perform-paid-action",
    "credentials-auth-permissions": "use-credentials",
    "migrations-data-loss": "apply-migration",
    "destructive-actions": "perform-destructive-action",
}
REVIEW_UNIT_STATES = ("pending", "opened", "checked", "merge-locked", "merged", "verified", "cleanup-eligible", "cleaned")
TIMESTAMP_PROTOCOL = "gauntlet.rfc3339-utc.v1"
PROGRESS_SCHEMA = "gauntlet.progress-units.v1"
PROGRESS_POLICY = "gauntlet.progress-policy.v1"


class RunError(Exception):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_consequence_triggers(raw: str | None, label: str) -> list[str]:
    if raw is None:
        raise RunError(f"{label} must declare High-consequence triggers")
    if not raw.strip():
        raise RunError(f"{label} must be literal `none` or a non-empty canonical trigger list")
    if raw.strip().lower() == "none":
        return []
    triggers = sorted(string_list([item.strip().lower() for item in raw.split(",") if item.strip()], label))
    unknown = set(triggers) - set(HIGH_CONSEQUENCE_TRIGGERS)
    if unknown:
        raise RunError(f"{label} uses unsupported high-consequence triggers: {sorted(unknown)}")
    if len(triggers) != len(set(triggers)):
        raise RunError(f"{label} must not repeat high-consequence triggers")
    return triggers


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def object_hash(value: Any) -> str:
    return sha_bytes(canonical_json(value).encode())


def utc_now() -> str:
    """Return one canonical UTC instant, with an injectable deterministic clock for tests."""

    supplied = os.environ.get("PRD_RUN_NOW")
    if supplied is not None:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", supplied):
            raise RunError("PRD_RUN_NOW must be an RFC 3339 UTC timestamp ending in Z")
        try:
            datetime.fromisoformat(supplied[:-1] + "+00:00")
        except ValueError as exc:
            raise RunError("PRD_RUN_NOW must be a valid RFC 3339 UTC timestamp") from exc
        return supplied
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def optional_ordinal(value: Any, label: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise RunError(f"{label} must be a non-negative integer")
    return value


def close_request_window(owner: dict[str, Any], end_ordinal: int | None, timestamp: str) -> None:
    window = owner["requestWindow"]
    start_ordinal = window.get("startOrdinal")
    if start_ordinal is not None and end_ordinal is not None and end_ordinal < start_ordinal:
        raise RunError("request end ordinal must not precede its exclusive start baseline")
    window.update({"endOrdinal": end_ordinal, "endedAt": timestamp})


def markdown_section(section: str, heading: str) -> str:
    match = re.search(rf"^### {re.escape(heading)}\s*$", section, re.MULTILINE | re.IGNORECASE)
    if not match:
        return ""
    following = re.search(r"^### ", section[match.end():], re.MULTILINE)
    end = match.end() + following.start() if following else len(section)
    return section[match.end():end].strip()


def section_items(section: str, heading: str) -> list[str]:
    content = markdown_section(section, heading)
    return [match.group(1).strip() for match in re.finditer(r"^\s*[-*]\s+(.+?)\s*$", content, re.MULTILINE)]


def source_contract(path: Path, requested_targets: list[str]) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    target_match = re.search(r"^Implementation target:\s*(.+?)\s*$", text, re.MULTILINE)
    if not target_match:
        raise RunError("PRD must declare Implementation target")
    declared = sorted(set(re.findall(r"\b[A-Z][A-Z0-9_-]{1,63}\b", target_match.group(1))))
    requested_raw = [require_id(item, "target Epic ID") for item in requested_targets]
    if len(requested_raw) != 1:
        raise RunError("new Execution Runs require exactly one target Epic; multi-Epic run inputs are unsupported")
    requested = requested_raw
    if requested[0] not in declared:
        raise RunError(f"target Epic {requested[0]} is not a member of PRD Implementation target {declared}")
    epic_matches = list(re.finditer(r"^## Epic ([A-Z][A-Z0-9_-]{0,63}):[ \t]*(.*?)[ \t]*$", text, re.MULTILINE))
    epic_sections: dict[str, str] = {}
    scope_hashes: dict[str, str] = {}
    epics: dict[str, Any] = {}
    for index, match in enumerate(epic_matches):
        epic_id = match.group(1)
        if epic_id in epic_sections:
            raise RunError(f"duplicate Epic ID in PRD: {epic_id}")
        section = text[match.start() : epic_matches[index + 1].start() if index + 1 < len(epic_matches) else len(text)]
        epic_sections[epic_id] = section
        epic_title = require_string(match.group(2), f"Epic {epic_id} title")
        epic_scopes: dict[str, Any] = {}
        if epic_id in requested and not re.search(r"^Epic status:\s*Accepted\s*$", section, re.MULTILINE | re.IGNORECASE):
            raise RunError(f"target Epic {epic_id} is not Accepted")
        if epic_id in requested:
            heading_matches = list(re.finditer(r"^### ([^\n]+)$", section, re.MULTILINE))
            scope_chunks: list[tuple[str, int, int, str]] = []
            for heading_index, heading in enumerate(heading_matches):
                scope_match = re.fullmatch(r"Scope Area ([A-Z][A-Z0-9_-]{0,63}):[ \t]*(.*?)[ \t]*", heading.group(1))
                if not scope_match:
                    continue
                scope_id = scope_match.group(1)
                responsibility = require_string(scope_match.group(2), f"Scope Area {scope_id} responsibility")
                if scope_id in scope_hashes or any(existing[0] == scope_id for existing in scope_chunks):
                    raise RunError(f"duplicate Scope Area ID in PRD: {scope_id}")
                if not scope_id.startswith(f"{epic_id}-"):
                    raise RunError(f"Scope Area {scope_id} must belong to target Epic {epic_id}")
                end = heading_matches[heading_index + 1].start() if heading_index + 1 < len(heading_matches) else len(section)
                scope_chunks.append((scope_id, heading.start(), end, section[heading.start():end]))
                epic_scopes[scope_id] = {"responsibility": responsibility}
            common_parts = []
            cursor = 0
            for _, start, end, _ in scope_chunks:
                common_parts.append(section[cursor:start]); cursor = end
            common_parts.append(section[cursor:])
            common = "".join(common_parts)
            for scope_id, _, _, scope_text in scope_chunks:
                scope_hashes[scope_id] = object_hash({"epic_common": common, "scope": scope_text})
                epic_scopes[scope_id]["sha256"] = scope_hashes[scope_id]
            acceptance = {
                heading: section_items(section, heading)
                for heading in ("Product Acceptance", "Design Acceptance", "Engineering Acceptance")
            }
            consequence_match = re.search(
                r"^High-consequence triggers:[ \t]*([^\r\n]*)[ \t]*$", section,
                re.MULTILINE | re.IGNORECASE,
            )
            epics[epic_id] = {
                "acceptance": acceptance,
                "cannot_verify": section_items(section, "Cannot Verify"),
                "consequence_triggers": canonical_consequence_triggers(
                    consequence_match.group(1) if consequence_match else None,
                    f"Epic {epic_id}",
                ),
                "non_goals": section_items(section, "Non-goals"),
                "scope_areas": dict(sorted(epic_scopes.items())),
                "section_sha256": sha_bytes(section.encode("utf-8")),
                "title": epic_title,
            }
    missing = set(requested) - set(epic_sections)
    if missing:
        raise RunError(f"target Epics are missing from the PRD: {sorted(missing)}")
    if not scope_hashes:
        raise RunError("Implementation target must define searchable '### Scope Area <ID>: <Responsibility>' sections")
    return {
        "epic_ids": requested,
        "epics": {key: epics[key] for key in requested},
        "scope_hashes": dict(sorted(scope_hashes.items())),
    }


def launch_coverage_projection(value: dict[str, Any]) -> dict[str, Any]:
    epics = value.get("epics")
    if not isinstance(epics, dict):
        raise RunError("launch set epics must be an object")
    coverage_epics: dict[str, Any] = {}
    for epic_id in sorted(epics):
        require_id(epic_id, "launch set Epic ID")
        item = epics[epic_id]
        if not isinstance(item, dict):
            raise RunError(f"launch set Epic {epic_id} must be an object")
        dependencies = item.get("dependencies")
        if not isinstance(dependencies, list):
            raise RunError(f"launch set Epic {epic_id}.dependencies must be a list")
        normalized_dependencies = []
        for index, dependency in enumerate(dependencies):
            if not isinstance(dependency, dict) or set(dependency) != {"epicId", "boundary"}:
                raise RunError(f"launch set Epic {epic_id}.dependencies[{index}] must contain epicId and boundary")
            boundary = dependency.get("boundary")
            if boundary not in ("merged", "deployed", "productionProved"):
                raise RunError(f"launch set Epic {epic_id} dependency boundary is unsupported: {boundary}")
            normalized_dependencies.append({
                "boundary": boundary,
                "epicId": require_id(dependency.get("epicId"), f"launch set Epic {epic_id} dependency"),
            })
        release_stages = sorted(string_list(item.get("releaseStages"), f"launch set Epic {epic_id}.releaseStages", allow_empty=False))
        unknown_stages = set(release_stages) - set(RELEASE_APPLICABILITY)
        if unknown_stages or "merge" not in release_stages or (
            "production-verification" in release_stages and "deployment" not in release_stages
        ):
            raise RunError(f"launch set Epic {epic_id}.releaseStages is invalid")
        coverage_epics[epic_id] = {
            "consequenceTriggers": canonical_consequence_triggers(
                ",".join(string_list(item.get("consequenceTriggers"), f"launch set Epic {epic_id}.consequenceTriggers")),
                f"launch set Epic {epic_id}.consequenceTriggers",
            ) if item.get("consequenceTriggers") else [],
            "dependencies": sorted(normalized_dependencies, key=lambda item: (item["epicId"], item["boundary"])),
            "releaseStages": release_stages,
            "title": require_string(item.get("title"), f"launch set Epic {epic_id}.title"),
        }
    source = value.get("source")
    if not isinstance(source, dict) or set(source) != {"path", "sha256", "snapshotPath"}:
        raise RunError("launch set source must contain exactly path, sha256, and snapshotPath")
    return {
        "epics": coverage_epics,
        "schemaVersion": value.get("schemaVersion"),
        "source": {
            "path": require_string(source.get("path"), "launch set source.path"),
            "sha256": require_sha(source.get("sha256"), "launch set source.sha256"),
        },
        "targetEpicIds": sorted(string_list(value.get("targetEpicIds"), "launch set targetEpicIds", allow_empty=False)),
    }


def validate_launch_set(path: Path, source: Path, source_info: dict[str, Any], target_epic_id: str) -> dict[str, Any]:
    raw = read_json(path)
    if not isinstance(raw, dict):
        raise RunError("launch set must be an object")
    required_top = {"schemaVersion", "source", "targetEpicIds", "coverageSha256", "epics", "aggregateEmittedEvents"}
    if set(raw) != required_top:
        raise RunError(f"launch set must contain exactly: {', '.join(sorted(required_top))}")
    if raw.get("schemaVersion") != LAUNCH_SCHEMA:
        raise RunError(f"unsupported launch set schema; expected {LAUNCH_SCHEMA}")
    coverage = launch_coverage_projection(raw)
    declared = sorted(set(re.findall(
        r"\b[A-Z][A-Z0-9_-]{1,63}\b",
        re.search(r"^Implementation target:\s*(.+?)\s*$", source.read_text(), re.MULTILINE).group(1),
    )))
    if coverage["targetEpicIds"] != declared or set(coverage["epics"]) != set(declared):
        raise RunError("launch set must cover the complete PRD Implementation target exactly once")
    snapshot = Path(require_string(raw["source"].get("snapshotPath"), "launch set source.snapshotPath")).resolve()
    if not snapshot.is_file() or sha_file(snapshot) != coverage["source"]["sha256"]:
        raise RunError("launch set snapshot is missing or does not match the locked source hash")
    if source.resolve() != snapshot or sha_file(source) != coverage["source"]["sha256"]:
        raise RunError("Execution Runs must initialize from the immutable launch-set snapshot")
    expected_coverage = object_hash(coverage)
    if raw.get("coverageSha256") != expected_coverage:
        raise RunError("launch set coverageSha256 does not match its immutable coverage projection")
    item = raw["epics"].get(target_epic_id)
    if not isinstance(item, dict):
        raise RunError(f"launch set does not contain target Epic {target_epic_id}")
    expected_epic_keys = {
        "title", "dependencies", "releaseStages", "consequenceTriggers", "taskId", "runPath", "status",
        "blocker", "stopDisposition", "startReconciliation", "emittedEvents",
    }
    for epic_id, epic in raw["epics"].items():
        if not isinstance(epic, dict) or set(epic) != expected_epic_keys:
            raise RunError(f"launch set Epic {epic_id} has an unsupported shape")
    task_id = require_string(item.get("taskId"), f"launch set Epic {target_epic_id}.taskId")
    if coverage["epics"][target_epic_id]["title"] != source_info["epics"][target_epic_id]["title"]:
        raise RunError("launch set Epic title does not match the locked canonical Epic")
    if coverage["epics"][target_epic_id]["consequenceTriggers"] != source_info["epics"][target_epic_id]["consequence_triggers"]:
        raise RunError("launch set high-consequence triggers do not match the locked canonical Epic")
    return {
        "coverage_sha256": expected_coverage,
        "canonical_source_path": coverage["source"]["path"],
        "path": str(path.resolve()),
        "snapshot_path": str(snapshot),
        "task_id": task_id,
    }


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


def require_fingerprint(value: Any, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise RunError(f"{label} must use sha256:<64 lowercase hex characters>")
    return value


def normalize_graph(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise RunError("ticket graph version must be 1")
    source_areas = raw.get("scope_areas")
    cohorts = raw.get("cohorts")
    tickets = raw.get("tickets")
    shared = raw.get("shared_context", {})
    planned_checks = raw.get("planned_checks")
    verification_identity_raw = raw.get("verification_identity")
    review_raw_facts = raw.get("review")
    if not isinstance(source_areas, list) or not source_areas:
        raise RunError("scope_areas must be a non-empty list of locked PRD IDs")
    if not isinstance(cohorts, dict):
        raise RunError("cohorts must be an object")
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
        cohort_id = item.get("cohort_id")
        if cohort_id is not None:
            cohort_id = require_id(cohort_id, f"ticket {ticket_id}.cohort_id")
        if cohort_id is not None and cohort_id not in cohort_out:
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

    if not isinstance(planned_checks, list) or not planned_checks:
        raise RunError("planned_checks must be a non-empty list")
    planned_out = []
    seen_checks = set()
    for index, check in enumerate(planned_checks):
        if not isinstance(check, dict):
            raise RunError(f"planned_checks[{index}] must be an object")
        allowed = {"id", "tier", "ticket_ids", "argv", "reason", "confidence", "invariant_id"}
        if set(check) - allowed or not {"id", "tier", "ticket_ids", "argv", "reason"}.issubset(check):
            raise RunError(f"planned_checks[{index}] has an unsupported shape")
        check_id = require_string(check["id"], f"planned_checks[{index}].id")
        if check_id in seen_checks:
            raise RunError(f"duplicate planned check ID: {check_id}")
        seen_checks.add(check_id)
        tier = check["tier"]
        if tier not in ("ticket", "shared", "final-epic"):
            raise RunError(f"planned check {check_id}.tier is unsupported")
        check_tickets = sorted(string_list(check["ticket_ids"], f"planned check {check_id}.ticket_ids"))
        unknown = set(check_tickets) - ticket_ids
        if unknown:
            raise RunError(f"planned check {check_id} references unknown Tickets: {sorted(unknown)}")
        normalized = {
            "argv": string_list(check["argv"], f"planned check {check_id}.argv", allow_empty=False),
            "id": check_id,
            "reason": require_string(check["reason"], f"planned check {check_id}.reason"),
            "ticketIds": check_tickets,
            "tier": tier,
        }
        if check.get("confidence") is not None:
            normalized["confidence"] = require_string(check["confidence"], f"planned check {check_id}.confidence")
        if check.get("invariant_id") is not None:
            normalized["invariantId"] = require_string(check["invariant_id"], f"planned check {check_id}.invariant_id")
        if tier == "shared" and "invariantId" not in normalized:
            raise RunError(f"shared planned check {check_id} requires invariant_id")
        planned_out.append(normalized)
    if sum(item["tier"] == "final-epic" for item in planned_out) != 1:
        raise RunError("planned_checks must contain exactly one final-epic check")

    verification_identity_raw = require_closed_object(
        verification_identity_raw,
        {"toolchain", "fixtures", "environment"},
        "verification_identity",
    )
    verification_identity_out = {
        key: require_fingerprint(verification_identity_raw[key], f"verification_identity.{key}")
        for key in ("toolchain", "fixtures", "environment")
    }
    review_raw_facts = require_closed_object(review_raw_facts, {"required", "triggers", "lenses"}, "review")
    if not isinstance(review_raw_facts["required"], bool):
        raise RunError("review.required must be boolean")
    lenses = []
    if not isinstance(review_raw_facts["lenses"], list):
        raise RunError("review.lenses must be a list")
    for index, lens in enumerate(review_raw_facts["lenses"]):
        lens = require_closed_object(lens, {"id", "charter"}, f"review.lenses[{index}]")
        lenses.append({
            "charter": require_string(lens["charter"], f"review.lenses[{index}].charter"),
            "id": require_string(lens["id"], f"review.lenses[{index}].id"),
        })
    triggers = sorted(string_list(review_raw_facts["triggers"], "review.triggers"))
    if len(triggers) != len(set(triggers)):
        raise RunError("review.triggers must not contain duplicates")
    unknown_triggers = set(triggers) - set(HIGH_CONSEQUENCE_TRIGGERS)
    if unknown_triggers:
        raise RunError(
            "review.triggers must use canonical high-consequence categories; "
            f"unsupported={sorted(unknown_triggers)}"
        )
    lens_ids = [item["id"] for item in lenses]
    if len(lens_ids) != len(set(lens_ids)):
        raise RunError("review.lenses must use distinct lens IDs")
    review_out_facts = {
        "lenses": lenses,
        "required": review_raw_facts["required"],
        "triggers": triggers,
    }
    if triggers:
        if not review_out_facts["required"]:
            raise RunError("high-consequence triggers require review.required=true")
        if len(lens_ids) != len(REQUIRED_REVIEW_LENSES) or set(lens_ids) != set(REQUIRED_REVIEW_LENSES):
            raise RunError(
                "high-consequence review requires exactly the authority-security, "
                "failure-recovery, and black-box lenses"
            )
    elif review_out_facts["required"] or lenses:
        raise RunError("ordinary work requires review.required=false and zero lenses")

    review_raw = raw.get("review_units")
    review_out: dict[str, Any] = {}
    if review_raw is not None:
        if not isinstance(review_raw, dict) or not review_raw:
            raise RunError("review_units must be a non-empty object when present")
        assigned: list[str] = []
        for unit_id in sorted(review_raw):
            require_id(unit_id, "review unit ID")
            unit = review_raw[unit_id]
            if not isinstance(unit, dict) or set(unit) != {"dependencies", "ticket_ids"}:
                raise RunError(f"review unit {unit_id} must contain exactly dependencies and ticket_ids")
            unit_tickets = sorted(string_list(unit["ticket_ids"], f"review unit {unit_id}.ticket_ids", allow_empty=False))
            if len(unit_tickets) != len(set(unit_tickets)):
                raise RunError(f"review unit {unit_id} contains duplicate tickets")
            unknown_tickets = set(unit_tickets) - ticket_ids
            if unknown_tickets:
                raise RunError(f"review unit {unit_id} has unknown tickets: {sorted(unknown_tickets)}")
            dependencies = sorted(string_list(unit["dependencies"], f"review unit {unit_id}.dependencies"))
            if len(dependencies) != len(set(dependencies)):
                raise RunError(f"review unit {unit_id} contains duplicate dependencies")
            review_out[unit_id] = {"dependencies": dependencies, "ticket_ids": unit_tickets}
            assigned.extend(unit_tickets)
        if len(assigned) != len(set(assigned)):
            raise RunError("each ticket must belong to exactly one review unit; duplicate membership found")
        if set(assigned) != ticket_ids:
            raise RunError("review unit ticket membership must exactly cover the Ticket Graph")
        ticket_unit = {ticket_id: unit_id for unit_id, unit in review_out.items() for ticket_id in unit["ticket_ids"]}
        for unit_id, unit in review_out.items():
            unknown_units = set(unit["dependencies"]) - set(review_out)
            if unknown_units:
                raise RunError(f"review unit {unit_id} has unknown dependencies: {sorted(unknown_units)}")
            if unit_id in unit["dependencies"]:
                raise RunError(f"review unit {unit_id} cannot depend on itself")
            required = {
                ticket_unit[dependency]
                for ticket_id in unit["ticket_ids"]
                for dependency in next(item for item in ticket_out if item["id"] == ticket_id)["dependencies"]
                if ticket_unit[dependency] != unit_id
            }
            declared = set(unit["dependencies"])
            if declared != required:
                raise RunError(
                    f"review unit {unit_id} dependencies must exactly match cross-ticket dependencies; "
                    f"missing={sorted(required - declared)}, extra={sorted(declared - required)}"
                )
        detect_dependency_cycles({key: value["dependencies"] for key, value in review_out.items()}, "review unit")

    cohort_context = shared.get("cohorts", {})
    if not isinstance(cohort_context, dict):
        raise RunError("shared_context.cohorts must be an object")
    unknown_contexts = set(cohort_context) - set(cohort_out)
    if unknown_contexts:
        raise RunError(f"shared_context.cohorts contains unknown Cohorts: {sorted(unknown_contexts)}")
    return {
        "cohorts": cohort_out,
        "scope_areas": scope_out,
        "shared_context": {
            "cohorts": {key: require_string(cohort_context[key], f"shared context {key}") for key in sorted(cohort_context)},
            "global": require_string(shared.get("global"), "shared_context.global"),
        },
        "review_units": review_out,
        "planned_checks": planned_out,
        "review": review_out_facts,
        "tickets": ticket_out,
        "verification_identity": verification_identity_out,
        "version": 1,
    }


def detect_cycles(tickets: list[dict[str, Any]]) -> None:
    detect_dependency_cycles({item["id"]: item["dependencies"] for item in tickets}, "dependency")


def detect_dependency_cycles(dependencies: dict[str, list[str]], label: str) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(ticket_id: str) -> None:
        if ticket_id in visiting:
            raise RunError(f"{label} cycle includes {ticket_id}")
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
    if not isinstance(lock.get("launch_set"), dict) or len(lock.get("target_epic_ids", [])) != 1:
        raise RunError("unsupported Execution Run schema; start one launch-authorized Epic Run")
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


def event(
    run: Path,
    manifest: dict[str, Any],
    action: str,
    payload: dict[str, Any],
    *,
    timestamp: str | None = None,
) -> str:
    timestamp = timestamp or utc_now()
    sequence = int(manifest.get("event_sequence", 0)) + 1
    record = {"action": action, "payload": payload, "sequence": sequence, "timestamp": timestamp}
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
    time_facts = manifest.setdefault("time", {
        "created_at": None,
        "protocol_version": None,
        "started_at": None,
        "terminal_at": None,
        "updated_at": None,
    })
    time_facts["updated_at"] = timestamp
    return timestamp


def progress_unit_specs(graph: dict[str, Any], manifest: dict[str, Any]) -> list[dict[str, Any]]:
    specs = [
        {"id": "prepare:source-lock", "kind": "prepare", "phase": "prepare", "dependencies": []},
        {"id": "prepare:ticket-graph", "kind": "prepare", "phase": "prepare", "dependencies": ["prepare:source-lock"]},
    ]
    for ticket in sorted(graph["tickets"], key=lambda item: item["id"]):
        specs.extend((
            {
                "id": f"build:ticket:{ticket['id']}", "kind": "ticket-build", "phase": "build",
                "dependencies": [f"integrate:ticket:{item}" for item in ticket["dependencies"]],
            },
            {
                "id": f"integrate:ticket:{ticket['id']}", "kind": "ticket-integration", "phase": "integrate",
                "dependencies": [f"build:ticket:{ticket['id']}"],
            },
        ))
    specs.extend(
        {
            "id": f"integrate:cohort:{cohort_id}", "kind": "cohort-verification", "phase": "integrate",
            "dependencies": [f"integrate:ticket:{ticket_id}" for ticket_id in graph["cohorts"][cohort_id]["ticket_ids"]],
        } for cohort_id in sorted(graph["cohorts"])
    )
    integration_dependencies = [
        item["id"] for item in specs if item["kind"] in {"ticket-integration", "cohort-verification"}
    ]
    if graph["review"]["required"]:
        specs.extend(
            {
                "id": f"verify:review:{lens['id']}", "kind": "consequence-review", "phase": "final-verify",
                "dependencies": integration_dependencies,
            }
            for lens in sorted(graph["review"]["lenses"], key=lambda item: item["id"])
        )
    final_dependencies = integration_dependencies + [item["id"] for item in specs if item["kind"] == "consequence-review"]
    specs.append({
        "id": "verify:final-epic", "kind": "final-epic-verification", "phase": "final-verify",
        "dependencies": final_dependencies,
    })
    if graph["review"]["triggers"]:
        specs.append({
            "id": "ship:safeguard:dry-run-no-mutation", "kind": "release-safeguard", "phase": "ship",
            "dependencies": ["verify:final-epic"],
        })
        if manifest["release"]["applicability"]["production-verification"]:
            specs.append({
                "id": "ship:safeguard:rollback-readiness", "kind": "release-safeguard", "phase": "ship",
                "dependencies": ["verify:final-epic"],
            })
            specs.append({
                "id": "ship:safeguard:bounded-live", "kind": "release-safeguard", "phase": "ship",
                "dependencies": ["ship:deployment"],
            })
    dry_run_dependencies = (
        ["ship:safeguard:dry-run-no-mutation"] if graph["review"]["triggers"] else []
    )
    specs.append({
        "id": "ship:merge", "kind": "release-gate", "phase": "ship",
        "dependencies": ["verify:final-epic", *dry_run_dependencies],
    })
    for stage in RELEASE_STAGES:
        if manifest["release"]["applicability"][stage]:
            dependencies = ["ship:merge"] if stage == "deployment" else ["ship:deployment"]
            if stage == "production-verification" and graph["review"]["triggers"]:
                dependencies.extend([
                    "ship:safeguard:bounded-live",
                    "ship:safeguard:rollback-readiness",
                ])
            specs.append({
                "id": f"ship:{stage}", "kind": "release-gate", "phase": "ship",
                "dependencies": dependencies,
            })
    return sorted(specs, key=lambda item: item["id"])


def progress_facts(graph: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    units = progress_unit_specs(graph, manifest)
    denominator = {
        "policyVersion": PROGRESS_POLICY,
        "schemaVersion": PROGRESS_SCHEMA,
        "unitIds": [item["id"] for item in units],
    }
    return {
        "denominator_sha256": object_hash(denominator),
        "policy_version": PROGRESS_POLICY,
        "schema_version": PROGRESS_SCHEMA,
        "units": units,
    }


def operation_entry(unit: dict[str, str], timestamp: str) -> dict[str, Any]:
    return {
        "attempt": 0,
        "attempts": [],
        "finished_at": None,
        "id": unit["id"],
        "kind": unit["kind"],
        "phase": unit["phase"],
        "queued_at": timestamp,
        "started_at": None,
        "status": "queued",
    }


def operation_units(progress: dict[str, Any]) -> list[dict[str, str]]:
    return [
        item for item in progress["units"]
        if item["kind"] not in ("prepare", "ticket-build")
    ]


def begin_operation(run: Path, manifest: dict[str, Any], operation_id: str) -> None:
    operation = manifest.get("operations", {}).get(operation_id)
    if operation is None:  # Compatibility: old runs have no durable operation protocol.
        return
    if operation["status"] == "running":
        return
    if operation["status"] not in ("queued", "fail", "pass"):
        raise RunError(f"operation {operation_id} is already {operation['status']}")
    timestamp = utc_now()
    attempt = int(operation.get("attempt", 0)) + 1
    attempt_record = {
        "attempt": attempt,
        "finished_at": None,
        "started_at": timestamp,
        "status": "running",
    }
    operation.update({
        "attempt": attempt,
        "finished_at": None,
        "started_at": timestamp,
        "status": "running",
    })
    operation.setdefault("attempts", []).append(attempt_record)
    event(
        run,
        manifest,
        "operation_started",
        {"attempt": attempt, "operation": operation_id},
        timestamp=timestamp,
    )
    save_manifest(run, manifest)


def finish_operation(manifest: dict[str, Any], operation_id: str, result: str, timestamp: str) -> None:
    operation = manifest.get("operations", {}).get(operation_id)
    if operation is None:
        return
    if result not in ("pass", "fail"):
        raise RunError(f"operation {operation_id} result must be pass or fail")
    if operation["status"] != "running" or not operation.get("attempts"):
        raise RunError(f"operation {operation_id} is not running")
    operation.update({"finished_at": timestamp, "status": result})
    operation["attempts"][-1].update({"finished_at": timestamp, "status": result})


def reset_operation(manifest: dict[str, Any], operation_id: str, timestamp: str) -> None:
    operation = manifest.get("operations", {}).get(operation_id)
    if operation is None:
        return
    operation.update({
        "finished_at": None,
        "queued_at": timestamp,
        "started_at": None,
        "status": "queued",
    })


VERIFICATION_RECEIPT_SCHEMA = "gauntlet.verification-receipt.v1"
VERIFICATION_IDENTITY_KEYS = {
    "commitSha", "treeSha", "argv", "toolchainSha256", "fixturesSha256",
    "oracleSha256", "environmentSha256",
}


def verification_identity(value: Any, label: str) -> dict[str, Any]:
    identity = require_closed_object(value, VERIFICATION_IDENTITY_KEYS, label)
    argv = string_list(identity["argv"], f"{label}.argv", allow_empty=False)
    result = {
        "argv": argv,
        "commitSha": require_sha(identity["commitSha"], f"{label}.commitSha"),
        "environmentSha256": require_sha(identity["environmentSha256"], f"{label}.environmentSha256"),
        "fixturesSha256": require_sha(identity["fixturesSha256"], f"{label}.fixturesSha256"),
        "oracleSha256": require_sha(identity["oracleSha256"], f"{label}.oracleSha256"),
        "toolchainSha256": require_sha(identity["toolchainSha256"], f"{label}.toolchainSha256"),
        "treeSha": require_sha(identity["treeSha"], f"{label}.treeSha"),
    }
    return result


def validate_verification_receipt(
    run: Path,
    manifest: dict[str, Any],
    raw: Any,
    label: str,
    *,
    expected_commit: str,
    expected_tree: str,
) -> dict[str, Any]:
    keys = {"schemaVersion", "result", "summary", "evidence", "identity"}
    receipt = require_closed_object(raw, keys, label)
    if receipt["schemaVersion"] != VERIFICATION_RECEIPT_SCHEMA:
        raise RunError(f"{label}.schemaVersion must be {VERIFICATION_RECEIPT_SCHEMA}")
    if receipt["result"] not in ("pass", "fail"):
        raise RunError(f"{label}.result must be pass or fail")
    identity = verification_identity(receipt["identity"], f"{label}.identity")
    if identity["commitSha"] != expected_commit or identity["treeSha"] != expected_tree:
        raise RunError(f"{label} does not match the exact integrated commit and tree")
    evidence_refs = sorted(string_list(receipt["evidence"], f"{label}.evidence", allow_empty=False))
    for reference in evidence_refs:
        evidence, _ = proof_path(run, run / reference, f"{label} evidence")
        pin_artifact(run, manifest, evidence)
    return {
        "evidence": evidence_refs,
        "identity": identity,
        "result": receipt["result"],
        "schemaVersion": VERIFICATION_RECEIPT_SCHEMA,
        "summary": require_string(receipt["summary"], f"{label}.summary"),
    }


def exact_integration_revision(manifest: dict[str, Any], lock: dict[str, Any]) -> tuple[str, str]:
    repo, repository_identity = git_repository_identity(Path.cwd())
    if repository_identity != lock.get("repository_identity"):
        raise RunError("verification must run in the repository locked at initialization")
    branch = git_value(["branch", "--show-current"], "current branch", repo)
    if branch != manifest["integration"]["branch"]:
        raise RunError("verification must run on the Execution Run integration branch")
    commit = require_sha(git_value(["rev-parse", "HEAD"], "integration HEAD", repo), "integration HEAD")
    tree = require_sha(git_value(["rev-parse", "HEAD^{tree}"], "integration tree", repo), "integration tree")
    return commit, tree


def record_verification_receipt(
    run: Path,
    manifest: dict[str, Any],
    source_path: Path,
    destination_name: str,
    label: str,
    *,
    expected_oracle: str | None = None,
) -> tuple[dict[str, Any], str]:
    lock = read_json(run / "source-lock.json")
    commit, tree = exact_integration_revision(manifest, lock)
    receipt = validate_verification_receipt(
        run,
        manifest,
        read_json(source_path),
        label,
        expected_commit=commit,
        expected_tree=tree,
    )
    if expected_oracle is not None and receipt["identity"]["oracleSha256"] != expected_oracle:
        raise RunError(f"{label} uses the wrong controller-owned oracle")
    destination = run / "receipts" / destination_name
    if destination.exists() and read_json(destination) != receipt:
        destination = destination.with_name(f"{destination.stem}-{object_hash(receipt)[:12]}{destination.suffix}")
    if destination.exists() and read_json(destination) != receipt:
        raise RunError(f"{label} receipt identity collision")
    atomic_json(destination, receipt)
    relative = pin_artifact(run, manifest, destination)
    return receipt, relative


def consequence_oracle(manifest: dict[str, Any], *, lens: str | None = None, safeguard: str | None = None) -> str:
    policy = manifest.get("consequence_review", {}).get("policy", {})
    subject = {"lens": lens} if lens is not None else {"safeguard": safeguard}
    return object_hash({
        "schemaVersion": "gauntlet.consequence-proof.v1",
        "triggers": policy.get("triggers", []),
        **subject,
    })


def exact_record_status(record: dict[str, Any] | None, commit: str | None, tree: str | None = None) -> str:
    if not record:
        return "pending"
    if record.get("result") != "pass":
        return "fail"
    identity = record.get("identity", {})
    if not commit or identity.get("commitSha") != commit or (tree and identity.get("treeSha") != tree):
        return "stale"
    return "pass"


def consequence_review_status(manifest: dict[str, Any], commit: str | None, tree: str | None = None) -> dict[str, Any]:
    policy = manifest.get("consequence_review", {}).get("policy", {"required": False, "triggers": [], "lenses": []})
    records = manifest.get("consequence_review", {}).get("results", {})
    results = [
        {
            "id": lens["id"],
            "status": exact_record_status(records.get(lens["id"]), commit, tree),
            "evidence": records.get(lens["id"], {}).get("evidence", []),
        }
        for lens in policy.get("lenses", [])
    ]
    status = "not-required" if not policy.get("required") else (
        "pass" if results and all(item["status"] == "pass" for item in results) else
        "fail" if any(item["status"] == "fail" for item in results) else
        "stale" if any(item["status"] == "stale" for item in results) else
        "pending"
    )
    return {**policy, "results": results, "status": status}


def safeguard_status(manifest: dict[str, Any], kind: str, commit: str | None, tree: str | None = None) -> dict[str, Any]:
    policy = manifest.get("consequence_review", {}).get("policy", {})
    triggered = bool(policy.get("triggers"))
    required = triggered and (
        kind == "dry-run-no-mutation"
        or bool(manifest.get("release", {}).get("applicability", {}).get("production-verification"))
    )
    record = manifest.get("release", {}).get("safeguards", {}).get(kind)
    return {
        "evidence": record.get("evidence", []) if record else [],
        "kind": kind,
        "required": required,
        "status": exact_record_status(record, commit, tree) if required else "not-required",
    }


def require_safeguard(manifest: dict[str, Any], kind: str, commit: str, tree: str | None = None) -> None:
    status = safeguard_status(manifest, kind, commit, tree)
    if status["required"] and status["status"] != "pass":
        raise RunError(f"required {kind} safeguard is {status['status']} on the exact final revision")


def trigger_authorities(manifest: dict[str, Any]) -> list[str]:
    triggers = manifest.get("consequence_review", {}).get("policy", {}).get("triggers", [])
    return sorted({TRIGGER_AUTHORITY[item] for item in triggers if item in TRIGGER_AUTHORITY})


def observed_integration_head(manifest: dict[str, Any], lock: dict[str, Any]) -> str | None:
    root = Path(lock.get("repository_root", ""))
    branch = manifest.get("integration", {}).get("branch")
    if not root.is_dir() or not branch:
        return None
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", f"refs/heads/{branch}"],
        text=True,
        capture_output=True,
    )
    return result.stdout.strip().lower() if result.returncode == 0 else None


def completion_projection(manifest: dict[str, Any], *, observed_head: str | None = None) -> dict[str, Any]:
    release = manifest.get("release", {})
    final = release.get("epic-verification", {})
    tickets_pass = bool(manifest.get("tickets")) and all(
        item.get("status") == "integrated" for item in manifest.get("tickets", {}).values()
    )
    cohorts_pass = all(item.get("result") == "pass" for item in manifest.get("cohorts", {}).values())
    exact_revision = final.get("integration_head_sha")
    fresh = bool(exact_revision and (observed_head is None or observed_head == exact_revision))
    implemented = bool(final.get("result") == "pass" and tickets_pass and cohorts_pass and fresh)
    merge = release.get("merge", {})
    merged = bool(implemented and merge.get("result") == "pass" and merge.get("verified_head_sha") == exact_revision)
    deployment_applicable = bool(release.get("applicability", {}).get("deployment"))
    deployment = release.get("deployment", {})
    deployed = bool(
        merged and deployment_applicable and deployment.get("result") == "pass"
        and deployment.get("revision") == merge.get("main_sha")
    )
    production_applicable = bool(release.get("applicability", {}).get("production-verification"))
    production = release.get("production-verification", {})
    production_proved = bool(
        deployed and production_applicable and production.get("result") == "pass"
        and production.get("revision") == deployment.get("revision")
    )
    deployment_closed = deployed if deployment_applicable else deployment.get("result") == "skipped"
    production_closed = production_proved if production_applicable else production.get("result") == "skipped"
    pending: list[str] = []
    if not implemented:
        pending.append("final-epic-verification")
    if not merged:
        pending.append("merge")
    if deployment_applicable and not deployed:
        pending.append("deployment")
    elif not deployment_applicable and not deployment_closed:
        pending.append("deployment-not-applicable-record")
    if production_applicable and not production_proved:
        pending.append("production-proof")
    elif not production_applicable and not production_closed:
        pending.append("production-proof-not-applicable-record")
    complete = bool(
        implemented
        and merged
        and deployment_closed
        and production_closed
    )
    epic_ids = manifest.get("source", {}).get("epic_ids", [])
    exact_state = (
        "complete" if complete else
        "production-proved" if production_proved else
        "deployed" if deployed else
        "merged" if merged else
        "implementation-complete" if implemented else
        "in-progress"
    )
    return {
        "complete": complete,
        "deployed": deployed,
        "epicId": epic_ids[0] if len(epic_ids) == 1 else None,
        "exactRevision": exact_revision if implemented else None,
        "exactState": exact_state,
        "implemented": implemented,
        "merged": merged,
        "pendingGates": pending,
        "productionProved": production_proved,
        "sourceSha256": manifest.get("source", {}).get("sha256"),
        "verificationSummary": final.get("summary"),
    }


def write_resume(run: Path, manifest: dict[str, Any]) -> None:
    active = [ticket_id for ticket_id, item in sorted(manifest.get("tickets", {}).items()) if item["status"] not in ("integrated", "invalidated")]
    blocked = [ticket_id for ticket_id in active if manifest["tickets"][ticket_id]["status"] in ("blocked", "waiting")]
    integration = manifest.get("integration", {})
    lock = read_json(run / "source-lock.json")
    completion = completion_projection(manifest, observed_head=observed_integration_head(manifest, lock))
    lines = [
        "# Execution resume",
        "",
        f"State: {manifest['state']}",
        f"Source SHA-256: {manifest['source']['sha256']}",
        f"Graph SHA-256: {manifest.get('graph_sha256', 'not compiled')}",
        f"Integration branch: {integration.get('branch', 'not recorded')}",
        f"PR strategy: {integration.get('pr_strategy', 'not recorded')}",
        f"Completion state: {completion['exactState']}",
        f"Exact verified revision: {completion['exactRevision'] or 'none'}",
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
Cohort: {ticket['cohort_id'] or 'None'}
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


def require_sha(value: Any, label: str) -> str:
    digest = require_string(value, label).lower()
    if not re.fullmatch(r"[0-9a-f]{7,64}", digest):
        raise RunError(f"{label} must be a Git object ID")
    return digest


def canonical_git_object(repo: Path, value: Any, label: str, expected_type: str) -> str:
    supplied = require_sha(value, label)
    try:
        resolved = require_sha(git_value(["rev-parse", "--verify", supplied], label, repo), label)
        object_type = git_value(["cat-file", "-t", resolved], f"{label} type", repo)
    except RunError as exc:
        raise RunError(f"cannot resolve {label} as a Git {expected_type} object") from exc
    if object_type != expected_type:
        raise RunError(f"{label} must identify a Git {expected_type} object")
    return resolved


def legacy_checked_tree(repo: Path, check: dict[str, Any]):
    legacy = check.get("tested_merge_sha")
    if not legacy:
        return None
    merge_sha = canonical_git_object(repo, legacy, "legacy tested merge SHA", "commit")
    parents = git_value(["rev-list", "--parents", "-n", "1", merge_sha], "legacy tested merge parents", repo).split()
    base = canonical_git_object(repo, check.get("tested_base_sha"), "tested base SHA", "commit")
    head = canonical_git_object(repo, check.get("head_sha"), "review head SHA", "commit")
    if len(parents) != 3 or parents[1:] != [base, head]:
        raise RunError("legacy tested merge commit must have the tested base and review head as its two parents")
    return canonical_git_object(repo, git_value(["rev-parse", f"{merge_sha}^{{tree}}"], "legacy tested merge tree", repo), "legacy tested merge tree", "tree")


def require_closed_object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise RunError(f"{label} must contain exactly {', '.join(sorted(keys))}")
    return value


def require_authority(manifest: dict[str, Any], *capabilities: str) -> None:
    authority = manifest.get("authority", {})
    missing = [key for key in capabilities if not authority.get(key, {}).get("granted")]
    if missing:
        raise RunError(f"missing authority capabilities: {', '.join(missing)}")


def cmd_record_authority(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    capability = args.capability
    source = require_string(args.source, "authority source")
    record = manifest.setdefault("authority", {}).setdefault(capability, {"granted": False, "source": None})
    if record.get("granted"):
        if record.get("source") != source:
            raise RunError(f"authority {capability} is already recorded from a different source")
        return
    record.update({"granted": True, "source": source})
    event(run, manifest, "authority_recorded", {"capability": capability})
    save_manifest(run, manifest)


def cmd_authority_status(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    record = manifest.get("authority", {}).get(args.capability, {})
    print(pretty_json({
        "capability": args.capability,
        "granted": bool(record.get("granted")),
        "runId": manifest["run_id"],
        "schemaVersion": "1.0",
        "source": record.get("source"),
    }), end="")


def cmd_review_unit(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    require_state(manifest, ("executing", "integrating", "epic_verified"))
    if manifest.get("integration", {}).get("pr_strategy") != "review-prs-plus-final":
        raise RunError("review-unit operations require review-prs-plus-final")
    unit_id = require_id(args.unit, "review unit ID")
    unit = manifest.get("review_units", {}).get(unit_id)
    if not unit:
        raise RunError(f"unknown review unit {unit_id}")
    action = args.action
    target_index = REVIEW_UNIT_STATES.index(action)
    current_index = REVIEW_UNIT_STATES.index(unit["state"])
    if current_index < target_index - 1:
        raise RunError(f"invalid review unit transition {unit['state']} -> {action}")

    update: dict[str, Any] = {}
    if action == "opened":
        require_authority(manifest, "push-review-branch", "open-review-pr")
        update = {"branch": require_branch(args.branch, "review branch"), "pr": require_string(args.pr, "review PR")}
        if update["branch"] == manifest["integration"]["branch"]:
            raise RunError("review branch must differ from the integration branch")
        if current_index < target_index:
            pending_dependencies = [
                dependency for dependency in unit["dependencies"]
                if REVIEW_UNIT_STATES.index(manifest["review_units"][dependency]["state"]) < REVIEW_UNIT_STATES.index("merged")
            ]
            if pending_dependencies:
                raise RunError(f"review unit dependencies are not merged: {pending_dependencies}")
    elif action == "checked":
        pending_dependencies = [
            dependency for dependency in unit["dependencies"]
            if REVIEW_UNIT_STATES.index(manifest["review_units"][dependency]["state"]) < REVIEW_UNIT_STATES.index("merged")
        ]
        if pending_dependencies:
            raise RunError(f"review unit dependencies are not merged: {pending_dependencies}")
        evidence, relative = proof_path(run, Path(args.proof_evidence), "review check evidence")
        result = require_string(args.proof_result, "review proof result")
        if result != "pass":
            raise RunError("review unit check result must be pass")
        if not args.tested_tree_sha and not args.tested_merge_sha:
            raise RunError("checked review units require --tested-tree-sha")
        repo, _ = git_repository_identity(Path.cwd())
        checked_base = canonical_git_object(repo, args.tested_base_sha, "tested base SHA", "commit")
        checked_head = canonical_git_object(repo, args.head_sha, "review head SHA", "commit")
        if args.tested_tree_sha:
            checked_tree = canonical_git_object(repo, args.tested_tree_sha, "tested merge tree SHA", "tree")
        else:
            legacy_check = {
                "head_sha": checked_head,
                "tested_base_sha": checked_base,
                "tested_merge_sha": args.tested_merge_sha,
            }
            checked_tree = legacy_checked_tree(repo, legacy_check)
        proof_hash = sha_file(evidence)
        update = {
            "check": {
                "head_sha": checked_head,
                "proof": {
                    "command": require_string(args.proof_command, "review proof command"),
                    "evidence": relative,
                    "evidence_sha256": proof_hash,
                    "result": result,
                },
                "tested_base_sha": checked_base,
                "tested_tree_sha": checked_tree,
            }
        }
        previous = unit.get("check", {})
        previous_tuple = (
            previous.get("head_sha"),
            previous.get("tested_base_sha"),
            previous.get("tested_tree_sha") or legacy_checked_tree(repo, previous),
        )
        current_tuple = (
            update["check"]["head_sha"],
            update["check"]["tested_base_sha"],
            update["check"]["tested_tree_sha"],
        )
        previous_proof = previous.get("proof", {})
        if isinstance(previous_proof, list):
            previous_hash = sha_file(run / previous_proof[2]) if len(previous_proof) > 2 else None
        else:
            previous_hash = previous_proof.get("evidence_sha256")
        if previous and previous_tuple != current_tuple and previous_hash == proof_hash:
            raise RunError("a changed review tuple requires fresh proof evidence")
        pin_artifact(run, manifest, evidence)
    elif action == "merge-locked":
        require_authority(manifest, "merge-to-integration")
        repo, _ = git_repository_identity(Path.cwd())
        current_base = canonical_git_object(repo, args.current_base_sha, "current integration base SHA", "commit")
        checked_base = canonical_git_object(repo, unit.get("check", {}).get("tested_base_sha"), "tested base SHA", "commit")
        if current_base != checked_base:
            raise RunError("stale integration base; recheck the review unit against the current base")
        update = {"merge_lock": {"base_sha": current_base}}
    elif action == "merged":
        repo, _ = git_repository_identity(Path.cwd())
        merge_sha = canonical_git_object(repo, args.merge_sha, "review merge SHA", "commit")
        merged_tree_sha = canonical_git_object(repo, args.merged_tree_sha, "merged tree SHA", "tree")
        check = unit.get("check", {})
        tested_tree_sha = check.get("tested_tree_sha") or legacy_checked_tree(repo, check)
        if merged_tree_sha != tested_tree_sha:
            raise RunError("merged tree SHA must equal the checked synthetic merge tree SHA")
        parents = git_value(["rev-list", "--parents", "-n", "1", merge_sha], "review merge parents", repo).split()
        checked_base = canonical_git_object(repo, check.get("tested_base_sha"), "tested base SHA", "commit")
        checked_head = canonical_git_object(repo, check.get("head_sha"), "review head SHA", "commit")
        if len(parents) != 3 or parents[1:] != [checked_base, checked_head]:
            raise RunError("review merge commit must have the checked integration base and review head as its two parents")
        actual_tree = require_sha(git_value(["rev-parse", f"{merge_sha}^{{tree}}"], "review merge tree", repo), "review merge tree")
        if actual_tree != merged_tree_sha:
            raise RunError("merged tree SHA does not match the recorded merge commit")
        branch_ref = integration_ref(repo, manifest["integration"]["branch"])
        contains = subprocess.run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", merge_sha, branch_ref],
            text=True,
            capture_output=True,
        )
        if contains.returncode != 0:
            raise RunError("review merge commit is not present on the integration branch")
        update = {"merge_sha": merge_sha, "merged_tree_sha": merged_tree_sha}
    elif action == "verified":
        repo, _ = git_repository_identity(Path.cwd())
        branch_ref = integration_ref(repo, manifest["integration"]["branch"])
        merge_sha = unit.get("merge_sha")
        head_sha = unit.get("check", {}).get("head_sha")
        for candidate, label in ((merge_sha, "recorded review merge"), (head_sha, "reviewed head")):
            reachable = subprocess.run(
                ["git", "-C", str(repo), "merge-base", "--is-ancestor", candidate or "missing", branch_ref],
                text=True,
                capture_output=True,
            )
            if reachable.returncode != 0:
                raise RunError(f"{label} is not reachable from the integration branch")
        evidence, relative = proof_path(run, Path(args.evidence), "review verification evidence")
        update = {"verification": {"evidence": relative, "summary": require_string(args.summary, "review verification summary")}}
        pin_artifact(run, manifest, evidence)

    if action == "checked" and unit["state"] in ("checked", "merge-locked"):
        if unit.get("check") == update["check"] and unit["state"] == "checked":
            return
        unit.update(update)
        unit.pop("merge_lock", None)
        unit["state"] = "checked"
        event(run, manifest, "review_unit_rechecked", {"unit": unit_id})
        save_manifest(run, manifest)
        return
    if current_index >= target_index:
        for key, value in update.items():
            if unit.get(key) != value:
                raise RunError(f"review unit {unit_id} already passed {action} with different data")
        return
    unit.update(update)
    unit["state"] = action
    event(run, manifest, "review_unit_transitioned", {"state": action, "unit": unit_id})
    save_manifest(run, manifest)


def cmd_review_unit_status(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    if manifest.get("integration", {}).get("pr_strategy") != "review-prs-plus-final":
        raise RunError("review-unit status requires review-prs-plus-final")
    unit_id = require_id(args.unit, "review unit ID")
    unit = manifest.get("review_units", {}).get(unit_id)
    if not unit:
        raise RunError(f"unknown review unit {unit_id}")
    graph = read_json(run / "ticket-graph.json")
    graph_tickets = {item["id"]: item for item in graph["tickets"]}
    payload = {
        "authority": {
            key: bool(value.get("granted"))
            for key, value in sorted(manifest.get("authority", {}).items())
        },
        "integrationBranch": manifest["integration"]["branch"],
        "prStrategy": manifest["integration"]["pr_strategy"],
        "runId": manifest["run_id"],
        "schemaVersion": "1.0",
        "dependencyStates": {
            dependency: manifest["review_units"][dependency]["state"]
            for dependency in unit["dependencies"]
        },
        "unit": {
            **unit,
            "id": unit_id,
            "tickets": [
                {
                    "epicId": graph_tickets[ticket_id]["epic_id"],
                    "id": ticket_id,
                    "objective": graph_tickets[ticket_id]["objective"],
                    "status": manifest["tickets"][ticket_id]["status"],
                    "title": graph_tickets[ticket_id]["title"],
                }
                for ticket_id in unit["ticket_ids"]
            ],
        },
    }
    print(pretty_json(payload), end="")


def git_value(args: list[str], label: str, cwd: Path) -> str:
    result = subprocess.run(["git", "-C", str(cwd), *args], text=True, capture_output=True)
    if result.returncode:
        raise RunError(f"cannot determine {label}: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def git_repository_identity(cwd: Path) -> tuple[Path, str]:
    root = Path(git_value(["rev-parse", "--show-toplevel"], "repository root", cwd)).resolve()
    remote = subprocess.run(
        ["git", "-C", str(root), "config", "--get", "remote.origin.url"],
        text=True,
        capture_output=True,
    )
    identity = remote.stdout.strip() if remote.returncode == 0 and remote.stdout.strip() else str(root)
    return root, identity


def integration_ref(repo: Path, branch: str) -> str:
    for ref in (f"refs/remotes/origin/{branch}", f"refs/heads/{branch}"):
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", ref],
            text=True,
            capture_output=True,
        )
        if result.returncode == 0:
            return ref
    raise RunError(f"integration branch is not available locally or from origin: {branch}")


def observed_default_branch_ref(repo: Path) -> tuple[str, str]:
    symbolic = subprocess.run(
        ["git", "-C", str(repo), "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"],
        text=True,
        capture_output=True,
    )
    if symbolic.returncode == 0:
        ref = symbolic.stdout.strip()
        sha = git_value(["rev-parse", "--verify", f"{ref}^{{commit}}"], "observed default branch", repo)
        return ref, canonical_git_object(repo, sha, "observed default branch", "commit")
    candidates = []
    for ref in ("refs/heads/main", "refs/heads/master"):
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", ref],
            text=True,
            capture_output=True,
        )
        if result.returncode == 0:
            candidates.append(ref)
    if len(candidates) != 1:
        raise RunError("cannot determine one currently observed default-branch ref")
    ref = candidates[0]
    sha = git_value(["rev-parse", "--verify", f"{ref}^{{commit}}"], "observed default branch", repo)
    return ref, canonical_git_object(repo, sha, "observed default branch", "commit")


def run_binding_registry(repo: Path) -> Path:
    raw = Path(git_value(["rev-parse", "--git-common-dir"], "Git common directory", repo))
    common = raw if raw.is_absolute() else (repo / raw).resolve()
    return common / "gauntlet" / "run-bindings.json"


def register_run_binding(repo: Path, branch: str, run: Path, repository_identity: str) -> None:
    registry = run_binding_registry(repo)
    registry.parent.mkdir(parents=True, exist_ok=True)
    lock_path = registry.with_suffix(".lock")
    with lock_path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        records = read_json(registry) if registry.is_file() else {}
        if not isinstance(records, dict):
            raise RunError(f"invalid run-binding registry: {registry}")
        existing = records.get(branch)
        if existing and Path(existing.get("run", "")).is_dir() and Path(existing["run"]).resolve() != run.resolve():
            raise RunError(f"integration branch {branch} is already bound to Execution Run {existing['run']}")
        records[branch] = {"repository": repository_identity, "run": str(run.resolve())}
        atomic_json(registry, records)


def release_gates(manifest: dict[str, Any], completion: dict[str, Any]) -> list[dict[str, Any]]:
    final = manifest["release"].get("epic-verification", {})
    final_commit = final.get("integration_head_sha")
    final_tree = final.get("identity", {}).get("treeSha")
    gates = [
        {
            "blocksOverallCompletion": True,
            "blocksPr": True,
            "evidenceRefs": sorted(
                reference
                for item in manifest["tickets"].values()
                for reference in item.get("integration_verification", {}).get("evidence", [])
            ),
            "id": "ticket-integration",
            "stage": "implementation",
            "status": "pass" if all(item.get("status") == "integrated" for item in manifest["tickets"].values()) else "pending",
            "summary": "Every compiled Ticket is integrated with an exact-identity parent verification receipt.",
        },
    ]
    if manifest["cohorts"]:
        gates.append({
            "blocksOverallCompletion": True,
            "blocksPr": True,
            "evidenceRefs": sorted(
                reference for item in manifest["cohorts"].values() for reference in item.get("evidence", [])
            ),
            "id": "cohort-verification",
            "stage": "implementation",
            "status": "pass" if all(item.get("result") == "pass" for item in manifest["cohorts"].values()) else "pending",
            "summary": "Every declared shared invariant passed once.",
        })
    gates.append({
        "blocksOverallCompletion": True,
        "blocksPr": True,
        "evidenceRefs": final.get("evidence", []),
        "id": "final-epic-verification",
        "stage": "implementation",
        "status": "pass" if completion["implemented"] else final.get("result", "pending"),
        "summary": "Final Epic verification covered canonical acceptance on the exact integrated revision.",
    })
    review = consequence_review_status(manifest, final_commit, final_tree)
    if review["required"]:
        gates.append({
            "blocksOverallCompletion": True,
            "blocksPr": True,
            "evidenceRefs": sorted(reference for item in review["results"] for reference in item["evidence"]),
            "id": "consequence-review",
            "stage": "implementation",
            "status": review["status"],
            "summary": "The fixed authority/security, failure/recovery, and black-box lenses passed on the exact candidate revision.",
        })
        dry_run = safeguard_status(manifest, "dry-run-no-mutation", final_commit, final_tree)
        gates.append({
            "blocksOverallCompletion": True,
            "blocksPr": False,
            "evidenceRefs": dry_run["evidence"],
            "id": "dry-run-no-mutation",
            "stage": "merge",
            "status": dry_run["status"],
            "summary": "Repository-owned dry-run and no-mutation proof passed on the exact final revision.",
        })
        if manifest["release"]["applicability"]["production-verification"]:
            for kind, summary in (
                ("bounded-live", "Repository-owned bounded-live proof passed before production verification."),
                ("rollback-readiness", "Repository-owned rollback readiness proof passed before production verification."),
            ):
                safeguard = safeguard_status(manifest, kind, final_commit, final_tree)
                gates.append({
                    "blocksOverallCompletion": True,
                    "blocksPr": False,
                    "evidenceRefs": safeguard["evidence"],
                    "id": kind,
                    "stage": "release",
                    "status": safeguard["status"],
                    "summary": summary,
                })
    if manifest.get("integration", {}).get("pr_strategy") == "review-prs-plus-final":
        gates.append({
            "blocksOverallCompletion": True, "blocksPr": True,
            "evidenceRefs": sorted(unit["verification"]["evidence"] for unit in manifest["review_units"].values()),
            "id": "review-units", "stage": "implementation", "status": "pass",
            "summary": "Every review unit was checked, merged, and verified.",
        })
    gates.append({
        "blocksOverallCompletion": True, "blocksPr": False, "evidenceRefs": [],
        "id": "merge-to-default", "stage": "merge", "status": "pass" if completion["merged"] else "pending",
        "summary": "Final PR merge requires the distinct merge-to-default authority capability.",
    })
    for stage in ("deployment", "production-verification"):
        applicable = manifest["release"]["applicability"][stage]
        gates.append({
            "blocksOverallCompletion": applicable, "blocksPr": False, "evidenceRefs": [],
            "id": stage, "stage": "release",
            "status": manifest["release"].get(stage, {}).get("result", "pending") if applicable else "not-applicable",
            "summary": f"{stage.replace('-', ' ').title()} is {'required after merge' if applicable else 'not applicable to this run'}.",
        })
    return gates


def cmd_project_pr(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    require_state(manifest, ("epic_verified", "merged", "deployed", "production_verified", "complete"))
    require_authority(manifest, "open-final-pr")
    pending = [key for key, item in manifest["tickets"].items() if item["status"] != "integrated"]
    failed_cohorts = [key for key, item in manifest["cohorts"].items() if item.get("result") != "pass"]
    if pending or failed_cohorts or manifest["release"].get("epic-verification", {}).get("result") != "pass":
        raise RunError("project-pr requires integrated Tickets, passing declared Cohorts, and passing final Epic verification")
    if manifest.get("integration", {}).get("pr_strategy") == "review-prs-plus-final":
        unverified = [
            key for key, unit in manifest.get("review_units", {}).items()
            if REVIEW_UNIT_STATES.index(unit["state"]) < REVIEW_UNIT_STATES.index("verified")
        ]
        if unverified:
            raise RunError(f"project-pr requires verified review units: {unverified}")
    lock = read_json(run / "source-lock.json")
    epic_id = lock["target_epic_ids"][0]
    epic = lock["epics"][epic_id]

    cwd = Path.cwd().resolve()
    repo_root, repository = git_repository_identity(cwd)
    verification = manifest["release"]["epic-verification"]
    if repository != lock.get("repository_identity") or repository != verification.get("repository_identity"):
        raise RunError("project-pr repository does not match the locked and verified repository")
    branch = manifest["integration"]["branch"]
    head = require_sha(verification.get("integration_head_sha"), "final verified integration head")
    canonical_git_object(repo_root, head, "final verified integration head", "commit")
    if manifest["state"] == "epic_verified":
        if git_value(["status", "--porcelain"], "repository cleanliness", repo_root):
            raise RunError("project-pr requires a clean repository")
        if git_value(["branch", "--show-current"], "current branch", repo_root) != branch:
            raise RunError("current branch does not match the Execution Run integration branch")
        if require_sha(git_value(["rev-parse", "HEAD"], "HEAD", repo_root), "HEAD") != head:
            raise RunError("project-pr HEAD does not match the exact revision verified by final Epic verification")
    completion = completion_projection(manifest, observed_head=head)
    if not completion["implemented"]:
        raise RunError("project-pr cannot claim implementation while final Epic verification is failed or stale")
    changed_paths = sorted({
        path
        for item in manifest["tickets"].values()
        for path in read_json(run / item["receipt_file"]).get("changed_paths", [])
    })
    verification_receipts = sorted({
        item["integration_verification"]["receipt"] for item in manifest["tickets"].values()
    } | {
        item["receipt"] for item in manifest["cohorts"].values() if item.get("receipt")
    } | {verification["receipt"]} | {
        item["receipt"] for item in manifest.get("consequence_review", {}).get("results", {}).values()
        if item.get("receipt")
    } | {
        item["receipt"] for item in manifest["release"].get("safeguards", {}).values()
        if item.get("receipt")
    })
    projection = {
        "binding": {
            "branch": branch, "generation": manifest["generation"], "graphSha256": manifest["graph_sha256"],
            "headSha": head, "epicVerificationSha256": sha_file(run / verification["receipt"]), "repository": repository,
            "runId": manifest["run_id"], "sourceLockSha256": manifest["source_lock_sha256"],
        },
        "acceptedCriteria": epic["acceptance"],
        "changedPaths": changed_paths,
        "completion": completion,
        "deferrals": {"cannotVerify": epic["cannot_verify"], "nonGoals": epic["non_goals"]},
        "epic": {
            "id": epic_id,
            "scopeAreas": [
                {"id": scope_id, "responsibility": item["responsibility"]}
                for scope_id, item in sorted(epic["scope_areas"].items())
            ],
            "title": epic["title"],
        },
        "releaseGates": release_gates(manifest, completion),
        "schemaVersion": PROJECT_PR_SCHEMA,
        "title": f"{epic_id}: implement {epic['title']}",
        "verificationReceipts": verification_receipts,
    }
    print(pretty_json(projection), end="")


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
    target_epic_id = source_info["epic_ids"][0]
    launch = validate_launch_set(Path(args.launch_set).resolve(), source, source_info, target_epic_id)
    created_at = utc_now()
    root_start_ordinal = optional_ordinal(args.request_start_ordinal, "Epic-root request start ordinal")
    repository_root, repository_identity = git_repository_identity(Path.cwd())
    pr_strategy = args.pr_strategy
    if pr_strategy not in PR_STRATEGIES:
        raise RunError(f"PR strategy must be one of {', '.join(PR_STRATEGIES)}")
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
        "launch_set": launch,
        "release_contract": require_string(args.release_contract, "release contract"),
        "release_stages": stages,
        "repository_root": str(repository_root),
        "repository_identity": repository_identity,
        "canonical_source_path": launch["canonical_source_path"],
        "source_path": str(source), "source_sha256": source_hash,
        "target_epic_ids": source_info["epic_ids"], "scope_hashes": source_info["scope_hashes"],
        "epics": source_info["epics"],
    }
    manifest = {
        "artifact_hashes": {}, "cohorts": {}, "event_sequence": 0, "generation": 0, "graph_sha256": None,
        "ownership": {
            "children": ["assigned code worktree", "receipt input", "named evidence"],
            "parent": ["source-lock.json", "manifest.json", "resume.md", "events.jsonl", "cohorts/", "release/", "review_units"],
        },
        "protocol_version": PROTOCOL_VERSION,
        "authority": {key: {"granted": False, "source": None} for key in AUTHORITY_CAPABILITIES},
        "integration": {
            "branch": integration_branch,
            "merge_executor": "parent-after-user-authority",
            "mode": INTEGRATION_MODE,
            "pr_strategy": pr_strategy,
        },
        "release": {"applicability": {key: key in stages for key in RELEASE_APPLICABILITY}},
        "operations": {},
        "progress": None,
        "request_owners": {
            "root": {
                "nativeChildId": launch["task_id"],
                "ownerId": "root",
                "ownerKind": "parent",
                "ownerRef": "epic-root",
                "requestWindow": {
                    "endOrdinal": None,
                    "endedAt": None,
                    "startOrdinal": root_start_ordinal,
                    "startedAt": created_at,
                },
                "requestedProfile": None,
            },
        },
        "run_id": args.run_id, "shared_context": {}, "lanes": {}, "review_units": {},
        "source": {"epic_ids": source_info["epic_ids"], "path": str(source), "sha256": source_hash},
        "state": "discussing", "tickets": {},
        "time": {
            "created_at": created_at,
            "protocol_version": TIMESTAMP_PROTOCOL,
            "started_at": None,
            "terminal_at": None,
            "updated_at": created_at,
        },
    }
    atomic_json(run / "source-lock.json", lock)
    if os.environ.get("PRD_RUN_FAIL_INIT_AFTER") == "source-lock":
        raise RunError("injected initialization interruption after source lock")
    manifest["source_lock_sha256"] = sha_file(run / "source-lock.json")
    atomic_text(run / "events.jsonl", "")
    atomic_text(run / "shared-context" / "global-v1.md", "# Global context\n\nNot compiled.\n")
    for stage in (*RELEASE_STAGES, "merge", "rollback", "epic-verification"):
        atomic_text(run / "release" / f"{stage}.md", f"# {stage.replace('-', ' ').title()}\n\nNot recorded.\n")
    pin_artifact(run, manifest, run / "shared-context" / "global-v1.md")
    event(run, manifest, "run_initialized", {"source_sha256": source_hash}, timestamp=created_at)
    save_manifest(run, manifest)
    try:
        os.rename(run, final_run)
    except OSError as exc:
        raise RunError(f"cannot publish execution run {final_run}: {exc}") from exc
    try:
        register_run_binding(repository_root, integration_branch, final_run, repository_identity)
    except (OSError, RunError) as exc:
        shutil.rmtree(final_run)
        if isinstance(exc, RunError):
            raise
        raise RunError(f"cannot register Execution Run binding: {exc}") from exc
    args._init_temporary = None
    print(final_run)


def cmd_transition(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    target = args.to
    if target not in STATES:
        raise RunError(f"unknown state {target}")
    request_end_ordinal = optional_ordinal(args.request_end_ordinal, "Epic-root request end ordinal")
    if request_end_ordinal is not None and target != "complete":
        raise RunError("Epic-root request end ordinal is only valid for the complete transition")
    current_index = STATES.index(manifest["state"])
    if current_index + 1 >= len(STATES) or STATES[current_index + 1] != target:
        raise RunError(f"invalid transition {manifest['state']} -> {target}")
    if target == "epic_verified":
        pending = [key for key, item in manifest["tickets"].items() if item["status"] != "integrated"]
        unverified = [key for key, item in manifest["cohorts"].items() if item.get("result") != "pass"]
        if pending or unverified:
            raise RunError(f"cannot complete Epic verification; pending tickets={pending}, unverified cohorts={unverified}")
        if manifest["release"].get("epic-verification", {}).get("result") != "pass":
            raise RunError("final Epic verification has not passed")
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
    timestamp = utc_now()
    manifest["state"] = target
    time_facts = manifest.get("time", {})
    if (
        target == "executing"
        and time_facts.get("protocol_version") == TIMESTAMP_PROTOCOL
        and time_facts.get("started_at") is None
    ):
        time_facts["started_at"] = timestamp
    if target == "complete" and time_facts.get("started_at") is not None:
        time_facts["terminal_at"] = timestamp
        root_owner = manifest.get("request_owners", {}).get("root")
        if root_owner:
            close_request_window(root_owner, request_end_ordinal, timestamp)
    event(run, manifest, "state_transitioned", {"to": target}, timestamp=timestamp)
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
    strategy = manifest.get("integration", {}).get("pr_strategy", "one-final-pr-per-run")
    if strategy == "review-prs-plus-final" and not graph["review_units"]:
        raise RunError("review-prs-plus-final requires graph review_units")
    if strategy != "review-prs-plus-final" and graph["review_units"]:
        raise RunError("review_units are only valid with review-prs-plus-final")
    graph_epics = {item["epic_id"] for item in graph["tickets"]}
    if graph_epics != set(lock["target_epic_ids"]):
        raise RunError(f"ticket graph Epics {sorted(graph_epics)} do not match locked targets {lock['target_epic_ids']}")
    if set(graph["scope_areas"]) != set(lock["scope_hashes"]):
        raise RunError("ticket graph Scope Areas do not exactly match the locked PRD target")
    epic_id = lock["target_epic_ids"][0]
    locked_triggers = lock["epics"][epic_id]["consequence_triggers"]
    if graph["review"]["triggers"] != locked_triggers:
        raise RunError("Ticket Graph high-consequence triggers must exactly match the locked canonical Epic")
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
    ticket_units = {
        ticket_id: unit_id
        for unit_id, unit in graph["review_units"].items()
        for ticket_id in unit["ticket_ids"]
    }
    for ticket_id, unit_id in ticket_units.items():
        manifest["tickets"][ticket_id]["review_unit_id"] = unit_id
    manifest["review_units"] = {
        unit_id: {
            "dependencies": unit["dependencies"],
            "state": "pending",
            "ticket_ids": unit["ticket_ids"],
        }
        for unit_id, unit in graph["review_units"].items()
    }
    manifest["cohorts"] = {key: {"result": None, **graph["cohorts"][key]} for key in sorted(graph["cohorts"])}
    manifest["consequence_review"] = {"policy": graph["review"], "results": {}}
    manifest["release"]["safeguards"] = {}
    manifest["shared_context"] = {
        "cohorts": {key: f"shared-context/{key.lower()}-v1.md" for key in sorted(graph["cohorts"])},
        "global": "shared-context/global-v1.md",
    }
    compiled_at = utc_now()
    manifest["graph_sha256"] = object_hash(graph)
    manifest["progress"] = progress_facts(graph, manifest)
    manifest["operations"] = {
        unit["id"]: operation_entry(unit, compiled_at)
        for unit in operation_units(manifest["progress"])
    }
    manifest["state"] = "compiled"
    atomic_json(run / "ticket-graph.json", graph)
    atomic_text(run / "ticket-graph.md", render_ticket_graph(graph))
    pin_artifact(run, manifest, run / "ticket-graph.json")
    pin_artifact(run, manifest, run / "ticket-graph.md")
    pin_artifact(run, manifest, run / manifest["shared_context"]["global"])
    for relative in manifest["shared_context"]["cohorts"].values():
        pin_artifact(run, manifest, run / relative)
    event(
        run,
        manifest,
        "graph_compiled",
        {"graph_sha256": manifest["graph_sha256"], "tickets": sorted(tickets)},
        timestamp=compiled_at,
    )
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
    started_at = utc_now()
    start_ordinal = optional_ordinal(args.request_start_ordinal, "owner request start ordinal")
    request_owner_id = f"ticket:{args.ticket}:r{item['revision']}:a{args.attempt}"
    if request_owner_id in manifest.get("request_owners", {}):
        raise RunError(f"request owner window already exists: {request_owner_id}")
    item["lease"] = {"agent": agent, "attempt": args.attempt}
    item["owner"] = {
        "nativeChildId": args.native_child_id,
        "ownerKind": args.owner_kind,
        "ownerRef": agent,
        "requestOwnerId": request_owner_id,
        "requestedProfile": args.requested_profile,
    }
    manifest.setdefault("request_owners", {})[request_owner_id] = {
        "nativeChildId": args.native_child_id,
        "ownerId": request_owner_id,
        "ownerKind": args.owner_kind,
        "ownerRef": agent,
        "requestWindow": {
            "endOrdinal": None,
            "endedAt": None,
            "startOrdinal": start_ordinal,
            "startedAt": started_at,
        },
        "requestedProfile": args.requested_profile,
    }
    item["status"] = "dispatched"
    event(
        run,
        manifest,
        "ticket_claimed",
        {"agent": agent, "attempt": args.attempt, "revision": item["revision"], "ticket": args.ticket},
        timestamp=started_at,
    )
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
    started_at = utc_now()
    start_ordinal = optional_ordinal(args.request_start_ordinal, "owner request start ordinal")
    request_owner_id = f"lane:{lane_id}:a{args.attempt}"
    if request_owner_id in manifest.get("request_owners", {}):
        raise RunError(f"request owner window already exists: {request_owner_id}")
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
        state["owner"] = {
            "nativeChildId": args.native_child_id,
            "ownerKind": args.owner_kind,
            "ownerRef": agent,
            "requestOwnerId": request_owner_id,
            "requestedProfile": args.requested_profile,
        }
        state["status"] = "dispatched"
        event(run, manifest, "ticket_claimed", {
            "agent": agent, "attempt": args.attempt, "lane": lane_id,
            "revision": state["revision"], "ticket": ticket_id,
        }, timestamp=started_at)
    manifest.setdefault("request_owners", {})[request_owner_id] = {
        "nativeChildId": args.native_child_id,
        "ownerId": request_owner_id,
        "ownerKind": args.owner_kind,
        "ownerRef": agent,
        "requestWindow": {
            "endOrdinal": None,
            "endedAt": None,
            "startOrdinal": start_ordinal,
            "startedAt": started_at,
        },
        "requestedProfile": args.requested_profile,
    }
    event(run, manifest, "lane_claimed", {
        "affinity": args.affinity, "agent": agent, "attempt": args.attempt,
        "lane": lane_id, "tickets": ticket_ids,
    }, timestamp=started_at)
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


def cmd_completion(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    lock = read_json(run / "source-lock.json")
    print(pretty_json(completion_projection(
        manifest,
        observed_head=observed_integration_head(manifest, lock),
    )), end="")


def progress_projection(manifest: dict[str, Any]) -> dict[str, Any] | None:
    progress = manifest.get("progress")
    if not isinstance(progress, dict):
        return None
    units = []
    for unit in progress.get("units", []):
        status = "pass"
        if unit["kind"] == "ticket-build":
            ticket_id = unit["id"].removeprefix("build:ticket:")
            ticket_status = manifest.get("tickets", {}).get(ticket_id, {}).get("status")
            status = {
                "blocked": "fail",
                "completed": "pass",
                "dispatched": "running",
                "integrated": "pass",
                "ready": "queued",
                "waiting": "queued",
            }.get(ticket_status, "queued")
        elif unit["kind"] != "prepare":
            status = manifest.get("operations", {}).get(unit["id"], {}).get("status", "queued")
        units.append({**unit, "status": status})
    return {
        "denominatorSha256": progress["denominator_sha256"],
        "policyVersion": progress["policy_version"],
        "schemaVersion": progress["schema_version"],
        "units": units,
    }


def operations_projection(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    operations = []
    for operation_id, item in sorted(manifest.get("operations", {}).items()):
        operations.append({
            "attempt": item.get("attempt", 0),
            "attempts": [
                {
                    "attempt": attempt["attempt"],
                    "finishedAt": attempt.get("finished_at"),
                    "startedAt": attempt.get("started_at"),
                    "status": attempt["status"],
                }
                for attempt in item.get("attempts", [])
            ],
            "finishedAt": item.get("finished_at"),
            "id": operation_id,
            "kind": item["kind"],
            "phase": item["phase"],
            "queuedAt": item.get("queued_at"),
            "startedAt": item.get("started_at"),
            "status": item["status"],
        })
    return operations


def time_projection(manifest: dict[str, Any]) -> dict[str, Any]:
    facts = manifest.get("time") if isinstance(manifest.get("time"), dict) else {}
    started_at = facts.get("started_at")
    protocol = facts.get("protocol_version")
    return {
        "createdAt": facts.get("created_at"),
        "elapsedCoverage": "complete" if protocol == TIMESTAMP_PROTOCOL and started_at else "unavailable",
        "protocolVersion": protocol,
        "startedAt": started_at,
        "terminalAt": facts.get("terminal_at") if started_at else None,
        "updatedAt": facts.get("updated_at"),
    }


def run_facts_projection(run: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    graph = read_json(run / "ticket-graph.json")
    lock = read_json(run / "source-lock.json")
    commit = observed_integration_head(manifest, lock)
    tree = None
    if commit:
        result = subprocess.run(
            ["git", "-C", lock["repository_root"], "rev-parse", f"{commit}^{{tree}}"],
            text=True,
            capture_output=True,
        )
        if result.returncode == 0:
            tree = result.stdout.strip().lower()
    identity = graph["verification_identity"]
    receipts = []
    receipt_records: list[tuple[str, dict[str, Any]]] = []
    for ticket_id, item in sorted(manifest["tickets"].items()):
        if item.get("integration_verification"):
            receipt_records.append((f"ticket:{ticket_id}", item["integration_verification"]))
    for cohort_id, item in sorted(manifest["cohorts"].items()):
        if item.get("receipt"):
            receipt_records.append((f"shared:{cohort_id}", read_json(run / item["receipt"])))
    final = manifest.get("release", {}).get("epic-verification")
    if final:
        receipt_records.append(("final-epic", final))
    for receipt_id, record in receipt_records:
        receipt_identity = record.get("identity", {})
        if record.get("result", "pass") != "pass" or not receipt_identity:
            continue
        receipts.append({
            "id": receipt_id,
            "identity": {
                "argv": receipt_identity["argv"],
                "commit": receipt_identity["commitSha"],
                "environment": f"sha256:{receipt_identity['environmentSha256']}",
                "fixtures": f"sha256:{receipt_identity['fixturesSha256']}",
                "toolchain": f"sha256:{receipt_identity['toolchainSha256']}",
                "tree": receipt_identity["treeSha"],
            },
            "result": "pass",
        })
    epic_id = lock["target_epic_ids"][0]
    final_commit = final.get("integration_head_sha") if final else None
    final_tree = final.get("identity", {}).get("treeSha") if final else None
    review = consequence_review_status(manifest, final_commit or commit, final_tree or tree)
    safeguards = {
        kind: safeguard_status(manifest, kind, final_commit or commit, final_tree or tree)
        for kind in SAFEGUARD_KINDS
    }
    request_owners = manifest.get("request_owners")
    owners = (
        [request_owners[key] for key in sorted(request_owners)]
        if isinstance(request_owners, dict) and request_owners
        else [item["owner"] for _, item in sorted(manifest["tickets"].items()) if item.get("owner")]
    )
    return {
        "epicId": epic_id,
        "epicTitle": lock["epics"][epic_id]["title"],
        "exactRevision": completion_projection(manifest, observed_head=commit)["exactRevision"],
        "operations": operations_projection(manifest),
        "owners": owners,
        "plannedChecks": graph["planned_checks"],
        "progress": progress_projection(manifest),
        "review": review,
        "release": {
            "applicability": manifest["release"]["applicability"],
            "safeguards": safeguards,
        },
        "schemaVersion": "gauntlet/epic-run-facts/v1",
        "time": time_projection(manifest),
        "verificationIdentity": {
            "commit": commit,
            "environment": identity["environment"],
            "fixtures": identity["fixtures"],
            "toolchain": identity["toolchain"],
            "tree": tree,
        },
        "verificationReceipts": receipts,
    }


def cmd_run_facts(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    if manifest.get("graph_sha256") is None:
        raise RunError("run-facts requires a compiled single-Epic Ticket Graph")
    print(pretty_json(run_facts_projection(run, manifest)), end="")


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
            *(
                [{"id": cohort_id, "path": manifest["shared_context"]["cohorts"][cohort_id], "role": "cohort"}]
                if cohort_id else []
            ),
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
    end_ordinal = optional_ordinal(args.request_end_ordinal, "owner request end ordinal")
    request_owner_id = (item.get("owner") or {}).get("requestOwnerId")
    other_active = [
        ticket_id for ticket_id, other in manifest["tickets"].items()
        if ticket_id != args.ticket
        and other.get("status") == "dispatched"
        and (other.get("owner") or {}).get("requestOwnerId") == request_owner_id
    ]
    if end_ordinal is not None and other_active:
        raise RunError(f"owner request end ordinal requires every lane ticket to be terminal; active={other_active}")
    request_owner = manifest.get("request_owners", {}).get(request_owner_id) if request_owner_id else None
    if (
        request_owner
        and not other_active
        and end_ordinal is not None
        and request_owner["requestWindow"].get("startOrdinal") is not None
        and end_ordinal < request_owner["requestWindow"]["startOrdinal"]
    ):
        raise RunError("request end ordinal must not precede its exclusive start baseline")
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
    timestamp = utc_now()
    if request_owner_id and not other_active:
        if request_owner:
            close_request_window(request_owner, end_ordinal, timestamp)
    event(
        run,
        manifest,
        "receipt_recorded",
        {"revision": item["revision"], "status": receipt["status"], "ticket": args.ticket},
        timestamp=timestamp,
    )
    save_manifest(run, manifest)


def cmd_integrate(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    require_state(manifest, ("executing", "integrating"))
    item = get_ticket(manifest, args.ticket)
    if item["status"] != "completed":
        raise RunError(f"ticket {args.ticket} is not completed")
    receipt_path = run / item.get("receipt_file", "")
    if not item.get("receipt_file") or not receipt_path.is_file():
        raise RunError("ticket has no recorded receipt for the active attempt")
    operation_id = f"integrate:ticket:{args.ticket}"
    begin_operation(run, manifest, operation_id)
    verification, relative = record_verification_receipt(
        run,
        manifest,
        Path(args.verification_receipt),
        f"{args.ticket}.integration.json",
        "ticket integration verification receipt",
    )
    item["integration_verification"] = {
        "evidence": verification["evidence"],
        "identity": verification["identity"],
        "receipt": relative,
        "summary": verification["summary"],
    }
    item["status"] = "integrated"
    item["lease"] = None
    refresh_readiness(manifest)
    timestamp = utc_now()
    finish_operation(manifest, operation_id, verification["result"], timestamp)
    event(
        run,
        manifest,
        "ticket_integrated",
        {"receipt": relative, "revision": item["revision"], "ticket": args.ticket},
        timestamp=timestamp,
    )
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
    operation_id = f"integrate:cohort:{args.cohort}"
    begin_operation(run, manifest, operation_id)
    verification, relative = record_verification_receipt(
        run,
        manifest,
        Path(args.verification_receipt),
        f"cohort-{args.cohort}.json",
        "Cohort verification receipt",
    )
    cohort["result"] = verification["result"]
    cohort["evidence"] = verification["evidence"]
    cohort["receipt"] = relative
    cohort_report = run / "cohorts" / f"{args.cohort.lower()}.md"
    atomic_text(cohort_report, f"# Cohort {args.cohort}\n\nResult: {verification['result']}\n\nSummary: {verification['summary']}\n\nReceipt: {relative}\n")
    pin_artifact(run, manifest, cohort_report)
    timestamp = utc_now()
    finish_operation(manifest, operation_id, verification["result"], timestamp)
    event(
        run,
        manifest,
        "cohort_verified",
        {"cohort": args.cohort, "result": verification["result"]},
        timestamp=timestamp,
    )
    save_manifest(run, manifest)


def cmd_record_review(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    require_state(manifest, ("integrating",))
    policy = manifest.get("consequence_review", {}).get("policy", {})
    expected = {item["id"] for item in policy.get("lenses", [])}
    if not policy.get("required") or args.lens not in expected:
        raise RunError(f"review lens is not required by this run: {args.lens}")
    operation_id = f"verify:review:{args.lens}"
    begin_operation(run, manifest, operation_id)
    verification, relative = record_verification_receipt(
        run,
        manifest,
        Path(args.verification_receipt),
        f"consequence-review-{args.lens}.json",
        f"{args.lens} consequence review receipt",
        expected_oracle=consequence_oracle(manifest, lens=args.lens),
    )
    manifest["consequence_review"]["results"][args.lens] = {**verification, "receipt": relative}
    timestamp = utc_now()
    finish_operation(manifest, operation_id, verification["result"], timestamp)
    event(
        run,
        manifest,
        "consequence_review_recorded",
        {"lens": args.lens, "result": verification["result"]},
        timestamp=timestamp,
    )
    save_manifest(run, manifest)


def cmd_record_safeguard(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    policy = manifest.get("consequence_review", {}).get("policy", {})
    if not policy.get("triggers"):
        raise RunError("ordinary runs do not require consequence safeguards")
    if args.kind != "dry-run-no-mutation" and not manifest["release"]["applicability"]["production-verification"]:
        raise RunError(f"{args.kind} is not required without an applicable production-verification stage")
    if args.kind == "bounded-live":
        require_state(manifest, ("deployed",))
        require_authority(manifest, "deploy-production", "verify-production", *trigger_authorities(manifest))
    else:
        require_state(manifest, ("epic_verified", "merged", "deployed"))
    final = manifest.get("release", {}).get("epic-verification", {})
    if final.get("result") != "pass":
        raise RunError("consequence safeguards require passing final Epic verification")
    operation_id = f"ship:safeguard:{args.kind}"
    begin_operation(run, manifest, operation_id)
    verification, relative = record_verification_receipt(
        run,
        manifest,
        Path(args.verification_receipt),
        f"safeguard-{args.kind}.json",
        f"{args.kind} safeguard receipt",
        expected_oracle=consequence_oracle(manifest, safeguard=args.kind),
    )
    if verification["identity"]["commitSha"] != final.get("integration_head_sha"):
        raise RunError("safeguard receipt does not match the exact final verified revision")
    manifest["release"].setdefault("safeguards", {})[args.kind] = {**verification, "receipt": relative}
    timestamp = utc_now()
    finish_operation(manifest, operation_id, verification["result"], timestamp)
    event(
        run,
        manifest,
        "consequence_safeguard_recorded",
        {"kind": args.kind, "result": verification["result"]},
        timestamp=timestamp,
    )
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
    if applicable:
        final = manifest.get("release", {}).get("epic-verification", {})
        final_commit = require_sha(final.get("integration_head_sha"), "final verified revision")
        require_safeguard(manifest, "dry-run-no-mutation", final_commit)
        if stage == "deployment":
            require_authority(manifest, "deploy-production", *trigger_authorities(manifest))
        else:
            require_authority(manifest, "verify-production")
            require_safeguard(manifest, "bounded-live", final_commit)
            require_safeguard(manifest, "rollback-readiness", final_commit)
    previous = manifest["release"].get(stage, {})
    if previous.get("result") == "fail" and args.result == "pass" and manifest["release"].get("rollback", {}).get("result") != "pass":
        raise RunError(f"failed {stage} cannot be replaced with pass until rollback evidence is recorded")
    if stage == "deployment" and applicable and args.result == "pass":
        revision = require_string(args.revision, "deployed revision").lower()
        if revision != manifest["release"].get("merge", {}).get("main_sha"):
            raise RunError("deployment revision must equal the verified merged main SHA")
    elif stage == "production-verification" and applicable and args.result == "pass":
        revision = require_string(args.revision, "production-proved revision").lower()
        if revision != manifest["release"].get("deployment", {}).get("revision"):
            raise RunError("production proof revision must equal the exact deployed revision")
    else:
        revision = args.revision
    record = {"evidence": evidence, "result": args.result, "summary": summary}
    if revision:
        record["revision"] = revision
    previous_record = manifest["release"].get(stage)
    if previous_record and previous_record != record:
        if previous_record.get("result") != "fail" or args.result != "pass" or manifest["release"].get("rollback", {}).get("result") != "pass":
            raise RunError(f"recorded {stage} facts conflict with the observed release state")
    operation_id = f"ship:{stage}"
    if applicable:
        begin_operation(run, manifest, operation_id)
    manifest["release"][stage] = record
    revision_line = f"\nRevision: {revision}\n" if revision else ""
    report = f"# {stage.replace('-', ' ').title()}\n\nResult: {args.result}\n\nSummary: {summary}\n{revision_line}\nEvidence: {evidence}\n"
    atomic_text(run / "release" / f"{stage}.md", report)
    pin_artifact(run, manifest, run / "release" / f"{stage}.md")
    timestamp = utc_now()
    if applicable:
        finish_operation(manifest, operation_id, args.result, timestamp)
    event(
        run,
        manifest,
        "release_stage_recorded",
        {"result": args.result, "stage": stage},
        timestamp=timestamp,
    )
    save_manifest(run, manifest)


def cmd_verify_epic(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    require_state(manifest, ("integrating",))
    pending = [ticket_id for ticket_id, item in manifest["tickets"].items() if item["status"] != "integrated"]
    failed_cohorts = [cohort_id for cohort_id, item in manifest["cohorts"].items() if item.get("result") != "pass"]
    if pending or failed_cohorts:
        raise RunError(f"final Epic verification requires integrated Tickets and passing declared Cohorts; pending={pending}, cohorts={failed_cohorts}")
    lock = read_json(run / "source-lock.json")
    commit, tree = exact_integration_revision(manifest, lock)
    review = consequence_review_status(manifest, commit, tree)
    if review["required"] and review["status"] != "pass":
        raise RunError(f"final Epic verification requires all consequence lenses to pass on the exact candidate revision; status={review['status']}")
    operation_id = "verify:final-epic"
    begin_operation(run, manifest, operation_id)
    verification, relative = record_verification_receipt(
        run,
        manifest,
        Path(args.verification_receipt),
        "final-epic-verification.json",
        "final Epic verification receipt",
    )
    epic_id = lock["target_epic_ids"][0]
    if verification["identity"]["oracleSha256"] != lock["epics"][epic_id]["section_sha256"]:
        raise RunError("final Epic verification oracle must identify the locked canonical Epic section")
    commit = verification["identity"]["commitSha"]
    manifest["release"]["epic-verification"] = {
        **verification,
        "integration_head_sha": commit,
        "receipt": relative,
        "repository_identity": lock["repository_identity"],
    }
    report = run / "release" / "epic-verification.md"
    atomic_text(report, f"# Final Epic Verification\n\nResult: {verification['result']}\n\nSummary: {verification['summary']}\n\nExact revision: {commit}\n\nReceipt: {relative}\n")
    pin_artifact(run, manifest, report)
    timestamp = utc_now()
    finish_operation(manifest, operation_id, verification["result"], timestamp)
    event(
        run,
        manifest,
        "epic_verified",
        {"result": verification["result"], "revision": commit},
        timestamp=timestamp,
    )
    save_manifest(run, manifest)


def cmd_record_merge(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    require_state(manifest, ("epic_verified", "merged"))
    if "authority" in manifest:
        require_authority(manifest, "merge-to-default")
    lock = read_json(run / "source-lock.json")
    repository_root = Path(require_string(lock.get("repository_root"), "source-lock.repository_root")).resolve()
    repo, repository_identity = git_repository_identity(repository_root)
    if repo != repository_root or repository_identity != lock.get("repository_identity"):
        raise RunError("source-lock.repository_root no longer resolves to the locked repository")
    merged = canonical_git_object(repo, args.merged_sha, "merged SHA", "commit")
    main = canonical_git_object(repo, args.main_sha, "main SHA", "commit")
    if merged != main:
        raise RunError("merged SHA and verified main SHA must be the same Git object ID")
    default_ref, observed_main = observed_default_branch_ref(repo)
    if main != observed_main:
        raise RunError(f"verified main SHA does not equal the currently observed default-branch ref {default_ref}")
    verified_head = canonical_git_object(
        repo,
        manifest["release"]["epic-verification"].get("integration_head_sha"),
        "final verified integration head",
        "commit",
    )
    ancestry = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", verified_head, main],
        text=True,
        capture_output=True,
    )
    verification_method = "ancestry"
    if ancestry.returncode == 1:
        verified_tree = git_value(["rev-parse", f"{verified_head}^{{tree}}"], "verified candidate tree", repo)
        main_tree = git_value(["rev-parse", f"{main}^{{tree}}"], "observed default tree", repo)
        if verified_tree != main_tree:
            raise RunError("observed default branch preserves neither verified-head ancestry nor the exact verified candidate tree")
        verification_method = "tree-equivalence"
    elif ancestry.returncode != 0:
        raise RunError(f"cannot verify merge ancestry: {ancestry.stderr.strip() or ancestry.stdout.strip()}")
    require_safeguard(manifest, "dry-run-no-mutation", verified_head)
    integration = manifest.get("integration", {})
    record = {
        "evidence": require_string(args.evidence, "merge evidence"),
        "integration_branch": integration.get("branch"),
        "main_sha": main,
        "merged_sha": merged,
        "pr": require_string(args.pr, "PR reference"),
        "pr_strategy": integration.get("pr_strategy"),
        "result": "pass",
        "verification_method": verification_method,
        "verified_head_sha": verified_head,
    }
    existing = manifest["release"].get("merge")
    if existing and existing != record:
        raise RunError("recorded merge facts conflict with the observed merge")
    operation_id = "ship:merge"
    if not existing:
        begin_operation(run, manifest, operation_id)
    manifest["release"]["merge"] = record
    report = run / "release" / "merge.md"
    atomic_text(report, f"# Merge\n\nResult: pass\n\nPR: {record['pr']}\n\nIntegration branch: {record['integration_branch'] or 'not recorded'}\n\nPR strategy: {record['pr_strategy'] or 'not recorded'}\n\nMerged SHA: {merged}\n\nVerified main SHA: {main}\n\nVerification method: {verification_method}\n\nEvidence: {record['evidence']}\n")
    pin_artifact(run, manifest, report)
    timestamp = utc_now()
    if not existing:
        finish_operation(manifest, operation_id, "pass", timestamp)
        event(
            run,
            manifest,
            "merge_recorded",
            {"main_sha": main, "pr": record["pr"]},
            timestamp=timestamp,
        )
    save_manifest(run, manifest)


def cmd_record_rollback(args: argparse.Namespace) -> None:
    run = run_path(args.run)
    manifest = load_manifest(run)
    require_authority(manifest, "execute-rollback")
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
    if graph.get("review_units", {}) != old_graph.get("review_units", {}):
        raise RunError("reconcile cannot change frozen review unit membership or dependencies; compile a new run")
    old_by_id = {item["id"]: item for item in old_graph["tickets"]}
    new_by_id = {item["id"]: item for item in graph["tickets"]}
    if set(old_by_id) != set(new_by_id):
        raise RunError("reconcile cannot add or remove tickets; compile a new run")
    candidate_progress = progress_facts(graph, manifest)
    current_progress = manifest.get("progress")
    if (
        isinstance(current_progress, dict)
        and candidate_progress["denominator_sha256"] != current_progress.get("denominator_sha256")
    ):
        raise RunError("reconcile cannot change progress denominator membership; start a superseding run")
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
    impacted_units = {
        unit_id for unit_id, unit in graph.get("review_units", {}).items()
        if set(unit["ticket_ids"]) & impacted
    }
    reconciled_at = utc_now()
    backup, base_generation = begin_transaction_backup(
        run, "reconcile",
        ["source-lock.json", "ticket-graph.json", "ticket-graph.md", "manifest.json", "resume.md", "events.jsonl"],
        [],
    )
    manifest["consequence_review"] = {"policy": graph["review"], "results": {}}
    manifest["release"]["safeguards"] = {}
    manifest["release"].pop("epic-verification", None)
    for ticket_id in sorted(impacted):
        item = manifest["tickets"][ticket_id]
        history = dict(item.get("revision_history", {}))
        revision = item["revision"] + 1
        path = run / "tickets" / f"{ticket_id}.r{revision}.md"
        atomic_text(path, render_ticket(new_by_id[ticket_id], revision))
        manifest["tickets"][ticket_id] = ticket_entry(new_by_id[ticket_id], revision, path, new_scope_hashes)
        review_unit_id = next(
            (unit_id for unit_id, unit in graph.get("review_units", {}).items() if ticket_id in unit["ticket_ids"]),
            None,
        )
        if review_unit_id:
            manifest["tickets"][ticket_id]["review_unit_id"] = review_unit_id
        manifest["tickets"][ticket_id]["revision_history"] = {**history, **manifest["tickets"][ticket_id]["revision_history"]}
        reset_operation(manifest, f"integrate:ticket:{ticket_id}", reconciled_at)
    for unit_id in sorted(impacted_units):
        unit_graph = graph["review_units"][unit_id]
        manifest["review_units"][unit_id] = {
            "dependencies": unit_graph["dependencies"], "state": "pending", "ticket_ids": unit_graph["ticket_ids"],
        }
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
        "epics": source_info["epics"],
    }
    manifest["source"] = {"epic_ids": source_info["epic_ids"], "path": str(source), "sha256": lock["source_sha256"]}
    manifest["graph_sha256"] = object_hash(graph)
    previous_cohorts = manifest["cohorts"]
    manifest["cohorts"] = {}
    for key in sorted(graph["cohorts"]):
        affected = key in changed_cohort_contexts or bool(set(graph["cohorts"][key]["ticket_ids"]) & impacted)
        preserved = previous_cohorts.get(key, {}) if not affected else {}
        manifest["cohorts"][key] = {**graph["cohorts"][key], "result": preserved.get("result")}
        if preserved.get("evidence"):
            manifest["cohorts"][key]["evidence"] = preserved["evidence"]
        if affected:
            reset_operation(manifest, f"integrate:cohort:{key}", reconciled_at)
    for operation_id in sorted(manifest.get("operations", {})):
        if operation_id.startswith(("verify:", "ship:")):
            reset_operation(manifest, operation_id, reconciled_at)
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
    event(
        run,
        manifest,
        "source_reconciled",
        {"changed_scopes": sorted(changed_scopes), "invalidated_tickets": sorted(impacted)},
        timestamp=reconciled_at,
    )
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
    init.add_argument("--executions", required=True); init.add_argument("--run-id", required=True)
    init.add_argument(
        "--source",
        required=True,
        help="immutable launch-set.source.md / launch source snapshot (not the mutable canonical PRD)",
    )
    init.add_argument("--target", required=True, action="append"); init.add_argument("--launch-set", required=True)
    init.add_argument("--instruction-version", default="prd-run/v1")
    init.add_argument("--release-contract", required=True); init.add_argument("--release-stages", default="merge")
    init.add_argument("--request-start-ordinal", type=int)
    init.add_argument("--integration-branch")
    init.add_argument("--pr-strategy", choices=PR_STRATEGIES, default=DEFAULT_PR_STRATEGY)
    init.set_defaults(func=cmd_init)
    transition = commands.add_parser("transition")
    transition.add_argument("--run", required=True); transition.add_argument("--to", required=True)
    transition.add_argument("--request-end-ordinal", type=int); transition.set_defaults(func=cmd_transition)
    compile_cmd = commands.add_parser("compile")
    compile_cmd.add_argument("--run", required=True); compile_cmd.add_argument("--graph", required=True); compile_cmd.set_defaults(func=cmd_compile)
    claim = commands.add_parser("claim")
    claim.add_argument("--run", required=True); claim.add_argument("--ticket", required=True); claim.add_argument("--agent", required=True); claim.add_argument("--attempt", required=True, type=int)
    claim.add_argument("--owner-kind", choices=("parent", "delegated"), default="delegated")
    claim.add_argument("--native-child-id"); claim.add_argument("--requested-profile")
    claim.add_argument("--request-start-ordinal", type=int); claim.set_defaults(func=cmd_claim)
    claim_lane = commands.add_parser("claim-lane")
    claim_lane.add_argument("--run", required=True); claim_lane.add_argument("--lane", required=True); claim_lane.add_argument("--agent", required=True)
    claim_lane.add_argument("--attempt", required=True, type=int); claim_lane.add_argument("--affinity", required=True); claim_lane.add_argument("--ticket", required=True, action="append")
    claim_lane.add_argument("--owner-kind", choices=("parent", "delegated"), default="delegated")
    claim_lane.add_argument("--native-child-id"); claim_lane.add_argument("--requested-profile")
    claim_lane.add_argument("--request-start-ordinal", type=int); claim_lane.set_defaults(func=cmd_claim_lane)
    ready = commands.add_parser("ready")
    ready.add_argument("--run", required=True); ready.add_argument("--affinity"); ready.set_defaults(func=cmd_ready)
    resume = commands.add_parser("resume")
    resume.add_argument("--run", required=True); resume.set_defaults(func=cmd_resume)
    completion = commands.add_parser("completion")
    completion.add_argument("--run", required=True); completion.set_defaults(func=cmd_completion)
    run_facts = commands.add_parser("run-facts")
    run_facts.add_argument("--run", required=True); run_facts.set_defaults(func=cmd_run_facts)
    materialize = commands.add_parser("materialize-ticket")
    materialize.add_argument("--run", required=True); materialize.add_argument("--ticket", required=True); materialize.add_argument("--output"); materialize.set_defaults(func=cmd_materialize)
    materialize_lane = commands.add_parser("materialize-lane")
    materialize_lane.add_argument("--run", required=True); materialize_lane.add_argument("--lane", required=True); materialize_lane.set_defaults(func=cmd_materialize_lane)
    receipt = commands.add_parser("record-receipt")
    receipt.add_argument("--run", required=True); receipt.add_argument("--ticket", required=True); receipt.add_argument("--receipt", required=True)
    receipt.add_argument("--request-end-ordinal", type=int); receipt.set_defaults(func=cmd_receipt)
    integrate = commands.add_parser("integrate")
    integrate.add_argument("--run", required=True); integrate.add_argument("--ticket", required=True)
    integrate.add_argument("--verification-receipt", required=True); integrate.set_defaults(func=cmd_integrate)
    cohort = commands.add_parser("verify-cohort")
    cohort.add_argument("--run", required=True); cohort.add_argument("--cohort", required=True)
    cohort.add_argument("--verification-receipt", required=True); cohort.set_defaults(func=cmd_verify_cohort)
    review = commands.add_parser("record-review")
    review.add_argument("--run", required=True); review.add_argument("--lens", required=True, choices=REQUIRED_REVIEW_LENSES)
    review.add_argument("--verification-receipt", required=True); review.set_defaults(func=cmd_record_review)
    safeguard = commands.add_parser("record-safeguard")
    safeguard.add_argument("--run", required=True); safeguard.add_argument("--kind", required=True, choices=SAFEGUARD_KINDS)
    safeguard.add_argument("--verification-receipt", required=True); safeguard.set_defaults(func=cmd_record_safeguard)
    verify_epic = commands.add_parser("verify-epic")
    verify_epic.add_argument("--run", required=True); verify_epic.add_argument("--verification-receipt", required=True)
    verify_epic.set_defaults(func=cmd_verify_epic)
    merge = commands.add_parser("record-merge")
    merge.add_argument("--run", required=True); merge.add_argument("--pr", required=True); merge.add_argument("--merged-sha", required=True); merge.add_argument("--main-sha", required=True); merge.add_argument("--evidence", required=True); merge.set_defaults(func=cmd_record_merge)
    release = commands.add_parser("record-release")
    release.add_argument("--run", required=True); release.add_argument("--stage", required=True, choices=RELEASE_STAGES); release.add_argument("--result", required=True, choices=("pass", "fail", "skipped")); release.add_argument("--summary", required=True); release.add_argument("--evidence", required=True); release.add_argument("--revision"); release.set_defaults(func=cmd_record_release)
    rollback = commands.add_parser("record-rollback")
    rollback.add_argument("--run", required=True); rollback.add_argument("--trigger", required=True); rollback.add_argument("--action", required=True); rollback.add_argument("--result", required=True, choices=("pass", "fail")); rollback.add_argument("--evidence", required=True); rollback.set_defaults(func=cmd_record_rollback)
    reconcile = commands.add_parser("reconcile")
    reconcile.add_argument("--run", required=True); reconcile.add_argument("--source", required=True); reconcile.add_argument("--graph", required=True); reconcile.set_defaults(func=cmd_reconcile)
    authority = commands.add_parser("record-authority")
    authority.add_argument("--run", required=True); authority.add_argument("--capability", required=True, choices=AUTHORITY_CAPABILITIES); authority.add_argument("--source", required=True); authority.set_defaults(func=cmd_record_authority)
    authority_status = commands.add_parser("authority-status")
    authority_status.add_argument("--run", required=True); authority_status.add_argument("--capability", required=True, choices=AUTHORITY_CAPABILITIES); authority_status.set_defaults(func=cmd_authority_status)
    review_unit = commands.add_parser("review-unit")
    review_unit.add_argument("--run", required=True); review_unit.add_argument("--unit", required=True); review_unit.add_argument("--action", required=True, choices=REVIEW_UNIT_STATES[1:])
    review_unit.add_argument("--branch"); review_unit.add_argument("--pr"); review_unit.add_argument("--head-sha"); review_unit.add_argument("--tested-base-sha"); review_unit.add_argument("--tested-tree-sha"); review_unit.add_argument("--tested-merge-sha")
    review_unit.add_argument("--proof-command"); review_unit.add_argument("--proof-result"); review_unit.add_argument("--proof-evidence"); review_unit.add_argument("--current-base-sha"); review_unit.add_argument("--merge-sha"); review_unit.add_argument("--merged-tree-sha")
    review_unit.add_argument("--evidence"); review_unit.add_argument("--summary"); review_unit.set_defaults(func=cmd_review_unit)
    review_status = commands.add_parser("review-unit-status")
    review_status.add_argument("--run", required=True); review_status.add_argument("--unit", required=True); review_status.set_defaults(func=cmd_review_unit_status)
    project_pr = commands.add_parser("project-pr")
    project_pr.add_argument("--run", required=True); project_pr.add_argument("--json", action="store_true"); project_pr.set_defaults(func=cmd_project_pr)
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
