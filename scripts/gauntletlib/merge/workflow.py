"""Generic contextual pull-request preparation, planning, and execution."""

import json
import subprocess
import time
from pathlib import Path

from gauntletlib.cli import EXIT_CODES
from gauntletlib.contracts import validate_merge_handoff
from gauntletlib.core.findings import add_finding as _add_finding
from gauntletlib.core.findings import status_for as _status_for
from gauntletlib.core.proc import gh, git

PASSING_CHECK_CONCLUSIONS = {"SUCCESS", "SKIPPED", "NEUTRAL"}
PASSING_STATUS_STATES = {"SUCCESS", "SKIPPED", "NEUTRAL"}

_print_payload = None


def configure(*, print_payload):
    global _print_payload
    _print_payload = print_payload


def add_finding(payload, code, severity, message, **details):
    _add_finding(
        payload.setdefault("findings", []),
        code,
        severity,
        message,
        **details,
    )


def status_for(payload):
    return _status_for(payload.get("findings", []))


def current_default_head(repo):
    symbolic = git(
        ["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"],
        repo,
    )
    remote_ref = symbolic.stdout.strip() if symbolic.returncode == 0 else "origin/main"
    result = git(["rev-parse", remote_ref], repo)
    if result.returncode != 0:
        result = git(["rev-parse", "main"], repo)
    if result.returncode != 0:
        raise ValueError("Cannot resolve the current default-branch head")
    return result.stdout.strip(), remote_ref


def refresh_default_head(repo):
    remote = git(["remote", "get-url", "origin"], repo)
    if remote.returncode == 0:
        fetched = git(["fetch", "origin"], repo)
        if fetched.returncode != 0:
            raise ValueError(
                fetched.stderr.strip()
                or fetched.stdout.strip()
                or "Cannot refresh origin before merge"
            )
    return current_default_head(repo)


def default_represents_candidate(repo, candidate, default_head, *, git_fn=None):
    """Accept ancestry or an exact tree-equivalent squash/rebase result."""

    run_git = git_fn or git
    ancestry = run_git(
        ["merge-base", "--is-ancestor", candidate, default_head],
        repo,
    )
    if ancestry.returncode == 0:
        return True
    if ancestry.returncode != 1:
        raise ValueError(
            ancestry.stderr.strip() or "Cannot determine candidate ancestry"
        )
    candidate_tree = run_git(["rev-parse", f"{candidate}^{{tree}}"], repo)
    default_tree = run_git(["rev-parse", f"{default_head}^{{tree}}"], repo)
    if candidate_tree.returncode != 0 or default_tree.returncode != 0:
        raise ValueError(
            candidate_tree.stderr.strip()
            or default_tree.stderr.strip()
            or "Cannot compare candidate and default trees"
        )
    return candidate_tree.stdout.strip() == default_tree.stdout.strip()


