#!/usr/bin/env python3
"""Export privacy-bounded Gauntlet subagent usage from Codex native state."""

import argparse
import fcntl
import hashlib
import json
import os
import re
import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path


EXPECTED = {
    "gauntlet_fast_reader": ("gpt-5.6-luna", "medium"),
    "gauntlet_standard_worker": ("gpt-5.6-sol", "medium"),
    "gauntlet_deep_worker": ("gpt-5.6-sol", "high"),
    "gauntlet_independent_verifier": ("gpt-5.6-sol", "medium"),
    "gauntlet_release_integrator": ("gpt-5.6-terra", "high"),
    "gauntlet_deep_expert_researcher": ("gpt-5.6-sol", "xhigh"),
    "gauntlet_security_reviewer": ("gpt-5.6-sol", "high"),
}
OPAQUE_ID = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
SECRET_LIKE = re.compile(
    r"\A(?:sk-|gh[pousr]_|github_pat_|xox[a-z]-|akia|aiza|bearer-)",
    re.IGNORECASE,
)
PROMPT_LIKE = re.compile(
    r"\A(?:prompt(?:-|_)|system(?:-|_)prompt|user(?:-|_)prompt|assistant(?:-|_)prompt|ignore(?:-|_)previous)",
    re.IGNORECASE,
)
AUTHORITY_CLASS = {
    "gauntlet_fast_reader": "read-only",
    "gauntlet_independent_verifier": "read-only",
    "gauntlet_deep_expert_researcher": "read-only",
    "gauntlet_security_reviewer": "read-only",
    "gauntlet_standard_worker": "local-write",
    "gauntlet_deep_worker": "local-write",
    "gauntlet_release_integrator": "release-preparation",
}
TOKEN_KEYS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
)
NATIVE_COLUMNS = (
    "id", "agent_role", "model", "reasoning_effort", "sandbox_policy", "approval_mode",
    "agent_nickname", "source", "tokens_used", "cwd", "created_at_ms", "updated_at_ms",
    "rollout_path", "cli_version",
)


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".{}.".format(path.name), dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def fingerprint(value):
    if not value:
        return None
    return "sha256:" + hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def privacy_bounded_sandbox(value):
    """Retain the effective sandbox type without persisting private writable roots."""
    try:
        policy = json.loads(value)
    except (TypeError, ValueError):
        return value if isinstance(value, str) and "/" not in value else None
    if not isinstance(policy, dict) or not isinstance(policy.get("type"), str):
        return None
    return json.dumps({"type": policy["type"]}, separators=(",", ":"), sort_keys=True)


def native_records(database):
    if not database.is_file():
        raise RuntimeError("Codex native state database is missing: {}".format(database))
    connection = sqlite3.connect("file:{}?mode=ro".format(database), uri=True)
    connection.row_factory = sqlite3.Row
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(threads)")}
        missing = {"id", "agent_role"} - columns
        if missing:
            raise RuntimeError("Codex native state is missing required thread metadata: {}".format(", ".join(sorted(missing))))
        expressions = ["t.{} AS {}".format(name, name) if name in columns else "NULL AS {}".format(name) for name in NATIVE_COLUMNS]
        query = """
        SELECT {}, e.parent_thread_id
        FROM threads t
        LEFT JOIN thread_spawn_edges e ON e.child_thread_id = t.id
        WHERE t.agent_role GLOB 'gauntlet_*'
        ORDER BY COALESCE(t.created_at_ms, 0), t.id
        """.format(", ".join(expressions))
        rows = connection.execute(query).fetchall()
    finally:
        connection.close()
    return [
        {
            "agentId": row["id"],
            "parentAgentId": row["parent_thread_id"],
            "profile": row["agent_role"],
            "model": row["model"],
            "reasoningEffort": row["reasoning_effort"],
            "sandboxPolicy": row["sandbox_policy"],
            "approvalMode": row["approval_mode"],
            "nickname": row["agent_nickname"],
            "source": row["source"],
            "tokensUsed": row["tokens_used"],
            "cwd": row["cwd"],
            "createdAtMs": row["created_at_ms"],
            "updatedAtMs": row["updated_at_ms"],
            "rolloutPath": row["rollout_path"],
            "cliVersion": row["cli_version"],
        }
        for row in rows
    ]


