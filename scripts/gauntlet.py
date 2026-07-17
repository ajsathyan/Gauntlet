#!/usr/bin/env python3
import argparse
import fcntl
import json
import os
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from gauntletlib.analytics import register as register_analytics
from gauntletlib.cli import EXIT_CODES
from gauntletlib.cli import build_parser as build_cli_parser
from gauntletlib.cli import dispatch
from gauntletlib.closeout import configure as configure_closeout
from gauntletlib.closeout import (
    advance_run_release_state as advance_run_release_state,
    closeout_install_command as closeout_install_command,
    completion_allows_archive as completion_allows_archive,
)
from gauntletlib.contracts import (
    validate_merge_handoff as validate_merge_handoff,
    validate_run_merge_handoff as validate_run_merge_handoff,
)
from gauntletlib.closeout import register_archive
from gauntletlib.closeout import register_changelog
from gauntletlib.closeout import register_closeout
from gauntletlib.closeout import register_followup_memory
from gauntletlib.docs import DOC_EXECUTION_BLOCK_BEGIN as DOC_EXECUTION_BLOCK_BEGIN
from gauntletlib.docs import DOC_EXECUTION_BLOCK_END as DOC_EXECUTION_BLOCK_END
from gauntletlib.docs import DOC_EXECUTION_LEGACY_HASHES as DOC_EXECUTION_LEGACY_HASHES
from gauntletlib.docs import accepted_record_path
from gauntletlib.docs import command_docs_draft_promote as command_docs_draft_promote
from gauntletlib.docs import configure as configure_docs
from gauntletlib.docs import ensure_doc_execution_contract as ensure_doc_execution_contract
from gauntletlib.docs import migrate_doc_execution_contract as migrate_doc_execution_contract
from gauntletlib.docs import register as register_docs
from gauntletlib.docs import valid_epic_title
from gauntletlib.merge import acquire_run_merge_lease as _acquire_run_merge_lease
from gauntletlib.merge import branch_name
from gauntletlib.merge import checks_state
from gauntletlib.merge import configure as configure_merge
from gauntletlib.merge import current_default_head
from gauntletlib.merge import current_head
from gauntletlib.merge import default_represents_candidate as _default_represents_candidate
from gauntletlib.merge import delete_remote_branch
from gauntletlib.merge import dirty_paths
from gauntletlib.merge import launch_merge_lease_path
from gauntletlib.merge import merge_input_path
from gauntletlib.merge import pending_run_merge_gates as pending_run_merge_gates
from gauntletlib.merge import persisted_run_merge_lease as persisted_run_merge_lease
from gauntletlib.merge import persist_merge_lease as _persist_merge_lease
from gauntletlib.merge import projection_changelog_entry as projection_changelog_entry
from gauntletlib.merge import primary_worktree
from gauntletlib.merge import refresh_default_head
from gauntletlib.merge import release_run_merge_lease as _release_run_merge_lease
from gauntletlib.merge import render_pr_body as render_pr_body
from gauntletlib.merge import register as register_merge
from gauntletlib.review_unit import configure as configure_review_unit
from gauntletlib.review_unit import register as register_review_unit
from gauntletlib.core.fsio import atomic_write_text as _atomic_write_text
from gauntletlib.core.fsio import write_new_file as _write_new_file
from gauntletlib.core.findings import add_finding as _add_finding
from gauntletlib.core.findings import status_for as _status_for
from gauntletlib.core.hashing import sha256 as _sha256
from gauntletlib.core.jsonio import canonical_json as _canonical_json
from gauntletlib.core.proc import gh_binary as gh_binary, git, run_cmd as _run_cmd
from gauntletlib.core.redact import SECRET_PATTERNS as SECRET_PATTERNS
from gauntletlib.core.redact import has_secret
from gauntletlib.core.timefmt import utc_timestamp as _utc_timestamp
from thread_titles import epic_task_title, product_task_title


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
CHECKER = SCRIPTS / "check-workflow-etiquette.py"
EPIC_COPY_TEMPLATE = ROOT / "templates" / "epic-execution-copy.json"
EPIC_LAUNCH_SCHEMA = "gauntlet.epic-launch.v1"
EPIC_STATES = {
    "planned", "starting", "in-progress", "needs-decision",
    "implementation-complete", "failed", "stopped",
}
DEPENDENCY_BOUNDARIES = {"merged", "deployed", "productionProved"}
HIGH_CONSEQUENCE_TRIGGERS = {
    "billing-paid-actions",
    "credentials-auth-permissions",
    "migrations-data-loss",
    "production-authority",
    "destructive-actions",
}
PROGRESS_SOURCE_SCHEMA = "gauntlet/live-progress-source/v1"
PROGRESS_STATE_SCHEMA = "gauntlet.progress-dashboard-state/v1"
PROGRESS_HEALTH_SCHEMA = "gauntlet.progress-dashboard-health/v1"
PROGRESS_REFRESH_SECONDS = 2.5
PROGRESS_TERMINAL_GRACE_SECONDS = 10.0
PASSING_CHECK_CONCLUSIONS = {"SUCCESS", "SKIPPED", "NEUTRAL"}
PASSING_STATUS_STATES = {"SUCCESS", "SKIPPED", "NEUTRAL"}
def run_cmd(args, cwd=None, env=None, check=False):
    return _run_cmd(args, cwd=cwd, env=env, check=check)


def default_represents_candidate(repo, candidate, default_head):
    return _default_represents_candidate(
        repo,
        candidate,
        default_head,
        git_fn=git,
    )


def persist_merge_lease(repo, lease_path, lease, default_head):
    return _persist_merge_lease(
        repo,
        lease_path,
        lease,
        default_head,
        default_represents_candidate_fn=default_represents_candidate,
    )


def acquire_run_merge_lease(repo, run_path, handoff):
    return _acquire_run_merge_lease(
        repo,
        run_path,
        handoff,
        refresh_default_head_fn=refresh_default_head,
        git_fn=git,
        persist_merge_lease_fn=persist_merge_lease,
    )


def release_run_merge_lease(repo, lease_path, lease, merged_head):
    return _release_run_merge_lease(
        repo,
        lease_path,
        lease,
        merged_head,
        refresh_default_head_fn=refresh_default_head,
        default_represents_candidate_fn=default_represents_candidate,
        git_fn=git,
    )


def read_text(path):
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def utc_timestamp():
    return _utc_timestamp()


def git_root(repo):
    result = git(["rev-parse", "--show-toplevel"], repo)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def write_new_file(path, content):
    return _write_new_file(path, content)


def atomic_write_text(path, content, mode=0o600):
    return _atomic_write_text(path, content, mode=mode)


configure_docs(
    atomic_write_text=lambda path, content, mode=0o600: atomic_write_text(
        path, content, mode=mode
    ),
    parse_dependency_list=lambda raw: parse_dependency_list(raw),
    parse_release_stages=lambda raw: parse_release_stages(raw),
    parse_consequence_triggers=lambda raw: parse_consequence_triggers(raw),
    legacy_hashes=lambda: DOC_EXECUTION_LEGACY_HASHES,
)


def sha256_bytes(value):
    return _sha256(value)


def canonical_json(value):
    return _canonical_json(value)


def epic_source_sections(source_text):
    matches = list(re.finditer(r"^## Epic ([A-Z][A-Z0-9]*-\d{3}):\s*(.+?)\s*$", source_text, re.MULTILINE))
    sections = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source_text)
        section = source_text[match.start():end].rstrip() + "\n"
        sections[match.group(1)] = {
            "id": match.group(1),
            "title": match.group(2).strip(),
            "text": section,
        }
    return sections


