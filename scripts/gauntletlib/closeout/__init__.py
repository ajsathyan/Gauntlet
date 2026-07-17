"""Closeout, archive, follow-up, memory, and changelog support."""

import argparse
from pathlib import Path

from .workflow import advance_run_release_state as advance_run_release_state
from .workflow import completion_allows_archive as completion_allows_archive
from .workflow import command_archive_execute
from .workflow import command_archive_plan
from .workflow import command_changelog_pr
from .workflow import command_closeout_execute
from .workflow import command_followup_note
from .workflow import command_followup_thread
from .workflow import command_memory_lint
from .workflow import configure as configure
from .workflow import closeout_install_command as closeout_install_command


def _add_archive_args(parser):
    parser.add_argument("--title", default=None)
    parser.add_argument("--suggested-title", default=None)
    parser.add_argument("--content", type=Path, default=None)
    parser.add_argument(
        "--run",
        type=Path,
        default=None,
        help=(
            "Use a deterministic Epic completion projection instead of an "
            "authored Archive Summary."
        ),
    )
    parser.add_argument("--git-root", type=Path, default=Path.cwd())
    parser.add_argument("--require-kickoff", action="store_true")
    parser.add_argument("--require-assumptions", action="store_true")
    parser.add_argument("--archive-anyway", action="store_true")
    parser.add_argument("--confirm-git-risk", action="store_true")
    parser.add_argument("--allow-dirty", action="append", default=[])
    parser.add_argument("--json", action="store_true")


def register_archive(subparsers):
    archive = subparsers.add_parser(
        "archive", help="Plan or execute archive-safe actions."
    )
    archive_commands = archive.add_subparsers(
        dest="archive_command", required=True
    )
    for name, func in [
        ("plan", command_archive_plan),
        ("execute", command_archive_execute),
    ]:
        command = archive_commands.add_parser(name)
        _add_archive_args(command)
        command.set_defaults(func=func)



def register_closeout(subparsers):
    closeout = subparsers.add_parser(
        "closeout",
        help=(
            "Commit scoped work, merge it through a PR, install it locally, "
            "and plan task archival."
        ),
    )
    commands = closeout.add_subparsers(
        dest="closeout_command", required=True
    )
    execute = commands.add_parser("execute")
    execute.add_argument("--git-root", type=Path, default=Path.cwd())
    execute.add_argument("--handoff", type=Path, default=None)
    execute.add_argument("--run", type=Path, default=None)
    execute.add_argument("--stage", action="append", default=[])
    execute.add_argument(
        "--install-target",
        choices=["none", "codex"],
        default="none",
    )
    execute.add_argument("--agent-home", default=None)
    execute.add_argument("--instructions-reviewed", action="store_true")
    execute.add_argument(
        "--response-style",
        choices=["gauntlet", "existing"],
        default="gauntlet",
    )
    execute.add_argument(
        "--codex-preferences",
        choices=["prompt", "gauntlet", "existing", "skip"],
        default="prompt",
    )
    execute.add_argument("--title", required=True)
    execute.add_argument("--suggested-title", default=None)
    execute.add_argument("--content", type=Path, default=None)
    execute.add_argument("--json", action="store_true")
    execute.set_defaults(func=command_closeout_execute)



def register_followup_memory(subparsers):
    followup = subparsers.add_parser(
        "followup", help="Follow-up helpers."
    )
    followup_commands = followup.add_subparsers(
        dest="followup_command", required=True
    )
    note = followup_commands.add_parser("note")
    note.add_argument("--topic", required=True)
    note.add_argument(
        "--strength",
        choices=["strong follow-up", "follow-up for later"],
        required=True,
    )
    note.add_argument("--why", required=True)
    note.add_argument("--context", required=True)
    note.add_argument("--opener", required=True)
    note.set_defaults(func=command_followup_note)
    thread = followup_commands.add_parser("thread")
    thread.add_argument("--content", type=Path, default=None)
    thread.add_argument("--topic", default=None)
    thread.add_argument(
        "--strength",
        choices=["strong follow-up", "follow-up for later"],
        default=None,
    )
    thread.add_argument("--why", default=None)
    thread.add_argument("--context", default=None)
    thread.add_argument("--opener", default=None)
    thread.add_argument("--title", required=True)
    thread.add_argument("--cwd", type=Path, default=None)
    thread.add_argument("--source-thread", default=None)
    thread.add_argument("--json", action="store_true")
    thread.set_defaults(func=command_followup_thread)

    memory = subparsers.add_parser(
        "memory", help="Implementation Memory helpers."
    )
    memory_commands = memory.add_subparsers(
        dest="memory_command", required=True
    )
    lint = memory_commands.add_parser("lint")
    lint.add_argument("--path", type=Path, required=True)
    lint.add_argument("--json", action="store_true")
    lint.set_defaults(func=command_memory_lint)



def register_changelog(subparsers):
    changelog = subparsers.add_parser(
        "changelog", help="Changelog generation helpers."
    )
    changelog_commands = changelog.add_subparsers(
        dest="changelog_command", required=True
    )
    pr = changelog_commands.add_parser("pr")
    pr.add_argument("--accepted-spec", type=Path, default=None)
    pr.add_argument("--plan", type=Path, default=None)
    pr.add_argument(
        "--implementation-memory",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    pr.add_argument("--git-root", type=Path, default=Path.cwd())
    pr.add_argument("--output", type=Path, default=None)
    pr.add_argument("--json", action="store_true")
    pr.set_defaults(func=command_changelog_pr)
