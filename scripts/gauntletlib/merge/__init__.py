"""Merge workflow support."""

from pathlib import Path

from .workflow import acquire_run_merge_lease as acquire_run_merge_lease
from .workflow import branch_bound_run as branch_bound_run
from .workflow import branch_name as branch_name
from .workflow import build_merge_payload as build_merge_payload
from .workflow import checks_state as checks_state
from .workflow import command_merge_execute
from .workflow import command_merge_plan
from .workflow import command_merge_prepare
from .workflow import command_merge_reconcile
from .workflow import configure as configure
from .workflow import current_default_head as current_default_head
from .workflow import current_head as current_head
from .workflow import current_pr as current_pr
from .workflow import default_represents_candidate as default_represents_candidate
from .workflow import delete_remote_branch as delete_remote_branch
from .workflow import dirty_paths as dirty_paths
from .workflow import ensure_unreleased_changelog as ensure_unreleased_changelog
from .workflow import execute_merge_plan as execute_merge_plan
from .workflow import launch_merge_lease_path as launch_merge_lease_path
from .workflow import load_merge_handoff as load_merge_handoff
from .workflow import merge_input_path as merge_input_path
from .workflow import pending_run_merge_gates as pending_run_merge_gates
from .workflow import persist_merge_lease as persist_merge_lease
from .workflow import persisted_run_merge_lease as persisted_run_merge_lease
from .workflow import primary_worktree as primary_worktree
from .workflow import projection_changelog_entry as projection_changelog_entry
from .workflow import recorded_run_merge_head as recorded_run_merge_head
from .workflow import refresh_default_head as refresh_default_head
from .workflow import release_run_merge_lease as release_run_merge_lease
from .workflow import render_pr_body as render_pr_body
from .workflow import repository_merge_settings as repository_merge_settings
from .workflow import run_binding_findings as run_binding_findings
from .workflow import run_project_pr as run_project_pr
from .workflow import upstream_counts as upstream_counts


def register(subparsers):
    merge = subparsers.add_parser(
        "merge",
        help="Prepare or execute a contextual pull-request merge.",
    )
    commands = merge.add_subparsers(dest="merge_command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--git-root", type=Path, default=Path.cwd())
    prepare.add_argument("--handoff", type=Path, default=None)
    prepare.add_argument("--run", type=Path, default=None)
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
        command.add_argument(
            "--git-root", type=Path, default=Path.cwd()
        )
        command.add_argument("--handoff", type=Path, default=None)
        command.add_argument("--run", type=Path, default=None)
        command.add_argument(
            "--body",
            type=Path,
            default=Path(".gauntlet/pr-body.md"),
        )
        command.add_argument("--json", action="store_true")
        command.set_defaults(func=func)
    reconcile = commands.add_parser(
        "reconcile",
        help="Record an already-observed run-backed merge idempotently.",
    )
    reconcile.add_argument(
        "--git-root", type=Path, default=Path.cwd()
    )
    reconcile.add_argument("--run", type=Path, required=True)
    reconcile.add_argument("--json", action="store_true")
    reconcile.set_defaults(func=command_merge_reconcile)
