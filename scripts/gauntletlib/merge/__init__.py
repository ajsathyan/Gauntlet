"""Generic pull-request merge support."""

from pathlib import Path

from .workflow import branch_name as branch_name
from .workflow import build_merge_payload as build_merge_payload
from .workflow import checks_state as checks_state
from .workflow import command_merge_execute
from .workflow import command_merge_plan
from .workflow import command_merge_prepare
from .workflow import configure as configure
from .workflow import current_default_head as current_default_head
from .workflow import current_head as current_head
from .workflow import current_pr as current_pr
from .workflow import default_represents_candidate as default_represents_candidate
from .workflow import delete_remote_branch as delete_remote_branch
from .workflow import dirty_paths as dirty_paths
from .workflow import ensure_unreleased_changelog as ensure_unreleased_changelog
from .workflow import execute_merge_plan as execute_merge_plan
from .workflow import load_merge_handoff as load_merge_handoff
from .workflow import merge_input_path as merge_input_path
from .workflow import projection_changelog_entry as projection_changelog_entry
from .workflow import refresh_default_head as refresh_default_head
from .workflow import render_pr_body as render_pr_body
from .workflow import repository_merge_settings as repository_merge_settings
from .workflow import upstream_counts as upstream_counts


def register(subparsers):
    merge = subparsers.add_parser(
        "merge",
        help="Prepare, inspect, or execute a contextual pull-request merge.",
    )
    commands = merge.add_subparsers(dest="merge_command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--git-root", type=Path, default=Path.cwd())
    prepare.add_argument("--handoff", type=Path, required=True)
    prepare.add_argument(
        "--body-output",
        type=Path,
        default=Path(".gauntlet/pr-body.md"),
    )
    prepare.add_argument("--json", action="store_true")
    prepare.set_defaults(func=command_merge_prepare)
    for name, func in [
        ("plan", command_merge_plan),
        ("execute", command_merge_execute),
    ]:
        command = commands.add_parser(name)
        command.add_argument("--git-root", type=Path, default=Path.cwd())
        command.add_argument("--handoff", type=Path, required=True)
        command.add_argument(
            "--body",
            type=Path,
            default=Path(".gauntlet/pr-body.md"),
        )
        command.add_argument("--json", action="store_true")
        command.set_defaults(func=func)