def audit_record(row):
    return {
        "agentId": row["agentId"],
        "parentAgentId": row["parentAgentId"],
        "profile": row["profile"],
        "model": row["model"],
        "reasoningEffort": row["reasoningEffort"],
        "sandboxPolicy": privacy_bounded_sandbox(row["sandboxPolicy"]),
        "approvalMode": row["approvalMode"],
        "nickname": row["nickname"],
        "source": row["source"],
        "tokensUsed": row["tokensUsed"],
        # Keep the historical field name while replacing private absolute paths with an opaque value.
        "cwd": fingerprint(row["cwd"]) if row["cwd"] and not row["cwd"].startswith("sha256:") else row["cwd"],
        "createdAtMs": row["createdAtMs"],
        "updatedAtMs": row["updatedAtMs"],
    }


def existing_records(path):
    if not path.exists():
        return {}
    result = {}
    try:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            row = json.loads(line)
            agent_id = row.get("agentId")
            if not isinstance(agent_id, str) or not agent_id or agent_id in result:
                raise ValueError("invalid or duplicate agentId at line {}".format(line_number))
            if isinstance(row.get("cwd"), str) and not row["cwd"].startswith("sha256:"):
                row["cwd"] = fingerprint(row["cwd"])
            result[agent_id] = row
    except (OSError, UnicodeError, ValueError) as exc:
        raise RuntimeError("Refusing to replace unreadable existing audit log {}: {}".format(path, exc))
    return result


def valid_tokens(value):
    if not isinstance(value, dict) or set(value) != set(TOKEN_KEYS):
        return False
    if any(isinstance(value[key], bool) or not isinstance(value[key], int) or value[key] < 0 for key in TOKEN_KEYS):
        return False
    return (
        value["cached_input_tokens"] <= value["input_tokens"]
        and value["reasoning_output_tokens"] <= value["output_tokens"]
        and value["total_tokens"] == value["input_tokens"] + value["output_tokens"]
    )


def quarantine(agent_id, line_number, reason):
    return {"agentId": agent_id, "lineNumber": line_number, "reason": reason}


def request_analytics(row):
    path_value = row.get("rolloutPath")
    if not path_value:
        return None, []
    path = Path(path_value)
    if path.is_symlink() or not path.is_file():
        return None, [quarantine(row["agentId"], 0, "rollout-unavailable")]
    try:
        raw_lines = path.read_bytes().splitlines(keepends=True)
    except OSError:
        return None, [quarantine(row["agentId"], 0, "rollout-unreadable")]
    requests = []
    quarantined = []
    previous = {key: 0 for key in TOKEN_KEYS}
    for line_number, raw in enumerate(raw_lines, 1):
        if not raw.endswith((b"\n", b"\r")):
            quarantined.append(quarantine(row["agentId"], line_number, "unterminated-json-line"))
            continue
        try:
            event = json.loads(raw)
        except (UnicodeError, ValueError):
            quarantined.append(quarantine(row["agentId"], line_number, "invalid-json-line"))
            continue
        if event.get("type") != "event_msg" or not isinstance(event.get("payload"), dict):
            continue
        payload = event["payload"]
        if payload.get("type") != "token_count":
            continue
        info = payload.get("info")
        total = info.get("total_token_usage") if isinstance(info, dict) else None
        last = info.get("last_token_usage") if isinstance(info, dict) else None
        if not valid_tokens(total) or not valid_tokens(last):
            quarantined.append(quarantine(row["agentId"], line_number, "partial-token-count"))
            continue
        if any(total[key] < previous[key] for key in TOKEN_KEYS):
            quarantined.append(quarantine(row["agentId"], line_number, "nonmonotonic-cumulative-token-count"))
            continue
        delta = {key: total[key] - previous[key] for key in TOKEN_KEYS}
        if not any(delta.values()):
            continue
        if delta != last or not valid_tokens(delta):
            quarantined.append(quarantine(row["agentId"], line_number, "inconsistent-token-delta"))
            continue
        previous = total
        ordinal = len(requests) + 1
        requests.append({
            "agentId": row["agentId"],
            "codexVersion": row.get("cliVersion") or "unknown",
            "model": row.get("model"),
            "profile": row.get("profile"),
            "requestId": "{}:{}".format(row["agentId"], ordinal),
            "requestOrdinal": ordinal,
            "tokens": delta,
        })
    return requests, quarantined