def load_merge_handoff(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def render_pr_body(data):
    solution = data["solution"]
    solution_parts = [solution["outcome"].strip()]
    for label, field in [
        ("Invariants", "invariants"),
        ("Preserved", "preserved"),
        ("Non-goals", "nonGoals"),
    ]:
        items = solution.get(field, [])
        if items:
            solution_parts.extend(
                ["", f"{label}:", *[f"- {item.strip()}" for item in items]]
            )

    testing = [
        f"- `{item['command'].strip()}` — "
        f"**{item['result'].strip().upper()}** — {item['proves'].strip()}"
        for item in data["testing"]
    ]
    lines = [
        "## Problem",
        "",
        data["problem"]["context"].strip(),
        "",
        data["problem"]["impact"].strip(),
        "",
        "## Solution",
        "",
        *solution_parts,
        "",
        "## Changelog",
        "",
        f"- {data['changelog'].strip()}",
        "",
        "## Testing",
        "",
        *testing,
    ]
    if data.get("securityRisk"):
        lines.extend(
            ["", "## Security / Risk", "", data["securityRisk"].strip()]
        )
    return "\n".join(lines).rstrip() + "\n"


def projection_changelog_entry(data):
    return data["changelog"]


def ensure_unreleased_changelog(changelog_path, entry):
    changelog_path = Path(changelog_path)
    bullet = f"- {entry.strip()}"
    original = (
        changelog_path.read_text(encoding="utf-8")
        if changelog_path.exists()
        else ""
    )
    if any(line.rstrip() == bullet for line in original.splitlines()):
        return False

    if not original.strip():
        updated = f"# Changelog\n\n## Unreleased\n\n{bullet}\n"
    else:
        lines = original.rstrip().splitlines()
        heading_index = next(
            (
                index
                for index, line in enumerate(lines)
                if line.strip().lower() == "## unreleased"
            ),
            None,
        )
        if heading_index is None:
            updated = original.rstrip() + f"\n\n## Unreleased\n\n{bullet}\n"
        else:
            insert_at = heading_index + 1
            while insert_at < len(lines) and not lines[insert_at].strip():
                insert_at += 1
            lines[insert_at:insert_at] = [bullet, ""]
            updated = "\n".join(lines).rstrip() + "\n"
    changelog_path.write_text(updated, encoding="utf-8")
    return True


def repository_identity(repo):
    remote = git(["config", "--get", "remote.origin.url"], repo)
    if remote.returncode == 0 and remote.stdout.strip():
        return remote.stdout.strip()
    return str(Path(repo).resolve())


def current_head(repo):
    result = git(["rev-parse", "HEAD"], repo)
    return result.stdout.strip() if result.returncode == 0 else ""


def current_tree(repo):
    result = git(["rev-parse", "HEAD^{tree}"], repo)
    return result.stdout.strip() if result.returncode == 0 else ""


def merge_input_path(repo, path):
    path = Path(path)
    return path if path.is_absolute() else Path(repo) / path


def _validate_source_binding(repo, data, payload):
    """Validate an optional exact-revision binding without requiring one."""

    binding = data.get("sourceBinding")
    if binding is None:
        return
    if not isinstance(binding, dict) or set(binding) != {
        "repository",
        "commit",
        "tree",
    }:
        add_finding(
            payload,
            "invalid_source_binding",
            "fail",
            "sourceBinding must contain exactly repository, commit, and tree.",
        )
        return
    expected = {
        "repository": repository_identity(repo),
        "commit": current_head(repo),
        "tree": current_tree(repo),
    }
    if binding != expected:
        add_finding(
            payload,
            "source_binding_drift",
            "fail",
            "The handoff is bound to a different repository, commit, or tree.",
            expected=expected,
            supplied=binding,
        )


def command_merge_prepare(args):
    repo = Path(args.git_root).resolve()
    handoff_path = (
        merge_input_path(repo, args.handoff) if args.handoff else None
    )
    body_path = Path(args.body_output)
    if not body_path.is_absolute():
        body_path = repo / body_path
    changelog_path = repo / "CHANGELOG.md"
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "findings": [],
        "title": None,
        "bodyPath": str(body_path),
        "changelogPath": str(changelog_path),
        "changelogEntry": None,
        "changelogChanged": False,
    }
    data = None
    if not handoff_path or not handoff_path.is_file():
        add_finding(
            payload,
            "missing_handoff_file",
            "fail",
            f"Merge handoff does not exist: {handoff_path}",
        )
    else:
        try:
            data = load_merge_handoff(handoff_path)
        except (json.JSONDecodeError, OSError) as error:
            add_finding(payload, "invalid_handoff_file", "fail", str(error))
        if data is not None:
            payload["findings"].extend(validate_merge_handoff(data))
            _validate_source_binding(repo, data, payload)
    if data is not None:
        payload["title"] = data.get("title")
        if not payload["findings"]:
            payload["changelogEntry"] = projection_changelog_entry(data)
            body_path.parent.mkdir(parents=True, exist_ok=True)
            body_path.write_text(render_pr_body(data), encoding="utf-8")
            payload["changelogChanged"] = ensure_unreleased_changelog(
                changelog_path,
                projection_changelog_entry(data),
            )
    payload["status"] = status_for(payload)
    _print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def repository_merge_settings(repo):
    result = gh(
        [
            "repo",
            "view",
            "--json",
            "defaultBranchRef,mergeCommitAllowed,squashMergeAllowed,"
            "rebaseMergeAllowed",
        ],
        repo,
    )
    if result.returncode != 0:
        return None, result.stderr.strip() or result.stdout.strip()
    return json.loads(result.stdout), None


def merge_method_from_settings(settings):
    if not settings:
        return "merge"
    if settings.get("mergeCommitAllowed"):
        return "merge"
    if settings.get("squashMergeAllowed"):
        return "squash"
    if settings.get("rebaseMergeAllowed"):
        return "rebase"
    return None