def epic_metadata(section_text, name, default=None):
    match = re.search(rf"^{re.escape(name)}:[ \t]*([^\r\n]*)[ \t]*$", section_text, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else default


def parse_dependency_list(raw):
    if not raw or raw.strip().lower() in {"none", "n/a", "not applicable"}:
        return []
    dependencies = []
    for item in raw.split(","):
        value = item.strip().strip("`")
        match = re.fullmatch(r"([A-Z][A-Z0-9]*-\d{3})(?:@(merged|deployed|productionProved))?", value)
        if not match:
            raise ValueError(f"Invalid Epic dependency: {item.strip()}")
        dependencies.append({"epicId": match.group(1), "boundary": match.group(2) or "merged"})
    return dependencies


def parse_release_stages(raw):
    requested = {"merge"}
    if raw:
        values = {item.strip().lower().replace("_", "-") for item in raw.split(",") if item.strip()}
        aliases = {
            "production": "production-verification",
            "production-proof": "production-verification",
            "productionproved": "production-verification",
        }
        requested = {aliases.get(value, value) for value in values}
    unknown = requested - {"merge", "deployment", "production-verification"}
    if unknown:
        raise ValueError("Unknown release stage: " + ", ".join(sorted(unknown)))
    if "production-verification" in requested and "deployment" not in requested:
        raise ValueError("Production verification requires deployment")
    if "merge" not in requested:
        raise ValueError("Every Epic release requires merge")
    return sorted(requested)


def parse_consequence_triggers(raw):
    if raw is None:
        return []
    if not raw.strip():
        raise ValueError("High-consequence triggers must be literal `none` or a non-empty canonical list")
    if raw.strip().lower() == "none":
        return []
    triggers = sorted({item.strip().lower() for item in raw.split(",") if item.strip()})
    unknown = set(triggers) - HIGH_CONSEQUENCE_TRIGGERS
    if unknown:
        raise ValueError("Unknown high-consequence trigger: " + ", ".join(sorted(unknown)))
    return triggers


def implementation_target_ids(source_text):
    match = re.search(r"^Implementation target:\s*(.*?)\s*$", source_text, re.MULTILINE | re.IGNORECASE)
    if not match:
        raise ValueError("PRD is missing Implementation target")
    ids = re.findall(r"[A-Z][A-Z0-9]*-\d{3}", match.group(1))
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Implementation target must contain unique stable Epic IDs")
    return ids


def load_accepted_epic_record(source_path, source_bytes):
    path = accepted_record_path(source_path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("Flexible product documents require an explicit accepted-Epic record")
    record = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schemaVersion", "epicId", "title", "sourcePath", "sourceSha256", "acceptedAt",
        "dependencies", "releaseStages", "consequenceTriggers",
    }
    if not isinstance(record, dict) or set(record) != required or record.get("schemaVersion") != "gauntlet.accepted-epic.v1":
        raise ValueError("Accepted-Epic record has an unsupported shape")
    if Path(record["sourcePath"]).resolve() != source_path.resolve():
        raise ValueError("Accepted-Epic record points to a different product document")
    if record["sourceSha256"] != sha256_bytes(source_bytes):
        raise ValueError("Product document changed after acceptance; accept the revised version explicitly")
    epic_id = record.get("epicId")
    if not isinstance(epic_id, str) or not re.fullmatch(r"[A-Z][A-Z0-9]*-\d{3}", epic_id):
        raise ValueError("Accepted-Epic record has an invalid Epic ID")
    title = record.get("title")
    if not isinstance(title, str) or not valid_epic_title(title):
        raise ValueError("Accepted-Epic record has an invalid title")
    dependencies = record.get("dependencies")
    if not isinstance(dependencies, list):
        raise ValueError("Accepted-Epic dependencies must be a list")
    for item in dependencies:
        if not isinstance(item, dict) or set(item) != {"epicId", "boundary"} or item["boundary"] not in DEPENDENCY_BOUNDARIES:
            raise ValueError("Accepted-Epic dependencies have an unsupported shape")
    release_stages = record.get("releaseStages")
    if not isinstance(release_stages, list) or release_stages != parse_release_stages(",".join(release_stages)):
        raise ValueError("Accepted-Epic release stages are invalid")
    consequence_triggers = record.get("consequenceTriggers")
    if not isinstance(consequence_triggers, list) or consequence_triggers != parse_consequence_triggers(",".join(consequence_triggers) if consequence_triggers else "none"):
        raise ValueError("Accepted-Epic consequence triggers are invalid")
    return record


def validate_epic_dependency_graph(epics, target_ids):
    target = set(target_ids)
    for epic_id in target_ids:
        for dependency in epics[epic_id]["dependencies"]:
            dependency_id = dependency["epicId"]
            if dependency_id not in epics:
                raise ValueError(f"{epic_id} depends on unknown Epic {dependency_id}")
            if dependency_id not in target:
                status = epics[dependency_id]["sourceStatus"].lower()
                if status not in {"complete", "implemented", "release-complete"}:
                    raise ValueError(f"{epic_id} depends on {dependency_id}, which is outside the target and not complete")

    visiting = set()
    visited = set()

    def visit(epic_id):
        if epic_id in visiting:
            raise ValueError(f"Epic dependency cycle includes {epic_id}")
        if epic_id in visited:
            return
        visiting.add(epic_id)
        for dependency in epics[epic_id]["dependencies"]:
            if dependency["epicId"] in target:
                visit(dependency["epicId"])
        visiting.remove(epic_id)
        visited.add(epic_id)

    for epic_id in target_ids:
        visit(epic_id)


def build_epic_launch_set(source_path, target_ids, priority="p1"):
    source_path = Path(source_path).resolve()
    source_bytes = source_path.read_bytes()
    source_text = source_bytes.decode("utf-8")
    sections = epic_source_sections(source_text)
    parsed = {}
    if sections:
        declared_target = implementation_target_ids(source_text)
        if target_ids and list(target_ids) != declared_target:
            raise ValueError("Requested target must exactly match the PRD Implementation target in canonical order")
        target_ids = sorted(declared_target)
        for epic_id, section in sections.items():
            status = epic_metadata(section["text"], "Epic status", "")
            dependencies = parse_dependency_list(epic_metadata(section["text"], "Depends on", "None"))
            consequence_raw = epic_metadata(section["text"], "High-consequence triggers", None)
            if consequence_raw is None and epic_id in target_ids:
                raise ValueError(f"{epic_id} must declare `High-consequence triggers: none` or canonical trigger IDs")
            parsed[epic_id] = {
                "title": section["title"],
                "dependencies": dependencies,
                "releaseStages": parse_release_stages(epic_metadata(section["text"], "Release stages", "merge")),
                "consequenceTriggers": parse_consequence_triggers(consequence_raw),
                "sourceStatus": status,
            }
        missing = [epic_id for epic_id in target_ids if epic_id not in parsed]
        if missing:
            raise ValueError("Implementation target is missing Epic sections: " + ", ".join(missing))
        for epic_id in target_ids:
            section_text = sections[epic_id]["text"]
            epic = parsed[epic_id]
            if epic["sourceStatus"].lower() != "accepted":
                raise ValueError(f"{epic_id} must be Accepted before launch")
            for field in ("Build ready", "Ships independently", "Rolls back independently"):
                if (epic_metadata(section_text, field, "") or "").lower() != "yes":
                    raise ValueError(f"{epic_id} must declare `{field}: yes`")
    else:
        record = load_accepted_epic_record(source_path, source_bytes)
        declared_target = [record["epicId"]]
        if target_ids and list(target_ids) != declared_target:
            raise ValueError("Requested target must exactly match the accepted product document")
        target_ids = declared_target
        parsed[record["epicId"]] = {
            "title": record["title"],
            "dependencies": record["dependencies"],
            "releaseStages": record["releaseStages"],
            "consequenceTriggers": record["consequenceTriggers"],
            "sourceStatus": "Accepted",
        }
    validate_epic_dependency_graph(parsed, target_ids)

    source = {"path": str(source_path), "sha256": sha256_bytes(source_bytes)}
    coverage = {
        "schemaVersion": EPIC_LAUNCH_SCHEMA,
        "source": source,
        "targetEpicIds": target_ids,
        "epics": {
            epic_id: {
                "title": parsed[epic_id]["title"],
                "dependencies": parsed[epic_id]["dependencies"],
                "releaseStages": parsed[epic_id]["releaseStages"],
                "consequenceTriggers": parsed[epic_id]["consequenceTriggers"],
            }
            for epic_id in target_ids
        },
    }
    coverage_sha = sha256_bytes(canonical_json(coverage).encode("utf-8"))
    epics = {}
    for epic_id in target_ids:
        epics[epic_id] = {
            **coverage["epics"][epic_id],
            "taskId": None,
            "runPath": None,
            "status": "planned",
            "blocker": None,
            "stopDisposition": None,
            "startReconciliation": None,
            "emittedEvents": [],
        }
    return {
        "schemaVersion": EPIC_LAUNCH_SCHEMA,
        "source": source,
        "targetEpicIds": target_ids,
        "coverageSha256": coverage_sha,
        "epics": epics,
        "aggregateEmittedEvents": [],
    }, source_text


def write_launch_set(path, data):
    atomic_write_text(Path(path), json.dumps(data, indent=2, sort_keys=True) + "\n")


def launch_coverage_projection(data):
    return {
        "schemaVersion": data["schemaVersion"],
        "source": {key: data["source"][key] for key in ["path", "sha256"]},
        "targetEpicIds": data["targetEpicIds"],
        "epics": {
            epic_id: {
                "title": data["epics"][epic_id]["title"],
                "dependencies": data["epics"][epic_id]["dependencies"],
                "releaseStages": data["epics"][epic_id]["releaseStages"],
                "consequenceTriggers": data["epics"][epic_id]["consequenceTriggers"],
            }
            for epic_id in data["targetEpicIds"]
        },
    }


def launch_task_key(launch, epic_id):
    return sha256_bytes(f"{launch['coverageSha256']}:{epic_id}".encode("utf-8"))[:24]


def load_launch_set(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schemaVersion") != EPIC_LAUNCH_SCHEMA:
        raise ValueError(f"Unsupported Epic launch schema: {data.get('schemaVersion')}")
    required = {"schemaVersion", "source", "targetEpicIds", "coverageSha256", "epics", "aggregateEmittedEvents"}
    if set(data) != required:
        raise ValueError("Epic launch set has unexpected or missing top-level fields")
    if len(data["targetEpicIds"]) != len(set(data["targetEpicIds"])) or set(data["epics"]) != set(data["targetEpicIds"]):
        raise ValueError("Epic launch membership must exactly match targetEpicIds")
    expected_coverage = sha256_bytes(canonical_json(launch_coverage_projection(data)).encode("utf-8"))
    if data["coverageSha256"] != expected_coverage:
        raise ValueError("Epic launch coverage no longer matches its immutable coverage digest")
    for epic_id, epic in data["epics"].items():
        if epic.get("status") not in EPIC_STATES:
            raise ValueError(f"Invalid state for {epic_id}: {epic.get('status')}")
    return path, data


def progress_paths(launch_path):
    launch_path = Path(launch_path).resolve()
    stem = launch_path.stem
    return {
        "source": launch_path.with_name(stem + ".progress-source.json"),
        "state": launch_path.with_name(stem + ".progress-dashboard.json"),
        "supervisorLock": launch_path.with_name(stem + ".progress-supervisor.lock"),
    }


def progress_placeholder_facts(epic_id, epic):
    observed_at = utc_timestamp()
    return {
        "schemaVersion": "gauntlet/epic-run-facts/v1",
        "epicId": epic_id,
        "epicTitle": epic["title"],
        "time": {
            "protocolVersion": None, "elapsedCoverage": "unavailable", "createdAt": None,
            "startedAt": None, "updatedAt": observed_at, "terminalAt": None,
        },
        "progress": None,
        "operations": [],
        "owners": [],
        "release": {
            "applicability": {
                stage: stage in epic["releaseStages"]
                for stage in ("merge", "deployment", "production-verification")
            },
        },
    }


def run_facts_for_progress(repo, run_path):
    output, error = run_prd_controller(repo, ["run-facts", "--run", str(Path(run_path).resolve())])
    if error:
        return None
    try:
        facts = json.loads(output)
    except json.JSONDecodeError:
        return None
    return facts if facts.get("schemaVersion") == "gauntlet/epic-run-facts/v1" else None


def telemetry_for_progress(facts):
    owners = facts.get("owners") if isinstance(facts, dict) else None
    if not isinstance(owners, list) or not owners:
        return None
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix="gauntlet-progress-facts-", suffix=".json")
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(facts, handle, sort_keys=True)
        command = [
            sys.executable, str(SCRIPTS / "subagent-audit.py"), "summary",
            "--run-facts", temporary, "--json",
        ]
        result = subprocess.run(command, text=True, capture_output=True, timeout=2.0)
        if result.returncode != 0:
            return None
        telemetry = json.loads(result.stdout)
        return telemetry if telemetry.get("schemaVersion") == "gauntlet/run-telemetry-summary/v1" else None
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None
    finally:
        if temporary and Path(temporary).exists():
            Path(temporary).unlink()


def refresh_progress_source(launch_path, launch, repo):
    paths = progress_paths(launch_path)
    previous = {}
    if paths["source"].is_file():
        try:
            previous = json.loads(paths["source"].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}
    previous_runs = previous.get("runs") if isinstance(previous.get("runs"), dict) else {}
    previous_telemetry = previous.get("telemetry") if isinstance(previous.get("telemetry"), dict) else {}
    runs = {}
    telemetry = {}
    for epic_id in launch["targetEpicIds"]:
        epic = launch["epics"][epic_id]
        facts = run_facts_for_progress(repo, epic.get("runPath")) if epic.get("runPath") else None
        if facts is None:
            preserved = previous_runs.get(epic_id)
            if isinstance(preserved, dict) and epic.get("runPath"):
                runs[epic_id] = preserved
            else:
                runs[epic_id] = {"runId": epic_id, "facts": progress_placeholder_facts(epic_id, epic)}
            if epic_id in previous_telemetry:
                telemetry[epic_id] = previous_telemetry[epic_id]
            continue
        runs[epic_id] = {"runId": Path(epic["runPath"]).name, "facts": facts}
        summary = telemetry_for_progress(facts)
        if summary is not None:
            telemetry[epic_id] = summary
        elif epic_id in previous_telemetry:
            telemetry[epic_id] = previous_telemetry[epic_id]
    source = {
        "schemaVersion": PROGRESS_SOURCE_SCHEMA,
        "launch": {
            "coverageSha256": launch["coverageSha256"],
            "targetEpicIds": launch["targetEpicIds"],
            "epics": {
                epic_id: {
                    "status": launch["epics"][epic_id]["status"],
                    "blocker": launch["epics"][epic_id].get("blocker"),
                    "stopDisposition": launch["epics"][epic_id].get("stopDisposition"),
                }
                for epic_id in launch["targetEpicIds"]
            },
        },
        "runs": runs,
        "telemetry": telemetry,
    }
    atomic_write_text(paths["source"], json.dumps(source, indent=2, sort_keys=True) + "\n", mode=0o600)
    return paths["source"]


def progress_process_birth_sha(pid):
    result = subprocess.run(
        ["/bin/ps", "-o", "lstart=", "-p", str(pid)],
        text=True, capture_output=True, timeout=1.0,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return sha256_bytes(" ".join(result.stdout.split()).encode("utf-8"))


def read_progress_state(launch_path):
    state_path = progress_paths(launch_path)["state"]
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return state_path, None
    return state_path, state if isinstance(state, dict) else None


def progress_assets_sha():
    root = ROOT / "templates" / "progress-dashboard"
    parts = []
    for relative in ("assets/app.css", "assets/app.js", "index.html"):
        path = root / relative
        if not path.is_file():
            return None
        parts.append(relative.encode() + b"\0" + path.read_bytes())
    return sha256_bytes(b"\0".join(parts))


def authenticated_progress_state(launch_path):
    state_path, state = read_progress_state(launch_path)
    if not state or state.get("schemaVersion") != PROGRESS_STATE_SCHEMA:
        return state_path, None
    if state.get("status") == "stopped":
        return state_path, state
    if state.get("status") != "running" or not isinstance(state.get("pid"), int):
        return state_path, None
    capability = state.get("capability")
    origin = state.get("origin")
    if (
        not isinstance(capability, str)
        or not isinstance(origin, str)
        or not re.fullmatch(r"http://127\.0\.0\.1:\d{1,5}", origin)
        or state.get("processBirthSha256") != progress_process_birth_sha(state["pid"])
    ):
        return state_path, None
    request = urllib.request.Request(
        origin + "/healthz",
        headers={"Authorization": "Bearer " + capability},
        method="GET",
    )
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=1.0) as response:
            health = json.loads(response.read())
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return state_path, None
    if (
        health.get("schemaVersion") != PROGRESS_HEALTH_SCHEMA
        or health.get("processNonce") != state.get("processNonce")
        or health.get("executableSha256") != state.get("executableSha256")
        or health.get("launchId") != state.get("launchId")
    ):
        return state_path, None
    return state_path, state


def verified_progress_state(launch_path):
    state_path, state = authenticated_progress_state(launch_path)
    if not state or state.get("status") != "running":
        return state_path, state
    executable = SCRIPTS / "progress-dashboard.py"
    if (
        not executable.is_file()
        or state.get("executableSha256") != sha256_bytes(executable.read_bytes())
        or state.get("assetsSha256") != progress_assets_sha()
    ):
        return state_path, None
    return state_path, state


def progress_dashboard_status(launch_path):
    state_path, state = verified_progress_state(launch_path)
    if state and state.get("status") == "running":
        return {
            "status": "running", "stateFile": str(state_path), "pid": state["pid"],
            "launchId": state.get("launchId"), "sourceStatus": state.get("sourceStatus"),
        }
    if state and state.get("status") == "stopped":
        return {"status": "stopped", "stateFile": str(state_path), "launchId": state.get("launchId")}
    return {"status": "unavailable", "stateFile": str(state_path)}


def progress_launch_terminal(launch, projections):
    for epic_id in launch["targetEpicIds"]:
        epic = launch["epics"][epic_id]
        if epic["status"] in {"failed", "stopped"}:
            continue
        if (projections.get(epic_id) or {}).get("complete") is True:
            continue
        return False
    return True


def stop_progress_dashboard(launch_path):
    state_path, state = authenticated_progress_state(launch_path)
    if not state or state.get("status") != "running":
        return progress_dashboard_status(launch_path)
    status = {
        "status": "running", "stateFile": str(state_path), "pid": state["pid"],
        "launchId": state.get("launchId"), "sourceStatus": state.get("sourceStatus"),
    }
    try:
        os.kill(status["pid"], signal.SIGTERM)
    except (OSError, ProcessLookupError):
        return {**status, "status": "unavailable"}
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        _, current_state = read_progress_state(launch_path)
        if current_state and current_state.get("status") == "stopped":
            return {"status": "stopped", "stateFile": str(state_path), "launchId": current_state.get("launchId")}
        time.sleep(0.05)
    return {**status, "status": "unavailable"}


def start_progress_dashboard(launch_path, launch, repo):
    source = refresh_progress_source(launch_path, launch, repo)
    paths = progress_paths(launch_path)
    command = [
        sys.executable, str(SCRIPTS / "progress-dashboard.py"), "serve",
        "--source", str(source),
        "--assets", str(ROOT / "templates" / "progress-dashboard"),
        "--state-file", str(paths["state"]),
        "--host", "127.0.0.1", "--port", "0", "--stale-after", "300",
    ]
    subprocess.Popen(
        command, cwd=Path(repo).resolve(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True, close_fds=True,
    )
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        status = progress_dashboard_status(launch_path)
        if status["status"] == "running":
            return {**status, "started": True}
        time.sleep(0.05)
    return {"status": "unavailable", "stateFile": str(paths["state"]), "started": False}


def ensure_progress_supervisor(launch_path, launch, repo):
    _, owned = authenticated_progress_state(launch_path)
    if owned and owned.get("status") == "running" and verified_progress_state(launch_path)[1] is None:
        stop_progress_dashboard(launch_path)
    existing = progress_dashboard_status(launch_path)
    command = [
        sys.executable, str(Path(__file__).resolve()), "epic-tasks", "progress-supervise",
        "--git-root", str(Path(repo).resolve()), "--launch-set", str(Path(launch_path).resolve()),
        "--interval", str(PROGRESS_REFRESH_SECONDS),
    ]
    subprocess.Popen(
        command, cwd=Path(repo).resolve(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True, close_fds=True,
    )
    if existing["status"] == "running":
        # The detached contender exits immediately when a supervisor already owns
        # the launch lock, and takes ownership when the dashboard outlived it.
        return {**existing, "started": False}
    deadline = time.monotonic() + 4.0
    while time.monotonic() < deadline:
        status = progress_dashboard_status(launch_path)
        if status["status"] == "running":
            return {**status, "started": True}
        time.sleep(0.05)
    return {"status": "unavailable", "stateFile": str(progress_paths(launch_path)["state"]), "started": False}


def unavailable_progress_dashboard(launch_path, *, started=False):
    return {
        "status": "unavailable",
        "stateFile": str(progress_paths(launch_path)["state"]),
        "started": started,
    }


def safely_ensure_progress_supervisor(launch_path, launch, repo):
    try:
        return ensure_progress_supervisor(launch_path, launch, repo)
    except (OSError, ValueError, TypeError, subprocess.SubprocessError, json.JSONDecodeError, TimeoutError):
        return unavailable_progress_dashboard(launch_path)


def safely_stop_progress_dashboard(launch_path):
    try:
        return stop_progress_dashboard(launch_path)
    except (OSError, ValueError, TypeError, subprocess.SubprocessError, json.JSONDecodeError, TimeoutError):
        return unavailable_progress_dashboard(launch_path)


def safely_progress_dashboard_status(launch_path):
    try:
        return progress_dashboard_status(launch_path)
    except (OSError, ValueError, TypeError, subprocess.SubprocessError, json.JSONDecodeError, TimeoutError):
        return unavailable_progress_dashboard(launch_path)


def progress_browser_action(launch, epic_id, dashboard):
    if dashboard.get("status") != "running":
        return None
    action = {
        "type": "open_browser",
        "surface": "codex-in-app-browser",
        "stateFile": dashboard["stateFile"],
        "route": "/",
        "credentialTransport": "fragment-from-state-file",
        "reuseKey": "gauntlet-progress:" + launch["coverageSha256"][:24],
    }
    if len(launch["targetEpicIds"]) == 1:
        action["epicId"] = epic_id
    return action


def command_epic_tasks_progress_supervise(args):
    paths = progress_paths(args.launch_set)
    paths["supervisorLock"].parent.mkdir(parents=True, exist_ok=True)
    if not hasattr(os, "O_NOFOLLOW") and paths["supervisorLock"].is_symlink():
        return 0
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(paths["supervisorLock"], flags, 0o600)
    except OSError:
        return 0
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        return 0
    os.fchmod(descriptor, 0o600)
    lock = os.fdopen(descriptor, "a+")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        return 0
    stopped = False
    terminal_since = None

    def stop(signum, frame):
        nonlocal stopped
        stopped = True

    previous = {
        signal.SIGTERM: signal.signal(signal.SIGTERM, stop),
        signal.SIGINT: signal.signal(signal.SIGINT, stop),
    }
    try:
        while not stopped:
            cycle_started = time.monotonic()
            try:
                launch_path, launch = load_launch_set(args.launch_set)
                refresh_progress_source(launch_path, launch, args.git_root)
                projections = launch_projections(args.git_root, launch)
                if progress_launch_terminal(launch, projections):
                    terminal_since = terminal_since or time.monotonic()
                    if time.monotonic() - terminal_since >= PROGRESS_TERMINAL_GRACE_SECONDS:
                        stop_progress_dashboard(launch_path)
                        break
                else:
                    terminal_since = None
                if progress_dashboard_status(launch_path)["status"] != "running":
                    start_progress_dashboard(launch_path, launch, args.git_root)
            except (OSError, ValueError, json.JSONDecodeError):
                pass
            deadline = cycle_started + max(0.5, args.interval)
            while not stopped and time.monotonic() < deadline:
                time.sleep(min(0.1, deadline - time.monotonic()))
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()
    return 0


def command_epic_tasks_progress_stop(args):
    payload = {"schemaVersion": PROGRESS_STATE_SCHEMA, **safely_stop_progress_dashboard(args.launch_set)}
    print_payload(payload, args.json)
    return 0


def launch_source_text(launch):
    snapshot = launch["source"].get("snapshotPath")
    if not snapshot:
        raise ValueError("Epic launch set is missing its immutable source snapshot")
    path = Path(snapshot)
    content = path.read_bytes()
    if sha256_bytes(content) != launch["source"]["sha256"]:
        raise ValueError("Epic launch source snapshot does not match the locked source hash")
    return content.decode("utf-8")


def lifecycle_copy_contract():
    data = json.loads(EPIC_COPY_TEMPLATE.read_text(encoding="utf-8"))
    if data.get("schemaVersion") != "gauntlet.epic-copy.v1":
        raise ValueError("Unsupported Epic lifecycle copy template")
    return data


def render_lifecycle_copy(event, facts, variant="default"):
    contract = lifecycle_copy_contract()
    event_contract = contract["events"].get(event)
    if not event_contract:
        raise ValueError(f"Unknown Epic lifecycle event: {event}")
    required = event_contract.get("required", [])
    missing = [key for key in required if key not in facts]
    if missing:
        raise ValueError(f"Lifecycle event {event} is missing facts: {', '.join(missing)}")
    safe_facts = {key: str(value) for key, value in facts.items()}
    if has_secret(canonical_json(safe_facts)):
        raise ValueError("Lifecycle copy facts contain secret-like content")
    template = event_contract.get("variants", {}).get(variant) or event_contract.get("template")
    if not template:
        raise ValueError(f"Lifecycle event {event} has no {variant} template")
    return template.format_map(safe_facts).strip()


def completion_projection_for_run(repo, run_path):
    if not run_path:
        return None
    output, error = run_prd_controller(repo, ["completion", "--run", str(Path(run_path).resolve())])
    if error:
        return {"available": False, "error": error}
    try:
        data = json.loads(output)
    except json.JSONDecodeError as exc:
        return {"available": False, "error": f"completion did not emit JSON: {exc}"}
    data["available"] = True
    return data




def dependency_satisfied(epic, dependency, projections):
    projection = projections.get(dependency["epicId"])
    if not projection or projection.get("available") is not True:
        return False
    field = {"merged": "merged", "deployed": "deployed", "productionProved": "productionProved"}[dependency["boundary"]]
    return projection.get(field) is True


def launch_projections(repo, launch):
    return {
        epic_id: completion_projection_for_run(repo, epic.get("runPath"))
        for epic_id, epic in launch["epics"].items()
    }


def ready_launch_epics(launch, projections):
    target = set(launch["targetEpicIds"])
    ready = []
    for epic_id in launch["targetEpicIds"]:
        epic = launch["epics"][epic_id]
        if epic["status"] != "planned":
            continue
        target_dependencies = [item for item in epic["dependencies"] if item["epicId"] in target]
        if all(dependency_satisfied(epic, item, projections) for item in target_dependencies):
            ready.append(epic_id)
    return ready


def launch_path_reference(path, repo):
    path = Path(path).resolve()
    try:
        return path.relative_to(Path(repo).resolve()).as_posix()
    except ValueError:
        return str(path)


def epic_task_packet(launch_path, launch, epic_id, repo):
    epic = launch["epics"][epic_id]
    dependency_outputs = []
    projections = launch_projections(repo, launch)
    for dependency in epic["dependencies"]:
        if dependency["epicId"] in projections and projections[dependency["epicId"]]:
            projection = projections[dependency["epicId"]]
            dependency_outputs.append({
                "epicId": dependency["epicId"],
                "boundary": dependency["boundary"],
                "exactRevision": projection.get("exactRevision"),
            })
    source_reference = launch_path_reference(launch["source"]["snapshotPath"], repo)
    launch_reference = launch_path_reference(launch_path, repo)
    task_key = launch_task_key(launch, epic_id)
    bootstrap_argv = [
        "python3", str(Path(__file__).resolve()), "epic-tasks", "bootstrap",
        "-l", launch_reference, "-e", epic_id, "-t", task_key,
        "--json",
    ]
    packet = {
        "schemaVersion": "gauntlet.epic-task.v2",
        "mode": "single-epic-non-recursive",
        "epicId": epic_id,
        "epicTitle": epic["title"],
        "sourceReference": source_reference,
        "sourceSha256": launch["source"]["sha256"],
        "coverageSha256": launch["coverageSha256"],
        "launchSet": launch_reference,
        "taskKey": task_key,
        "dependencyOutputs": dependency_outputs,
        "bootstrap": {
            "instruction": "Run argv once in task cwd before run creation; use epicSection; stop on failure.",
            "argv": bootstrap_argv,
        },
    }
    opening = render_lifecycle_copy("epic_start", {
        "epic_id": epic_id,
        "epic_title": epic["title"],
        "dependency_note": "Its declared implementation dependencies are satisfied." if epic["dependencies"] else "It has no implementation dependencies.",
    })
    message = "\n".join([
        opening,
        "",
        "<gauntlet_epic_task>",
        canonical_json(packet),
        "</gauntlet_epic_task>",
    ])
    if has_secret(message):
        raise ValueError(f"Epic task packet for {epic_id} contains secret-like content")
    return message


def resolve_epic_bootstrap(launch_path, epic_id, task_key, source_sha256=None, coverage_sha256=None):
    launch_path, launch = load_launch_set(launch_path)
    if coverage_sha256 is not None and coverage_sha256 != launch["coverageSha256"]:
        raise ValueError("Epic bootstrap coverage digest does not match the launch set")
    if source_sha256 is not None and source_sha256 != launch["source"]["sha256"]:
        raise ValueError("Epic bootstrap source digest does not match the launch set")
    if epic_id not in launch["epics"] or task_key != launch_task_key(launch, epic_id):
        raise ValueError("Epic bootstrap task key does not match the launch set")

    source_text = launch_source_text(launch)
    snapshot_path = Path(launch["source"]["snapshotPath"]).resolve()
    sections = epic_source_sections(source_text)
    section = sections[epic_id]["text"] if sections else source_text.rstrip() + "\n"
    if has_secret(section):
        raise ValueError(f"Epic bootstrap for {epic_id} contains secret-like content")
    return {
        "schemaVersion": "gauntlet.epic-bootstrap.v1",
        "status": "pass",
        "launchSet": str(launch_path),
        "epicId": epic_id,
        "taskKey": task_key,
        "sourceSnapshot": str(snapshot_path),
        "sourceSha256": launch["source"]["sha256"],
        "coverageSha256": launch["coverageSha256"],
        "epicSectionSha256": sha256_bytes(section.encode("utf-8")),
        "epicSection": section,
        "findings": [],
    }


def command_epic_tasks_bootstrap(args):
    try:
        payload = resolve_epic_bootstrap(
            args.launch_set, args.epic, args.task_key,
            args.source_sha256, args.coverage_sha256,
        )
    except (OSError, ValueError, KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        payload = {
            "schemaVersion": "gauntlet.epic-bootstrap.v1",
            "status": "fail",
            "findings": [{"code": "epic_bootstrap_failed", "severity": "fail", "message": str(exc)}],
        }
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def launch_state(launch, projections):
    states = [epic["status"] for epic in launch["epics"].values()]
    if any(state == "needs-decision" for state in states):
        return "needs-decision"
    if any(state == "failed" for state in states):
        return "failed"
    if all(state in {"implementation-complete", "stopped"} for state in states):
        complete = True
        for epic_id, epic in launch["epics"].items():
            if epic["status"] == "stopped":
                continue
            projection = projections.get(epic_id) or {}
            if projection.get("complete") is not True:
                complete = False
        return "release-complete" if complete else "implementation-complete"
    if any(state in {"starting", "in-progress", "implementation-complete"} for state in states):
        return "running"
    return "planned"


def epic_launch_payload(launch_path, launch, repo, **extra):
    projections = launch_projections(repo, launch)
    return {
        "schemaVersion": EPIC_LAUNCH_SCHEMA,
        "status": "pass",
        "launchSet": str(Path(launch_path).resolve()),
        "launchState": launch_state(launch, projections),
        "targetCount": len(launch["targetEpicIds"]),
        "epics": launch["epics"],
        "projections": projections,
        "findings": [],
        **extra,
    }


def command_epic_tasks_init(args):
    payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "pass", "findings": [], "actions": []}
    try:
        launch, source_text = build_epic_launch_set(args.source, args.target, priority=args.priority)
        launch_path = Path(args.launch_set).resolve()
        snapshot_path = launch_path.with_name(launch_path.stem + ".source.md")
        if launch_path.exists() or snapshot_path.exists():
            raise ValueError("Epic launch initialization refuses to overwrite an existing launch set or snapshot")
        launch["source"]["snapshotPath"] = str(snapshot_path)
        try:
            atomic_write_text(snapshot_path, source_text)
            write_launch_set(launch_path, launch)
        except Exception:
            if launch_path.exists():
                launch_path.unlink()
            if snapshot_path.exists():
                snapshot_path.unlink()
            raise
        payload.update(epic_launch_payload(launch_path, launch, args.git_root))
        payload["productTaskTitle"] = product_task_title(args.priority, launch["targetEpicIds"][0].split("-", 1)[0])
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        add_finding(payload, "epic_launch_init_failed", "fail", str(exc))
        payload["status"] = status_for(payload)
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_epic_tasks_plan(args):
    try:
        launch_path, launch = load_launch_set(args.launch_set)
        projections = launch_projections(args.git_root, launch)
        ready = ready_launch_epics(launch, projections)
        actions = []
        for epic_id in ready:
            epic = launch["epics"][epic_id]
            epic["status"] = "starting"
            actions.append({
                "type": "create_thread",
                "taskKey": launch_task_key(launch, epic_id),
                "title": epic_task_title("p1", epic_id, epic["title"]),
                "cwd": str(Path(args.git_root).resolve()),
                "message": epic_task_packet(launch_path, launch, epic_id, args.git_root),
            })
        if ready:
            write_launch_set(launch_path, launch)
        reconcile = [
            {"epicId": epic_id, "taskKey": launch_task_key(launch, epic_id)}
            for epic_id, epic in launch["epics"].items()
            if epic["status"] == "starting" and not epic["taskId"] and epic_id not in ready
        ]
        payload = epic_launch_payload(launch_path, launch, args.git_root, actions=actions, reconcileRequired=reconcile)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "fail", "findings": [{"code": "epic_launch_plan_failed", "severity": "fail", "message": str(exc)}], "actions": []}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def maybe_aggregate_start_event(launch):
    if "aggregate_start" in launch["aggregateEmittedEvents"]:
        return None
    started = sum(1 for epic in launch["epics"].values() if epic["taskId"])
    if not started or any(epic["status"] == "starting" and not epic["taskId"] for epic in launch["epics"].values()):
        return None
    queued = sum(1 for epic in launch["epics"].values() if epic["status"] == "planned")
    launch["aggregateEmittedEvents"].append("aggregate_start")
    return {
        "event": "aggregate_start",
        "copy": render_lifecycle_copy("aggregate_start", {
            "target_count": len(launch["targetEpicIds"]),
            "started_count": started,
            "queued_count": queued,
        }, variant="break"),
    }


def command_epic_tasks_record_task(args):
    try:
        launch_path, launch = load_launch_set(args.launch_set)
        epic = launch["epics"].get(args.epic)
        if not epic:
            raise ValueError(f"Epic is not in the launch set: {args.epic}")
        if launch_task_key(launch, args.epic) != args.task_key:
            raise ValueError("Epic task key does not match the launch set")
        if epic["taskId"] and epic["taskId"] != args.task_id:
            raise ValueError(f"{args.epic} is already mapped to a different task ID")
        if not epic["taskId"] and epic["status"] != "starting":
            raise ValueError("A new Epic task can be recorded only from the starting state")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,255}", args.task_id):
            raise ValueError("Task ID has an invalid format")
        events = []
        if not epic["taskId"]:
            epic["taskId"] = args.task_id
            epic["status"] = "in-progress"
            if "epic_start" not in epic["emittedEvents"]:
                epic["emittedEvents"].append("epic_start")
                events.append({"event": "epic_start", "epicId": args.epic, "copy": render_lifecycle_copy("epic_start", {
                    "epic_id": args.epic,
                    "epic_title": epic["title"],
                    "dependency_note": "Its declared implementation dependencies are satisfied." if epic["dependencies"] else "It has no implementation dependencies.",
                })})
        aggregate = maybe_aggregate_start_event(launch)
        if aggregate:
            events.append(aggregate)
        write_launch_set(launch_path, launch)
        dashboard = safely_ensure_progress_supervisor(launch_path, launch, args.git_root)
        action = progress_browser_action(launch, args.epic, dashboard) if dashboard.get("started") else None
        payload = epic_launch_payload(
            launch_path, launch, args.git_root,
            lifecycleEvents=events,
            actions=[action] if action else [],
            progressDashboard=dashboard,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "fail", "findings": [{"code": "epic_task_record_failed", "severity": "fail", "message": str(exc)}], "lifecycleEvents": [], "actions": []}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_epic_tasks_release_start(args):
    try:
        launch_path, launch = load_launch_set(args.launch_set)
        epic = launch["epics"].get(args.epic)
        if not epic or launch_task_key(launch, args.epic) != args.task_key:
            raise ValueError("Epic task key does not match the launch set")
        if epic["taskId"]:
            raise ValueError("A recorded Epic task cannot be released for recreation")
        if epic["status"] != "starting":
            raise ValueError("Only an ambiguous starting action can be released")
        index_path = Path(args.native_index).resolve()
        native_index = json.loads(index_path.read_text(encoding="utf-8"))
        if not isinstance(native_index, dict) or set(native_index) != {"schemaVersion", "query", "threads", "unavailableHosts"}:
            raise ValueError("Native task index has an unsupported shape")
        if native_index.get("schemaVersion") != 2 or native_index.get("query") != args.task_key:
            raise ValueError("Native task index must be the exact Codex task-key query")
        if native_index.get("threads") != [] or native_index.get("unavailableHosts") != []:
            raise ValueError("Native task index does not prove this task key is absent on every available host")
        if has_secret(canonical_json(native_index)):
            raise ValueError("Native task index contains unsafe content")
        epic["startReconciliation"] = {
            "adapter": "codex-app-list-threads-v2",
            "nativeIndexSha256": sha256_bytes(canonical_json(native_index).encode("utf-8")),
            "result": "absent",
        }
        epic["status"] = "planned"
        write_launch_set(launch_path, launch)
        payload = epic_launch_payload(launch_path, launch, args.git_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "fail", "findings": [{"code": "epic_task_release_failed", "severity": "fail", "message": str(exc)}]}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_epic_tasks_record_run(args):
    try:
        launch_path, launch = load_launch_set(args.launch_set)
        epic = launch["epics"].get(args.epic)
        if not epic or not epic["taskId"]:
            raise ValueError("Record the Epic task before its Execution Run")
        run_path = Path(args.run).resolve()
        source_lock_path = run_path / "source-lock.json"
        if not source_lock_path.is_file():
            raise ValueError(f"Execution Run lacks source-lock.json: {run_path}")
        source_lock = json.loads(source_lock_path.read_text(encoding="utf-8"))
        locked_epics = source_lock.get("target_epic_ids") or source_lock.get("target_epics") or source_lock.get("targetEpicIds") or []
        if isinstance(locked_epics, dict):
            locked_epics = list(locked_epics)
        if locked_epics != [args.epic]:
            raise ValueError("Execution Run must lock exactly the recorded Epic")
        if set(source_lock.get("epics") or {}) != {args.epic}:
            raise ValueError("Execution Run source-lock Epic facts must match the recorded Epic exactly")
        locked_launch = source_lock.get("launch_set") or {}
        if Path(locked_launch.get("path", "")).resolve() != launch_path:
            raise ValueError("Execution Run is bound to a different Epic launch set")
        if locked_launch.get("coverage_sha256") != launch["coverageSha256"] or locked_launch.get("task_id") != epic["taskId"]:
            raise ValueError("Execution Run launch coverage or native task identity does not match")
        if epic["runPath"] and Path(epic["runPath"]).resolve() != run_path:
            raise ValueError("Epic is already mapped to a different Execution Run")
        epic["runPath"] = str(run_path)
        write_launch_set(launch_path, launch)
        dashboard = safely_ensure_progress_supervisor(launch_path, launch, args.git_root)
        action = progress_browser_action(launch, args.epic, dashboard) if dashboard.get("started") else None
        payload = epic_launch_payload(
            launch_path, launch, args.git_root,
            actions=[action] if action else [],
            progressDashboard=dashboard,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "fail", "findings": [{"code": "epic_run_record_failed", "severity": "fail", "message": str(exc)}], "actions": []}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_epic_tasks_status(args):
    try:
        launch_path, launch = load_launch_set(args.launch_set)
        payload = epic_launch_payload(
            launch_path, launch, args.git_root,
            progressDashboard=safely_progress_dashboard_status(launch_path),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "fail", "findings": [{"code": "epic_launch_status_failed", "severity": "fail", "message": str(exc)}]}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_epic_tasks_blocker(args):
    try:
        launch_path, launch = load_launch_set(args.launch_set)
        epic = launch["epics"].get(args.epic)
        if not epic:
            raise ValueError(f"Epic is not in the launch set: {args.epic}")
        if not epic.get("taskId") or epic["status"] not in {"in-progress", "needs-decision"}:
            raise ValueError("Only a started Epic task can report a blocker")
        blocker = json.loads(Path(args.blocker).read_text(encoding="utf-8"))
        allowed = {"classification", "decision", "recommendation", "reason", "impact", "authorityNotGranted", "question"}
        if set(blocker) - allowed or "classification" not in blocker:
            raise ValueError("Blocker contains unknown fields or lacks classification")
        if blocker["classification"] not in {"recoverable", "needs-parent", "requires-user", "terminal"}:
            raise ValueError("Unknown blocker classification")
        if blocker["classification"] == "requires-user":
            required = allowed
        elif blocker["classification"] == "terminal":
            required = {"classification", "reason"}
        else:
            required = {"classification", "reason"}
        missing = required - set(blocker)
        if missing:
            raise ValueError("Blocker is missing required fields: " + ", ".join(sorted(missing)))
        if has_secret(canonical_json(blocker)):
            raise ValueError("Blocker contains secret-like content")
        events = []
        epic["blocker"] = blocker
        if blocker["classification"] == "requires-user":
            epic["status"] = "needs-decision"
            digest = "material_blocker:" + sha256_bytes(canonical_json(blocker).encode("utf-8"))[:16]
            if digest not in epic["emittedEvents"]:
                epic["emittedEvents"].append(digest)
                continuing = sum(
                    1 for other_id, other in launch["epics"].items()
                    if other_id != args.epic and other["status"] in {"starting", "in-progress", "implementation-complete"}
                )
                events.append({"event": "material_blocker", "epicId": args.epic, "copy": render_lifecycle_copy("material_blocker", {
                    "epic_id": args.epic,
                    "decision": blocker["decision"],
                    "recommendation": blocker["recommendation"],
                    "reason": blocker["reason"],
                    "impact": blocker["impact"],
                    "authority_not_granted": blocker["authorityNotGranted"],
                    "other_epics_continuing": continuing,
                    "question": blocker["question"],
                })})
        elif blocker["classification"] == "terminal":
            epic["status"] = "failed"
        write_launch_set(launch_path, launch)
        payload = epic_launch_payload(launch_path, launch, args.git_root, lifecycleEvents=events)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "fail", "findings": [{"code": "epic_blocker_record_failed", "severity": "fail", "message": str(exc)}], "lifecycleEvents": []}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_epic_tasks_resolve_blocker(args):
    try:
        launch_path, launch = load_launch_set(args.launch_set)
        epic = launch["epics"].get(args.epic)
        if not epic or epic["status"] != "needs-decision" or not epic["blocker"]:
            raise ValueError("Epic has no user decision awaiting resolution")
        if args.disposition == "continue":
            epic["status"] = "in-progress"
            epic["blocker"] = None
        else:
            if not args.reason:
                raise ValueError("Stopping an Epic requires an accepted disposition reason")
            if has_secret(args.reason):
                raise ValueError("Stop disposition contains secret-like content")
            epic["status"] = "stopped"
            epic["stopDisposition"] = args.reason
            epic["blocker"] = None
        write_launch_set(launch_path, launch)
        payload = epic_launch_payload(launch_path, launch, args.git_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "fail", "findings": [{"code": "epic_blocker_resolution_failed", "severity": "fail", "message": str(exc)}]}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def pending_gate_text(projection):
    gates = projection.get("pendingGates") or []
    if not gates:
        return "no applicable release gates"
    labels = []
    for gate in gates:
        if isinstance(gate, dict):
            labels.append(str(gate.get("stage") or gate.get("id") or "an unnamed gate"))
        else:
            labels.append(str(gate))
    return ", ".join(labels)