def existing_analytics(path):
    if not path.exists():
        return {}
    result = {}
    try:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            row = json.loads(line)
            request_id = row.get("requestId")
            if not isinstance(request_id, str) or not request_id or request_id in result:
                raise ValueError("invalid or duplicate requestId at line {}".format(line_number))
            result[request_id] = row
    except (OSError, UnicodeError, ValueError) as exc:
        raise RuntimeError("Refusing to replace unreadable model-request analytics {}: {}".format(path, exc))
    return result


def render_jsonl(rows):
    return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)


def sync(native, output, analytics_path, quarantine_path):
    merged = existing_records(output)
    merged.update({row["agentId"]: audit_record(row) for row in native})
    ordered = sorted(merged.values(), key=lambda row: (row.get("createdAtMs") or 0, row["agentId"]))
    analytics = existing_analytics(analytics_path)
    quarantined = []
    for row in native:
        current, current_quarantine = request_analytics(row)
        quarantined.extend(current_quarantine)
        if current is None:
            continue
        analytics = {key: value for key, value in analytics.items() if value.get("agentId") != row["agentId"]}
        analytics.update({item["requestId"]: item for item in current})
    analytics_rows = sorted(analytics.values(), key=lambda row: (row["agentId"], row["requestOrdinal"]))
    quarantine_rows = sorted(quarantined, key=lambda row: (row["agentId"], row["lineNumber"], row["reason"]))
    atomic_write(output, render_jsonl(ordered))
    atomic_write(analytics_path, render_jsonl(analytics_rows))
    atomic_write(quarantine_path, render_jsonl(quarantine_rows))


def sandbox_type(row):
    try:
        policy = json.loads(row.get("sandboxPolicy"))
    except (TypeError, ValueError):
        return None
    return policy.get("type") if isinstance(policy, dict) else None


def mismatch_taxonomy(row, requested_profile, require_version=True):
    taxonomy = []
    actual_profile = row.get("profile")
    expected = EXPECTED.get(requested_profile)
    required = (actual_profile, row.get("model"), row.get("reasoningEffort"), row.get("sandboxPolicy"))
    if require_version:
        required += (row.get("cliVersion"),)
    if any(value is None or value == "" for value in required):
        taxonomy.append("missing_start_metadata")
    if actual_profile != requested_profile:
        taxonomy.append("profile_substitution")
        if AUTHORITY_CLASS.get(actual_profile) != AUTHORITY_CLASS.get(requested_profile):
            taxonomy.append("authority_substitution")
    if expected and row.get("model") != expected[0]:
        taxonomy.append("model_substitution")
    if expected and row.get("reasoningEffort") != expected[1]:
        taxonomy.append("reasoning_substitution")
    if requested_profile == "gauntlet_security_reviewer" or actual_profile == "gauntlet_security_reviewer":
        if sandbox_type(row) != "read-only":
            taxonomy.append("security_sandbox_violation")
    return sorted(set(taxonomy))


def load_circuit(path):
    if not path.exists():
        return {"schemaVersion": 1, "versions": {}}
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Refusing unsafe routing circuit state: {}".format(path))
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise RuntimeError("Cannot safely read routing circuit state {}: {}".format(path, exc))
    if state.get("schemaVersion") != 1 or not isinstance(state.get("versions"), dict):
        raise RuntimeError("Unsupported routing circuit state: {}".format(path))
    return state