def load_merge_inputs(args, payload):
    repo = Path(args.git_root).resolve()
    handoff_arg = getattr(args, "handoff", None)
    handoff_path = (
        merge_input_path(repo, handoff_arg) if handoff_arg else None
    )
    body_path = merge_input_path(repo, args.body)
    data = None
    body = ""
    if git(["rev-parse", "--is-inside-work-tree"], repo).returncode != 0:
        add_finding(
            payload,
            "git_root_not_repo",
            "fail",
            f"Not a git repository: {repo}",
        )
    if not handoff_path or not handoff_path.is_file():
        add_finding(
            payload,
            "missing_handoff_file",
            "fail",
            f"Merge handoff does not exist: {handoff_path}",
        )
    else:
        try:
            data = load_merge_handoff(handoff_path)
        except (json.JSONDecodeError, OSError) as error:
            add_finding(payload, "invalid_handoff_file", "fail", str(error))
        if data is not None:
            payload["findings"].extend(validate_merge_handoff(data))
            _validate_source_binding(repo, data, payload)
    if not body_path.is_file():
        add_finding(
            payload,
            "missing_pr_body",
            "fail",
            f"PR body does not exist: {body_path}",
        )
    else:
        body = body_path.read_text(encoding="utf-8")
    payload["handoffPath"] = str(handoff_path) if handoff_path else None
    payload["bodyPath"] = str(body_path)
    return repo, data, body


def add_existing_pr_blockers(payload, pr):
    if not pr:
        return
    if pr.get("state") != "OPEN":
        add_finding(
            payload,
            "pull_request_not_open",
            "review",
            f"Pull request is {pr.get('state')}.",
        )
    if pr.get("isDraft"):
        add_finding(
            payload,
            "pull_request_is_draft",
            "review",
            "Pull request is still a draft.",
        )
    if pr.get("reviewDecision") in {"CHANGES_REQUESTED", "REVIEW_REQUIRED"}:
        add_finding(
            payload,
            "pull_request_review_pending",
            "review",
            f"Pull request review decision is {pr.get('reviewDecision')}.",
        )
    if pr.get("mergeable") not in {"MERGEABLE", "UNKNOWN"}:
        add_finding(
            payload,
            "pull_request_not_mergeable",
            "review",
            f"Pull request mergeable state is {pr.get('mergeable')}.",
        )
    check_status, check_message = checks_state(
        pr.get("statusCheckRollup", [])
    )
    if check_status == "failing":
        add_finding(
            payload,
            "pull_request_checks_failing",
            "review",
            check_message,
        )


def collect_merge_state(git_root, handoff, body):
    repo = Path(git_root).resolve()
    branch = branch_name(repo)
    settings, settings_error = repository_merge_settings(repo)
    pr, pr_error = current_pr(repo)
    default_branch = (
        ((settings or {}).get("defaultBranchRef") or {}).get("name") or "main"
    )
    default_counts = None
    remote_default = f"origin/{default_branch}"
    if git(["rev-parse", "--verify", remote_default], repo).returncode == 0:
        counts = git(
            ["rev-list", "--left-right", "--count", f"{remote_default}...HEAD"],
            repo,
        )
        if counts.returncode == 0 and len(counts.stdout.split()) == 2:
            behind, ahead = [int(value) for value in counts.stdout.split()]
            default_counts = {"behind": behind, "ahead": ahead}
    return {
        "repo": str(repo),
        "branch": branch,
        "head": current_head(repo),
        "tree": current_tree(repo),
        "dirty": dirty_paths(repo),
        "handoff": handoff,
        "body": body,
        "settings": settings,
        "settingsError": settings_error,
        "defaultBranch": default_branch,
        "defaultCounts": default_counts,
        "pr": pr,
        "prError": pr_error,
    }


