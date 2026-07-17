"""Parent-owned Review Unit pull-request workflow."""

import json
import re
import time
from pathlib import Path

from gauntletlib.cli import EXIT_CODES
from gauntletlib.core.findings import add_finding as _add_finding
from gauntletlib.core.findings import status_for as _status_for
from gauntletlib.core.proc import gh, git, run_cmd


_merge_input_path = None
_run_prd_controller = None
_branch_name = None
_current_head = None
_dirty_paths = None
_checks_state = None
_delete_remote_branch = None
_print_payload = None


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


def configure(
    *,
    merge_input_path,
    run_prd_controller,
    branch_name,
    current_head,
    dirty_paths,
    checks_state,
    delete_remote_branch,
    print_payload,
):
    global _merge_input_path
    global _run_prd_controller
    global _branch_name
    global _current_head
    global _dirty_paths
    global _checks_state
    global _delete_remote_branch
    global _print_payload
    _merge_input_path = merge_input_path
    _run_prd_controller = run_prd_controller
    _branch_name = branch_name
    _current_head = current_head
    _dirty_paths = dirty_paths
    _checks_state = checks_state
    _delete_remote_branch = delete_remote_branch
    _print_payload = print_payload


def review_unit_status(repo, run_path, unit_id):
    output, error = _run_prd_controller(repo, [
        "review-unit-status", "--run", str(Path(run_path).resolve()),
        "--unit", unit_id,
    ])
    if error:
        return None, error
    try:
        return json.loads(output), None
    except json.JSONDecodeError as exc:
        return None, f"review-unit-status did not emit JSON: {exc}"


def update_review_unit(repo, run_path, unit_id, action, **fields):
    arguments = [
        "review-unit", "--run", str(Path(run_path).resolve()),
        "--unit", unit_id, "--action", action,
    ]
    for key, value in fields.items():
        if value is not None:
            arguments.extend([
                "--" + key.replace("_", "-"),
                str(value),
            ])
    _, error = _run_prd_controller(repo, arguments)
    return error


def review_unit_pr(repo, branch):
    result = gh([
        "pr", "list", "--head", branch, "--state", "open", "--limit", "1",
        "--json",
        "number,state,isDraft,mergeable,mergedAt,mergeCommit,"
        "statusCheckRollup,url,baseRefName,headRefName,headRefOid,"
        "reviewDecision",
    ], repo)
    if result.returncode != 0:
        return None, result.stderr.strip() or result.stdout.strip()
    try:
        values = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return None, f"GitHub review-unit query returned invalid JSON: {exc}"
    return (values[0] if values else None), None


def review_pr_identity_error(pr, integration_branch, branch, head_sha):
    if not pr:
        return "No open review-unit PR exists for the review branch."
    if pr.get("state") != "OPEN":
        return "Review-unit PR must be open."
    if (
        pr.get("baseRefName") != integration_branch
        or pr.get("headRefName") != branch
    ):
        return (
            "Review-unit PR base or head branch does not match the frozen "
            "Review Unit."
        )
    if pr.get("headRefOid") != head_sha:
        return (
            "Review-unit PR head changed; rerun checks against the exact "
            "remote head."
        )
    return None


def render_review_unit_body(status):
    unit = status["unit"]
    epics = sorted({ticket["epicId"] for ticket in unit["tickets"]})
    lines = [
        "## Review Unit",
        "",
        f"Unit `{unit['id']}` covers Epics {', '.join(epics)} and targets "
        f"integration branch `{status['integrationBranch']}`.",
        "",
        "## Included Tickets",
        "",
    ]
    for ticket in unit["tickets"]:
        lines.append(
            f"- **{ticket['id']} — {ticket['title']}**: "
            f"{ticket['objective']}"
        )
    lines.extend([
        "",
        "## Integration Contract",
        "",
        "- Checks bind this review branch to the current integration-branch "
        "commit and its synthetic merge tree.",
        "- Advancing the integration branch invalidates the merge-sensitive "
        "check and requires a recheck.",
        "- Merging this PR grants no authority to merge the final Project PR "
        "to the default branch.",
        "",
    ])
    return "\n".join(lines)