def gap_review_text(projection):
    review = projection.get("gapReview") or {}
    dispositions = review.get("dispositions") or {}
    parts = []
    for label in ("ask-user", "deferred", "omitted"):
        values = dispositions.get(label) or []
        if values:
            parts.append(f"{label}: {', '.join(values)}")
    candidate_ids = [item.get("id") for item in review.get("candidates", []) if item.get("id")]
    if candidate_ids:
        parts.append("guidance gaps: " + ", ".join(candidate_ids))
    return "; ".join(parts) if parts else "none"


def maybe_finish_events(launch, projections):
    events = []
    for epic_id in launch["targetEpicIds"]:
        epic = launch["epics"][epic_id]
        projection = projections.get(epic_id) or {}
        if epic["status"] != "stopped" and projection.get("available") is True and projection.get("implemented") is True:
            epic["status"] = "implementation-complete"
            if "epic_finish" not in epic["emittedEvents"]:
                epic["emittedEvents"].append("epic_finish")
                remaining = sum(
                    1 for other_id, other in launch["epics"].items()
                    if other_id != epic_id and other["status"] not in {"implementation-complete", "stopped"}
                )
                events.append({"event": "epic_finish", "epicId": epic_id, "copy": render_lifecycle_copy("epic_finish", {
                    "epic_id": epic_id,
                    "epic_title": epic["title"],
                    "exact_revision": projection.get("exactRevision") or "an unavailable revision",
                    "verification_summary": projection.get("verificationSummary") or "final Epic verification passed",
                    "pending_release_gates": pending_gate_text(projection),
                    "gap_summary": gap_review_text(projection),
                    "remaining_count": remaining,
                })})
    finished = all(epic["status"] in {"implementation-complete", "stopped"} for epic in launch["epics"].values())
    if finished and "aggregate_finish" not in launch["aggregateEmittedEvents"]:
        launch["aggregateEmittedEvents"].append("aggregate_finish")
        stopped = [f"{epic_id} ({epic['stopDisposition']})" for epic_id, epic in launch["epics"].items() if epic["status"] == "stopped"]
        implemented = sum(1 for epic in launch["epics"].values() if epic["status"] == "implementation-complete")
        release_states = []
        pending = []
        gaps = []
        for epic_id, projection in projections.items():
            if not projection or projection.get("available") is not True:
                continue
            release_states.append(
                f"{epic_id}: implemented={str(bool(projection.get('implemented'))).lower()}, "
                f"merged={str(bool(projection.get('merged'))).lower()}, deployed={str(bool(projection.get('deployed'))).lower()}, "
                f"production-proved={str(bool(projection.get('productionProved'))).lower()}"
            )
            if projection.get("pendingGates"):
                pending.append(f"{epic_id}: {pending_gate_text(projection)}")
            summary = gap_review_text(projection)
            if summary != "none":
                gaps.append(f"{epic_id}: {summary}")
        if stopped:
            copy = (
                f"Implementation has reached its accepted stopping point for all {len(launch['targetEpicIds'])} targeted Epics. "
                f"{implemented} are implementation-complete; stopped with an accepted disposition: {', '.join(stopped)}. "
                f"Release state: {'; '.join(release_states) or 'unavailable'}. {'Pending gates: ' + '; '.join(pending) + '.' if pending else ''}"
            ).strip()
        else:
            copy = render_lifecycle_copy("aggregate_finish", {
                "implemented_count": implemented,
                "exact_release_state": "; ".join(release_states) or "unavailable",
                "pending_gates": ("Pending gates: " + "; ".join(pending) + ".") if pending else "No applicable gates remain.",
                "gap_summary": "; ".join(gaps) if gaps else "none",
            })
        events.append({"event": "aggregate_finish", "copy": copy})
    return events


