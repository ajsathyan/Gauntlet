"""Local private analytics and bounded attempt-memory commands."""

from pathlib import Path

from .attempt_memory import command_add as command_attempt_memory_add
from .attempt_memory import command_list as command_attempt_memory_list
from .commands import command_closeout as command_analytics_closeout
from .commands import command_emit as command_analytics_emit
from .commands import command_summarize as command_analytics_summarize


def register(subparsers):
    analytics = subparsers.add_parser("analytics", help="Local private analytics helpers.")
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

    attempt_memory = subparsers.add_parser("attempt-memory", help="Bounded local attempt memory helpers.")
    attempt_memory_subcommands = attempt_memory.add_subparsers(dest="attempt_memory_command", required=True)
    attempt_memory_add = attempt_memory_subcommands.add_parser("add")
    attempt_memory_add.add_argument("--project-root", type=Path, default=Path.cwd())
    attempt_memory_add.add_argument("--path", type=Path, default=None)
    attempt_memory_add.add_argument("--analytics-path", type=Path, default=None)
    attempt_memory_add.add_argument("--run-id", default=None)
    attempt_memory_add.add_argument(
        "--kind",
        choices=["failed_attempt", "proof_failure", "rejected_alternative", "observation"],
        required=True,
    )
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