def build_merge_plan(state):
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "findings": [],
        "mergePlan": {
            "canMerge": False,
            "actions": [],
            "blockers": [],
            "warnings": [],
        },
        "branch": state.get("branch"),
        "defaultBranch": state.get("defaultBranch"),
        "candidate": {
            "commit": state.get("head"),
            "tree": state.get("tree"),
        },
        "pr": state.get("pr"),
    }
    handoff = state.get("handoff") or {}
    branch = state.get("branch") or ""
    if (
        not branch
        or branch == state.get("defaultBranch")
        or branch in {"main", "master"}
    ):
        add_finding(
            payload,
            "task_branch_required",
            "fail",
            "Merge automation requires a named task branch, not the default branch.",
        )
    if state.get("dirty"):
        add_finding(
            payload,
            "uncommitted_merge_work",
            "fail",
            "Commit or preserve all merge work before creating the PR: "
            + ", ".join(state["dirty"][:4]),
        )

    if handoff:
        expected_body = render_pr_body(handoff)
        if state.get("body") != expected_body:
            add_finding(
                payload,
                "pr_body_out_of_date",
                "fail",
                "PR body does not match the current merge handoff; run merge "
                "prepare again.",
            )
        bullet = f"- {projection_changelog_entry(handoff).strip()}"
        changelog_path = Path(state["repo"]) / "CHANGELOG.md"
        changelog = (
            changelog_path.read_text(encoding="utf-8")
            if changelog_path.is_file()
            else ""
        )
        if (
            not bullet.strip("- ")
            or sum(line.rstrip() == bullet for line in changelog.splitlines())
            != 1
        ):
            add_finding(
                payload,
                "changelog_mismatch",
                "fail",
                "CHANGELOG.md must contain the exact PR changelog entry once.",
            )

    counts = state.get("defaultCounts")
    if counts and counts.get("behind"):
        add_finding(
            payload,
            "branch_behind_default",
            "review",
            f"Task branch is behind origin/{state['defaultBranch']} by "
            f"{counts['behind']} commit(s); update and verify again before merge.",
        )
    if state.get("settingsError"):
        add_finding(
            payload,
            "merge_settings_unverified",
            "warn",
            "Could not verify repository merge settings; using merge-commit fallback.",
        )
    merge_method = merge_method_from_settings(state.get("settings"))
    if not merge_method:
        add_finding(
            payload,
            "no_allowed_merge_method",
            "fail",
            "Repository reports no allowed pull-request merge method.",
        )
    add_existing_pr_blockers(payload, state.get("pr"))
    if state.get("pr"):
        if state["pr"].get("headRefName") != branch:
            add_finding(
                payload,
                "pull_request_head_mismatch",
                "fail",
                "The existing pull request head does not match the task branch.",
            )
        if state["pr"].get("baseRefName") != state.get("defaultBranch"):
            add_finding(
                payload,
                "pull_request_base_mismatch",
                "fail",
                "The existing pull request base does not match the default branch.",
            )

    payload["status"] = status_for(payload)
    pr = state.get("pr")
    actions = [
        {"type": "git_push", "branch": branch},
        {
            "type": "gh_pr_edit" if pr else "gh_pr_create",
            "prNumber": pr.get("number") if pr else None,
        },
        {
            "type": "gh_pr_checks_watch",
            "prNumber": pr.get("number") if pr else None,
        },
        {
            "type": "gh_pr_merge",
            "prNumber": pr.get("number") if pr else None,
            "mergeMethod": merge_method,
        },
        {"type": "verify_default_branch", "branch": state.get("defaultBranch")},
        {"type": "delete_remote_branch", "branch": branch},
    ]
    blockers = [
        item["code"]
        for item in payload["findings"]
        if item["severity"] in {"review", "fail"}
    ]
    warnings = [
        item["code"]
        for item in payload["findings"]
        if item["severity"] == "warn"
    ]
    payload["mergePlan"] = {
        "canMerge": payload["status"] in {"pass", "warn"},
        "actions": actions if payload["status"] in {"pass", "warn"} else [],
        "blockers": blockers,
        "warnings": warnings,
    }
    return payload


def build_merge_payload(args):
    shell = {"schemaVersion": "1.0", "status": "pass", "findings": []}
    repo, data, body = load_merge_inputs(args, shell)
    if shell["findings"]:
        shell["status"] = status_for(shell)
        shell["mergePlan"] = {
            "canMerge": False,
            "actions": [],
            "blockers": [item["code"] for item in shell["findings"]],
            "warnings": [],
        }
        return shell
    return build_merge_plan(collect_merge_state(repo, data, body))


def refreshed_pr_is_mergeable(payload, pr, expected_head=None):
    if not pr:
        add_finding(
            payload,
            "pull_request_missing_after_publish",
            "fail",
            "Could not find the pull request after publishing it.",
        )
        return False
    before = len(payload["findings"])
    add_existing_pr_blockers(payload, pr)
    if expected_head and pr.get("headRefOid") != expected_head:
        add_finding(
            payload,
            "pull_request_head_drift",
            "fail",
            "Pull request head no longer matches the planned candidate revision.",
        )
    check_status, check_message = checks_state(
        pr.get("statusCheckRollup", [])
    )
    if check_status != "passing":
        add_finding(
            payload,
            f"pull_request_checks_{check_status}",
            "fail",
            check_message,
        )
    return len(payload["findings"]) == before