def review_unit_title(status):
    unit = status["unit"]
    titles = ", ".join(ticket["title"] for ticket in unit["tickets"][:2])
    if len(unit["tickets"]) > 2:
        titles += f" and {len(unit['tickets']) - 2} more"
    return f"review({unit['id'].lower()}): {titles}"


def review_unit_body_path(repo, unit_id, requested=None):
    path = (
        Path(requested)
        if requested
        else Path(".gauntlet") / f"review-unit-{unit_id.lower()}.md"
    )
    return path if path.is_absolute() else Path(repo) / path


def _review_unit_plan_findings(
    payload, status, unit_id, branch, body_path, write_body
):
    unit = status["unit"]
    integration_branch = status["integrationBranch"]
    if status.get("prStrategy") != "review-prs-plus-final":
        add_finding(
            payload, "review_unit_strategy_required", "fail",
            "Review-unit PRs require review-prs-plus-final.",
        )
    if (
        not branch
        or branch == integration_branch
        or branch in {"main", "master"}
    ):
        add_finding(
            payload, "review_unit_branch_required", "fail",
            "Run this command from the dedicated review-unit branch, not the "
            "integration or default branch.",
        )
    recorded_branch = unit.get("branch")
    if recorded_branch and recorded_branch != branch:
        add_finding(
            payload, "review_unit_branch_mismatch", "fail",
            f"Unit {unit_id} is bound to {recorded_branch}, not {branch}.",
        )
    if any(ticket["status"] != "integrated" for ticket in unit["tickets"]):
        add_finding(
            payload, "review_unit_tickets_not_integrated", "fail",
            "Every review-unit Ticket must have parent integration evidence "
            "before its PR can open.",
        )
    incomplete = [
        dependency for dependency in unit.get("dependencies", [])
        if status.get("dependencyStates", {}).get(dependency)
        not in {"merged", "verified", "cleanup-eligible", "cleaned"}
    ]
    if incomplete:
        add_finding(
            payload, "review_unit_dependencies_pending", "fail",
            "Review-unit dependencies are not merged: "
            + ", ".join(incomplete),
        )
    required = (
        ("push-review-branch", "open-review-pr")
        + (() if write_body else ("merge-to-integration",))
    )
    missing = [
        key for key in required if not status.get("authority", {}).get(key)
    ]
    if missing:
        add_finding(
            payload, "review_unit_authority_missing", "fail",
            "Missing review-unit authority: " + ", ".join(missing),
        )
    if _dirty_paths(payload["_repo"]):
        add_finding(
            payload, "uncommitted_review_unit_work", "fail",
            "Commit or preserve review-unit work before opening its PR.",
        )
    if write_body and not payload["findings"]:
        body_path.parent.mkdir(parents=True, exist_ok=True)
        body_path.write_text(render_review_unit_body(status), encoding="utf-8")
    elif not write_body:
        expected = render_review_unit_body(status)
        if (
            not body_path.is_file()
            or body_path.read_text(encoding="utf-8") != expected
        ):
            add_finding(
                payload, "review_unit_body_out_of_date", "fail",
                "Run review-unit prepare again before plan or execute.",
            )