@contextmanager
def circuit_lock(path):
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        os.chmod(str(lock_path), 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def reconcile(row, requested_profile, requested_risk, circuit_path):
    taxonomy = mismatch_taxonomy(row, requested_profile)
    fail_closed = bool(taxonomy) and (
        requested_risk == "consequential"
        or "security_sandbox_violation" in taxonomy
        or "authority_substitution" in taxonomy
        or "missing_start_metadata" in taxonomy
    )
    version = row.get("cliVersion") or "unknown"
    if taxonomy or requested_profile == "gauntlet_security_reviewer":
        with circuit_lock(circuit_path):
            state = load_circuit(circuit_path)
            version_state = state["versions"].setdefault(version, {"blockedProfiles": {}, "validatedAuthorities": {}})
            version_state.setdefault("blockedProfiles", {})
            version_state.setdefault("validatedAuthorities", {})
            if taxonomy:
                version_state["blockedProfiles"].setdefault(requested_profile, {
                    "firstObservedAgentId": row["agentId"],
                    "taxonomy": taxonomy,
                })
            elif requested_profile == "gauntlet_security_reviewer":
                version_state["validatedAuthorities"][requested_profile] = {
                    "agentId": row["agentId"],
                    "sandboxMode": "read-only",
                }
            atomic_write(circuit_path, json.dumps(state, indent=2, sort_keys=True) + "\n")
    return {
        "agent": audit_record(row),
        "codexVersion": version,
        "failClosed": fail_closed,
        "status": "mismatch-observed" if taxonomy else "pass",
        "taxonomy": taxonomy,
    }


def summary_payload(native, analytics_path, quarantine_path, output):
    profile_counts = {}
    for row in native:
        profile_counts[row["profile"]] = profile_counts.get(row["profile"], 0) + 1
    analytics = existing_analytics(analytics_path)
    token_totals = {key: 0 for key in TOKEN_KEYS}
    for row in analytics.values():
        for key in TOKEN_KEYS:
            token_totals[key] += row["tokens"][key]
    quarantine_count = len(quarantine_path.read_text(encoding="utf-8").splitlines()) if quarantine_path.exists() else 0
    return {
        "auditLog": str(output),
        "count": len(native),
        "modelRequests": len(analytics),
        "profiles": profile_counts,
        "quarantinedRecords": quarantine_count,
        "tokens": token_totals,
    }


def opaque_id(value, label):
    if not isinstance(value, str) or not value or len(value) > 128:
        raise RuntimeError("{} must be a bounded opaque ID".format(label))
    if SECRET_LIKE.match(value) or PROMPT_LIKE.match(value) or not OPAQUE_ID.fullmatch(value):
        raise RuntimeError("{} must be a bounded opaque ID".format(label))
    return value


def validate_owners(owners):
    if not isinstance(owners, list) or not owners:
        raise RuntimeError("Epic Run facts require a non-empty owners list")
    normalized = []
    seen_refs = set()
    for index, owner in enumerate(owners, 1):
        if not isinstance(owner, dict) or owner.get("ownerKind") not in {"parent", "delegated"}:
            raise RuntimeError("Epic Run owner {} has an invalid ownerKind".format(index))
        owner_ref = opaque_id(owner.get("ownerRef"), "Epic Run owner {} ownerRef".format(index))
        if owner_ref in seen_refs:
            raise RuntimeError("Epic Run owner {} requires a unique ownerRef".format(index))
        child_id = owner.get("nativeChildId")
        if child_id is not None:
            child_id = opaque_id(child_id, "Epic Run owner {} nativeChildId".format(index))
        requested_profile = owner.get("requestedProfile")
        if requested_profile is not None and (
            not isinstance(requested_profile, str) or requested_profile not in EXPECTED
        ):
            raise RuntimeError("Epic Run owner {} requestedProfile is not canonical".format(index))
        seen_refs.add(owner_ref)
        normalized.append({
            "ownerKind": owner["ownerKind"],
            "ownerRef": owner_ref,
            "nativeChildId": child_id,
            "requestedProfile": requested_profile,
        })
    return normalized


def read_run_facts(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise RuntimeError("Cannot read Epic Run facts {}: {}".format(path, exc))
    if not isinstance(value, dict) or value.get("schemaVersion") != "gauntlet/epic-run-facts/v1":
        raise RuntimeError("Unsupported Epic Run facts schema")
    return validate_owners(value.get("owners"))


def run_summary_payload(owners, audit_path, analytics_path):
    owners = validate_owners(owners)
    audit = existing_records(audit_path)
    analytics = existing_analytics(analytics_path)
    by_agent = {}
    for row in analytics.values():
        by_agent.setdefault(row.get("agentId"), []).append(row)
    unavailable = []
    observed = []
    token_totals = {key: 0 for key in TOKEN_KEYS}
    request_count = 0
    profile_mismatches = []
    counted_agents = set()
    for owner in owners:
        agent_id = owner["nativeChildId"]
        if not agent_id:
            unavailable.append({
                "ownerKind": owner["ownerKind"], "ownerRef": owner["ownerRef"],
                "reason": "native-id-unavailable",
            })
            continue
        if agent_id not in audit:
            unavailable.append({
                "ownerKind": owner["ownerKind"], "ownerRef": owner["ownerRef"],
                "reason": "native-record-unavailable",
            })
            continue
        rows = by_agent.get(agent_id, [])
        if not rows:
            unavailable.append({
                "ownerKind": owner["ownerKind"], "ownerRef": owner["ownerRef"],
                "reason": "request-telemetry-unavailable",
            })
            continue
        observed.append({"ownerKind": owner["ownerKind"], "ownerRef": owner["ownerRef"]})
        actual_profile = audit[agent_id].get("profile")
        if owner.get("requestedProfile") and owner["requestedProfile"] != actual_profile:
            profile_mismatches.append({
                "ownerRef": owner["ownerRef"], "requestedProfile": owner["requestedProfile"],
                "actualProfile": (
                    actual_profile
                    if isinstance(actual_profile, str) and actual_profile in EXPECTED
                    else "unrecognized"
                ),
            })
        if agent_id in counted_agents:
            continue
        counted_agents.add(agent_id)
        request_count += len(rows)
        for row in rows:
            for key in TOKEN_KEYS:
                token_totals[key] += row["tokens"][key]
    if not observed:
        status = "unavailable"
        model_requests = None
        tokens = None
        totals_scope = "unavailable"
    else:
        status = "partial" if unavailable else "complete"
        model_requests = request_count
        tokens = token_totals
        totals_scope = "observed-only" if unavailable else "all-declared-owners"
    return {
        "schemaVersion": "gauntlet/run-telemetry-summary/v1",
        "coverage": {
            "status": status,
            "declaredOwners": len(owners),
            "observedOwners": len(observed),
            "unavailableOwners": unavailable,
            "totalsScope": totals_scope,
        },
        "modelRequests": model_requests,
        "tokens": tokens,
        "profileMismatches": profile_mismatches,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("sync", "list", "summary", "verify", "reconcile"), nargs="?", default="sync")
    parser.add_argument("--agent-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--agent-id")
    parser.add_argument("--requested-profile")
    parser.add_argument("--requested-risk", choices=("ordinary", "consequential"), default="ordinary")
    parser.add_argument("--require-read-only", action="store_true")
    parser.add_argument("--circuit-file", type=Path)
    parser.add_argument("--run-facts", type=Path, help="JSON emitted by the Epic Run controller's run-facts --run projection")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    agent_home = args.agent_home.expanduser()
    database = agent_home / "state_5.sqlite"
    output = agent_home / "gauntlet" / "logs" / "subagents.jsonl"
    analytics_path = agent_home / "gauntlet" / "logs" / "subagent-model-requests.jsonl"
    quarantine_path = agent_home / "gauntlet" / "logs" / "subagent-quarantine.jsonl"
    circuit_path = args.circuit_file or agent_home / "gauntlet" / "state" / "routing-circuit.json"
    if args.action == "summary" and args.run_facts:
        try:
            owners = read_run_facts(args.run_facts)
            payload = run_summary_payload(owners, output, analytics_path)
        except RuntimeError as exc:
            parser.error(str(exc))
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    try:
        data = native_records(database)
    except (RuntimeError, sqlite3.Error) as exc:
        parser.error(str(exc))
    if args.action == "sync":
        try:
            sync(data, output, analytics_path, quarantine_path)
        except RuntimeError as exc:
            parser.error(str(exc))
        payload = summary_payload(data, analytics_path, quarantine_path, output)
    elif args.action in {"verify", "reconcile"}:
        if not args.agent_id or not args.requested_profile:
            parser.error("{} requires --agent-id and --requested-profile".format(args.action))
        if args.requested_profile not in EXPECTED:
            parser.error("requested profile is not a canonical Gauntlet profile: {}".format(args.requested_profile))
        row = next((item for item in data if item["agentId"] == args.agent_id), None)
        if row is None:
            parser.error("agent ID is not present in Codex native state: {}".format(args.agent_id))
        if args.action == "reconcile":
            try:
                payload = reconcile(row, args.requested_profile, args.requested_risk, circuit_path)
            except RuntimeError as exc:
                parser.error(str(exc))
            if args.json:
                print(json.dumps(payload, indent=2, sort_keys=True))
            return 4 if payload["failClosed"] else 0
        taxonomy = mismatch_taxonomy(row, args.requested_profile, require_version=False)
        if args.require_read_only and sandbox_type(row) != "read-only":
            parser.error("effective sandbox is not read-only: {}".format(row["sandboxPolicy"]))
        if taxonomy:
            parser.error("start metadata mismatch: {}".format(", ".join(taxonomy)))
        payload = {"status": "pass", "agent": audit_record(row)}
    elif args.action == "summary":
        payload = summary_payload(data, analytics_path, quarantine_path, output)
    else:
        payload = [audit_record(row) for row in data]
    if args.json or args.action not in {"sync"}:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