def command_epic_tasks_reconcile(args):
    try:
        launch_path, launch = load_launch_set(args.launch_set)
        projections = launch_projections(args.git_root, launch)
        events = maybe_finish_events(launch, projections)
        ready = ready_launch_epics(launch, projections)
        actions = []
        for epic_id in ready:
            epic = launch["epics"][epic_id]
            epic["status"] = "starting"
            actions.append({
                "type": "create_thread",
                "taskKey": launch_task_key(launch, epic_id),
                "title": epic_task_title("p1", epic_id, epic["title"]),
                "cwd": str(Path(args.git_root).resolve()),
                "message": epic_task_packet(launch_path, launch, epic_id, args.git_root),
            })
        write_launch_set(launch_path, launch)
        projections = launch_projections(args.git_root, launch)
        if any(epic.get("runPath") for epic in launch["epics"].values()):
            dashboard = safely_ensure_progress_supervisor(launch_path, launch, args.git_root)
            if dashboard.get("started"):
                action = progress_browser_action(launch, None, dashboard)
                if action:
                    actions.append(action)
        else:
            dashboard = safely_progress_dashboard_status(launch_path)
        payload = epic_launch_payload(
            launch_path, launch, args.git_root,
            lifecycleEvents=events, actions=actions, progressDashboard=dashboard,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "fail", "findings": [{"code": "epic_launch_reconcile_failed", "severity": "fail", "message": str(exc)}], "lifecycleEvents": [], "actions": []}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def replace_epic_metadata(source_text, epic_id, updates):
    sections = epic_source_sections(source_text)
    if epic_id not in sections:
        raise ValueError(f"Canonical PRD no longer contains {epic_id}")
    section = sections[epic_id]["text"]
    updated = section
    heading_end = updated.find("\n") + 1
    for field, value in updates.items():
        pattern = re.compile(rf"^{re.escape(field)}:\s*.*$", re.MULTILINE | re.IGNORECASE)
        replacement = f"{field}: {value}"
        if pattern.search(updated):
            updated = pattern.sub(replacement, updated, count=1)
        else:
            updated = updated[:heading_end] + "\n" + replacement + updated[heading_end:]
            heading_end += len(replacement) + 1
    start = source_text.index(section)
    return source_text[:start] + updated + source_text[start + len(section):]


