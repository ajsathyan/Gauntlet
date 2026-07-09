#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
CHECKER = SCRIPTS / "check-workflow-etiquette.py"
STATUS_ORDER = {"pass": 0, "warn": 1, "review": 2, "fail": 3}
EXIT_CODES = {"pass": 0, "warn": 0, "review": 2, "fail": 1}
APP_ACTIONS = {"set_thread_title", "archive_thread", "create_thread"}
PASSING_CHECK_CONCLUSIONS = {"SUCCESS", "SKIPPED", "NEUTRAL"}
PASSING_STATUS_STATES = {"SUCCESS", "SKIPPED", "NEUTRAL"}
TITLE_PATTERN = re.compile(r"^p[0-4](?:-auto)?: .+")
SECTION_REQUIRED = [
    ("goal", ["goal"]),
    ("scope", ["scope"]),
    ("non_goals", ["non-goals", "non goals", "non-goal", "non goal"]),
    ("scan_index", ["scan index"]),
    ("source_of_truth_files", ["source-of-truth files", "source of truth files", "source files", "read first"]),
    ("edge_cases_and_invariants", ["edge cases and invariants", "edge cases", "invariants"]),
    ("verification", ["verification", "proof"]),
    ("follow_ups", ["follow-ups", "follow ups", "followup", "followups"]),
    ("stale_context_warning", ["stale context warning", "stale-context warning", "stale context"]),
    ("redaction_notes", ["redaction notes", "redaction", "secrets"]),
]
SECRET_PATTERNS = [
    re.compile(r"(?i)\b[A-Z0-9_]*(SECRET|TOKEN|PASSWORD|API_KEY|PRIVATE_KEY)[A-Z0-9_]*\s*=\s*['\"]?[^\s'\"`]+"),
    re.compile(r"(?i)\b(sk|pk|rk)-(live|test)-[A-Za-z0-9_-]{8,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
ARCHIVE_SUMMARY_ALIASES = ["archive summary", "what changed", "change summary"]
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


def run_cmd(args, cwd=None, env=None, check=False):
    result = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"{args} failed with {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
    return result


def git(args, cwd):
    return run_cmd(["git", *args], cwd=cwd)


def gh_binary():
    return os.environ.get("GAUNTLET_GH", "gh")


def gh(args, cwd):
    return run_cmd([gh_binary(), *args], cwd=cwd, env=os.environ.copy())


def read_text(path):
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def redact_secrets(text):
    redacted = text or ""
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    return redacted


def has_secret(text):
    return any(pattern.search(text or "") for pattern in SECRET_PATTERNS)


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def attempt_memory_path(project_root, path=None):
    return Path(path) if path else Path(project_root) / ".gauntlet" / "attempt-memory.jsonl"


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


def git_root(repo):
    result = git(["rev-parse", "--show-toplevel"], repo)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def payload_key_is_sensitive(key):
    normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
    return normalized in SENSITIVE_PAYLOAD_KEYS or any(fragment in normalized for fragment in SENSITIVE_PAYLOAD_FRAGMENTS)


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
                sanitize_payload(item, salt) if isinstance(item, dict)
                else ("[REDACTED_SECRET]" if isinstance(item, str) and has_secret(item) else item)
                for item in value
            ]
        elif isinstance(value, str):
            sanitized[key] = redact_secrets(value)
        else:
            sanitized[key] = value
    return sanitized


def analytics_event(project_root, event_type, run_id, payload=None, agent="codex", gauntlet_version="2.0.2", created_at=None):
    root = Path(project_root).resolve()
    salt = local_salt(root)
    repo_root = git_root(root) or str(root)
    branch = branch_name(root) or "detached"
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


def append_analytics_event(project_root, event_type, run_id, payload=None, agent="codex", gauntlet_version="2.0.2", path=None, dry_run=False, created_at=None):
    root = Path(project_root).resolve()
    event = analytics_event(root, event_type, run_id, payload, agent, gauntlet_version, created_at=created_at)
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
                latency = seconds_between(requested_at, parse_event_time(event.get("created_at")))
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
        event
        for event in completed
        if (event.get("payload") or {}).get("verified") is True
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
        summaries.append({
            "mode": mode,
            "depth": depth,
            "proofScope": proof_scope,
            "taskType": task_type,
            **counts,
        })
    return summaries


def display_path(root, path):
    path = Path(path)
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def heading_key(line):
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None
    hashes, _, title = stripped.partition(" ")
    if not title or not set(hashes) <= {"#"}:
        return None
    key = re.sub(r"[^a-z0-9]+", " ", title.strip().rstrip("#").lower()).strip()
    return len(hashes), key


def markdown_sections(text):
    sections = {}
    current = None
    for line in text.splitlines():
        parsed = heading_key(line)
        if parsed:
            _, current = parsed
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    return {key: "\n".join(lines).strip() for key, lines in sections.items()}


def find_section(sections, aliases):
    normalized = {re.sub(r"[^a-z0-9]+", " ", alias.lower()).strip() for alias in aliases}
    for key, value in sections.items():
        if key in normalized:
            return value
    return None


def first_nonempty_line(text, fallback="None supplied."):
    for line in (text or "").splitlines():
        clean = line.strip().lstrip("-").strip()
        if clean:
            return clean
    return fallback


def section_bullets(text):
    items = []
    for line in (text or "").splitlines():
        clean = line.strip()
        if clean.startswith("- "):
            items.append(clean[2:].strip())
    if items:
        return items
    return [first_nonempty_line(text)] if (text or "").strip() else []


def archive_summary_from_sections(sections):
    explicit = find_section(sections, ARCHIVE_SUMMARY_ALIASES)
    if explicit:
        return [redact_secrets(item) for item in section_bullets(explicit)[:10]]

    bullets = []
    goal = first_nonempty_line(find_section(sections, ["goal"]) or "", "")
    if goal:
        bullets.append(redact_secrets(goal))
    scope = section_bullets(find_section(sections, ["scope"]) or "")
    bullets.extend(redact_secrets(item) for item in scope[:4])
    verification = section_bullets(find_section(sections, ["verification", "proof"]) or "")
    if verification:
        bullets.append("Verification expected: " + "; ".join(redact_secrets(item) for item in verification[:2]))
    return bullets[:10]


def archive_summary_from_content(path):
    if not path:
        return None, []
    path = Path(path)
    if not path.exists():
        return None, [{"code": "missing_archive_summary_content", "severity": "warn", "message": f"Archive summary content file does not exist: {path}."}]
    text = read_text(path)
    sections = markdown_sections(text)
    raw_summary = find_section(sections, ARCHIVE_SUMMARY_ALIASES)
    if not raw_summary:
        return None, [{"code": "missing_archive_summary", "severity": "warn", "message": f"No Archive Summary section found in {path}."}]
    if has_secret(raw_summary):
        return None, [{"code": "secret_like_archive_summary", "severity": "fail", "message": "Archive Summary contains secret-like content; redact it before archive."}]
    bullets = [redact_secrets(item) for item in section_bullets(raw_summary)[:10]]
    return {"source": "content", "path": str(path), "bullets": bullets}, []


def parse_followups(text):
    followups = []
    lines = (text or "").splitlines()
    index = 0
    while index < len(lines):
        if lines[index].strip().lower() != "follow-up captured:":
            index += 1
            continue
        block = {}
        index += 1
        while index < len(lines):
            line = lines[index].strip()
            if not line:
                break
            if line.lower() == "follow-up captured:":
                index -= 1
                break
            match = re.match(r"-\s*([^:]+):\s*(.*)", line)
            if match:
                key = re.sub(r"[^a-z0-9]+", "_", match.group(1).lower()).strip("_")
                block[key] = match.group(2).strip()
            index += 1
        if block:
            followups.append(block)
        index += 1
    return followups


def add_finding(payload, code, severity, message):
    payload.setdefault("findings", []).append({
        "code": code,
        "severity": severity,
        "message": message,
    })


def status_for(payload):
    status = "pass"
    for finding in payload.get("findings", []):
        severity = finding.get("severity", "warn")
        if STATUS_ORDER[severity] > STATUS_ORDER[status]:
            status = severity
    return status


def memory_lint_payload(path):
    root = Path.cwd().resolve()
    path = Path(path)
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "path": str(path),
        "findings": [],
        "sections": {},
    }
    if not path.exists():
        add_finding(payload, "missing_memory_file", "fail", f"Implementation Memory file does not exist: {path}")
        payload["status"] = status_for(payload)
        return payload

    text = read_text(path)
    sections = markdown_sections(text)
    found = {}
    for code, aliases in SECTION_REQUIRED:
        value = find_section(sections, aliases)
        found[code] = bool(value)
        if not value:
            add_finding(
                payload,
                "missing_memory_section",
                "fail",
                f"Implementation Memory is missing required section: {aliases[0]}.",
            )
    if has_secret(text):
        add_finding(
            payload,
            "secret_like_memory_content",
            "fail",
            "Implementation Memory contains secret-like content; redact it before using workflow helpers.",
        )
    payload["sections"] = found
    payload["path"] = display_path(root, path)
    payload["status"] = status_for(payload)
    return payload


