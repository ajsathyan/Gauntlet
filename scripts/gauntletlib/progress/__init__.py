"""Progress projection and dashboard lifecycle support."""

import argparse
from pathlib import Path

from .supervisor import command_epic_tasks_progress_stop
from .supervisor import command_epic_tasks_progress_supervise
from .supervisor import configure as configure
from .supervisor import progress_browser_action as progress_browser_action
from .supervisor import safely_ensure_progress_supervisor as safely_ensure_progress_supervisor
from .supervisor import safely_progress_dashboard_status as safely_progress_dashboard_status


def register(subcommands, refresh_seconds):
    supervise = subcommands.add_parser(
        "progress-supervise", help=argparse.SUPPRESS
    )
    supervise.add_argument(
        "--git-root", type=Path, default=Path.cwd()
    )
    supervise.add_argument("--launch-set", type=Path, required=True)
    supervise.add_argument(
        "--interval", type=float, default=refresh_seconds
    )
    supervise.set_defaults(func=command_epic_tasks_progress_supervise)
    stop = subcommands.add_parser(
        "progress-stop",
        help="Idempotently stop a launch-scoped progress dashboard.",
    )
    stop.add_argument("--launch-set", type=Path, required=True)
    stop.add_argument("--json", action="store_true")
    stop.set_defaults(func=command_epic_tasks_progress_stop)
