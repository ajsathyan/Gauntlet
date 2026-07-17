"""Construction, wiring, and compatibility surface for the Gauntlet CLI."""
# ruff: noqa: E402, F401
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from contextlib import contextmanager
from functools import wraps
from pathlib import Path

from gauntletlib.cli_support import EXIT_CODES
from gauntletlib.cli_support import build_parser as build_cli_parser
from gauntletlib.cli_support import dispatch
from gauntletlib.cli_support import print_json_or_brief
from gauntletlib.cli_config import configure_runtime
from gauntletlib.cli_registration import register_commands

# Import command families only after the shared CLI symbols above are available.
# Several legacy modules still import these names from ``gauntletlib.cli``.
from gauntletlib.analytics import register as register_analytics
from gauntletlib.closeout import configure as configure_closeout
from gauntletlib.closeout import (
    advance_run_release_state as advance_run_release_state,
    closeout_install_command as closeout_install_command,
    completion_allows_archive as completion_allows_archive,
)
from gauntletlib.contracts import (
    validate_merge_handoff as validate_merge_handoff,
    validate_run_merge_handoff as validate_run_merge_handoff,
)
from gauntletlib.closeout import register_archive
from gauntletlib.closeout import register_changelog
from gauntletlib.closeout import register_closeout
from gauntletlib.closeout import register_followup_memory
from gauntletlib.docs import DOC_EXECUTION_BLOCK_BEGIN as DOC_EXECUTION_BLOCK_BEGIN
from gauntletlib.docs import DOC_EXECUTION_BLOCK_END as DOC_EXECUTION_BLOCK_END
from gauntletlib.docs import DOC_EXECUTION_LEGACY_HASHES as DOC_EXECUTION_LEGACY_HASHES
from gauntletlib.docs import accepted_record_path
from gauntletlib.docs import command_docs_draft_promote as command_docs_draft_promote
from gauntletlib.docs import configure as configure_docs
from gauntletlib.docs import ensure_doc_execution_contract as ensure_doc_execution_contract
from gauntletlib.docs import migrate_doc_execution_contract as migrate_doc_execution_contract
from gauntletlib.docs import register as register_docs
from gauntletlib.docs import valid_epic_title
from gauntletlib.diagram import command_find as _command_diagram_find
from gauntletlib.diagram import register as register_diagram
from gauntletlib.install.verify import command_verify as command_install_verify
from gauntletlib.install.verify import register as register_install
from gauntletlib.land import configure as configure_land
from gauntletlib.land import register as register_land
from gauntletlib.merge import acquire_run_merge_lease as _acquire_run_merge_lease
from gauntletlib.merge import branch_name
from gauntletlib.merge import checks_state
from gauntletlib.merge import configure as configure_merge
from gauntletlib.merge import current_default_head
from gauntletlib.merge import current_head
from gauntletlib.merge import default_represents_candidate as _default_represents_candidate
from gauntletlib.merge import delete_remote_branch
from gauntletlib.merge import dirty_paths
from gauntletlib.merge import launch_merge_lease_path
from gauntletlib.merge import merge_input_path
from gauntletlib.merge import pending_run_merge_gates as pending_run_merge_gates
from gauntletlib.merge import persisted_run_merge_lease as persisted_run_merge_lease
from gauntletlib.merge import persist_merge_lease as _persist_merge_lease
from gauntletlib.merge import projection_changelog_entry as projection_changelog_entry
from gauntletlib.merge import primary_worktree
from gauntletlib.merge import refresh_default_head
from gauntletlib.merge import release_run_merge_lease as _release_run_merge_lease
from gauntletlib.merge import render_pr_body as render_pr_body
from gauntletlib.merge import register as register_merge
from gauntletlib.review_unit import configure as configure_review_unit
from gauntletlib.review_unit import register as register_review_unit
from gauntletlib.progress import configure as configure_progress
from gauntletlib.progress import progress_browser_action
from gauntletlib.progress import register as register_progress
from gauntletlib.progress import supervisor as _progress_supervisor
from gauntletlib.run import invoke as invoke_prd_controller
from gauntletlib.core.fsio import atomic_write_text as _atomic_write_text
from gauntletlib.core.fsio import write_new_file as _write_new_file
from gauntletlib.core.findings import add_finding as _add_finding
from gauntletlib.core.findings import status_for as _status_for
from gauntletlib.core.hashing import sha256 as _sha256
from gauntletlib.core.jsonio import canonical_json as _canonical_json
from gauntletlib.core.proc import gh_binary as gh_binary, git, run_cmd as _run_cmd
from gauntletlib.core.redact import SECRET_PATTERNS as SECRET_PATTERNS
from gauntletlib.core.redact import has_secret
from gauntletlib.core.timefmt import utc_timestamp as _utc_timestamp
from thread_titles import epic_task_title, product_task_title