def epic_acceptance_identity(source_text, epic_id):
    sections = epic_source_sections(source_text)
    if epic_id not in sections:
        raise ValueError(f"Canonical PRD no longer contains {epic_id}")
    controller_fields = {"epic status", "implemented by", "verified by"}
    lines = []
    for line in sections[epic_id]["text"].splitlines():
        match = re.match(r"^([A-Za-z][A-Za-z ]+):\s*.*$", line)
        if match and match.group(1).strip().lower() in controller_fields:
            continue
        lines.append(line.rstrip())
    return sha256_bytes(("\n".join(lines).strip() + "\n").encode("utf-8"))


def index_epic_cells(index_text, epic_id):
    for line in index_text.splitlines():
        if re.match(rf"^\|\s*`{re.escape(epic_id)}`\s*\|", line):
            cells = [cell.strip() for cell in line.split("|")]
            if len(cells) < 11:
                raise ValueError(f"Index row for {epic_id} has an unexpected shape")
            return {"status": cells[4], "implementation": cells[8], "verification": cells[9]}
    raise ValueError(f"Local document index has no row for {epic_id}")


def placeholder_index_value(value, kind):
    lowered = value.lower()
    markers = {
        "implementation": ("not started", "not implemented", "not authorized", "build-ready"),
        "verification": ("not verified", "not authorized", "build-ready"),
    }
    return any(marker in lowered for marker in markers[kind])


