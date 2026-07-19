"""Thin JSON command surface for the generic local workstream queue."""

from __future__ import annotations

import json
from pathlib import Path

from .queue import QueueError, TERMINAL_RESULTS, WorkstreamQueue


COMMAND_SCHEMA = "gauntlet.workstream-command.v1"


def _queue(args):
    return WorkstreamQueue(
        args.state,
        args.repo,
        default_ref=args.default_ref,
    )


def _emit(payload):
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))


def _run(args, action, operation):
    try:
        queue = _queue(args)
        result = operation(queue)
        payload = {
            "schemaVersion": COMMAND_SCHEMA,
            "status": "pass",
            "action": action,
            "state": result if isinstance(result, dict) and "entries" in result else queue.snapshot(),
        }
        if payload["state"] is not result:
            payload["result"] = result
        _emit(payload)
        return 0
    except (QueueError, OSError) as error:
        _emit(
            {
                "schemaVersion": COMMAND_SCHEMA,
                "status": "fail",
                "action": action,
                "error": {
                    "code": "workstream_queue_error",
                    "message": str(error),
                },
            }
        )
        return 1


def _snapshot(args):
    return _run(args, "snapshot", lambda queue: queue.snapshot())


def _enqueue(args):
    return _run(
        args,
        "enqueue",
        lambda queue: queue.enqueue(args.workstream, args.source_commit),
    )


def _claim(args):
    return _run(args, "claim", lambda queue: queue.claim())


def _bind_candidate(args):
    return _run(
        args,
        "bind-candidate",
        lambda queue: queue.bind_candidate(
            args.attempt,
            args.candidate_commit,
            args.candidate_tree,
        ),
    )


def _release(args):
    return _run(
        args,
        "release",
        lambda queue: queue.release(args.attempt, args.result, args.reason),
    )


def _reconcile(args):
    return _run(args, "reconcile", lambda queue: queue.reconcile())


def _common(command):
    command.add_argument("--state", type=Path, required=True)
    command.add_argument("--repo", type=Path, required=True)
    command.add_argument("--default-ref", default="main")
    command.add_argument("--json", action="store_true", help="Emit JSON.")


def register(subparsers):
    """Register the deterministic workstream queue command family."""

    workstreams = subparsers.add_parser(
        "workstreams",
        help="Serialize local workstreams against an exact Git default head.",
    )
    commands = workstreams.add_subparsers(
        dest="workstreams_command",
        required=True,
    )

    snapshot = commands.add_parser("snapshot")
    _common(snapshot)
    snapshot.set_defaults(func=_snapshot)

    enqueue = commands.add_parser("enqueue")
    _common(enqueue)
    enqueue.add_argument("--workstream", required=True)
    enqueue.add_argument("--source-commit", required=True)
    enqueue.set_defaults(func=_enqueue)

    claim = commands.add_parser("claim")
    _common(claim)
    claim.set_defaults(func=_claim)

    bind = commands.add_parser("bind-candidate")
    _common(bind)
    bind.add_argument("--attempt", required=True)
    bind.add_argument("--candidate-commit", required=True)
    bind.add_argument("--candidate-tree", required=True)
    bind.set_defaults(func=_bind_candidate)

    release = commands.add_parser("release")
    _common(release)
    release.add_argument("--attempt", required=True)
    release.add_argument("--result", choices=TERMINAL_RESULTS, required=True)
    release.add_argument("--reason", required=True)
    release.set_defaults(func=_release)

    reconcile = commands.add_parser("reconcile")
    _common(reconcile)
    reconcile.set_defaults(func=_reconcile)