def pr_for_changelog(repo):
    result = gh([
        "pr",
        "view",
        "--json",
        "number,state,mergedAt,url,title,baseRefName,headRefName,statusCheckRollup",
    ], cwd=repo)
    if result.returncode != 0:
        return None, result.stderr.strip() or result.stdout.strip()
    return json.loads(result.stdout), None


def markdown_list(items, empty="- None."):
    if not items:
        return empty
    return "\n".join(f"- {item}" for item in items)


def build_changelog_markdown(source_path, sections, pr, followups, findings):
    goal = find_section(sections, ["goal"]) or ""
    scope = find_section(sections, ["scope"]) or ""
    archive_summary = archive_summary_from_sections(sections)
    source_files = section_bullets(find_section(sections, [
        "source-of-truth files",
        "source of truth files",
        "source files",
    ]) or "")
    verification = section_bullets(find_section(sections, ["verification", "proof"]) or "")
    stale = find_section(sections, [
        "stale context warning",
        "stale-context warning",
        "stale context",
    ]) or "GitHub, branch, and thread state can change after generation."

    if pr:
        number = pr.get("number")
        url = pr.get("url") or ""
        label = f"[#{number}]({url})" if number and url else f"#{number or 'unknown'}"
        pr_rows = [f"| {label} | {pr.get('state', 'UNKNOWN')} | {redact_secrets(pr.get('title') or 'Untitled PR')} |"]
    else:
        pr_rows = ["| Cannot verify | Unknown | No current PR metadata available. |"]

    followup_lines = []
    for followup in followups:
        topic = redact_secrets(followup.get("topic", "Untitled follow-up"))
        strength = redact_secrets(followup.get("strength", "unknown strength"))
        why = redact_secrets(followup.get("why_it_matters", "No rationale supplied."))
        opener = redact_secrets(followup.get("suggested_opener", "No opener supplied."))
        followup_lines.append(f"- {topic} (`{strength}`): {why} Suggested opener: {opener}")

    cannot_verify = [
        finding["message"]
        for finding in findings
        if finding.get("severity") in {"warn", "review", "fail"}
    ]
    return "\n".join([
        "# PR Changelog",
        "",
        f"Source: `{source_path}`",
        "",
        "## Implementation Summary",
        "",
        first_nonempty_line(redact_secrets(goal)),
        "",
        "## Archive Summary",
        "",
        markdown_list(archive_summary, empty="- Cannot verify chat-level changes from CLI metadata alone. Supply an agent-authored Archive Summary in the PR changelog or closeout content."),
        "",
        "## Scope",
        "",
        redact_secrets(scope or "None supplied."),
        "",
        "## PRs",
        "",
        "| PR | State | Title |",
        "| --- | --- | --- |",
        *pr_rows,
        "",
        "## Source Files",
        "",
        markdown_list([redact_secrets(item) for item in source_files]),
        "",
        "## Verification Expected",
        "",
        markdown_list([redact_secrets(item) for item in verification]),
        "",
        "## Follow-Ups",
        "",
        markdown_list(followup_lines),
        "",
        "## Stale Context Warning",
        "",
        redact_secrets(stale.strip()),
        "",
        "## Cannot Verify",
        "",
        markdown_list(cannot_verify),
        "",
    ])


