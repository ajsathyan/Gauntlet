"""Merge, monitor, synchronize, and safely clean up one landed branch."""

import json
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from gauntletlib.cli_support import EXIT_CODES
from gauntletlib.core.findings import add_finding
from gauntletlib.core.findings import status_for
from gauntletlib.core.proc import gh, git, run_cmd
from gauntletlib.merge import branch_name, default_represents_candidate, dirty_paths

def _missing_payload_printer(_payload: dict[str, Any], _as_json: bool) -> None:
    raise RuntimeError("land payload printer is not configured")


_print_payload: Callable[[dict[str, Any], bool], None] = _missing_payload_printer


def configure(*, print_payload: Callable[[dict[str, Any], bool], None]) -> None:
    global _print_payload
    _print_payload = print_payload


def register(subparsers):
    land = subparsers.add_parser(
        "land",
        help="Merge through a PR, monitor the landed revision, and clean up safely.",
    )
    commands = land.add_subparsers(dest="land_command", required=True)
    execute = commands.add_parser("execute")
    execute.add_argument("--git-root", type=Path, default=Path.cwd())
    execute.add_argument("--handoff", type=Path, required=True)
    execute.add_argument("--body", type=Path, default=Path(".gauntlet/pr-body.md"))
    execute.add_argument("--monitor-timeout", type=int, default=180)
    execute.add_argument("--json", action="store_true")
    execute.set_defaults(func=command_land_execute)