ROOT = Path(__file__).resolve().parents[2]
_URL_REQUEST_COMPAT = urllib.request
SCRIPTS = ROOT / "scripts"
CHECKER = SCRIPTS / "check-workflow-etiquette.py"
PROGRESS_SOURCE_SCHEMA = "gauntlet/live-progress-source/v1"
PROGRESS_STATE_SCHEMA = "gauntlet.progress-dashboard-state/v1"
PROGRESS_HEALTH_SCHEMA = "gauntlet.progress-dashboard-health/v1"
PROGRESS_REFRESH_SECONDS = 2.5
PROGRESS_TERMINAL_GRACE_SECONDS = 10.0
PASSING_CHECK_CONCLUSIONS = {"SUCCESS", "SKIPPED", "NEUTRAL"}
PASSING_STATUS_STATES = {"SUCCESS", "SKIPPED", "NEUTRAL"}

_COMPATIBILITY_OVERRIDE_NAMES = {
    "DOC_EXECUTION_LEGACY_HASHES",
    "authenticated_progress_state",
    "completion_projection_for_run",
    "ensure_progress_supervisor",
    "git",
    "launch_projections",
    "print_payload",
    "progress_dashboard_status",
    "read_progress_state",
    "refresh_default_head",
    "run_facts_for_progress",
    "run_prd_controller",
    "stop_progress_dashboard",
    "telemetry_for_progress",
    "verified_progress_state",
}


@contextmanager
def _compatibility_overrides(namespace):
    if namespace is None:
        yield
        return
    previous = {}
    for name in _COMPATIBILITY_OVERRIDE_NAMES:
        if name in namespace and name in globals():
            previous[name] = globals()[name]
            globals()[name] = namespace[name]
    try:
        yield
    finally:
        globals().update(previous)


def run_cmd(args, cwd=None, env=None, check=False):
    return _run_cmd(args, cwd=cwd, env=env, check=check)


def default_represents_candidate(repo, candidate, default_head):
    return _default_represents_candidate(
        repo,
        candidate,
        default_head,
        git_fn=git,
    )


def persist_merge_lease(repo, lease_path, lease, default_head):
    return _persist_merge_lease(
        repo,
        lease_path,
        lease,
        default_head,
        default_represents_candidate_fn=default_represents_candidate,
    )


def acquire_run_merge_lease(repo, run_path, handoff):
    return _acquire_run_merge_lease(
        repo,
        run_path,
        handoff,
        refresh_default_head_fn=refresh_default_head,
        git_fn=git,
        persist_merge_lease_fn=persist_merge_lease,
    )


def release_run_merge_lease(repo, lease_path, lease, merged_head):
    return _release_run_merge_lease(
        repo,
        lease_path,
        lease,
        merged_head,
        refresh_default_head_fn=refresh_default_head,
        default_represents_candidate_fn=default_represents_candidate,
        git_fn=git,
    )


def read_text(path):
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def utc_timestamp():
    return _utc_timestamp()


def git_root(repo):
    result = git(["rev-parse", "--show-toplevel"], repo)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def write_new_file(path, content):
    return _write_new_file(path, content)


def atomic_write_text(path, content, mode=0o600):
    return _atomic_write_text(path, content, mode=mode)


def sha256_bytes(value):
    return _sha256(value)


def canonical_json(value):
    return _canonical_json(value)


from gauntletlib.launch import (
    DEPENDENCY_BOUNDARIES,
    EPIC_COPY_TEMPLATE,
    EPIC_LAUNCH_SCHEMA,
    EPIC_STATES,
    HIGH_CONSEQUENCE_TRIGGERS,
    build_epic_launch_set,
    command_epic_tasks_blocker,
    command_epic_tasks_bootstrap,
    command_epic_tasks_init,
    command_epic_tasks_merge_lease_acquire,
    command_epic_tasks_merge_lease_release,
    command_epic_tasks_plan,
    command_epic_tasks_reconcile,
    command_epic_tasks_reconcile_docs,
    command_epic_tasks_record_run,
    command_epic_tasks_record_task,
    command_epic_tasks_release_start,
    command_epic_tasks_resolve_blocker,
    command_epic_tasks_status,
    completion_projection_for_run,
    configure as _configure_launch,
    dependency_satisfied,
    epic_acceptance_identity,
    epic_launch_payload,
    epic_metadata,
    epic_source_sections,
    epic_task_packet,
    gap_review_text,
    implementation_target_ids,
    index_epic_cells,
    launch_coverage_projection,
    launch_path_reference,
    launch_projections,
    launch_source_text,
    launch_state,
    launch_task_key,
    lifecycle_copy_contract,
    load_accepted_epic_record,
    load_launch_set,
    maybe_aggregate_start_event,
    maybe_finish_events,
    parse_consequence_triggers,
    parse_dependency_list,
    parse_release_stages,
    pending_gate_text,
    placeholder_index_value,
    ready_launch_epics,
    register as _register_launch,
    render_lifecycle_copy,
    replace_epic_metadata,
    resolve_epic_bootstrap,
    update_epic_index,
    validate_epic_dependency_graph,
    write_launch_set,
)