def wait_for_pr_checks(repo, timeout_seconds=60, poll_seconds=2):
    deadline = time.monotonic() + timeout_seconds
    last_error = None
    while True:
        pr, last_error = current_pr(repo)
        if pr and pr.get("statusCheckRollup"):
            return pr, None
        if time.monotonic() >= deadline:
            return (
                pr,
                last_error
                or f"No PR status checks were reported within {timeout_seconds} seconds.",
            )
        time.sleep(poll_seconds)


def delete_remote_branch(repo, branch, expected_sha=None, git_runner=None):
    git_runner = git_runner or git
    probe = git_runner(
        ["ls-remote", "--exit-code", "--heads", "origin", branch],
        repo,
    )
    if probe.returncode == 2:
        return subprocess.CompletedProcess(
            probe.args,
            0,
            probe.stdout,
            probe.stderr,
        )
    if probe.returncode != 0:
        return probe
    remote_values = probe.stdout.split()
    remote_sha = remote_values[0] if remote_values else ""
    if expected_sha and remote_sha != expected_sha:
        return subprocess.CompletedProcess(
            probe.args,
            1,
            probe.stdout,
            f"remote branch {branch} changed from expected {expected_sha} "
            f"to {remote_sha}; refusing cleanup",
        )

    deletion_args = ["push", "origin", f":refs/heads/{branch}"]
    if expected_sha:
        deletion_args.append(
            f"--force-with-lease=refs/heads/{branch}:{expected_sha}"
        )
    deletion = git_runner(deletion_args, repo)
    if deletion.returncode == 0:
        return deletion
    confirmation = git_runner(
        ["ls-remote", "--exit-code", "--heads", "origin", branch],
        repo,
    )
    if confirmation.returncode == 2:
        return subprocess.CompletedProcess(
            deletion.args,
            0,
            deletion.stdout,
            deletion.stderr,
        )
    return deletion


def execute_merge_plan(payload, git_root, handoff_source, body_path):
    repo = Path(git_root).resolve()
    executed = []
    branch = payload.get("branch")
    default_branch = payload.get("defaultBranch") or "main"
    handoff = (
        handoff_source
        if isinstance(handoff_source, dict)
        else load_merge_handoff(handoff_source)
    )
    pr = payload.get("pr")
    expected_head = (payload.get("candidate") or {}).get("commit")
    expected_tree = (payload.get("candidate") or {}).get("tree")
    if current_head(repo) != expected_head or current_tree(repo) != expected_tree:
        add_finding(
            payload,
            "candidate_revision_drift",
            "fail",
            "The candidate commit or tree changed after merge planning.",
        )
        payload["status"] = status_for(payload)
        return payload

    for action in payload.get("mergePlan", {}).get("actions", []):
        action_type = action["type"]
        if action_type == "git_push":
            result = git(["push", "-u", "origin", f"HEAD:{branch}"], repo)
        elif action_type == "gh_pr_create":
            result = gh(
                [
                    "pr",
                    "create",
                    "--title",
                    handoff["title"],
                    "--body-file",
                    str(body_path),
                    "--base",
                    default_branch,
                    "--head",
                    branch,
                ],
                repo,
            )
        elif action_type == "gh_pr_edit":
            result = gh(
                [
                    "pr",
                    "edit",
                    str(pr.get("number")),
                    "--title",
                    handoff["title"],
                    "--body-file",
                    str(body_path),
                ],
                repo,
            )
        elif action_type == "gh_pr_checks_watch":
            pr, checks_error = wait_for_pr_checks(repo)
            if checks_error:
                add_finding(
                    payload,
                    "pull_request_checks_missing",
                    "fail",
                    checks_error,
                )
                break
            if pr.get("headRefOid") != expected_head:
                add_finding(
                    payload,
                    "pull_request_head_drift",
                    "fail",
                    "Pull request head changed before checks were accepted.",
                )
                break
            action["prNumber"] = pr.get("number")
            result = gh(
                ["pr", "checks", str(pr.get("number")), "--watch"],
                repo,
            )
        elif action_type == "gh_pr_merge":
            pr, _ = current_pr(repo)
            if not refreshed_pr_is_mergeable(payload, pr, expected_head):
                break
            action["prNumber"] = pr.get("number")
            method = action.get("mergeMethod") or "merge"
            result = gh(
                [
                    "pr",
                    "merge",
                    str(pr.get("number")),
                    f"--{method}",
                    "--match-head-commit",
                    expected_head,
                ],
                repo,
            )
        elif action_type == "delete_remote_branch":
            result = delete_remote_branch(
                repo,
                branch,
                expected_sha=expected_head,
            )
        elif action_type == "verify_default_branch":
            fetch = git(["fetch", "origin", default_branch], repo)
            if fetch.returncode != 0:
                result = fetch
            else:
                represented = default_represents_candidate(
                    repo,
                    expected_head,
                    f"origin/{default_branch}",
                )
                result = subprocess.CompletedProcess(
                    ["verify-default-branch"],
                    0 if represented else 1,
                    "represented\n" if represented else "",
                    "" if represented else "landed revision does not represent candidate",
                )
        else:
            add_finding(
                payload,
                "unknown_merge_action",
                "fail",
                f"Unknown merge action: {action_type}",
            )
            break
        if result.returncode != 0:
            add_finding(
                payload,
                f"{action_type}_failed",
                "fail",
                result.stderr.strip()
                or result.stdout.strip()
                or f"{action_type} failed",
            )
            break
        executed.append(action)

    payload["executedActions"] = executed
    payload["pr"] = pr
    payload["status"] = status_for(payload)
    return payload