def dirty_paths(repo):
    status = git(["status", "--porcelain"], repo)
    if status.returncode != 0:
        raise RuntimeError(status.stderr.strip() or "git status failed")
    return [line[3:] if len(line) > 3 else line for line in status.stdout.splitlines() if line.strip()]


def branch_name(repo):
    branch = git(["branch", "--show-current"], repo)
    if branch.returncode != 0:
        return ""
    return branch.stdout.strip()


def upstream_counts(repo):
    upstream = git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], repo)
    if upstream.returncode != 0:
        return None
    counts = git(["rev-list", "--left-right", "--count", "@{u}...HEAD"], repo)
    if counts.returncode != 0:
        raise RuntimeError(counts.stderr.strip() or "could not compare upstream")
    parts = counts.stdout.strip().split()
    if len(parts) != 2:
        raise RuntimeError(f"unexpected upstream count output: {counts.stdout}")
    return {
        "upstream": upstream.stdout.strip(),
        "behind": int(parts[0]),
        "ahead": int(parts[1]),
    }


def run_checker(args):
    cmd = [str(CHECKER), "--archive", "--json"]
    if args.title:
        cmd += ["--title", args.title]
    if getattr(args, "suggested_title", None):
        cmd += ["--suggested-title", args.suggested_title]
    if getattr(args, "content", None):
        cmd += ["--content", str(args.content)]
    if getattr(args, "require_kickoff", False):
        cmd.append("--require-kickoff")
    if getattr(args, "require_assumptions", False):
        cmd.append("--require-assumptions")
    if getattr(args, "archive_anyway", False):
        cmd.append("--archive-anyway")

    result = run_cmd(cmd, cwd=ROOT)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"workflow etiquette checker did not emit JSON: {error}\n{result.stdout}\n{result.stderr}") from error


def checks_state(status_rollup):
    if not status_rollup:
        return "missing", "No PR status checks were reported."

    pending = []
    failing = []
    for check in status_rollup:
        typename = check.get("__typename")
        if typename == "CheckRun":
            status = check.get("status")
            conclusion = check.get("conclusion")
            name = check.get("name", "check")
            if status != "COMPLETED":
                pending.append(name)
            elif conclusion not in PASSING_CHECK_CONCLUSIONS:
                failing.append(f"{name}={conclusion}")
        else:
            state = check.get("state") or check.get("conclusion") or check.get("status")
            name = check.get("context") or check.get("name") or "status"
            if state not in PASSING_STATUS_STATES:
                failing.append(f"{name}={state}")

    if failing:
        return "failing", "PR checks are failing: " + ", ".join(failing[:4])
    if pending:
        return "pending", "PR checks are still pending: " + ", ".join(pending[:4])
    return "passing", "PR checks passed."


def current_pr(repo):
    result = gh([
        "pr",
        "view",
        "--json",
        "number,state,isDraft,mergeable,mergedAt,statusCheckRollup,url,baseRefName,headRefName,reviewDecision",
    ], cwd=repo)
    if result.returncode != 0:
        return None, result.stderr.strip() or result.stdout.strip()
    return json.loads(result.stdout), None


def github_archive_actions(repo, payload, args):
    actions = []
    if not repo:
        return actions

    repo = Path(repo).resolve()
    inside = git(["rev-parse", "--is-inside-work-tree"], repo)
    if inside.returncode != 0:
        return actions

    allow_dirty = {str(Path(path)) for path in getattr(args, "allow_dirty", [])}
    dirty = dirty_paths(repo)
    if dirty:
        unexpected_dirty = [path for path in dirty if path not in allow_dirty]
        if not unexpected_dirty:
            add_finding(
                payload,
                "dirty_worktree_allowlisted",
                "warn",
                "Dirty files are explicitly allowlisted for this archive: " + ", ".join(dirty[:4]) + ".",
            )
        elif getattr(args, "confirm_git_risk", False):
            add_finding(
                payload,
                "git_risk_confirmed",
                "warn",
                "User confirmed archive can proceed even though git has unpreserved work: "
                + ", ".join(unexpected_dirty[:4])
                + ".",
            )
        else:
            add_finding(
                payload,
                "dirty_worktree",
                "review",
                "Worktree has uncommitted or untracked files: " + ", ".join(unexpected_dirty[:4]) + ".",
            )
            add_finding(
                payload,
                "git_risk_confirmation_required",
                "review",
                "Ask the user to confirm whether this unpreserved work should be left out of git before archiving.",
            )
            return actions

    branch = branch_name(repo)
    counts = upstream_counts(repo)
    if counts and counts["behind"]:
        add_finding(
            payload,
            "branch_behind_upstream",
            "review",
            f"Branch is behind {counts['upstream']} by {counts['behind']} commit(s).",
        )
        return actions

    defaultish = branch in {"main", "master"}
    if defaultish:
        if counts and counts["ahead"]:
            if getattr(args, "confirm_git_risk", False):
                add_finding(
                    payload,
                    "default_branch_ahead_confirmed",
                    "warn",
                    "User confirmed archive can proceed even though the default branch has unpushed commits.",
                )
            else:
                add_finding(
                    payload,
                    "default_branch_ahead",
                    "review",
                    f"Default branch has {counts['ahead']} unpushed commit(s); push or confirm abandonment before archive.",
                )
                add_finding(
                    payload,
                    "git_risk_confirmation_required",
                    "review",
                    "Ask the user to confirm before archiving with unpushed default-branch commits.",
                )
        return actions

    if counts and counts["ahead"]:
        actions.append({"type": "git_push", "upstream": counts["upstream"], "ahead": counts["ahead"]})
        add_finding(
            payload,
            "branch_push_needed_before_pr_merge",
            "review",
            "Branch has local commits that must be pushed before PR checks can be trusted.",
        )
        return actions

    pr, error = current_pr(repo)
    if not pr:
        if getattr(args, "confirm_git_risk", False):
            add_finding(
                payload,
                "missing_pull_request_confirmed",
                "warn",
                "User confirmed archive can proceed without a merged pull request for this branch.",
            )
            return actions
        add_finding(
            payload,
            "missing_pull_request",
            "review",
            f"No pull request found for branch {branch}: {error or 'unknown gh error'}.",
        )
        add_finding(
            payload,
            "git_risk_confirmation_required",
            "review",
            "Ask the user to confirm before archiving work that is not merged through a PR.",
        )
        return actions

    if pr.get("state") == "MERGED" or pr.get("mergedAt"):
        return actions
    if pr.get("state") != "OPEN":
        add_finding(payload, "pull_request_not_open", "review", f"Pull request is {pr.get('state')}.")
        return actions
    if pr.get("isDraft"):
        add_finding(payload, "pull_request_is_draft", "review", "Pull request is still a draft.")
        return actions
    if pr.get("reviewDecision") in {"CHANGES_REQUESTED", "REVIEW_REQUIRED"}:
        add_finding(
            payload,
            "pull_request_review_pending",
            "review",
            f"Pull request review decision is {pr.get('reviewDecision')}.",
        )
        return actions
    if pr.get("mergeable") not in {"MERGEABLE", "UNKNOWN"}:
        add_finding(payload, "pull_request_not_mergeable", "review", f"Pull request mergeable state is {pr.get('mergeable')}.")
        return actions

    check_status, check_message = checks_state(pr.get("statusCheckRollup", []))
    if check_status != "passing":
        add_finding(payload, f"pull_request_checks_{check_status}", "review", check_message)
        return actions

    actions.append({
        "type": "gh_pr_merge",
        "prNumber": pr.get("number"),
        "url": pr.get("url"),
        "mergeMethod": "merge",
        "deleteBranch": True,
    })
    return actions