def add_finding(payload, code, severity, message, **details):
    _add_finding(payload.setdefault("findings", []), code, severity, message, **details)


def status_for(payload):
    return _status_for(payload.get("findings", []))




























def run_prd_controller(repo, arguments):
    controller = prd_controller_path()
    if not controller.is_file():
        return None, f"Execution Run controller does not exist: {controller}"
    if os.environ.get("GAUNTLET_DEV_PRD_CONTROLLER"):
        result = run_cmd([sys.executable, str(controller), *arguments], cwd=repo)
    else:
        result = invoke_prd_controller(arguments, cwd=repo)
    if result.returncode != 0:
        return None, result.stderr.strip() or result.stdout.strip() or "prd-run command failed"
    return result.stdout, None


def prd_controller_path():
    override = os.environ.get("GAUNTLET_DEV_PRD_CONTROLLER")
    if override:
        if os.environ.get("GAUNTLET_ALLOW_DEV_CONTROLLER") != "1":
            return Path("/__gauntlet_untrusted_controller_override_rejected__")
        return Path(override).resolve()
    return SCRIPTS / "prd-run.py"


def run_authority_granted(repo, run_path, capability):
    output, error = run_prd_controller(repo, [
        "authority-status", "--run", str(Path(run_path).resolve()), "--capability", capability,
    ])
    if error:
        return False, error
    try:
        status = json.loads(output)
    except json.JSONDecodeError as exc:
        return False, f"authority-status did not emit JSON: {exc}"
    if status.get("capability") != capability or status.get("granted") is not True:
        return False, f"Execution Run has not granted {capability} authority"
    return True, None












































































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
        if payload["status"] in {"pass", "warn"}:
            return
        print()
    print(f"Gauntlet: {payload['status']}")
    for finding in payload.get("findings", []):
        print(f"- [{finding['severity']}] {finding['code']}: {finding['message']}")
    for action in payload.get("archivePlan", {}).get("actions", []):
        print(f"- action: {action.get('type')}")
















def command_diagram_find(args):
    return _command_diagram_find(args, root=ROOT)




progress_paths = _progress_supervisor.progress_paths
progress_launch_terminal = _progress_supervisor.progress_launch_terminal
read_progress_state = _progress_supervisor.read_progress_state
authenticated_progress_state = _progress_supervisor.authenticated_progress_state
progress_dashboard_status = _progress_supervisor.progress_dashboard_status
start_progress_dashboard = _progress_supervisor.start_progress_dashboard
run_facts_for_progress = _progress_supervisor.run_facts_for_progress
telemetry_for_progress = _progress_supervisor.telemetry_for_progress
verified_progress_state = _progress_supervisor.verified_progress_state
command_epic_tasks_progress_supervise = (
    _progress_supervisor.command_epic_tasks_progress_supervise
)


def refresh_progress_source(*args, **kwargs):
    _progress_supervisor.run_facts_for_progress = run_facts_for_progress
    _progress_supervisor.telemetry_for_progress = telemetry_for_progress
    return _progress_supervisor.refresh_progress_source(*args, **kwargs)


def ensure_progress_supervisor(*args, **kwargs):
    _progress_supervisor.authenticated_progress_state = (
        authenticated_progress_state
    )
    _progress_supervisor.progress_dashboard_status = progress_dashboard_status
    _progress_supervisor.verified_progress_state = verified_progress_state
    _progress_supervisor.stop_progress_dashboard = stop_progress_dashboard
    _progress_supervisor.start_progress_dashboard = start_progress_dashboard
    return _progress_supervisor.ensure_progress_supervisor(*args, **kwargs)


def stop_progress_dashboard(*args, **kwargs):
    _progress_supervisor.authenticated_progress_state = (
        authenticated_progress_state
    )
    _progress_supervisor.progress_dashboard_status = progress_dashboard_status
    return _progress_supervisor.stop_progress_dashboard(*args, **kwargs)