def review_unit_plan_payload(args, write_body=False):
    repo = Path(args.git_root).resolve()
    run_path = _merge_input_path(repo, args.run)
    payload = {
        "schemaVersion": "1.0", "status": "pass", "findings": [],
        "actions": [], "run": str(run_path), "unit": args.unit,
        "_repo": repo,
    }
    status, error = review_unit_status(repo, run_path, args.unit)
    if error:
        payload.pop("_repo")
        add_finding(payload, "review_unit_status_failed", "fail", error)
        payload["status"] = status_for(payload)
        return payload
    payload["reviewUnit"] = status
    branch = _branch_name(repo)
    integration_branch = status["integrationBranch"]
    payload["branch"] = branch
    payload["integrationBranch"] = integration_branch
    body_path = review_unit_body_path(
        repo,
        args.unit,
        getattr(args, "body", None) or getattr(args, "body_output", None),
    )
    payload["bodyPath"] = str(body_path)
    _review_unit_plan_findings(
        payload, status, args.unit, branch, body_path, write_body
    )
    payload.pop("_repo")

    fetch = git(["fetch", "origin", integration_branch], repo)
    if fetch.returncode != 0:
        add_finding(
            payload, "review_unit_base_fetch_failed", "fail",
            fetch.stderr.strip() or fetch.stdout.strip(),
        )
    else:
        base = git(["rev-parse", f"origin/{integration_branch}"], repo)
        if base.returncode == 0:
            payload["testedBaseSha"] = base.stdout.strip()
    pr, pr_error = review_unit_pr(repo, branch) if branch else (None, None)
    payload["pr"] = pr
    if pr_error:
        add_finding(
            payload, "review_unit_pr_unverified", "warn", pr_error
        )
    if pr and (
        pr.get("baseRefName") != integration_branch
        or pr.get("headRefName") != branch
    ):
        add_finding(
            payload, "review_unit_pr_branch_mismatch", "fail",
            "Existing review PR does not match the frozen head/base branches.",
        )
    payload["status"] = status_for(payload)
    if payload["status"] in {"pass", "warn"}:
        payload["actions"] = [
            {"type": "git_push", "branch": branch},
            {"type": "gh_pr_edit" if pr else "gh_pr_create"},
            {"type": "record_review_opened"},
            {"type": "gh_pr_checks_watch"},
            {"type": "record_review_checked"},
            {"type": "record_review_merge_lock"},
            {"type": "git_push_integration_with_lease"},
            {"type": "verify_review_merge"},
            {"type": "cleanup_review_branch"},
        ]
    return payload


def command_review_unit_prepare(args):
    payload = review_unit_plan_payload(args, write_body=True)
    _print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_review_unit_plan(args):
    payload = review_unit_plan_payload(args)
    _print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def wait_for_review_unit_checks(
    repo, branch, timeout_seconds=60, poll_seconds=2
):
    deadline = time.monotonic() + timeout_seconds
    last_error = None
    while True:
        pr, last_error = review_unit_pr(repo, branch)
        if pr and pr.get("statusCheckRollup"):
            return pr, None
        if time.monotonic() >= deadline:
            return (
                pr,
                last_error
                or f"No review-unit checks were reported within "
                f"{timeout_seconds} seconds.",
            )
        time.sleep(poll_seconds)


def synthetic_merge_tree(repo, base_sha, head_sha):
    result = git(["merge-tree", "--write-tree", base_sha, head_sha], repo)
    if result.returncode != 0:
        return (
            None,
            result.stderr.strip()
            or result.stdout.strip()
            or "synthetic merge failed",
        )
    first = (
        result.stdout.splitlines()[0].strip()
        if result.stdout.splitlines()
        else ""
    )
    if not re.fullmatch(r"[0-9a-f]{40,64}", first):
        return None, "git merge-tree did not return a merge tree object ID"
    return first, None


def find_review_merge(repo, tip, base_sha, head_sha, tree_sha):
    history = git(["rev-list", "--first-parent", tip, f"^{base_sha}"], repo)
    if history.returncode != 0:
        return None
    for commit in history.stdout.splitlines():
        parents = git(["rev-list", "--parents", "-n", "1", commit], repo)
        tree = git(["rev-parse", f"{commit}^{{tree}}"], repo)
        values = parents.stdout.split() if parents.returncode == 0 else []
        if (
            len(values) == 3
            and values[1:] == [base_sha, head_sha]
            and tree.returncode == 0
            and tree.stdout.strip() == tree_sha
        ):
            return commit
    return None


def review_unit_evidence_path(
    run_path, unit_id, kind, discriminator
):
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", unit_id.lower())
    return (
        Path(run_path)
        / "evidence"
        / f"review-unit-{safe}-{kind}-{discriminator[:12]}.md"
    )