def rebuild_archive_plan(payload, git_actions):
    prior_plan = payload.get("archivePlan") or {}
    prior_actions = prior_plan.get("actions") or []
    prefix_actions = []
    archive_action = None
    for action in prior_actions:
        if action.get("type") == "archive_thread":
            archive_action = action
        elif action.get("type") != "git_push":
            prefix_actions.append(action)

    status = status_for(payload)
    payload["status"] = status
    blockers = [
        finding["code"]
        for finding in payload.get("findings", [])
        if finding.get("severity") in {"review", "fail"}
    ]
    warnings = [
        finding["code"]
        for finding in payload.get("findings", [])
        if finding.get("severity") == "warn"
    ]
    actions = [*prefix_actions, *git_actions]
    if status in {"pass", "warn"} and archive_action:
        actions.append(archive_action)

    payload["archivePlan"] = {
        "canArchive": status in {"pass", "warn"},
        "requiresReview": status in {"review", "fail"},
        "actions": actions,
        "blockers": blockers,
        "warnings": warnings,
    }
    return payload


def build_archive_payload(args):
    original_content = getattr(args, "content", None)
    temporary_content = None
    if original_content and str(original_content) == "-":
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write(sys.stdin.read())
            temporary_content = Path(handle.name)
        args.content = temporary_content

    try:
        payload = run_checker(args)
        summary, findings = archive_summary_from_content(getattr(args, "content", None))
        for finding in findings:
            add_finding(payload, finding["code"], finding["severity"], finding["message"])
        payload["archiveSummary"] = summary or {
            "source": "fallback",
            "bullets": [
                "Cannot verify chat-level changes from CLI metadata alone. Supply the PR changelog or closeout content with an Archive Summary.",
            ],
        }
        git_actions = github_archive_actions(args.git_root, payload, args)
        return rebuild_archive_plan(payload, git_actions)
    finally:
        args.content = original_content
        if temporary_content:
            temporary_content.unlink(missing_ok=True)


def execute_archive_actions(payload, git_root):
    executed = []
    remaining_app = []
    for action in payload.get("archivePlan", {}).get("actions", []):
        action_type = action.get("type")
        if action_type in APP_ACTIONS:
            remaining_app.append(action)
        elif action_type == "git_push":
            result = git(["push"], git_root)
            if result.returncode != 0:
                add_finding(payload, "git_push_failed", "fail", result.stderr.strip() or result.stdout.strip())
                break
            executed.append(action)
        elif action_type == "gh_pr_merge":
            pr_number = str(action.get("prNumber"))
            result = gh(["pr", "merge", pr_number, "--merge", "--delete-branch"], git_root)
            if result.returncode != 0:
                add_finding(payload, "gh_pr_merge_failed", "fail", result.stderr.strip() or result.stdout.strip())
                break
            executed.append(action)
        else:
            add_finding(payload, "unknown_archive_action", "fail", f"Unknown archive action: {action_type}")
            break

    payload["status"] = status_for(payload)
    payload["executedActions"] = executed
    payload["remainingAppActions"] = remaining_app if payload["status"] in {"pass", "warn"} else []
    return payload


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
        return
    print(f"Gauntlet: {payload['status']}")
    for finding in payload.get("findings", []):
        print(f"- [{finding['severity']}] {finding['code']}: {finding['message']}")
    for action in payload.get("archivePlan", {}).get("actions", []):
        print(f"- action: {action.get('type')}")


def command_archive_plan(args):
    payload = build_archive_payload(args)
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_archive_execute(args):
    payload = build_archive_payload(args)
    if payload["status"] not in {"pass", "warn"}:
        print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    payload = execute_archive_actions(payload, args.git_root)
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_followup_note(args):
    lines = [
        "Follow-up captured:",
        f"- Topic: {args.topic}",
        f"- Strength: {args.strength}",
        f"- Why it matters: {args.why}",
        f"- Context already known: {args.context}",
        f"- Suggested opener: {args.opener}",
    ]
    print("\n".join(lines))
    return 0


