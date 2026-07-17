"""Command handlers for local analytics emission, closeout, and summaries."""

import json
from pathlib import Path

from gauntletlib.cli import EXIT_CODES, print_json_or_brief
from gauntletlib.core.findings import add_finding, status_for

from .attempt_memory import attempt_memory_path, read_attempt_entries, write_attempt_entries
from .events import (
    ANALYTICS_EVENT_TYPES,
    analytics_dir,
    analytics_events_path,
    append_analytics_event,
    cohort_summary,
    confidence_label,
    event_cohort,
    read_analytics_events,
    segment_summaries,
)


def _read_text(path):
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def payload_from_args(args):
    payload = {}
    if getattr(args, "payload_file", None):
        path = Path(args.payload_file)
        if not path.exists():
            raise RuntimeError(f"Payload file does not exist: {path}")
        payload.update(json.loads(_read_text(path)))
    if getattr(args, "payload_json", None):
        payload.update(json.loads(args.payload_json))
    return payload


def command_emit(args):
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
            result["findings"],
            "unknown_event_type",
            "warn",
            f"Event type is not in Gauntlet's known local analytics vocabulary: {args.event_type}.",
        )
        result["status"] = status_for(result["findings"])
    print_json_or_brief(result, args.json, f"Analytics event recorded: {args.event_type}")
    return EXIT_CODES[result["status"]]


def command_closeout(args):
    attempt_memory_expired = 0
    if args.expire_attempt_memory:
        memory_path = attempt_memory_path(args.project_root, args.attempt_memory_path)
        entries = read_attempt_entries(memory_path)
        kept = [
            entry for entry in entries if args.run_id not in set(entry.get("runIds") or [])
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


def command_summarize(args):
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
            payload["findings"],
            "missing_baseline_or_candidate",
            "review",
            "Provide both --baseline and --candidate so Gauntlet does not guess which cohorts to compare.",
        )
        payload["status"] = status_for(payload["findings"])
        print_json_or_brief(
            payload,
            args.json,
            "Need --baseline and --candidate to summarize impact.",
        )
        return EXIT_CODES[payload["status"]]

    events = read_analytics_events(path)
    baseline_events = [event for event in events if event_cohort(event) == args.baseline]
    candidate_events = [event for event in events if event_cohort(event) == args.candidate]
    baseline_summary = cohort_summary(
        baseline_events,
        stale_wait_seconds=args.stale_wait_seconds,
    )
    candidate_summary = cohort_summary(
        candidate_events,
        stale_wait_seconds=args.stale_wait_seconds,
    )
    payload["baseline"].update(baseline_summary)
    payload["candidate"].update(candidate_summary)
    payload["confidence"] = confidence_label(
        baseline_summary["runs"],
        candidate_summary["runs"],
    )
    payload["segments"] = segment_summaries(baseline_events, candidate_events)
    if payload["confidence"] == "no claim":
        add_finding(
            payload["findings"],
            "insufficient_comparable_samples",
            "warn",
            "One or both cohorts have no comparable local runs.",
        )
    elif payload["confidence"] == "anecdotal":
        payload["note"] = "Counts are useful for review but too small for a strong public claim."
    payload["status"] = status_for(payload["findings"])

    derived = analytics_dir(args.project_root) / "derived-summary.json"
    derived.parent.mkdir(parents=True, exist_ok=True)
    derived.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    payload["derivedSummary"] = str(derived)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(
            f"Analytics summary: {args.baseline} -> {args.candidate} "
            f"({payload['confidence']})"
        )
        print(
            f"- Baseline runs: {baseline_summary['runs']} "
            f"events: {baseline_summary['events']}"
        )
        print(
            f"- Candidate runs: {candidate_summary['runs']} "
            f"events: {candidate_summary['events']}"
        )
    return EXIT_CODES[payload["status"]]
