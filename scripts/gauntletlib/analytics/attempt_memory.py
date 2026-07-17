"""Bounded local attempt-memory storage and commands."""

import json
from datetime import datetime, timezone
from pathlib import Path

from gauntletlib.cli import print_json_or_brief
from gauntletlib.core.redact import redact_secrets
from gauntletlib.core.timefmt import utc_timestamp

from .events import append_analytics_event, local_hash, local_salt, parse_event_time


def attempt_memory_path(project_root, path=None):
    return Path(path) if path else Path(project_root) / ".gauntlet" / "attempt-memory.jsonl"


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


def command_add(args):
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
        entries.append(
            {
                "schemaVersion": "1.0",
                "kind": args.kind,
                "fingerprintHash": fingerprint_hash,
                "summary": redact_secrets(args.summary),
                "repeatCount": 1,
                "firstSeen": now,
                "lastSeen": now,
                "runIds": [args.run_id] if args.run_id else [],
            }
        )

    entries = prune_attempt_entries(entries, max_age_days=args.max_age_days, now=args.now)
    entries = sorted(entries, key=lambda item: item.get("lastSeen", ""))[-args.max_active :]
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
        "entry": next(
            (entry for entry in entries if entry.get("fingerprintHash") == fingerprint_hash),
            None,
        ),
        "event": event,
        "findings": [],
    }
    print_json_or_brief(payload, args.json, f"Attempt memory entries: {len(entries)}")
    return 0


def command_list(args):
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
