#!/usr/bin/env python3
"""Export privacy-bounded Gauntlet subagent usage from Codex native state."""

import argparse
from datetime import datetime
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
OPAQUE_ID = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_:-]{0,127}\Z")
MODEL_ID = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
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
OPTIONAL_EMITTED_TOKEN_KEYS = ("cache_write_input_tokens",)
REQUEST_WINDOW_KEYS = {"startedAt", "endedAt", "startOrdinal", "endOrdinal"}
PRICING_SCHEMA = "gauntlet.model-api-pricing.v1"
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


def rfc3339(value):
    if value is None:
        return None
    if not isinstance(value, str) or not value.endswith("Z"):
        raise RuntimeError("timestamp must use RFC 3339 UTC with a Z suffix")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise RuntimeError("timestamp must use RFC 3339 UTC") from exc
    return value


def privacy_bounded_sandbox(value):
    """Retain the effective sandbox type without persisting private writable roots."""
    try:
        policy = json.loads(value)
    except (TypeError, ValueError):
        return value if isinstance(value, str) and "/" not in value else None
    if not isinstance(policy, dict) or not isinstance(policy.get("type"), str):
        return None
    return json.dumps({"type": policy["type"]}, separators=(",", ":"), sort_keys=True)


def native_record(row):
    return {
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


def native_records(database, agent_ids=None):
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
        where = "t.agent_role GLOB 'gauntlet_*'"
        params = []
        if agent_ids is not None:
            bounded = sorted({opaque_id(value, "native agent ID") for value in agent_ids if value})
            if not bounded:
                return []
            where = "t.id IN ({})".format(",".join("?" for _ in bounded))
            params = bounded
        query = """
        SELECT {}, e.parent_thread_id
        FROM threads t
        LEFT JOIN thread_spawn_edges e ON e.child_thread_id = t.id
        WHERE {}
        ORDER BY COALESCE(t.created_at_ms, 0), t.id
        """.format(", ".join(expressions), where)
        rows = connection.execute(query, params).fetchall()
    finally:
        connection.close()
    return [native_record(row) for row in rows]


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


def normalized_emitted_tokens(value):
    if not isinstance(value, dict):
        return None
    allowed = set(TOKEN_KEYS) | set(OPTIONAL_EMITTED_TOKEN_KEYS)
    if not set(TOKEN_KEYS).issubset(value) or not set(value).issubset(allowed):
        return None
    for key in OPTIONAL_EMITTED_TOKEN_KEYS:
        extra = value.get(key, 0)
        if isinstance(extra, bool) or not isinstance(extra, int) or extra < 0:
            return None
    normalized = {key: value[key] for key in TOKEN_KEYS}
    return normalized if valid_tokens(normalized) else None


def valid_model_id(value):
    return value if isinstance(value, str) and MODEL_ID.fullmatch(value) else None


def quarantine(agent_id, line_number, reason):
    return {"agentId": agent_id, "lineNumber": line_number, "reason": reason}


def read_cursor_state(path):
    if not path.exists():
        return {"schemaVersion": 1, "agents": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise RuntimeError("Cannot read request cursor state {}: {}".format(path, exc))
    if value.get("schemaVersion") != 1 or not isinstance(value.get("agents"), dict):
        raise RuntimeError("Unsupported request cursor state: {}".format(path))
    return value


def request_analytics(row, cursor=None):
    path_value = row.get("rolloutPath")
    if not path_value:
        return None, [], cursor
    path = Path(path_value)
    if path.is_symlink() or not path.is_file():
        return None, [quarantine(row["agentId"], 0, "rollout-unavailable")], cursor
    path_fingerprint = fingerprint(str(path.resolve()))
    cursor = dict(cursor or {})
    if cursor and cursor.get("pathFingerprint") != path_fingerprint:
        return None, [quarantine(row["agentId"], cursor.get("lineNumber", 0), "rollout-rotated")], cursor
    offset = cursor.get("byteOffset", 0)
    line_number = cursor.get("lineNumber", 0)
    ordinal = cursor.get("requestOrdinal", 0)
    previous = cursor.get("lastTotals", {key: 0 for key in TOKEN_KEYS})
    current_model = valid_model_id(cursor.get("currentModel")) or valid_model_id(row.get("model"))
    if (
        not isinstance(offset, int) or offset < 0
        or not isinstance(line_number, int) or line_number < 0
        or not isinstance(ordinal, int) or ordinal < 0
        or not valid_tokens(previous)
    ):
        raise RuntimeError("Invalid request cursor for {}".format(row["agentId"]))
    try:
        size = path.stat().st_size
        if size < offset:
            return None, [quarantine(row["agentId"], line_number, "rollout-truncated")], cursor
        with path.open("rb") as handle:
            handle.seek(offset)
            raw_lines = handle.read().splitlines(keepends=True)
    except OSError:
        return None, [quarantine(row["agentId"], line_number, "rollout-unreadable")], cursor
    requests = []
    quarantined = []
    committed_offset = offset
    committed_line = line_number
    for raw in raw_lines:
        current_line = committed_line + 1
        if not raw.endswith((b"\n", b"\r")):
            quarantined.append(quarantine(row["agentId"], current_line, "unterminated-json-line"))
            break
        try:
            event = json.loads(raw)
        except (UnicodeError, ValueError):
            quarantined.append(quarantine(row["agentId"], current_line, "invalid-json-line"))
            break
        next_offset = committed_offset + len(raw)
        committed_line = current_line
        if event.get("type") == "turn_context" and isinstance(event.get("payload"), dict):
            current_model = valid_model_id(event["payload"].get("model")) or current_model
            committed_offset = next_offset
            continue
        if event.get("type") != "event_msg" or not isinstance(event.get("payload"), dict):
            committed_offset = next_offset
            continue
        payload = event["payload"]
        if payload.get("type") != "token_count":
            committed_offset = next_offset
            continue
        info = payload.get("info")
        total = normalized_emitted_tokens(info.get("total_token_usage")) if isinstance(info, dict) else None
        last = normalized_emitted_tokens(info.get("last_token_usage")) if isinstance(info, dict) else None
        if total is None or last is None:
            quarantined.append(quarantine(row["agentId"], current_line, "partial-token-count"))
            committed_line -= 1
            break
        if any(total[key] < previous[key] for key in TOKEN_KEYS):
            quarantined.append(quarantine(row["agentId"], current_line, "nonmonotonic-cumulative-token-count"))
            committed_line -= 1
            break
        delta = {key: total[key] - previous[key] for key in TOKEN_KEYS}
        if not any(delta.values()):
            committed_offset = next_offset
            continue
        if delta != last or not valid_tokens(delta):
            quarantined.append(quarantine(row["agentId"], current_line, "inconsistent-token-delta"))
            committed_line -= 1
            break
        previous = total
        ordinal += 1
        observed_at = event.get("timestamp")
        try:
            observed_at = rfc3339(observed_at) if observed_at is not None else None
        except RuntimeError:
            observed_at = None
        requests.append({
            "agentId": row["agentId"],
            "codexVersion": row.get("cliVersion") or "unknown",
            "model": current_model,
            "profile": row.get("profile"),
            "reasoningEffort": row.get("reasoningEffort"),
            "requestId": "{}:{}".format(row["agentId"], ordinal),
            "requestOrdinal": ordinal,
            "observedAt": observed_at,
            "observedThrough": next_offset,
            "tokens": delta,
        })
        committed_offset = next_offset
    next_cursor = {
        "byteOffset": committed_offset,
        "currentModel": current_model,
        "lastTotals": previous,
        "lineNumber": committed_line,
        "pathFingerprint": path_fingerprint,
        "requestOrdinal": ordinal,
    }
    return requests, quarantined, next_cursor


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


def read_jsonl_rows(path):
    if not path.exists():
        return []
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    except (OSError, UnicodeError, ValueError) as exc:
        raise RuntimeError("Cannot read JSONL {}: {}".format(path, exc))


def sync(native, output, analytics_path, quarantine_path, cursor_path):
    merged = existing_records(output)
    merged.update({row["agentId"]: audit_record(row) for row in native})
    ordered = sorted(merged.values(), key=lambda row: (row.get("createdAtMs") or 0, row["agentId"]))
    analytics = existing_analytics(analytics_path)
    cursor_state = read_cursor_state(cursor_path)
    native_ids = {row["agentId"] for row in native}
    quarantined = [
        row for row in read_jsonl_rows(quarantine_path)
        if row.get("agentId") not in native_ids
    ]
    for row in native:
        agent_id = row["agentId"]
        current, current_quarantine, next_cursor = request_analytics(
            row, cursor_state["agents"].get(agent_id)
        )
        quarantined.extend(current_quarantine)
        if current is not None:
            analytics.update({item["requestId"]: item for item in current})
        if next_cursor is not None:
            cursor_state["agents"][agent_id] = next_cursor
    analytics_rows = sorted(analytics.values(), key=lambda row: (row["agentId"], row["requestOrdinal"]))
    quarantine_rows = sorted(quarantined, key=lambda row: (row["agentId"], row["lineNumber"], row["reason"]))
    atomic_write(output, render_jsonl(ordered))
    atomic_write(analytics_path, render_jsonl(analytics_rows))
    atomic_write(quarantine_path, render_jsonl(quarantine_rows))
    atomic_write(cursor_path, json.dumps(cursor_state, indent=2, sort_keys=True) + "\n")


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
    seen_ids = set()
    for index, owner in enumerate(owners, 1):
        if not isinstance(owner, dict) or owner.get("ownerKind") not in {"parent", "delegated"}:
            raise RuntimeError("Epic Run owner {} has an invalid ownerKind".format(index))
        owner_ref = opaque_id(owner.get("ownerRef"), "Epic Run owner {} ownerRef".format(index))
        owner_id = opaque_id(owner.get("ownerId", owner_ref), "Epic Run owner {} ownerId".format(index))
        if owner_id in seen_ids:
            raise RuntimeError("Epic Run owner {} requires a unique ownerId".format(index))
        child_id = owner.get("nativeChildId")
        if child_id is not None:
            child_id = opaque_id(child_id, "Epic Run owner {} nativeChildId".format(index))
        requested_profile = owner.get("requestedProfile")
        if requested_profile is not None and (
            not isinstance(requested_profile, str) or requested_profile not in EXPECTED
        ):
            raise RuntimeError("Epic Run owner {} requestedProfile is not canonical".format(index))
        request_window = owner.get("requestWindow")
        normalized_window = None
        if request_window is not None:
            if not isinstance(request_window, dict) or set(request_window) != REQUEST_WINDOW_KEYS:
                raise RuntimeError("Epic Run owner {} requestWindow is invalid".format(index))
            started_at = rfc3339(request_window.get("startedAt"))
            ended_at = rfc3339(request_window.get("endedAt"))
            start_ordinal = request_window.get("startOrdinal")
            end_ordinal = request_window.get("endOrdinal")
            for label, ordinal in (("startOrdinal", start_ordinal), ("endOrdinal", end_ordinal)):
                if ordinal is not None and (
                    isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 0
                ):
                    raise RuntimeError("Epic Run owner {} {} is invalid".format(index, label))
            if start_ordinal is not None and end_ordinal is not None and start_ordinal > end_ordinal:
                raise RuntimeError("Epic Run owner {} requestWindow ordinals are reversed".format(index))
            if started_at and ended_at and started_at > ended_at:
                raise RuntimeError("Epic Run owner {} requestWindow timestamps are reversed".format(index))
            normalized_window = {
                "startedAt": started_at,
                "endedAt": ended_at,
                "startOrdinal": start_ordinal,
                "endOrdinal": end_ordinal,
            }
        seen_ids.add(owner_id)
        normalized.append({
            "ownerId": owner_id,
            "ownerKind": owner["ownerKind"],
            "ownerRef": owner_ref,
            "nativeChildId": child_id,
            "requestedProfile": requested_profile,
            "requestWindow": normalized_window,
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


def read_pricing_registry(path):
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise RuntimeError("Cannot read model API pricing registry {}: {}".format(path, exc))
    if registry.get("schemaVersion") != PRICING_SCHEMA or not isinstance(registry.get("models"), dict):
        raise RuntimeError("Unsupported model API pricing registry")
    rfc3339(registry.get("effectiveAt"))
    return registry


def price_requests(rows, registry):
    components = {"cachedInputUsd": 0.0, "inputUsd": 0.0, "outputUsd": 0.0}
    by_model = {}
    reasons = set()
    priced_requests = 0
    for row in rows:
        rates = registry["models"].get(row.get("model"))
        if not rates:
            reasons.add("model-price-unavailable")
            continue
        model_cost = by_model.setdefault(row["model"], {
            "requests": 0, "cachedInputUsd": 0.0, "inputUsd": 0.0, "outputUsd": 0.0,
            "inputTokens": 0, "cachedInputTokens": 0, "outputTokens": 0,
            "reasoningOutputTokens": 0, "totalTokens": 0,
        })
        token_values = row["tokens"]
        input_multiplier = 1.0
        output_multiplier = 1.0
        if token_values["input_tokens"] > rates.get("longContextThreshold", 272000):
            input_multiplier = rates.get("longContextInputMultiplier", 2.0)
            output_multiplier = rates.get("longContextOutputMultiplier", 1.5)
        uncached = token_values["input_tokens"] - token_values["cached_input_tokens"]
        input_cost = uncached * rates["inputPerMillion"] * input_multiplier / 1_000_000
        cached_cost = token_values["cached_input_tokens"] * rates["cachedInputPerMillion"] * input_multiplier / 1_000_000
        # Reasoning tokens are already included in output_tokens and must not be charged twice.
        output_cost = token_values["output_tokens"] * rates["outputPerMillion"] * output_multiplier / 1_000_000
        components["inputUsd"] += input_cost
        components["cachedInputUsd"] += cached_cost
        components["outputUsd"] += output_cost
        model_cost["requests"] += 1
        model_cost["inputUsd"] += input_cost
        model_cost["cachedInputUsd"] += cached_cost
        model_cost["outputUsd"] += output_cost
        model_cost["inputTokens"] += token_values["input_tokens"]
        model_cost["cachedInputTokens"] += token_values["cached_input_tokens"]
        model_cost["outputTokens"] += token_values["output_tokens"]
        model_cost["reasoningOutputTokens"] += token_values["reasoning_output_tokens"]
        model_cost["totalTokens"] += token_values["total_tokens"]
        priced_requests += 1
        if not rates.get("cacheWriteObservable", False):
            reasons.add("cache-write-telemetry-unavailable")
    rounded = {key: round(value, 8) for key, value in components.items()}
    rounded_models = {}
    for model, values in sorted(by_model.items()):
        rounded_values = {
            key: (value if key == "requests" or key.endswith("Tokens") else round(value, 8))
            for key, value in values.items()
        }
        rounded_values["totalUsd"] = round(sum(
            rounded_values[key] for key in ("cachedInputUsd", "inputUsd", "outputUsd")
        ), 8)
        rounded_models[model] = rounded_values
    lower_bound = round(sum(rounded.values()), 8)
    complete = not reasons and priced_requests == len(rows)
    return {
        "status": "complete" if complete else ("partial" if priced_requests else "unavailable"),
        "currency": registry.get("currency", "USD"),
        "registryVersion": registry["schemaVersion"],
        "effectiveAt": registry["effectiveAt"],
        "source": registry.get("source"),
        "pricedRequests": priced_requests,
        "components": rounded if priced_requests else None,
        "byModel": rounded_models,
        "lowerBoundUsd": lower_bound if priced_requests else None,
        "estimatedUsd": lower_bound if complete else None,
        "limitations": sorted(reasons),
    }


def rows_for_window(rows, window):
    if window is None:
        return []
    start = window.get("startOrdinal")
    end = window.get("endOrdinal")
    started_at = window.get("startedAt")
    ended_at = window.get("endedAt")
    started_time = datetime.fromisoformat(started_at[:-1] + "+00:00") if started_at else None
    ended_time = datetime.fromisoformat(ended_at[:-1] + "+00:00") if ended_at else None
    bounded = []
    for row in rows:
        ordinal = row.get("requestOrdinal")
        observed_at = row.get("observedAt")
        observed_time = (
            datetime.fromisoformat(observed_at[:-1] + "+00:00")
            if isinstance(observed_at, str) and observed_at.endswith("Z") else None
        )
        after_start = (
            ordinal > start if start is not None and isinstance(ordinal, int)
            else observed_time >= started_time if started_time and observed_time
            else False
        )
        before_end = (
            ordinal <= end if end is not None and isinstance(ordinal, int)
            else observed_time <= ended_time if ended_time and observed_time
            else ended_time is None
        )
        if after_start and before_end:
            bounded.append(row)
    return bounded


def run_summary_payload(owners, audit_path, analytics_path, quarantine_path, pricing_path):
    owners = validate_owners(owners)
    audit = existing_records(audit_path)
    analytics = existing_analytics(analytics_path)
    by_agent = {}
    for row in analytics.values():
        by_agent.setdefault(row.get("agentId"), []).append(row)
    unavailable = []
    observed = []
    coverage_limitations = set()
    token_totals = {key: 0 for key in TOKEN_KEYS}
    tokens_by_model = {}
    request_count = 0
    profile_mismatches = []
    counted_requests = set()
    included_rows = []
    owner_freshness = []
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
        all_rows = by_agent.get(agent_id, [])
        if owner["requestWindow"] is None:
            coverage_limitations.add("owner-window-unavailable")
        elif owner["requestWindow"].get("startOrdinal") is None or owner["requestWindow"].get("endOrdinal") is None:
            coverage_limitations.add("owner-window-partial")
        rows = rows_for_window(all_rows, owner["requestWindow"])
        if not rows:
            unavailable.append({
                "ownerKind": owner["ownerKind"], "ownerRef": owner["ownerRef"],
                "reason": "request-telemetry-unavailable",
            })
            continue
        observed_through = max((row.get("observedAt") for row in rows if row.get("observedAt")), default=None)
        observed.append({
            "ownerKind": owner["ownerKind"], "ownerRef": owner["ownerRef"],
            "observedThrough": observed_through,
        })
        owner_freshness.append(observed_through)
        if observed_through is None:
            coverage_limitations.add("request-timestamps-unavailable")
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
        for row in rows:
            if row["requestId"] in counted_requests:
                continue
            counted_requests.add(row["requestId"])
            request_count += 1
            included_rows.append(row)
            for key in TOKEN_KEYS:
                token_totals[key] += row["tokens"][key]
            model = row.get("model")
            if isinstance(model, str):
                tokens_by_model[model] = tokens_by_model.get(model, 0) + row["tokens"]["total_tokens"]
    if not observed:
        status = "unavailable"
        model_requests = None
        tokens = None
        model_tokens = None
        totals_scope = "unavailable"
    else:
        status = "partial" if unavailable or coverage_limitations else "complete"
        model_requests = request_count
        tokens = token_totals
        model_tokens = dict(sorted(tokens_by_model.items()))
        totals_scope = "observed-only" if unavailable or coverage_limitations else "all-declared-owners"
    quarantined_agents = set()
    if quarantine_path.exists():
        for row in read_jsonl_rows(quarantine_path):
            quarantined_agents.add(row.get("agentId"))
    if any(owner.get("nativeChildId") in quarantined_agents for owner in owners):
        coverage_limitations.add("request-integrity-quarantine")
        if status == "complete":
            status = "partial"
            totals_scope = "observed-only"
    pricing = price_requests(included_rows, read_pricing_registry(pricing_path)) if included_rows else {
        "status": "unavailable", "currency": "USD", "registryVersion": PRICING_SCHEMA,
        "effectiveAt": None, "source": None, "pricedRequests": 0, "components": None,
        "byModel": {}, "lowerBoundUsd": None, "estimatedUsd": None,
        "limitations": ["request-telemetry-unavailable"],
    }
    return {
        "schemaVersion": "gauntlet/run-telemetry-summary/v1",
        "coverage": {
            "status": status,
            "declaredOwners": len(owners),
            "observedOwners": len(observed),
            "unavailableOwners": unavailable,
            "totalsScope": totals_scope,
            "limitations": sorted(coverage_limitations),
            "freshness": {
                "observedThrough": max((value for value in owner_freshness if value), default=None),
                "status": "observed" if any(owner_freshness) else "unavailable",
            },
        },
        "modelRequests": model_requests,
        "tokens": tokens,
        "tokensByModel": model_tokens,
        "pricing": pricing,
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
    cursor_path = agent_home / "gauntlet" / "state" / "subagent-request-cursors.json"
    pricing_path = Path(__file__).resolve().parents[1] / "templates" / "model-api-pricing.json"
    circuit_path = args.circuit_file or agent_home / "gauntlet" / "state" / "routing-circuit.json"
    if args.action == "summary" and args.run_facts:
        try:
            owners = read_run_facts(args.run_facts)
            owner_agent_ids = [owner["nativeChildId"] for owner in owners if owner["nativeChildId"]]
            if database.is_file() and owner_agent_ids:
                scoped_native = native_records(database, owner_agent_ids)
                if scoped_native:
                    sync(scoped_native, output, analytics_path, quarantine_path, cursor_path)
            payload = run_summary_payload(
                owners, output, analytics_path, quarantine_path, pricing_path
            )
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
            sync(data, output, analytics_path, quarantine_path, cursor_path)
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