def command_memory_lint(args):
    payload = memory_lint_payload(args.path)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Implementation Memory lint: {payload['status']}")
        for finding in payload.get("findings", []):
            print(f"- [{finding['severity']}] {finding['code']}: {finding['message']}")
    return EXIT_CODES[payload["status"]]


def command_changelog_pr(args):
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "source": str(args.implementation_memory),
        "findings": [],
        "pr": None,
        "markdown": "",
    }
    memory_path = Path(args.implementation_memory)
    if not memory_path.exists():
        add_finding(payload, "missing_memory_file", "fail", f"Implementation Memory file does not exist: {memory_path}")
        payload["status"] = status_for(payload)
        payload["markdown"] = build_changelog_markdown(str(memory_path), {}, None, [], payload["findings"])
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(payload["markdown"])
        return EXIT_CODES[payload["status"]]

    text = read_text(memory_path)
    sections = markdown_sections(text)
    followups = parse_followups(text)
    lint = memory_lint_payload(memory_path)
    for finding in lint.get("findings", []):
        add_finding(payload, finding["code"], finding["severity"], finding["message"])

    repo = Path(args.git_root).resolve()
    inside = git(["rev-parse", "--is-inside-work-tree"], repo)
    pr = None
    if inside.returncode != 0:
        add_finding(payload, "git_root_not_repo", "warn", f"Cannot verify PR metadata because {repo} is not a git repo.")
    else:
        pr, error = pr_for_changelog(repo)
        if pr:
            payload["pr"] = {
                "number": pr.get("number"),
                "state": pr.get("state"),
                "url": pr.get("url"),
                "title": pr.get("title"),
                "baseRefName": pr.get("baseRefName"),
                "headRefName": pr.get("headRefName"),
                "mergedAt": pr.get("mergedAt"),
            }
        else:
            add_finding(payload, "cannot_verify_pr_metadata", "warn", f"Could not verify current PR metadata: {error or 'unknown gh error'}.")

    payload["status"] = status_for(payload)
    payload["markdown"] = build_changelog_markdown(display_path(Path.cwd().resolve(), memory_path), sections, pr, followups, payload["findings"])
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload["markdown"], encoding="utf-8")
        payload["output"] = str(output)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(payload["markdown"])
    return EXIT_CODES[payload["status"]]


def payload_from_args(args):
    payload = {}
    if getattr(args, "payload_file", None):
        path = Path(args.payload_file)
        if not path.exists():
            raise RuntimeError(f"Payload file does not exist: {path}")
        payload.update(json.loads(read_text(path)))
    if getattr(args, "payload_json", None):
        payload.update(json.loads(args.payload_json))
    return payload


def print_json_or_brief(payload, as_json, brief):
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        print(brief)


def command_analytics_emit(args):
    payload = payload_from_args(args)
    event, path = append_analytics_event(
        args.project_root,
        args.event_type,
        args.run_id,
        payload,
        agent=args.agent,
        gauntlet_version=args.gauntlet_version,
        path=args.path,
        dry_run=args.dry_run,
        created_at=args.created_at,
    )
    result = {
        "schemaVersion": "1.0",
        "status": "pass",
        "localPrivate": True,
        "path": str(path),
        "dryRun": args.dry_run,
        "event": event,
        "findings": [],
    }
    if args.event_type not in ANALYTICS_EVENT_TYPES:
        add_finding(
            result,
            "unknown_event_type",
            "warn",
            f"Event type is not in Gauntlet's known local analytics vocabulary: {args.event_type}.",
        )
        result["status"] = status_for(result)
    print_json_or_brief(result, args.json, f"Analytics event recorded: {args.event_type}")
    return EXIT_CODES[result["status"]]


def command_analytics_closeout(args):
    attempt_memory_expired = 0
    if args.expire_attempt_memory:
        memory_path = attempt_memory_path(args.project_root, args.attempt_memory_path)
        entries = read_attempt_entries(memory_path)
        kept = [
            entry for entry in entries
            if args.run_id not in set(entry.get("runIds") or [])
        ]
        attempt_memory_expired = len(entries) - len(kept)
        write_attempt_entries(memory_path, kept)

    summary = {
        "filesChanged": args.file_changed,
        "filesChangedCount": len(args.file_changed),
        "proofCompleted": args.proof,
        "testsCompletedCount": len(args.proof),
        "unresolvedRisks": args.risk,
        "attemptMemoryExpired": attempt_memory_expired,
    }
    event_payload = {
        "files_changed": args.file_changed,
        "files_changed_count": len(args.file_changed),
        "proof_commands": args.proof,
        "proof_completed_count": len(args.proof),
        "risk_notes": args.risk,
        "unresolved_risk_count": len(args.risk),
        "attempt_memory_expired": attempt_memory_expired,
    }
    event, path = append_analytics_event(
        args.project_root,
        "closeout_completed",
        args.run_id,
        event_payload,
        agent=args.agent,
        gauntlet_version=args.gauntlet_version,
        path=args.path,
    )
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "localPrivate": True,
        "path": str(path),
        "summary": summary,
        "event": event,
        "actions": [],
        "attemptMemoryExpired": attempt_memory_expired,
        "findings": [],
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("Gauntlet Closeout Facts")
        print(f"- Files changed: {summary['filesChangedCount']}")
        for item in summary["filesChanged"]:
            print(f"  - {item}")
        print(f"- Proof/tests completed: {summary['testsCompletedCount']}")
        for item in summary["proofCompleted"]:
            print(f"  - {item}")
        print("- Unresolved risks:")
        for item in summary["unresolvedRisks"] or ["None reported."]:
            print(f"  - {item}")
        print(f"- Attempt memory expired: {attempt_memory_expired}")
    return 0