def _execute_open(context):
    payload = context["payload"]
    unit = context["unit"]
    if (
        payload["status"] not in {"pass", "warn"}
        or unit.get("state") != "pending"
    ):
        return
    repo = context["repo"]
    branch = context["branch"]
    result = git(["push", "-u", "origin", f"HEAD:{branch}"], repo)
    if result.returncode != 0:
        context["fail"](
            "review_unit_push_failed",
            result.stderr.strip() or result.stdout.strip(),
        )
        return
    context["executed"].append({"type": "git_push", "branch": branch})
    pr, _ = review_unit_pr(repo, branch)
    status = context["status"]
    if pr:
        result = gh([
            "pr", "edit", str(pr["number"]), "--title",
            review_unit_title(status), "--body-file",
            str(context["body_path"]),
        ], repo)
        action = "gh_pr_edit"
    else:
        result = gh([
            "pr", "create", "--title", review_unit_title(status),
            "--body-file", str(context["body_path"]),
            "--base", context["integration_branch"], "--head", branch,
        ], repo)
        action = "gh_pr_create"
    if result.returncode != 0:
        context["fail"](
            f"review_unit_{action}_failed",
            result.stderr.strip() or result.stdout.strip(),
        )
        return
    context["executed"].append({"type": action})
    pr, pr_error = review_unit_pr(repo, branch)
    if not pr:
        context["fail"](
            "review_unit_pr_missing",
            pr_error
            or "Review-unit PR was not discoverable after publication.",
        )
        return
    identity_error = review_pr_identity_error(
        pr,
        context["integration_branch"],
        branch,
        _current_head(repo),
    )
    if identity_error:
        context["fail"](
            "review_unit_pr_identity_mismatch", identity_error
        )
        return
    error = update_review_unit(
        repo,
        context["run_path"],
        context["unit_id"],
        "opened",
        branch=branch,
        pr=pr.get("url") or f"#{pr.get('number')}",
    )
    if error:
        context["fail"]("record_review_opened_failed", error)
        return
    context["executed"].append({"type": "record_review_opened"})
    status, _ = review_unit_status(
        repo, context["run_path"], context["unit_id"]
    )
    context["status"] = status
    context["unit"] = status["unit"]


def _review_check_needed(context):
    unit = context["unit"]
    checked = unit.get("check", {})
    base_drift = (
        unit.get("state") == "merge-locked"
        and context["payload"].get("testedBaseSha")
        != checked.get("tested_base_sha")
    )
    recoverable_merge = None
    if base_drift:
        recoverable_merge = find_review_merge(
            context["repo"],
            f"origin/{context['integration_branch']}",
            checked.get("tested_base_sha"),
            checked.get("head_sha"),
            checked.get("tested_tree_sha"),
        )
    should_check = unit.get("state") in {"opened", "checked"} or (
        unit.get("state") == "merge-locked"
        and (
            _current_head(context["repo"]) != checked.get("head_sha")
            or (base_drift and recoverable_merge is None)
        )
    )
    return should_check


def _record_passing_review_check(context, pr, base, head):
    repo = context["repo"]
    tree, tree_error = synthetic_merge_tree(repo, base, head)
    if tree_error:
        context["fail"]("review_unit_synthetic_merge_failed", tree_error)
        return
    evidence = review_unit_evidence_path(
        context["run_path"],
        context["unit_id"],
        "check",
        base + head,
    )
    evidence.write_text(
        "# Review unit check\n\n"
        f"Unit: {context['unit_id']}\n\nHead: {head}\n\n"
        f"Tested base: {base}\n\n"
        f"Synthetic merge tree: {tree}\n\nGitHub checks: pass\n",
        encoding="utf-8",
    )
    error = update_review_unit(
        repo,
        context["run_path"],
        context["unit_id"],
        "checked",
        head_sha=head,
        tested_base_sha=base,
        tested_tree_sha=tree,
        proof_command=f"gh pr checks {pr['number']} --watch",
        proof_result="pass",
        proof_evidence=evidence,
    )
    if error:
        context["fail"]("record_review_checked_failed", error)
        return
    context["executed"].append({
        "type": "record_review_checked",
        "testedBaseSha": base,
        "testedTreeSha": tree,
    })
    error = update_review_unit(
        repo,
        context["run_path"],
        context["unit_id"],
        "merge-locked",
        current_base_sha=base,
    )
    if error:
        context["fail"]("record_review_merge_lock_failed", error)
        return
    context["executed"].append({"type": "record_review_merge_lock"})
    status, _ = review_unit_status(
        repo, context["run_path"], context["unit_id"]
    )
    context["status"] = status
    context["unit"] = status["unit"]


