"""Private local analytics event creation, sanitization, and aggregation."""

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from gauntletlib.core.proc import git
from gauntletlib.core.redact import has_secret, redact_secrets
from gauntletlib.core.timefmt import utc_timestamp


ANALYTICS_SCHEMA_VERSION = "gauntlet.analytics.v1"
ANALYTICS_EVENT_TYPES = {
    "run_started",
    "mode_selected",
    "plan_created",
    "plan_revised",
    "implementation_started",
    "proof_started",
    "proof_completed",
    "role_review_completed",
    "human_review_requested",
    "human_review_completed",
    "plan_invalidated",
    "attempt_memory_read",
    "attempt_memory_written",
    "commit_created",
    "changelog_updated",
    "pr_opened",
    "closeout_completed",
    "run_completed",
    "annotation_added",
}
SAFE_COMMAND_LABELS = {
    "npm test",
    "npm run test",
    "pytest",
    "python -m pytest",
    "python3 -m pytest",
    "npm run lint",
    "lint",
    "npm run typecheck",
    "typecheck",
}
SENSITIVE_PAYLOAD_KEYS = {
    "command",
    "command_string",
    "repo",
    "repo_name",
    "repository",
    "repository_name",
    "branch",
    "branch_name",
    "file",
    "file_name",
    "path",
    "source",
    "raw_diff",
    "diff",
    "prompt",
    "stack",
    "stack_trace",
    "trace",
    "issue_body",
    "pr_body",
    "customer_data",
    "fingerprint",
    "proof_completed",
    "proof_commands",
    "unresolved_risks",
    "risk_notes",
}
SENSITIVE_PAYLOAD_FRAGMENTS = [
    "repo",
    "branch",
    "command",
    "file",
    "path",
    "diff",
    "prompt",
    "stack",
    "trace",
    "issue_body",
    "pr_body",
    "customer",
]


def local_hash(value, salt):
    digest = hashlib.sha256()
    digest.update(salt.encode("utf-8"))
    digest.update(b"\0")
    digest.update(str(value).encode("utf-8", errors="ignore"))
    return digest.hexdigest()[:24]


def analytics_dir(project_root):
    return Path(project_root) / ".gauntlet" / "analytics"


def analytics_events_path(project_root, path=None):
    return Path(path) if path else analytics_dir(project_root) / "events.ndjson"


def local_salt(project_root):
    directory = analytics_dir(project_root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "local-salt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    salt = uuid.uuid4().hex
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(salt + "\n")
    return salt


def _git_root(repo):
    result = git(["rev-parse", "--show-toplevel"], repo)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _branch_name(repo):
    branch = git(["branch", "--show-current"], repo)
    if branch.returncode != 0:
        return ""
    return branch.stdout.strip()


def payload_key_is_sensitive(key):
    normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
    return normalized in SENSITIVE_PAYLOAD_KEYS or any(
        fragment in normalized for fragment in SENSITIVE_PAYLOAD_FRAGMENTS
    )


def hash_payload_value(value, salt):
    if isinstance(value, list):
        return [hash_payload_value(item, salt) for item in value]
    if isinstance(value, dict):
        return local_hash(json.dumps(value, sort_keys=True), salt)
    return local_hash(value, salt)


def sanitize_payload(payload, salt):
    if not isinstance(payload, dict):
        return {}
    sanitized = {}
    for key, value in payload.items():
        normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
        if normalized == "command_label":
            if isinstance(value, str) and value in SAFE_COMMAND_LABELS:
                sanitized[key] = value
            else:
                sanitized[f"{key}_hash"] = local_hash(value, salt)
            continue
        if payload_key_is_sensitive(key) and isinstance(value, (int, float, bool)):
            sanitized[key] = value
            continue
        if payload_key_is_sensitive(key) or (isinstance(value, str) and has_secret(value)):
            suffix = "hashes" if isinstance(value, list) else "hash"
            sanitized[f"{key}_{suffix}"] = hash_payload_value(value, salt)
            continue
        if isinstance(value, dict):
            sanitized[key] = sanitize_payload(value, salt)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_payload(item, salt)
                if isinstance(item, dict)
                else ("[REDACTED_SECRET]" if isinstance(item, str) and has_secret(item) else item)
                for item in value
            ]
        elif isinstance(value, str):
            sanitized[key] = redact_secrets(value)
        else:
            sanitized[key] = value
    return sanitized


def analytics_event(
    project_root,
    event_type,
    run_id,
    payload=None,
    agent="codex",
    gauntlet_version="2.0.2",
    created_at=None,
):
    root = Path(project_root).resolve()
    salt = local_salt(root)
    repo_root = _git_root(root) or str(root)
    branch = _branch_name(root) or "detached"
    return {
        "schema_version": ANALYTICS_SCHEMA_VERSION,
        "event_id": uuid.uuid4().hex,
        "run_id": run_id or uuid.uuid4().hex,
        "event_type": event_type,
        "created_at": created_at or utc_timestamp(),
        "project_hash": local_hash(str(root), salt),
        "repo_hash": local_hash(repo_root, salt),
        "branch_hash": local_hash(branch, salt),
        "agent": agent,
        "gauntlet_version": gauntlet_version,
        "payload": sanitize_payload(payload or {}, salt),
    }