def configured_push_workflows(repo, default_branch):
    """Return named workflows that visibly declare a push trigger for default."""
    workflows = []
    workflow_root = Path(repo) / ".github" / "workflows"
    for path in sorted([*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml")]):
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        push_index = next(
            (
                index
                for index, line in enumerate(lines)
                if line.strip() == "push:" and len(line) - len(line.lstrip()) <= 2
            ),
            None,
        )
        if push_index is None:
            continue
        push_indent = len(lines[push_index]) - len(lines[push_index].lstrip())
        block = []
        for line in lines[push_index + 1 :]:
            if line.strip() and len(line) - len(line.lstrip()) <= push_indent:
                break
            block.append(line.strip())
        branch_filters = [
            line.removeprefix("-").strip().strip("'\"")
            for line in block
            if line.startswith("-")
        ]
        if not branch_filters or default_branch in branch_filters:
            workflow_name = next(
                (
                    line.split(":", 1)[1].strip().strip("'\"")
                    for line in lines
                    if line.startswith("name:") and line.split(":", 1)[1].strip()
                ),
                path.stem,
            )
            workflows.append(
                {"path": str(path.relative_to(repo)), "name": workflow_name}
            )
    return workflows


def select_exact_sha_runs(records, landed_sha):
    return [
        record
        for record in records
        if record.get("headSha") == landed_sha and record.get("event") == "push"
    ]


def monitor_landed_revision(
    repo,
    landed_sha,
    default_branch,
    *,
    timeout_seconds=180,
    poll_seconds=2,
    gh_runner=None,
    sleep_fn=None,
):
    """Wait for every declared exact-SHA push workflow and require each to pass."""
    gh_runner = gh_runner or gh
    sleep_fn = sleep_fn or time.sleep
    workflows = configured_push_workflows(repo, default_branch)
    result = {
        "status": "not-configured" if not workflows else "pending",
        "landedSha": landed_sha,
        "workflows": workflows,
        "runs": [],
    }
    if not workflows:
        return result, None

    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    expected_names = {workflow["name"] for workflow in workflows}
    exact = []
    while True:
        listed = gh_runner(
            [
                "run",
                "list",
                "--commit",
                landed_sha,
                "--event",
                "push",
                "--limit",
                "100",
                "--json",
                "databaseId,status,conclusion,headSha,event,url,workflowName",
            ],
            repo,
        )
        if listed.returncode == 0:
            try:
                exact = select_exact_sha_runs(json.loads(listed.stdout or "[]"), landed_sha)
            except json.JSONDecodeError as error:
                last_error = f"GitHub Actions returned invalid JSON: {error}"
                exact = []
            observed_names = {record.get("workflowName") for record in exact}
            if expected_names <= observed_names:
                break
        else:
            last_error = listed.stderr.strip() or listed.stdout.strip()
        if time.monotonic() >= deadline:
            missing = sorted(expected_names - {record.get("workflowName") for record in exact})
            return result, last_error or (
                f"No exact-revision run appeared for declared workflow(s) "
                f"{', '.join(missing)} within {timeout_seconds} seconds."
            )
        sleep_fn(poll_seconds)

    for record in exact:
        watched = gh_runner(
            ["run", "watch", str(record["databaseId"]), "--exit-status"],
            repo,
        )
        record = dict(record)
        record["watchExitCode"] = watched.returncode
        result["runs"].append(record)
        if watched.returncode != 0:
            result["status"] = "fail"
            return result, watched.stderr.strip() or watched.stdout.strip() or f"Push run {record['databaseId']} failed."
    result["status"] = "pass"
    return result, None


def worktrees(repo):
    result = git(["worktree", "list", "--porcelain"], repo)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Cannot inspect Git worktrees")
    records = []
    current = {}
    for line in [*result.stdout.splitlines(), ""]:
        if not line:
            if current:
                records.append(current)
                current = {}
        elif " " in line:
            key, value = line.split(" ", 1)
            current[key] = value
        else:
            current[line] = True
    return records


def default_worktree(repo, default_branch):
    expected = f"refs/heads/{default_branch}"
    for record in worktrees(repo):
        if record.get("branch") == expected:
            return Path(record["worktree"]).resolve()
    return None


def sync_default_worktree(repo, default_branch, landed_sha, base_remote):
    main_worktree = default_worktree(repo, default_branch)
    if main_worktree is None:
        repo = Path(repo).resolve()
        exists = git(["show-ref", "--verify", f"refs/heads/{default_branch}"], repo)
        if exists.returncode != 0 or dirty_paths(repo):
            return None, f"No clean local worktree can switch to the default branch {default_branch}."
        switched = git(["switch", default_branch], repo)
        if switched.returncode != 0:
            return None, switched.stderr.strip() or switched.stdout.strip()
        main_worktree = repo
    pulled = git(["pull", "--ff-only", base_remote, default_branch], main_worktree)
    if pulled.returncode != 0:
        return main_worktree, pulled.stderr.strip() or pulled.stdout.strip()
    head = git(["rev-parse", "HEAD"], main_worktree)
    if head.returncode != 0 or head.stdout.strip() != landed_sha:
        return main_worktree, f"Local {default_branch} did not synchronize to landed revision {landed_sha}."
    return main_worktree, None


def clean_task_checkout(repo, main_worktree, branch, default_branch, task_head, landed_sha):
    """Remove the landed checkout and branch only after preservation checks."""
    repo = Path(repo).resolve()
    main_worktree = Path(main_worktree).resolve()
    previous_cwd = Path.cwd()
    if dirty_paths(repo):
        return {"worktreeRemoved": False, "branchDeleted": False}, "Task worktree became dirty after merge; preserving it."
    represented = default_represents_candidate(repo, task_head, landed_sha)
    if not represented:
        return {"worktreeRemoved": False, "branchDeleted": False}, "Landed revision does not preserve the task head or its exact tree; preserving it."

    os.chdir(main_worktree)
    cleanup = {"worktreeRemoved": False, "branchDeleted": False}
    try:
        if repo != main_worktree:
            removed = git(["worktree", "remove", str(repo)], main_worktree)
            if removed.returncode != 0:
                return cleanup, removed.stderr.strip() or removed.stdout.strip()
            cleanup["worktreeRemoved"] = True
        else:
            switched = git(["switch", default_branch], main_worktree)
            if switched.returncode != 0:
                return cleanup, switched.stderr.strip() or switched.stdout.strip()

        deleted = git(["branch", "-D", branch], main_worktree)
        if deleted.returncode != 0:
            return cleanup, deleted.stderr.strip() or deleted.stdout.strip()
        cleanup["branchDeleted"] = True
        return cleanup, None
    finally:
        if previous_cwd.exists():
            os.chdir(previous_cwd)


def merge_command(args):
    cli = Path(__file__).resolve().parents[2] / "gauntlet.py"
    command = [
        sys.executable,
        str(cli),
        "merge",
        "execute",
        "--git-root",
        str(Path(args.git_root).resolve()),
        "--body",
        str(args.body),
        "--json",
    ]
    command.extend(["--handoff", str(args.handoff)])
    return command


def command_land_execute(args):
    repo = Path(args.git_root).resolve()
    if not repo.is_dir():
        payload: dict[str, Any] = {
            "schemaVersion": "gauntlet.land.v1",
            "status": "fail",
            "findings": [],
            "cleanup": {"defaultSynced": False, "worktreeRemoved": False, "branchDeleted": False},
        }
        add_finding(payload["findings"], "land_context_invalid", "fail", f"Land Git root does not exist: {repo}")
        _print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    branch = branch_name(repo)
    task_head = git(["rev-parse", "HEAD"], repo)
    payload: dict[str, Any] = {
        "schemaVersion": "gauntlet.land.v1",
        "status": "pass",
        "findings": [],
        "branch": branch,
        "taskHead": task_head.stdout.strip() if task_head.returncode == 0 else None,
        "merge": None,
        "monitor": None,
        "cleanup": {"defaultSynced": False, "worktreeRemoved": False, "branchDeleted": False},
    }
    if not branch or task_head.returncode != 0:
        add_finding(payload["findings"], "land_context_invalid", "fail", "Land requires a named task branch in a Git repository.")
    if payload["findings"]:
        payload["status"] = status_for(payload["findings"])
        _print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]

    merged = run_cmd(merge_command(args), cwd=repo)
    try:
        payload["merge"] = json.loads(merged.stdout or "{}")
    except json.JSONDecodeError as error:
        add_finding(payload["findings"], "merge_output_invalid", "fail", str(error))
    if merged.returncode != 0:
        message = merged.stderr.strip() or (payload["merge"] or {}).get("findings") or merged.stdout.strip()
        add_finding(payload["findings"], "merge_failed", "fail", str(message))

    default_branch = "main"
    base_remote = None
    if not payload["findings"]:
        merge_payload = payload["merge"]
        if not isinstance(merge_payload, dict):
            add_finding(
                payload["findings"],
                "merge_output_invalid",
                "fail",
                "Merge did not return an object payload.",
            )
            repository_context = {}
        else:
            default_branch = merge_payload.get("defaultBranch") or "main"
            repository_context = merge_payload.get("repositoryContext") or {}
        base_remote = repository_context.get("baseRemote")
        if not base_remote:
            add_finding(
                payload["findings"],
                "landed_repository_context_missing",
                "fail",
                "Merge did not return the resolved PR base remote.",
            )
            fetched = landed = None
        else:
            fetched = git(["fetch", base_remote, default_branch], repo)
            landed = git(["rev-parse", f"{base_remote}/{default_branch}"], repo)
        if (
            fetched is None
            or landed is None
            or fetched.returncode != 0
            or landed.returncode != 0
        ):
            if fetched is not None:
                landed_error = landed.stderr.strip() if landed is not None else ""
                add_finding(payload["findings"], "landed_revision_unresolved", "fail", fetched.stderr.strip() or landed_error)
        else:
            landed_sha = landed.stdout.strip()
            payload["landedSha"] = landed_sha
            monitor, error = monitor_landed_revision(
                repo,
                landed_sha,
                default_branch,
                timeout_seconds=max(args.monitor_timeout, 1),
            )
            payload["monitor"] = monitor
            if error:
                add_finding(payload["findings"], "landed_revision_monitor_failed", "fail", error)

    if not payload["findings"] and isinstance(base_remote, str):
        main_worktree, error = sync_default_worktree(
            repo, default_branch, payload["landedSha"], base_remote
        )
        if error:
            add_finding(payload["findings"], "default_branch_sync_failed", "fail", error)
        else:
            payload["cleanup"]["defaultSynced"] = True
            cleanup, error = clean_task_checkout(
                repo,
                main_worktree,
                branch,
                default_branch,
                payload["taskHead"],
                payload["landedSha"],
            )
            payload["cleanup"].update(cleanup)
            if error:
                add_finding(payload["findings"], "local_cleanup_preserved", "review", error)

    payload["status"] = status_for(payload["findings"])
    _print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]