def update_epic_index(index_text, epic_id, status, implementation, verification):
    lines = index_text.splitlines()
    found = False
    for index, line in enumerate(lines):
        if not re.match(rf"^\|\s*`{re.escape(epic_id)}`\s*\|", line):
            continue
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) < 11:
            raise ValueError(f"Index row for {epic_id} has an unexpected shape")
        cells[4] = status
        cells[8] = implementation
        cells[9] = verification
        lines[index] = "| " + " | ".join(cells[1:-1]) + " |"
        found = True
        break
    if not found:
        raise ValueError(f"Local document index has no row for {epic_id}")
    return "\n".join(lines) + ("\n" if index_text.endswith("\n") else "")


def command_epic_tasks_reconcile_docs(args):
    try:
        launch_path, launch = load_launch_set(args.launch_set)
        epic = launch["epics"].get(args.epic)
        if not epic or not epic.get("runPath"):
            raise ValueError("Epic has no recorded Execution Run")
        projection = completion_projection_for_run(args.git_root, epic["runPath"])
        if not projection or projection.get("available") is not True or projection.get("implemented") is not True:
            raise ValueError("Canonical documents require an implemented completion projection")
        if projection.get("sourceSha256") != launch["source"]["sha256"]:
            raise ValueError("Completion projection does not match the launch-set source lock")
        primary = primary_worktree(args.git_root)
        source_path = Path(launch["source"]["path"]).resolve()
        try:
            source_path.relative_to(primary)
        except ValueError as exc:
            raise ValueError("Canonical PRD is not in the primary worktree") from exc
        index_path = primary / "local-docs" / "INDEX.md"
        exact_revision = projection.get("exactRevision") or "revision unavailable"
        final_status = "Complete" if projection.get("complete") is True else "Implementation-complete"
        source_before = source_path.read_text(encoding="utf-8")
        index_before = index_path.read_text(encoding="utf-8")
        locked_source = launch_source_text(launch)
        if epic_acceptance_identity(source_before, args.epic) != epic_acceptance_identity(locked_source, args.epic):
            raise ValueError("Canonical Epic acceptance changed after launch; start a new run for the revised source")
        existing_cells = index_epic_cells(index_before, args.epic)
        desired_implementation = f"Execution Run `{Path(epic['runPath']).name}` at `{exact_revision}`"
        desired_verification = f"Final Epic verification passed on `{exact_revision}`"
        if existing_cells["status"] not in {"Accepted", final_status}:
            raise ValueError("Canonical index status conflicts with the launch and completion projection")
        if existing_cells["implementation"] != desired_implementation and not placeholder_index_value(existing_cells["implementation"], "implementation"):
            raise ValueError("Canonical index implementation cell conflicts with the completion projection")
        if existing_cells["verification"] != desired_verification and not placeholder_index_value(existing_cells["verification"], "verification"):
            raise ValueError("Canonical index verification cell conflicts with the completion projection")
        source_after = replace_epic_metadata(source_before, args.epic, {
            "Epic status": final_status,
            "Implemented by": f"Execution Run {Path(epic['runPath']).name} at `{exact_revision}`",
            "Verified by": f"Final Epic verification on `{exact_revision}`",
        })
        index_after = update_epic_index(
            index_before, args.epic, final_status,
            desired_implementation,
            desired_verification,
        )
        if source_after != source_before:
            atomic_write_text(source_path, source_after)
        if index_after != index_before:
            atomic_write_text(index_path, index_after)
        payload = epic_launch_payload(
            launch_path, launch, args.git_root,
            reconciled={"epicId": args.epic, "prd": str(source_path), "index": str(index_path), "changed": source_after != source_before or index_after != index_before},
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "fail", "findings": [{"code": "canonical_epic_reconcile_failed", "severity": "fail", "message": str(exc)}]}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]
