def command_analytics_summarize(args):
    path = analytics_events_path(args.project_root, args.path)
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "localPrivate": True,
        "path": str(path),
        "baseline": {"label": args.baseline},
        "candidate": {"label": args.candidate},
        "confidence": "no claim",
        "segments": [],
        "findings": [],
    }
    if not args.baseline or not args.candidate:
        add_finding(
            payload,
            "missing_baseline_or_candidate",
            "review",
            "Provide both --baseline and --candidate so Gauntlet does not guess which cohorts to compare.",
        )
        payload["status"] = status_for(payload)
        print_json_or_brief(payload, args.json, "Need --baseline and --candidate to summarize impact.")
        return EXIT_CODES[payload["status"]]

    events = read_analytics_events(path)
    baseline_events = [event for event in events if event_cohort(event) == args.baseline]
    candidate_events = [event for event in events if event_cohort(event) == args.candidate]
    baseline_summary = cohort_summary(baseline_events, stale_wait_seconds=args.stale_wait_seconds)
    candidate_summary = cohort_summary(candidate_events, stale_wait_seconds=args.stale_wait_seconds)
    payload["baseline"].update(baseline_summary)
    payload["candidate"].update(candidate_summary)
    payload["confidence"] = confidence_label(baseline_summary["runs"], candidate_summary["runs"])
    payload["segments"] = segment_summaries(baseline_events, candidate_events)
    if payload["confidence"] == "no claim":
        add_finding(
            payload,
            "insufficient_comparable_samples",
            "warn",
            "One or both cohorts have no comparable local runs.",
        )
    elif payload["confidence"] == "anecdotal":
        payload["note"] = "Counts are useful for review but too small for a strong public claim."
    payload["status"] = status_for(payload)

    derived = analytics_dir(args.project_root) / "derived-summary.json"
    derived.parent.mkdir(parents=True, exist_ok=True)
    derived.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    payload["derivedSummary"] = str(derived)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Analytics summary: {args.baseline} -> {args.candidate} ({payload['confidence']})")
        print(f"- Baseline runs: {baseline_summary['runs']} events: {baseline_summary['events']}")
        print(f"- Candidate runs: {candidate_summary['runs']} events: {candidate_summary['events']}")
    return EXIT_CODES[payload["status"]]


def read_attempt_entries(path):
    path = Path(path)
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def write_attempt_entries(path, entries):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")


def prune_attempt_entries(entries, max_age_days=None, now=None):
    if max_age_days is None:
        return entries
    now_time = parse_event_time(now) if now else datetime.now(timezone.utc)
    if not now_time:
        return entries
    max_age_seconds = max_age_days * 86400
    kept = []
    for entry in entries:
        last_seen = parse_event_time(entry.get("lastSeen"))
        if not last_seen:
            kept.append(entry)
            continue
        age = int((now_time - last_seen).total_seconds())
        if age <= max_age_seconds:
            kept.append(entry)
    return kept


def command_attempt_memory_add(args):
    project_root = Path(args.project_root).resolve()
    salt = local_salt(project_root)
    path = attempt_memory_path(project_root, args.path)
    entries = read_attempt_entries(path)
    fingerprint_hash = local_hash(args.fingerprint, salt)
    now = utc_timestamp()
    found = None
    for entry in entries:
        if entry.get("fingerprintHash") == fingerprint_hash:
            found = entry
            break
    if found:
        found["repeatCount"] = int(found.get("repeatCount", 1)) + 1
        found["lastSeen"] = now
        found["summary"] = redact_secrets(args.summary)
        found["kind"] = args.kind
        run_ids = list(dict.fromkeys([*(found.get("runIds") or []), args.run_id]))
        found["runIds"] = [run_id for run_id in run_ids if run_id]
    else:
        entries.append({
            "schemaVersion": "1.0",
            "kind": args.kind,
            "fingerprintHash": fingerprint_hash,
            "summary": redact_secrets(args.summary),
            "repeatCount": 1,
            "firstSeen": now,
            "lastSeen": now,
            "runIds": [args.run_id] if args.run_id else [],
        })

    entries = prune_attempt_entries(entries, max_age_days=args.max_age_days, now=args.now)
    entries = sorted(entries, key=lambda item: item.get("lastSeen", ""))[-args.max_active:]
    write_attempt_entries(path, entries)
    event, event_path = append_analytics_event(
        project_root,
        "attempt_memory_written",
        args.run_id,
        {
            "kind": args.kind,
            "fingerprint_hash": fingerprint_hash,
            "active_count": len(entries),
        },
        agent=args.agent,
        gauntlet_version=args.gauntlet_version,
        path=args.analytics_path,
    )
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "localPrivate": True,
        "path": str(path),
        "analyticsPath": str(event_path),
        "activeCount": len(entries),
        "entry": next((entry for entry in entries if entry.get("fingerprintHash") == fingerprint_hash), None),
        "event": event,
        "findings": [],
    }
    print_json_or_brief(payload, args.json, f"Attempt memory entries: {len(entries)}")
    return 0


def command_attempt_memory_list(args):
    project_root = Path(args.project_root).resolve()
    path = attempt_memory_path(project_root, args.path)
    entries = read_attempt_entries(path)
    pruned_entries = prune_attempt_entries(entries, max_age_days=args.max_age_days, now=args.now)
    if pruned_entries != entries:
        write_attempt_entries(path, pruned_entries)
    entries = pruned_entries
    event, event_path = append_analytics_event(
        project_root,
        "attempt_memory_read",
        args.run_id,
        {"active_count": len(entries)},
        agent=args.agent,
        gauntlet_version=args.gauntlet_version,
        path=args.analytics_path,
    )
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "localPrivate": True,
        "path": str(path),
        "analyticsPath": str(event_path),
        "activeCount": len(entries),
        "entries": entries,
        "event": event,
        "findings": [],
    }
    print_json_or_brief(payload, args.json, f"Attempt memory entries: {len(entries)}")
    return 0