def _execute_checks(context):
    payload = context["payload"]
    if (
        payload["status"] not in {"pass", "warn"}
        or not _review_check_needed(context)
    ):
        return
    repo = context["repo"]
    branch = context["branch"]
    integration_branch = context["integration_branch"]
    refresh = git(["fetch", "origin", integration_branch, branch], repo)
    if refresh.returncode != 0:
        context["fail"](
            "review_unit_refresh_failed",
            refresh.stderr.strip() or refresh.stdout.strip(),
        )
        return
    base = git(["rev-parse", f"origin/{integration_branch}"], repo).stdout.strip()
    head = git(["rev-parse", f"origin/{branch}"], repo).stdout.strip()
    local_head = _current_head(repo)
    pr, checks_error = wait_for_review_unit_checks(repo, branch)
    identity_error = review_pr_identity_error(
        pr, integration_branch, branch, head
    )
    if checks_error:
        context["fail"]("review_unit_checks_missing", checks_error)
        return
    if local_head != head:
        context["fail"](
            "review_unit_local_head_drift",
            "Local HEAD must equal the exact remote review branch head before "
            "checks are accepted.",
        )
        return
    if identity_error:
        context["fail"](
            "review_unit_pr_identity_mismatch", identity_error
        )
        return
    check_state, check_message = _checks_state(
        pr.get("statusCheckRollup", [])
    )
    if check_state != "passing":
        context["fail"](
            f"review_unit_checks_{check_state}", check_message
        )
        return
    result = gh(["pr", "checks", str(pr["number"]), "--watch"], repo)
    if result.returncode != 0:
        context["fail"](
            "review_unit_checks_failed",
            result.stderr.strip() or result.stdout.strip(),
        )
        return
    context["executed"].append({
        "type": "gh_pr_checks_watch",
        "prNumber": pr["number"],
    })
    _refresh_and_record_review_check(context, pr, base, head)


def _refresh_and_record_review_check(context, pr, base, head):
    repo = context["repo"]
    branch = context["branch"]
    integration_branch = context["integration_branch"]
    fetch = git(["fetch", "origin", integration_branch, branch], repo)
    refreshed_pr, pr_error = review_unit_pr(repo, branch)
    refreshed_base = (
        git(["rev-parse", f"origin/{integration_branch}"], repo).stdout.strip()
        if fetch.returncode == 0
        else ""
    )
    refreshed_head = (
        git(["rev-parse", f"origin/{branch}"], repo).stdout.strip()
        if fetch.returncode == 0
        else ""
    )
    identity_error = review_pr_identity_error(
        refreshed_pr, integration_branch, branch, head
    )
    if fetch.returncode != 0:
        context["fail"](
            "review_unit_refresh_failed",
            fetch.stderr.strip() or fetch.stdout.strip(),
        )
    elif pr_error:
        context["fail"]("review_unit_pr_refresh_failed", pr_error)
    elif (
        refreshed_base != base
        or refreshed_head != head
        or _current_head(repo) != head
    ):
        context["fail"](
            "review_unit_head_changed_after_checks",
            "Review or integration branch changed while checks were running; "
            "recheck the new tuple.",
        )
    elif identity_error:
        context["fail"](
            "review_unit_pr_identity_mismatch", identity_error
        )
    else:
        _record_passing_review_check(context, pr, base, head)