def command_epic_tasks_merge_lease_acquire(args):
    try:
        launch_path, launch = load_launch_set(args.launch_set)
        epic = launch["epics"].get(args.epic)
        if not epic or not epic.get("runPath"):
            raise ValueError("Epic has no recorded Execution Run")
        projection = completion_projection_for_run(args.git_root, epic["runPath"])
        if not projection or projection.get("available") is not True or projection.get("implemented") is not True:
            raise ValueError("Merge lease requires an implemented completion projection")
        if projection.get("exactRevision") != args.candidate_head:
            raise ValueError("Candidate head differs from the final Epic verification revision")
        default_head, default_ref = current_default_head(args.git_root)
        if default_head != args.verified_base:
            raise ValueError(f"Default branch advanced from {args.verified_base} to {default_head}; re-integrate and reverify before merging")
        if git(["merge-base", "--is-ancestor", default_head, args.candidate_head], args.git_root).returncode != 0:
            raise ValueError("Candidate does not contain the verified default-branch base; re-integrate and reverify before merging")
        lease_path = launch_merge_lease_path(launch_path)
        lease = {
            "schemaVersion": "gauntlet.epic-merge-lease.v1",
            "coverageSha256": launch["coverageSha256"],
            "epicId": args.epic,
            "candidateHead": args.candidate_head,
            "baseHead": args.verified_base,
            "baseRef": default_ref,
        }
        persist_merge_lease(args.git_root, lease_path, lease, default_head)
        payload = epic_launch_payload(launch_path, launch, args.git_root, mergeLease=lease)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "fail", "findings": [{"code": "epic_merge_lease_failed", "severity": "fail", "message": str(exc)}]}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_epic_tasks_merge_lease_release(args):
    try:
        launch_path, launch = load_launch_set(args.launch_set)
        lease_path = launch_merge_lease_path(launch_path)
        if not lease_path.is_file():
            raise ValueError("No Epic merge lease exists")
        lease = json.loads(lease_path.read_text(encoding="utf-8"))
        if lease.get("epicId") != args.epic or lease.get("candidateHead") != args.candidate_head:
            raise ValueError("Merge lease does not match the releasing Epic and candidate")
        default_head, _ = refresh_default_head(args.git_root)
        if git(["merge-base", "--is-ancestor", args.merged_head, default_head], args.git_root).returncode != 0:
            raise ValueError("Currently observed default branch does not contain the recorded merged head")
        if not default_represents_candidate(args.git_root, args.candidate_head, args.merged_head):
            raise ValueError("Merged revision does not contain the leased candidate head")
        lease_path.unlink()
        payload = epic_launch_payload(launch_path, launch, args.git_root, releasedMergeLease={"epicId": args.epic, "mergedHead": args.merged_head})
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "fail", "findings": [{"code": "epic_merge_lease_release_failed", "severity": "fail", "message": str(exc)}]}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]






















def add_finding(payload, code, severity, message, **details):
    _add_finding(payload.setdefault("findings", []), code, severity, message, **details)


def status_for(payload):
    return _status_for(payload.get("findings", []))




























def run_prd_controller(repo, arguments):
    controller = prd_controller_path()
    if not controller.is_file():
        return None, f"Execution Run controller does not exist: {controller}"
    result = run_cmd([sys.executable, str(controller), *arguments], cwd=repo)
    if result.returncode != 0:
        return None, result.stderr.strip() or result.stdout.strip() or "prd-run command failed"
    return result.stdout, None


def prd_controller_path():
    override = os.environ.get("GAUNTLET_DEV_PRD_CONTROLLER")
    if override:
        if os.environ.get("GAUNTLET_ALLOW_DEV_CONTROLLER") != "1":
            return Path("/__gauntlet_untrusted_controller_override_rejected__")
        return Path(override).resolve()
    return SCRIPTS / "prd-run.py"


def run_authority_granted(repo, run_path, capability):
    output, error = run_prd_controller(repo, [
        "authority-status", "--run", str(Path(run_path).resolve()), "--capability", capability,
    ])
    if error:
        return False, error
    try:
        status = json.loads(output)
    except json.JSONDecodeError as exc:
        return False, f"authority-status did not emit JSON: {exc}"
    if status.get("capability") != capability or status.get("granted") is not True:
        return False, f"Execution Run has not granted {capability} authority"
    return True, None












































































def print_payload(payload, as_json):
    if as_json:
        print(json.dumps(payload, indent=2))
        return
    summary = payload.get("archiveSummary") or {}
    bullets = summary.get("bullets") or []
    if bullets:
        print("Archive Summary")
        for bullet in bullets:
            print(f"- {bullet}")
        if payload["status"] in {"pass", "warn"}:
            return
        print()
    print(f"Gauntlet: {payload['status']}")
    for finding in payload.get("findings", []):
        print(f"- [{finding['severity']}] {finding['code']}: {finding['message']}")
    for action in payload.get("archivePlan", {}).get("actions", []):
        print(f"- action: {action.get('type')}")
















def command_diagram_find(args):
    index = ROOT / "docs" / "gauntlet-diagrams" / "index.md"
    matches = []
    if index.exists():
        for line in index.read_text(encoding="utf-8").splitlines():
            if not line.startswith("| `"):
                continue
            if args.query.lower() in line.lower():
                cells = [cell.strip() for cell in line.strip("|").split("|")]
                if len(cells) >= 5:
                    matches.append({
                        "id": cells[0].strip("`"),
                        "title": cells[1],
                        "feature": cells[2].strip("`"),
                        "tags": [tag.strip().strip("`") for tag in cells[3].split(",")],
                        "path": cells[4].strip("`"),
                    })
    payload = {"schemaVersion": "1.0", "status": "pass", "matches": matches}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for match in matches:
            print(f"{match['id']}: {match['path']}")
    return 0


def command_install_verify(args):
    agent_home = Path(args.agent_home).expanduser()
    if not agent_home.is_absolute():
        agent_home = (Path.cwd() / agent_home).absolute()
    findings = []
    def require(path, code):
        if not path.exists():
            findings.append({"code": code, "severity": "fail", "message": f"Missing {path}"})

    require(agent_home / "gauntlet" / "AGENTS.md", "missing_installed_agents")
    require(agent_home / "gauntlet" / "router" / "AGENTS.md", "missing_router_source")
    require(agent_home / "gauntlet" / "router" / "response-style.md", "missing_response_style_source")
    require(agent_home / "gauntlet" / "scripts" / "check-gauntlet-workflow.py", "missing_installed_workflow_check")
    require(agent_home / "gauntlet" / "scripts" / "gauntlet.py", "missing_installed_gauntlet_cli")
    require(agent_home / "gauntlet" / "scripts" / "progress-dashboard.py", "missing_progress_dashboard")
    require(agent_home / "gauntlet" / "scripts" / "progress_projection.py", "missing_progress_projection")
    require(agent_home / "gauntlet" / "scripts" / "install-codex-agents.py", "missing_custom_agent_installer")
    require(agent_home / "gauntlet" / "scripts" / "subagent-audit.py", "missing_subagent_audit_exporter")
    require(agent_home / "gauntlet" / "scripts" / "route-codex-agent.py", "missing_custom_agent_router")
    require(agent_home / "gauntlet" / "docs" / "local-documentation.md", "missing_local_documentation_policy")
    require(agent_home / "gauntlet" / "templates" / "local-docs" / "doc_org.md.tmpl", "missing_local_document_template")
    require(agent_home / "gauntlet" / "templates" / "model-api-pricing.json", "missing_model_api_pricing")
    require(agent_home / "gauntlet" / "templates" / "progress-dashboard" / "index.html", "missing_progress_dashboard_html")
    require(agent_home / "gauntlet" / "templates" / "progress-dashboard" / "assets" / "app.js", "missing_progress_dashboard_js")
    require(agent_home / "gauntlet" / "templates" / "progress-dashboard" / "assets" / "app.css", "missing_progress_dashboard_css")
    require(agent_home / "skills", "missing_installed_skills")
    installed_root = agent_home / "gauntlet"
    if (installed_root / "ui").exists() or list(installed_root.rglob("node_modules")):
        findings.append({"code": "development_ui_installed", "severity": "fail", "message": "Installed runtime must not contain ui/ or node_modules/."})

    installed_router = agent_home / "gauntlet" / "AGENTS.md"
    if installed_router.exists():
        router_text = installed_router.read_text(encoding="utf-8")
        expected_root = str(agent_home / "gauntlet")
        expected_skills = str(agent_home / "skills")
        if any(placeholder in router_text for placeholder in ["{{GAUNTLET_ROOT}}", "{{AGENT_HOME}}", "{{RESPONSE_STYLE}}"]):
            findings.append({"code": "unresolved_router_placeholder", "severity": "fail", "message": "Installed router contains an unresolved path placeholder."})
        if expected_root not in router_text:
            findings.append({"code": "missing_installed_root_path", "severity": "fail", "message": "Installed router lacks the rendered Gauntlet root."})
        if expected_skills not in router_text:
            findings.append({"code": "missing_installed_skills_path", "severity": "fail", "message": "Installed router lacks the rendered skills root."})
        if len(router_text.encode("utf-8")) >= 32768:
            findings.append({"code": "installed_router_too_large", "severity": "fail", "message": "Installed router exceeds the 32 KiB default instruction budget."})

    if args.target == "codex":
        codex_agents = agent_home / "AGENTS.md"
        require(codex_agents, "missing_codex_agents")
        if codex_agents.exists():
            text = codex_agents.read_text(encoding="utf-8")
            if text.count("BEGIN GAUNTLET MANAGED BLOCK") != 1 or text.count("END GAUNTLET MANAGED BLOCK") != 1:
                findings.append({"code": "invalid_codex_managed_block", "severity": "fail", "message": "Codex AGENTS.md must contain exactly one complete Gauntlet managed block."})
            if "Gauntlet Workflow Router" not in text:
                findings.append({"code": "missing_codex_router", "severity": "fail", "message": "Codex AGENTS.md lacks the installed Gauntlet router."})
        source = agent_home / "gauntlet" / "agents" / "codex"
        verifier = agent_home / "gauntlet" / "scripts" / "install-codex-agents.py"
        if source.is_dir() and verifier.is_file():
            result = subprocess.run(
                [sys.executable, str(verifier), "verify", "--source", str(source), "--agent-home", str(agent_home)],
                text=True, capture_output=True,
            )
            if result.returncode:
                findings.append({"code": "invalid_codex_custom_agents", "severity": "fail", "message": result.stderr.strip() or result.stdout.strip()})
    if args.target == "claude":
        claude_md = agent_home / "CLAUDE.md"
        require(claude_md, "missing_claude_md")
        if claude_md.exists():
            text = claude_md.read_text(encoding="utf-8")
            expected_import = f"@{agent_home}/gauntlet/AGENTS.md"
            if "BEGIN GAUNTLET MANAGED BLOCK" not in text:
                findings.append({"code": "missing_claude_managed_block", "severity": "fail", "message": "CLAUDE.md lacks Gauntlet managed block."})
            if expected_import not in text:
                findings.append({"code": "missing_claude_agents_import", "severity": "fail", "message": "CLAUDE.md does not import installed AGENTS.md."})

    payload = {"schemaVersion": "1.0", "status": "pass", "target": args.target, "agentHome": str(agent_home), "findings": findings}
    payload["status"] = status_for(payload)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Install verify: {payload['status']}")
        for finding in findings:
            print(f"- [{finding['severity']}] {finding['code']}: {finding['message']}")
    return EXIT_CODES[payload["status"]]