def command_merge_plan(args):
    payload = build_merge_payload(args)
    _print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_merge_execute(args):
    payload = build_merge_payload(args)
    if payload["status"] not in {"pass", "warn"}:
        _print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    repo = Path(args.git_root).resolve()
    body_path = merge_input_path(repo, args.body)
    handoff = merge_input_path(repo, args.handoff)
    payload = execute_merge_plan(payload, repo, handoff, body_path)
    _print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def dirty_paths(repo):
    status = git(["status", "--porcelain", "--untracked-files=all"], repo)
    if status.returncode != 0:
        raise RuntimeError(status.stderr.strip() or "git status failed")
    return [
        line[3:] if len(line) > 3 else line
        for line in status.stdout.splitlines()
        if line.strip()
    ]


def branch_name(repo):
    branch = git(["branch", "--show-current"], repo)
    if branch.returncode != 0:
        return ""
    return branch.stdout.strip()


def upstream_counts(repo):
    upstream = git(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        repo,
    )
    if upstream.returncode != 0:
        return None
    counts = git(
        ["rev-list", "--left-right", "--count", "@{u}...HEAD"],
        repo,
    )
    if counts.returncode != 0:
        raise RuntimeError(
            counts.stderr.strip() or "could not compare upstream"
        )
    parts = counts.stdout.strip().split()
    if len(parts) != 2:
        raise RuntimeError(
            f"unexpected upstream count output: {counts.stdout}"
        )
    return {
        "upstream": upstream.stdout.strip(),
        "behind": int(parts[0]),
        "ahead": int(parts[1]),
    }


def checks_state(status_rollup):
    if not status_rollup:
        return "missing", "No PR status checks were reported."

    pending = []
    failing = []
    for check in status_rollup:
        typename = check.get("__typename")
        if typename == "CheckRun":
            status = check.get("status")
            conclusion = check.get("conclusion")
            name = check.get("name", "check")
            if status != "COMPLETED":
                pending.append(name)
            elif conclusion not in PASSING_CHECK_CONCLUSIONS:
                failing.append(f"{name}={conclusion}")
        else:
            state = (
                check.get("state")
                or check.get("conclusion")
                or check.get("status")
            )
            name = check.get("context") or check.get("name") or "status"
            if state not in PASSING_STATUS_STATES:
                failing.append(f"{name}={state}")

    if failing:
        return "failing", "PR checks are failing: " + ", ".join(failing[:4])
    if pending:
        return "pending", "PR checks are still pending: " + ", ".join(
            pending[:4]
        )
    return "passing", "PR checks passed."


def current_pr(repo):
    result = gh(
        [
            "pr",
            "view",
            "--json",
            "number,state,isDraft,mergeable,mergedAt,statusCheckRollup,url,"
            "baseRefName,headRefName,headRefOid,reviewDecision",
        ],
        repo,
    )
    if result.returncode != 0:
        return None, result.stderr.strip() or result.stdout.strip()
    return json.loads(result.stdout), None