def _resolve_or_create_merge_commit(context):
    repo = context["repo"]
    unit = context["unit"]
    integration_branch = context["integration_branch"]
    fetch = git(["fetch", "origin", integration_branch], repo)
    current_base = (
        git(["rev-parse", f"origin/{integration_branch}"], repo).stdout.strip()
        if fetch.returncode == 0
        else ""
    )
    locked_base = unit.get("merge_lock", {}).get("base_sha")
    head = unit.get("check", {}).get("head_sha")
    tested_tree = unit.get("check", {}).get("tested_tree_sha")
    merge_commit = None
    if fetch.returncode == 0 and current_base != locked_base:
        merge_commit = find_review_merge(
            repo,
            f"origin/{integration_branch}",
            locked_base,
            head,
            tested_tree,
        )
        if merge_commit is None:
            context["fail"](
                "review_unit_base_changed_after_lock",
                "Integration branch advanced after merge lock; rerun execute "
                "to recheck against the new base.",
            )
    elif fetch.returncode != 0:
        context["fail"](
            "review_unit_base_refresh_failed",
            fetch.stderr.strip() or fetch.stdout.strip(),
        )
    if (
        context["payload"]["status"] not in {"pass", "warn"}
        or merge_commit is not None
    ):
        return merge_commit
    commit = run_cmd([
        "git", "commit-tree", tested_tree, "-p", locked_base, "-p", head,
        "-m",
        f"Merge review unit {context['unit_id']} into {integration_branch}",
    ], cwd=repo)
    if commit.returncode != 0:
        context["fail"](
            "review_unit_merge_commit_failed",
            commit.stderr.strip() or commit.stdout.strip(),
        )
        return None
    merge_commit = commit.stdout.strip()
    push = git([
        "push", "origin",
        f"{merge_commit}:refs/heads/{integration_branch}",
        f"--force-with-lease=refs/heads/{integration_branch}:{locked_base}",
    ], repo)
    if push.returncode != 0:
        context["fail"](
            "review_unit_integration_push_failed",
            push.stderr.strip() or push.stdout.strip(),
        )
        return None
    context["executed"].append({
        "type": "git_push_integration_with_lease",
        "mergeSha": merge_commit,
    })
    return merge_commit


def _record_review_merge(context, merge_commit):
    repo = context["repo"]
    integration_branch = context["integration_branch"]
    refreshed = git(["fetch", "origin", integration_branch], repo)
    tree_result = git(["rev-parse", f"{merge_commit}^{{tree}}"], repo)
    reachable = (
        git([
            "merge-base", "--is-ancestor", merge_commit,
            f"origin/{integration_branch}",
        ], repo)
        if refreshed.returncode == 0
        else refreshed
    )
    if refreshed.returncode != 0:
        context["fail"](
            "review_unit_base_refresh_failed",
            refreshed.stderr.strip() or refreshed.stdout.strip(),
        )
        return
    if tree_result.returncode != 0:
        context["fail"](
            "review_unit_merge_tree_missing",
            tree_result.stderr.strip() or tree_result.stdout.strip(),
        )
        return
    if reachable.returncode != 0:
        context["fail"](
            "review_unit_merge_not_on_integration",
            "Recorded review merge is not reachable from the remote "
            "integration branch.",
        )
        return
    error = update_review_unit(
        repo,
        context["run_path"],
        context["unit_id"],
        "merged",
        merge_sha=merge_commit,
        merged_tree_sha=tree_result.stdout.strip(),
    )
    if error:
        context["fail"]("record_review_merged_failed", error)
        return
    context["executed"].append({
        "type": "record_review_merged",
        "mergeSha": merge_commit,
    })
    status, _ = review_unit_status(
        repo, context["run_path"], context["unit_id"]
    )
    context["status"] = status
    context["unit"] = status["unit"]


def _execute_merge(context):
    if (
        context["payload"]["status"] not in {"pass", "warn"}
        or context["unit"].get("state") != "merge-locked"
    ):
        return
    merge_commit = _resolve_or_create_merge_commit(context)
    if (
        context["payload"]["status"] in {"pass", "warn"}
        and merge_commit
    ):
        _record_review_merge(context, merge_commit)