configure_closeout(
    gap_review_text=lambda projection: gap_review_text(projection),
    run_authority_granted=lambda repo, run_path, capability:
        run_authority_granted(repo, run_path, capability),
    run_prd_controller=lambda repo, arguments: run_prd_controller(
        repo, arguments
    ),
    print_payload=lambda payload, as_json: print_payload(payload, as_json),
)


configure_merge(
    load_launch_set=lambda path: load_launch_set(path),
    launch_source_text=lambda launch: launch_source_text(launch),
    prd_controller_path=lambda: prd_controller_path(),
    run_authority_granted=lambda repo, run_path, capability:
        run_authority_granted(repo, run_path, capability),
    run_prd_controller=lambda repo, arguments: run_prd_controller(
        repo, arguments
    ),
    print_payload=lambda payload, as_json: print_payload(payload, as_json),
)


configure_review_unit(
    merge_input_path=lambda repo, supplied: merge_input_path(repo, supplied),
    run_prd_controller=lambda repo, arguments: run_prd_controller(
        repo, arguments
    ),
    branch_name=lambda repo: branch_name(repo),
    current_head=lambda repo: current_head(repo),
    dirty_paths=lambda repo: dirty_paths(repo),
    checks_state=lambda checks: checks_state(checks),
    delete_remote_branch=lambda repo, branch, expected_sha=None:
        delete_remote_branch(repo, branch, expected_sha=expected_sha),
    print_payload=lambda payload, as_json: print_payload(payload, as_json),
)


def register(subcommands):
    register_archive(subcommands)

    register_merge(subcommands)

    register_review_unit(subcommands)

    register_closeout(subcommands)

    install = subcommands.add_parser("install", help="Installed-layout helpers.")
    install_subcommands = install.add_subparsers(dest="install_command", required=True)
    install_verify = install_subcommands.add_parser("verify")
    install_verify.add_argument("--target", choices=["codex", "claude"], required=True)
    install_verify.add_argument("--agent-home", required=True)
    install_verify.add_argument("--json", action="store_true")
    install_verify.set_defaults(func=command_install_verify)

    epic_tasks = subcommands.add_parser("epic-tasks", help="Plan and reconcile one visible implementation task per build-ready Epic.")
    epic_task_subcommands = epic_tasks.add_subparsers(dest="epic_tasks_command", required=True)
    epic_init = epic_task_subcommands.add_parser("init", help="Freeze one complete PRD target into an Epic launch set.")
    epic_init.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_init.add_argument("--source", type=Path, required=True)
    epic_init.add_argument("--target", action="append", default=[])
    epic_init.add_argument("--launch-set", type=Path, required=True)
    epic_init.add_argument("--priority", choices=["p0", "p1", "p2", "p3", "p4"], default="p1")
    epic_init.add_argument("--json", action="store_true")
    epic_init.set_defaults(func=command_epic_tasks_init)
    epic_plan = epic_task_subcommands.add_parser("plan", help="Emit only missing dependency-ready task actions.")
    epic_plan.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_plan.add_argument("--launch-set", type=Path, required=True)
    epic_plan.add_argument("--json", action="store_true")
    epic_plan.set_defaults(func=command_epic_tasks_plan)
    epic_bootstrap = epic_task_subcommands.add_parser("bootstrap", help="Verify and resolve one complete accepted Epic before run creation.")
    epic_bootstrap.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_bootstrap.add_argument("-l", "--launch-set", type=Path, required=True)
    epic_bootstrap.add_argument("-e", "--epic", required=True)
    epic_bootstrap.add_argument("-t", "--task-key", required=True)
    epic_bootstrap.add_argument("-s", "--source-sha256")
    epic_bootstrap.add_argument("-c", "--coverage-sha256")
    epic_bootstrap.add_argument("--json", action="store_true")
    epic_bootstrap.set_defaults(func=command_epic_tasks_bootstrap)
    epic_record_task = epic_task_subcommands.add_parser("record-task", help="Persist a proven native task ID for an Epic.")
    epic_record_task.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_record_task.add_argument("--launch-set", type=Path, required=True)
    epic_record_task.add_argument("--epic", required=True)
    epic_record_task.add_argument("--task-key", required=True)
    epic_record_task.add_argument("--task-id", required=True)
    epic_record_task.add_argument("--json", action="store_true")
    epic_record_task.set_defaults(func=command_epic_tasks_record_task)
    epic_release = epic_task_subcommands.add_parser("release-start", help="Release an ambiguous task action only after native reconciliation proves no task exists.")
    epic_release.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_release.add_argument("--launch-set", type=Path, required=True)
    epic_release.add_argument("--epic", required=True)
    epic_release.add_argument("--task-key", required=True)
    epic_release.add_argument("--native-index", type=Path, required=True)
    epic_release.add_argument("--json", action="store_true")
    epic_release.set_defaults(func=command_epic_tasks_release_start)
    epic_record_run = epic_task_subcommands.add_parser("record-run", help="Bind an Epic task to its single-Epic Execution Run.")
    epic_record_run.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_record_run.add_argument("--launch-set", type=Path, required=True)
    epic_record_run.add_argument("--epic", required=True)
    epic_record_run.add_argument("--run", type=Path, required=True)
    epic_record_run.add_argument("--json", action="store_true")
    epic_record_run.set_defaults(func=command_epic_tasks_record_run)
    epic_status = epic_task_subcommands.add_parser("status", help="Read current Epic task and completion projections without changing state.")
    epic_status.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_status.add_argument("--launch-set", type=Path, required=True)
    epic_status.add_argument("--json", action="store_true")
    epic_status.set_defaults(func=command_epic_tasks_status)
    epic_reconcile = epic_task_subcommands.add_parser("reconcile", help="Refresh completion facts, finish copy, and newly ready task actions.")
    epic_reconcile.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_reconcile.add_argument("--launch-set", type=Path, required=True)
    epic_reconcile.add_argument("--json", action="store_true")
    epic_reconcile.set_defaults(func=command_epic_tasks_reconcile)
    epic_progress_supervise = epic_task_subcommands.add_parser("progress-supervise", help=argparse.SUPPRESS)
    epic_progress_supervise.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_progress_supervise.add_argument("--launch-set", type=Path, required=True)
    epic_progress_supervise.add_argument("--interval", type=float, default=PROGRESS_REFRESH_SECONDS)
    epic_progress_supervise.set_defaults(func=command_epic_tasks_progress_supervise)
    epic_progress_stop = epic_task_subcommands.add_parser("progress-stop", help="Idempotently stop a launch-scoped progress dashboard.")
    epic_progress_stop.add_argument("--launch-set", type=Path, required=True)
    epic_progress_stop.add_argument("--json", action="store_true")
    epic_progress_stop.set_defaults(func=command_epic_tasks_progress_stop)
    epic_blocker = epic_task_subcommands.add_parser("blocker", help="Record a structured Epic blocker and emit a user question only when required.")
    epic_blocker.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_blocker.add_argument("--launch-set", type=Path, required=True)
    epic_blocker.add_argument("--epic", required=True)
    epic_blocker.add_argument("--blocker", type=Path, required=True)
    epic_blocker.add_argument("--json", action="store_true")
    epic_blocker.set_defaults(func=command_epic_tasks_blocker)
    epic_resolve = epic_task_subcommands.add_parser("resolve-blocker", help="Apply the product task's accepted blocker disposition.")
    epic_resolve.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_resolve.add_argument("--launch-set", type=Path, required=True)
    epic_resolve.add_argument("--epic", required=True)
    epic_resolve.add_argument("--disposition", choices=["continue", "stop"], required=True)
    epic_resolve.add_argument("--reason", default=None)
    epic_resolve.add_argument("--json", action="store_true")
    epic_resolve.set_defaults(func=command_epic_tasks_resolve_blocker)
    epic_docs = epic_task_subcommands.add_parser("reconcile-docs", help="Project one implemented Epic back into its canonical PRD and index.")
    epic_docs.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_docs.add_argument("--launch-set", type=Path, required=True)
    epic_docs.add_argument("--epic", required=True)
    epic_docs.add_argument("--json", action="store_true")
    epic_docs.set_defaults(func=command_epic_tasks_reconcile_docs)
    epic_lease = epic_task_subcommands.add_parser("merge-lease", help="Serialize default-branch mutation across ready Epic PRs.")
    epic_lease_subcommands = epic_lease.add_subparsers(dest="epic_merge_lease_command", required=True)
    epic_lease_acquire = epic_lease_subcommands.add_parser("acquire")
    epic_lease_acquire.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_lease_acquire.add_argument("--launch-set", type=Path, required=True)
    epic_lease_acquire.add_argument("--epic", required=True)
    epic_lease_acquire.add_argument("--candidate-head", required=True)
    epic_lease_acquire.add_argument("--verified-base", required=True)
    epic_lease_acquire.add_argument("--json", action="store_true")
    epic_lease_acquire.set_defaults(func=command_epic_tasks_merge_lease_acquire)
    epic_lease_release = epic_lease_subcommands.add_parser("release")
    epic_lease_release.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_lease_release.add_argument("--launch-set", type=Path, required=True)
    epic_lease_release.add_argument("--epic", required=True)
    epic_lease_release.add_argument("--candidate-head", required=True)
    epic_lease_release.add_argument("--merged-head", required=True)
    epic_lease_release.add_argument("--json", action="store_true")
    epic_lease_release.set_defaults(func=command_epic_tasks_merge_lease_release)

    register_docs(subcommands)

    register_followup_memory(subcommands)

    register_analytics(subcommands)

    register_changelog(subcommands)

    diagram = subcommands.add_parser("diagram", help="Saved diagram helpers.")
    diagram_subcommands = diagram.add_subparsers(dest="diagram_command", required=True)
    diagram_find = diagram_subcommands.add_parser("find")
    diagram_find.add_argument("--query", required=True)
    diagram_find.add_argument("--json", action="store_true")
    diagram_find.set_defaults(func=command_diagram_find)

def build_parser():
    return build_cli_parser(register)


def main(argv=None):
    return dispatch(build_parser(), argv, error_printer=print_payload)


if __name__ == "__main__":
    raise SystemExit(main())