def safely_ensure_progress_supervisor(*args, **kwargs):
    try:
        return ensure_progress_supervisor(*args, **kwargs)
    except (OSError, ValueError, json.JSONDecodeError):
        return _progress_supervisor.unavailable_progress_dashboard(args[0])


def safely_progress_dashboard_status(*args, **kwargs):
    try:
        return progress_dashboard_status(*args, **kwargs)
    except (OSError, ValueError, json.JSONDecodeError):
        return _progress_supervisor.unavailable_progress_dashboard(args[0])


configure_runtime(
    configure_docs=configure_docs,
    configure_launch=_configure_launch,
    configure_progress=configure_progress,
    configure_closeout=configure_closeout,
    configure_merge=configure_merge,
    configure_review_unit=configure_review_unit,
    dependencies={
        "atomic_write_text": lambda path, content, mode=0o600:
            atomic_write_text(path, content, mode=mode),
        "parse_dependency_list": lambda raw: parse_dependency_list(raw),
        "parse_release_stages": lambda raw: parse_release_stages(raw),
        "parse_consequence_triggers": lambda raw: parse_consequence_triggers(raw),
        "legacy_hashes": lambda: DOC_EXECUTION_LEGACY_HASHES,
        "run_prd_controller": lambda repo, arguments:
            run_prd_controller(repo, arguments),
        "print_payload": lambda payload, as_json: print_payload(payload, as_json),
        "completion_projection_for_run": lambda repo, run_path:
            completion_projection_for_run(repo, run_path),
        "safely_ensure_progress_supervisor": lambda launch_path, launch, repo:
            safely_ensure_progress_supervisor(launch_path, launch, repo),
        "safely_progress_dashboard_status": lambda launch_path:
            safely_progress_dashboard_status(launch_path),
        "gauntlet_cli_path": lambda: SCRIPTS / "gauntlet.py",
        "load_launch_set": lambda path: load_launch_set(path),
        "launch_projections": lambda repo, launch:
            launch_projections(repo, launch),
        "gap_review_text": lambda projection: gap_review_text(projection),
        "run_authority_granted": lambda repo, run_path, capability:
            run_authority_granted(repo, run_path, capability),
        "launch_source_text": lambda launch: launch_source_text(launch),
        "prd_controller_path": lambda: prd_controller_path(),
        "merge_input_path": lambda repo, supplied:
            merge_input_path(repo, supplied),
        "branch_name": lambda repo: branch_name(repo),
        "current_head": lambda repo: current_head(repo),
        "dirty_paths": lambda repo: dirty_paths(repo),
        "checks_state": lambda checks: checks_state(checks),
        "delete_remote_branch": lambda repo, branch, expected_sha=None:
            delete_remote_branch(repo, branch, expected_sha=expected_sha),
    },
)


def register(subcommands):
    configure_land(print_payload=print_payload)
    register_commands(
        subcommands,
        register_archive=register_archive,
        register_land=register_land,
        register_merge=register_merge,
        register_review_unit=register_review_unit,
        register_closeout=register_closeout,
        register_install=register_install,
        register_launch=_register_launch,
        register_docs=register_docs,
        register_followup_memory=register_followup_memory,
        register_analytics=register_analytics,
        register_changelog=register_changelog,
        register_diagram=register_diagram,
        command_install_verify=command_install_verify,
        command_diagram_find=command_diagram_find,
    )

def build_parser():
    return build_cli_parser(register)


def main(argv=None, *, compatibility=None):
    with _compatibility_overrides(compatibility):
        return dispatch(build_parser(), argv, error_printer=print_payload)


_COMPATIBILITY_FUNCTIONS = {}


def _compatibility_call(namespace, name, *args, **kwargs):
    with _compatibility_overrides(namespace):
        return _COMPATIBILITY_FUNCTIONS[name](*args, **kwargs)


def install_compatibility_exports(namespace):
    """Populate the legacy script module without retaining CLI implementation there."""
    excluded = {
        "_COMPATIBILITY_FUNCTIONS",
        "_compatibility_call",
        "_compatibility_overrides",
        "install_compatibility_exports",
    }
    exports = {
        name: value
        for name, value in globals().items()
        if not name.startswith("__") and name not in excluded
    }
    for name, value in exports.items():
        if callable(value) and not isinstance(value, type):
            _COMPATIBILITY_FUNCTIONS[name] = value

            @wraps(value)
            def compatibility_wrapper(*args, __name=name, **kwargs):
                return _compatibility_call(
                    namespace,
                    __name,
                    *args,
                    **kwargs,
                )

            namespace[name] = compatibility_wrapper
        else:
            namespace[name] = value


if __name__ == "__main__":
    raise SystemExit(main())