def append_analytics_event(
    project_root,
    event_type,
    run_id,
    payload=None,
    agent="codex",
    gauntlet_version="2.0.2",
    path=None,
    dry_run=False,
    created_at=None,
):
    root = Path(project_root).resolve()
    event = analytics_event(
        root,
        event_type,
        run_id,
        payload,
        agent,
        gauntlet_version,
        created_at=created_at,
    )
    output_path = analytics_events_path(root, path)
    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
    return event, output_path


def read_analytics_events(path):
    path = Path(path)
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def confidence_label(baseline_runs, candidate_runs):
    sample = min(baseline_runs, candidate_runs)
    if sample == 0:
        return "no claim"
    if sample < 6:
        return "anecdotal"
    if sample < 20:
        return "directional"
    return "strong signal"


def event_cohort(event):
    payload = event.get("payload") or {}
    return payload.get("cohort") or event.get("gauntlet_version")


def event_segment_key(event):
    payload = event.get("payload") or {}
    return (
        payload.get("mode", "unknown"),
        payload.get("depth", "unknown"),
        payload.get("proof_scope", "unknown"),
        payload.get("task_type", "unknown"),
    )


def parse_event_time(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def seconds_between(start, end):
    if not start or not end:
        return None
    return int((end - start).total_seconds())


def duration_summary(values):
    clean = [value for value in values if value is not None and value >= 0]
    total = sum(clean)
    return {
        "count": len(clean),
        "total": total,
        "average": round(total / len(clean), 2) if clean else 0,
    }


def first_event_time(events, event_type):
    for event in events:
        if event.get("event_type") == event_type:
            return parse_event_time(event.get("created_at"))
    return None


def cohort_timing_summary(events, stale_wait_seconds=86400):
    by_run = {}
    for event in events:
        by_run.setdefault(event.get("run_id") or "unknown", []).append(event)

    calendar_spans = []
    active_planning = []
    human_review_latencies = []
    long_review_gaps = 0
    autonomous_eligible = 0
    autonomous_completed = 0

    for run_events in by_run.values():
        ordered = sorted(run_events, key=lambda event: event.get("created_at", ""))
        run_start = first_event_time(ordered, "run_started")
        implementation_start = first_event_time(ordered, "implementation_started")
        calendar_spans.append(seconds_between(run_start, implementation_start))

        active_seconds = 0
        for event in ordered:
            event_time = parse_event_time(event.get("created_at"))
            if implementation_start and event_time and event_time > implementation_start:
                continue
            if event.get("event_type") not in {"mode_selected", "plan_created", "plan_revised"}:
                continue
            value = (event.get("payload") or {}).get("active_agent_seconds")
            if isinstance(value, (int, float)):
                active_seconds += int(value)
        if active_seconds:
            active_planning.append(active_seconds)

        pending_reviews = []
        for event in ordered:
            if event.get("event_type") == "human_review_requested":
                pending_reviews.append(parse_event_time(event.get("created_at")))
            elif event.get("event_type") == "human_review_completed" and pending_reviews:
                requested_at = pending_reviews.pop(0)
                latency = seconds_between(
                    requested_at,
                    parse_event_time(event.get("created_at")),
                )
                if latency is not None and latency >= 0:
                    human_review_latencies.append(latency)
                    if latency > stale_wait_seconds:
                        long_review_gaps += 1

        if any(
            event.get("event_type") == "annotation_added"
            and (event.get("payload") or {}).get("autonomous_eligible") is True
            for event in ordered
        ):
            autonomous_eligible += 1
        if any(
            event.get("event_type") == "run_completed"
            and (event.get("payload") or {}).get("autonomous_completed") is True
            for event in ordered
        ):
            autonomous_completed += 1

    return {
        "calendarPlanningSpanSeconds": duration_summary(calendar_spans),
        "activeAgentPlanningSeconds": duration_summary(active_planning),
        "humanReviewLatencySeconds": duration_summary(human_review_latencies),
        "humanReviewLongGapCount": long_review_gaps,
        "autonomousEligibleRuns": autonomous_eligible,
        "autonomousCompletedRuns": autonomous_completed,
    }


def cohort_summary(events, stale_wait_seconds=86400):
    run_ids = {event.get("run_id") for event in events if event.get("run_id")}
    completed = [event for event in events if event.get("event_type") == "run_completed"]
    verified = [
        event for event in completed if (event.get("payload") or {}).get("verified") is True
    ]
    event_counts = {}
    for event in events:
        event_type = event.get("event_type", "unknown")
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
    return {
        "runs": len(run_ids),
        "events": len(events),
        "runCompleted": len(completed),
        "verifiedCompleted": len(verified),
        "eventCounts": event_counts,
        "timing": cohort_timing_summary(events, stale_wait_seconds=stale_wait_seconds),
    }


def segment_summaries(baseline_events, candidate_events):
    rows = {}
    for label, events in [("baselineCount", baseline_events), ("candidateCount", candidate_events)]:
        for event in events:
            key = event_segment_key(event)
            rows.setdefault(key, {"baselineCount": 0, "candidateCount": 0})
            rows[key][label] += 1
    summaries = []
    for (mode, depth, proof_scope, task_type), counts in sorted(rows.items()):
        summaries.append(
            {
                "mode": mode,
                "depth": depth,
                "proofScope": proof_scope,
                "taskType": task_type,
                **counts,
            }
        )
    return summaries