def _execute_verify(context):
    if (
        context["payload"]["status"] not in {"pass", "warn"}
        or context["unit"].get("state") != "merged"
    ):
        return
    repo = context["repo"]
    unit = context["unit"]
    integration_branch = context["integration_branch"]
    head = unit.get("check", {}).get("head_sha")
    merge_sha = unit.get("merge_sha")
    refreshed = git(["fetch", "origin", integration_branch], repo)
    ancestor = git(["merge-base", "--is-ancestor", head, merge_sha], repo)
    remote_ancestor = (
        git([
            "merge-base", "--is-ancestor", merge_sha,
            f"origin/{integration_branch}",
        ], repo)
        if refreshed.returncode == 0
        else refreshed
    )
    if refreshed.returncode != 0:
        context["fail"](
            "review_unit_verification_refresh_failed",
            refreshed.stderr.strip() or refreshed.stdout.strip(),
        )
        return
    if ancestor.returncode != 0:
        context["fail"](
            "review_unit_merge_not_verified",
            "Reviewed head is not reachable from the recorded merge commit.",
        )
        return
    if remote_ancestor.returncode != 0:
        context["fail"](
            "review_unit_merge_not_on_integration",
            "Recorded review merge is absent from the remote integration "
            "branch.",
        )
        return
    evidence = review_unit_evidence_path(
        context["run_path"],
        context["unit_id"],
        "verified",
        merge_sha,
    )
    evidence.write_text(
        f"# Review unit verification\n\nUnit: {context['unit_id']}\n\n"
        f"Head: {head}\n\nMerge commit: {merge_sha}\n\n"
        "Reachability: pass\n",
        encoding="utf-8",
    )
    error = update_review_unit(
        repo,
        context["run_path"],
        context["unit_id"],
        "verified",
        evidence=evidence,
        summary=(
            "The reviewed head is reachable from the recorded integration "
            "merge commit and its tree matches the tested synthetic merge."
        ),
    )
    if error:
        context["fail"]("record_review_verified_failed", error)
        return
    context["executed"].append({"type": "record_review_verified"})
    status, _ = review_unit_status(
        repo, context["run_path"], context["unit_id"]
    )
    context["status"] = status
    context["unit"] = status["unit"]


def _execute_cleanup(context):
    payload = context["payload"]
    repo = context["repo"]
    run_path = context["run_path"]
    unit_id = context["unit_id"]
    if (
        payload["status"] in {"pass", "warn"}
        and context["unit"].get("state") == "verified"
    ):
        error = update_review_unit(
            repo, run_path, unit_id, "cleanup-eligible"
        )
        if error:
            context["fail"](
                "record_review_cleanup_eligible_failed", error
            )
        else:
            context["executed"].append({
                "type": "record_review_cleanup_eligible"
            })
            status, _ = review_unit_status(repo, run_path, unit_id)
            context["status"] = status
            context["unit"] = status["unit"]
    if (
        payload["status"] not in {"pass", "warn"}
        or context["unit"].get("state") != "cleanup-eligible"
    ):
        return
    deletion = _delete_remote_branch(
        repo,
        context["branch"],
        expected_sha=context["unit"].get("check", {}).get("head_sha"),
    )
    if deletion.returncode != 0:
        context["fail"](
            "review_unit_remote_cleanup_failed",
            deletion.stderr.strip() or deletion.stdout.strip(),
        )
        return
    error = update_review_unit(repo, run_path, unit_id, "cleaned")
    if error:
        context["fail"]("record_review_cleaned_failed", error)
    else:
        context["executed"].append({
            "type": "cleanup_review_branch",
            "branch": context["branch"],
        })


def command_review_unit_execute(args):
    payload = review_unit_plan_payload(args)
    if payload["status"] not in {"pass", "warn"}:
        _print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    repo = Path(args.git_root).resolve()
    run_path = _merge_input_path(repo, args.run)
    executed = []

    def fail(code, message):
        add_finding(payload, code, "fail", message)
        payload["status"] = status_for(payload)

    status, error = review_unit_status(repo, run_path, args.unit)
    if error:
        fail("review_unit_status_failed", error)
    context = {
        "payload": payload,
        "repo": repo,
        "run_path": run_path,
        "unit_id": args.unit,
        "branch": payload["branch"],
        "integration_branch": payload["integrationBranch"],
        "body_path": Path(payload["bodyPath"]),
        "executed": executed,
        "fail": fail,
        "status": status,
        "unit": (status or {}).get("unit", {}),
    }
    _execute_open(context)
    _execute_checks(context)
    _execute_merge(context)
    _execute_verify(context)
    _execute_cleanup(context)
    payload["executedActions"] = executed
    payload["status"] = status_for(payload)
    _print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]