def followup_from_args(args):
    if args.content:
        if not args.content.exists():
            return {}, [{"code": "missing_followup_file", "severity": "fail", "message": f"Follow-up content file does not exist: {args.content}."}]
        followups = parse_followups(read_text(args.content))
        if followups:
            return followups[0], []
        return {}, [{"code": "missing_followup_block", "severity": "fail", "message": f"No follow-up block found in {args.content}."}]
    required = {
        "topic": args.topic,
        "strength": args.strength,
        "why_it_matters": args.why,
        "context_already_known": args.context,
        "suggested_opener": args.opener,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        return {}, [{"code": "missing_followup_fields", "severity": "fail", "message": "Missing follow-up fields: " + ", ".join(missing) + "."}]
    return required, []


def command_followup_thread(args):
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "findings": [],
        "actions": [],
    }
    if not TITLE_PATTERN.match(args.title):
        add_finding(payload, "malformed_thread_title", "fail", "Thread title must start with p0-p4 or p#-auto, followed by a colon.")

    followup, findings = followup_from_args(args)
    for finding in findings:
        add_finding(payload, finding["code"], finding["severity"], finding["message"])
    if followup and has_secret("\n".join(followup.values())):
        add_finding(
            payload,
            "secret_like_followup_content",
            "fail",
            "Follow-up content contains secret-like text; redact it before creating a thread packet.",
        )

    if payload["findings"]:
        payload["status"] = status_for(payload)
    else:
        source_line = f"Source thread: {args.source_thread}" if args.source_thread else "Source thread: not supplied"
        message = "\n".join([
            followup.get("suggested_opener", ""),
            "",
            "Follow-up captured:",
            f"- Topic: {followup.get('topic', '')}",
            f"- Strength: {followup.get('strength', '')}",
            f"- Why it matters: {followup.get('why_it_matters', '')}",
            f"- Context already known: {followup.get('context_already_known', '')}",
            f"- Suggested opener: {followup.get('suggested_opener', '')}",
            f"- {source_line}",
        ]).strip()
        payload["actions"].append({
            "type": "create_thread",
            "title": args.title,
            "cwd": str(Path(args.cwd).resolve()) if args.cwd else str(Path.cwd().resolve()),
            "message": message,
        })
        payload["status"] = status_for(payload)

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Follow-up thread packet: {payload['status']}")
        for action in payload.get("actions", []):
            print(f"- action: {action['type']} title={action['title']}")
        for finding in payload.get("findings", []):
            print(f"- [{finding['severity']}] {finding['code']}: {finding['message']}")
    return EXIT_CODES[payload["status"]]


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
    require(agent_home / "gauntlet" / "scripts" / "check-gauntlet-workflow.py", "missing_installed_workflow_check")
    require(agent_home / "gauntlet" / "scripts" / "gauntlet.py", "missing_installed_gauntlet_cli")
    require(agent_home / "skills", "missing_installed_skills")

    if args.target == "codex":
        require(agent_home / "AGENTS.md", "missing_codex_agents")
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


def add_archive_args(parser):
    parser.add_argument("--title", default=None)
    parser.add_argument("--suggested-title", default=None)
    parser.add_argument("--content", type=Path, default=None)
    parser.add_argument("--git-root", type=Path, default=Path.cwd())
    parser.add_argument("--require-kickoff", action="store_true")
    parser.add_argument("--require-assumptions", action="store_true")
    parser.add_argument("--archive-anyway", action="store_true")
    parser.add_argument("--confirm-git-risk", action="store_true")
    parser.add_argument("--allow-dirty", action="append", default=[])
    parser.add_argument("--json", action="store_true")


def build_parser():
    parser = argparse.ArgumentParser(description="Gauntlet workflow helper CLI.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    archive = subcommands.add_parser("archive", help="Plan or execute archive-safe actions.")
    archive_subcommands = archive.add_subparsers(dest="archive_command", required=True)
    archive_plan = archive_subcommands.add_parser("plan")
    add_archive_args(archive_plan)
    archive_plan.set_defaults(func=command_archive_plan)
    archive_execute = archive_subcommands.add_parser("execute")
    add_archive_args(archive_execute)
    archive_execute.set_defaults(func=command_archive_execute)

    install = subcommands.add_parser("install", help="Installed-layout helpers.")
    install_subcommands = install.add_subparsers(dest="install_command", required=True)
    install_verify = install_subcommands.add_parser("verify")
    install_verify.add_argument("--target", choices=["codex", "claude"], required=True)
    install_verify.add_argument("--agent-home", required=True)
    install_verify.add_argument("--json", action="store_true")
    install_verify.set_defaults(func=command_install_verify)

    followup = subcommands.add_parser("followup", help="Follow-up helpers.")
    followup_subcommands = followup.add_subparsers(dest="followup_command", required=True)
    followup_note = followup_subcommands.add_parser("note")
    followup_note.add_argument("--topic", required=True)
    followup_note.add_argument("--strength", choices=["strong follow-up", "follow-up for later"], required=True)
    followup_note.add_argument("--why", required=True)
    followup_note.add_argument("--context", required=True)
    followup_note.add_argument("--opener", required=True)
    followup_note.set_defaults(func=command_followup_note)
    followup_thread = followup_subcommands.add_parser("thread")
    followup_thread.add_argument("--content", type=Path, default=None)
    followup_thread.add_argument("--topic", default=None)
    followup_thread.add_argument("--strength", choices=["strong follow-up", "follow-up for later"], default=None)
    followup_thread.add_argument("--why", default=None)
    followup_thread.add_argument("--context", default=None)
    followup_thread.add_argument("--opener", default=None)
    followup_thread.add_argument("--title", required=True)
    followup_thread.add_argument("--cwd", type=Path, default=None)
    followup_thread.add_argument("--source-thread", default=None)
    followup_thread.add_argument("--json", action="store_true")
    followup_thread.set_defaults(func=command_followup_thread)

    memory = subcommands.add_parser("memory", help="Implementation Memory helpers.")
    memory_subcommands = memory.add_subparsers(dest="memory_command", required=True)
    memory_lint = memory_subcommands.add_parser("lint")
    memory_lint.add_argument("--path", type=Path, required=True)
    memory_lint.add_argument("--json", action="store_true")
    memory_lint.set_defaults(func=command_memory_lint)

    analytics = subcommands.add_parser("analytics", help="Local private analytics helpers.")
    analytics_subcommands = analytics.add_subparsers(dest="analytics_command", required=True)
    analytics_emit = analytics_subcommands.add_parser("emit")
    analytics_emit.add_argument("--project-root", type=Path, default=Path.cwd())
    analytics_emit.add_argument("--path", type=Path, default=None)
    analytics_emit.add_argument("--run-id", default=None)
    analytics_emit.add_argument("--event-type", required=True)
    analytics_emit.add_argument("--created-at", default=None)
    analytics_emit.add_argument("--payload-json", default=None)
    analytics_emit.add_argument("--payload-file", type=Path, default=None)
    analytics_emit.add_argument("--agent", default="codex")
    analytics_emit.add_argument("--gauntlet-version", default="2.0.2")
    analytics_emit.add_argument("--dry-run", action="store_true")
    analytics_emit.add_argument("--json", action="store_true")
    analytics_emit.set_defaults(func=command_analytics_emit)

    analytics_closeout = analytics_subcommands.add_parser("closeout")
    analytics_closeout.add_argument("--project-root", type=Path, default=Path.cwd())
    analytics_closeout.add_argument("--path", type=Path, default=None)
    analytics_closeout.add_argument("--run-id", default=None)
    analytics_closeout.add_argument("--file-changed", action="append", default=[])
    analytics_closeout.add_argument("--proof", action="append", default=[])
    analytics_closeout.add_argument("--risk", action="append", default=[])
    analytics_closeout.add_argument("--attempt-memory-path", type=Path, default=None)
    analytics_closeout.add_argument("--expire-attempt-memory", action="store_true")
    analytics_closeout.add_argument("--agent", default="codex")
    analytics_closeout.add_argument("--gauntlet-version", default="2.0.2")
    analytics_closeout.add_argument("--json", action="store_true")
    analytics_closeout.set_defaults(func=command_analytics_closeout)

    analytics_summarize = analytics_subcommands.add_parser("summarize")
    analytics_summarize.add_argument("--project-root", type=Path, default=Path.cwd())
    analytics_summarize.add_argument("--path", type=Path, default=None)
    analytics_summarize.add_argument("--baseline", default=None)
    analytics_summarize.add_argument("--candidate", default=None)
    analytics_summarize.add_argument("--stale-wait-seconds", type=int, default=86400)
    analytics_summarize.add_argument("--json", action="store_true")
    analytics_summarize.set_defaults(func=command_analytics_summarize)

    attempt_memory = subcommands.add_parser("attempt-memory", help="Bounded local attempt memory helpers.")
    attempt_memory_subcommands = attempt_memory.add_subparsers(dest="attempt_memory_command", required=True)
    attempt_memory_add = attempt_memory_subcommands.add_parser("add")
    attempt_memory_add.add_argument("--project-root", type=Path, default=Path.cwd())
    attempt_memory_add.add_argument("--path", type=Path, default=None)
    attempt_memory_add.add_argument("--analytics-path", type=Path, default=None)
    attempt_memory_add.add_argument("--run-id", default=None)
    attempt_memory_add.add_argument("--kind", choices=["failed_attempt", "proof_failure", "rejected_alternative", "observation"], required=True)
    attempt_memory_add.add_argument("--fingerprint", required=True)
    attempt_memory_add.add_argument("--summary", required=True)
    attempt_memory_add.add_argument("--max-active", type=int, default=50)
    attempt_memory_add.add_argument("--max-age-days", type=int, default=None)
    attempt_memory_add.add_argument("--now", default=None)
    attempt_memory_add.add_argument("--agent", default="codex")
    attempt_memory_add.add_argument("--gauntlet-version", default="2.0.2")
    attempt_memory_add.add_argument("--json", action="store_true")
    attempt_memory_add.set_defaults(func=command_attempt_memory_add)

    attempt_memory_list = attempt_memory_subcommands.add_parser("list")
    attempt_memory_list.add_argument("--project-root", type=Path, default=Path.cwd())
    attempt_memory_list.add_argument("--path", type=Path, default=None)
    attempt_memory_list.add_argument("--analytics-path", type=Path, default=None)
    attempt_memory_list.add_argument("--run-id", default=None)
    attempt_memory_list.add_argument("--max-age-days", type=int, default=None)
    attempt_memory_list.add_argument("--now", default=None)
    attempt_memory_list.add_argument("--agent", default="codex")
    attempt_memory_list.add_argument("--gauntlet-version", default="2.0.2")
    attempt_memory_list.add_argument("--json", action="store_true")
    attempt_memory_list.set_defaults(func=command_attempt_memory_list)

    changelog = subcommands.add_parser("changelog", help="Changelog generation helpers.")
    changelog_subcommands = changelog.add_subparsers(dest="changelog_command", required=True)
    changelog_pr = changelog_subcommands.add_parser("pr")
    changelog_pr.add_argument("--implementation-memory", type=Path, required=True)
    changelog_pr.add_argument("--git-root", type=Path, default=Path.cwd())
    changelog_pr.add_argument("--output", type=Path, default=None)
    changelog_pr.add_argument("--json", action="store_true")
    changelog_pr.set_defaults(func=command_changelog_pr)

    diagram = subcommands.add_parser("diagram", help="Saved diagram helpers.")
    diagram_subcommands = diagram.add_subparsers(dest="diagram_command", required=True)
    diagram_find = diagram_subcommands.add_parser("find")
    diagram_find.add_argument("--query", required=True)
    diagram_find.add_argument("--json", action="store_true")
    diagram_find.set_defaults(func=command_diagram_find)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except RuntimeError as error:
        payload = {
            "schemaVersion": "1.0",
            "status": "fail",
            "findings": [{"code": "command_failed", "severity": "fail", "message": str(error)}],
        }
        print_payload(payload, getattr(args, "json", False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
