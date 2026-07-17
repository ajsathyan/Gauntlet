"""Contextual merge planning, execution, reconciliation, and cleanup."""

import json
import re
import subprocess
import sys
import time
from pathlib import Path

from gauntletlib.cli import EXIT_CODES
from gauntletlib.contracts import handoff_finding
from gauntletlib.contracts import merge_binding_digest
from gauntletlib.contracts import nonempty_string
from gauntletlib.contracts import validate_merge_handoff
from gauntletlib.contracts import validate_run_merge_handoff
from gauntletlib.core.findings import add_finding as _add_finding
from gauntletlib.core.findings import status_for as _status_for
from gauntletlib.core.fsio import atomic_write_text, write_new_file
from gauntletlib.core.proc import gh, git, run_cmd

PASSING_CHECK_CONCLUSIONS = {"SUCCESS", "SKIPPED", "NEUTRAL"}
PASSING_STATUS_STATES = {"SUCCESS", "SKIPPED", "NEUTRAL"}

_load_launch_set = None
_launch_source_text = None
_prd_controller_path = None
_run_authority_granted = None
_run_prd_controller = None
_print_payload = None

def configure(*, load_launch_set, launch_source_text, prd_controller_path, run_authority_granted, run_prd_controller, print_payload):
    global _load_launch_set, _launch_source_text, _prd_controller_path
    global _run_authority_granted, _run_prd_controller, _print_payload
    _load_launch_set = load_launch_set
    _launch_source_text = launch_source_text
    _prd_controller_path = prd_controller_path
    _run_authority_granted = run_authority_granted
    _run_prd_controller = run_prd_controller
    _print_payload = print_payload

def add_finding(payload, code, severity, message, **details):
    _add_finding(payload.setdefault("findings", []), code, severity, message, **details)

def status_for(payload):
    return _status_for(payload.get("findings", []))

def launch_merge_lease_path(launch_path):
    launch_path = Path(launch_path).resolve()
    return launch_path.with_name(launch_path.stem + ".merge-lease.json")


def current_default_head(repo):
    symbolic = git(["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"], repo)
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
            raise ValueError(fetched.stderr.strip() or fetched.stdout.strip() or "Cannot refresh origin before merge")
    return current_default_head(repo)


def run_launch_lease_context(run_path, handoff):
    run_path = Path(run_path).resolve()
    lock_path = run_path / "source-lock.json"
    if not lock_path.is_file():
        raise ValueError("Run-backed merge requires source-lock.json with an Epic launch binding")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    target = lock.get("target_epic_ids")
    launch_binding = lock.get("launch_set")
    if not isinstance(target, list) or len(target) != 1 or not isinstance(launch_binding, dict):
        raise ValueError("Run-backed merge requires exactly one launch-bound Epic")
    launch_path, launch = _load_launch_set(launch_binding.get("path", ""))
    _launch_source_text(launch)
    epic_id = target[0]
    epic = launch["epics"].get(epic_id)
    if (
        launch_binding.get("coverage_sha256") != launch["coverageSha256"]
        or handoff.get("epic", {}).get("id") != epic_id
        or handoff.get("binding", {}).get("runId") != run_path.name
        or not epic
        or epic.get("taskId") != launch_binding.get("task_id")
        or Path(epic.get("runPath") or "").resolve() != run_path
    ):
        raise ValueError("Run, launch coverage, Epic, task, or run-path binding does not match")
    return launch_path, launch, epic_id


def acquire_run_merge_lease(
    repo,
    run_path,
    handoff,
    *,
    refresh_default_head_fn=None,
    git_fn=None,
    persist_merge_lease_fn=None,
):
    launch_path, launch, epic_id = run_launch_lease_context(run_path, handoff)
    candidate = handoff["binding"]["headSha"]
    refresh = refresh_default_head_fn or refresh_default_head
    run_git = git_fn or git
    persist = persist_merge_lease_fn or persist_merge_lease
    default_head, default_ref = refresh(repo)
    if run_git(["merge-base", "--is-ancestor", default_head, candidate], repo).returncode != 0:
        raise ValueError("Verified Epic candidate does not contain the current default-branch head; re-integrate and reverify")
    lease = {
        "schemaVersion": "gauntlet.epic-merge-lease.v1",
        "coverageSha256": launch["coverageSha256"],
        "epicId": epic_id,
        "candidateHead": candidate,
        "baseHead": default_head,
        "baseRef": default_ref,
    }
    lease_path = launch_merge_lease_path(launch_path)
    persist(repo, lease_path, lease, default_head)
    return lease_path, lease


def persist_merge_lease(
    repo,
    lease_path,
    lease,
    default_head,
    *,
    default_represents_candidate_fn=None,
):
    represents_candidate = (
        default_represents_candidate_fn or default_represents_candidate
    )
    if lease_path.exists():
        current = json.loads(lease_path.read_text(encoding="utf-8"))
        if current != lease:
            if current.get("epicId") == lease["epicId"] and current.get("candidateHead") == lease["candidateHead"]:
                lease_path.unlink()
                raise ValueError("Default branch changed while this Epic held the merge lease; re-integrate and reverify")
            if current.get("epicId") == lease["epicId"]:
                old_candidate = current.get("candidateHead")
                if represents_candidate(repo, old_candidate, default_head):
                    raise ValueError("The previous leased Epic candidate is already on the default branch; reconcile that merge before replacing the lease")
                atomic_write_text(lease_path, json.dumps(lease, indent=2, sort_keys=True) + "\n")
            else:
                raise ValueError(f"Default-branch merge lease is held by {current.get('epicId', 'another Epic')}")
    else:
        write_new_file(lease_path, json.dumps(lease, indent=2, sort_keys=True) + "\n")


def validate_run_merge_lease(repo, lease_path, lease):
    if not Path(lease_path).is_file() or json.loads(Path(lease_path).read_text(encoding="utf-8")) != lease:
        raise ValueError("Run-backed merge lease disappeared or changed")
    default_head, _ = refresh_default_head(repo)
    if default_head != lease["baseHead"]:
        Path(lease_path).unlink(missing_ok=True)
        raise ValueError("Default branch advanced after lease acquisition; re-integrate and reverify")
    if git(["merge-base", "--is-ancestor", lease["baseHead"], lease["candidateHead"]], repo).returncode != 0:
        raise ValueError("Leased candidate no longer contains its verified default-branch base")


def default_represents_candidate(repo, candidate, default_head, *, git_fn=None):
    run_git = git_fn or git
    ancestry = run_git(["merge-base", "--is-ancestor", candidate, default_head], repo)
    if ancestry.returncode == 0:
        return True
    if ancestry.returncode != 1:
        raise ValueError(ancestry.stderr.strip() or "Cannot determine candidate ancestry")
    candidate_tree = run_git(["rev-parse", f"{candidate}^{{tree}}"], repo)
    default_tree = run_git(["rev-parse", f"{default_head}^{{tree}}"], repo)
    if candidate_tree.returncode != 0 or default_tree.returncode != 0:
        raise ValueError(candidate_tree.stderr.strip() or default_tree.stderr.strip() or "Cannot compare candidate and default trees")
    return (
        candidate_tree.stdout.strip() == default_tree.stdout.strip()
    )


def release_run_merge_lease(
    repo,
    lease_path,
    lease,
    merged_head,
    *,
    refresh_default_head_fn=None,
    default_represents_candidate_fn=None,
    git_fn=None,
):
    refresh = refresh_default_head_fn or refresh_default_head
    represents_candidate = (
        default_represents_candidate_fn or default_represents_candidate
    )
    run_git = git_fn or git
    default_head, _ = refresh(repo)
    if not represents_candidate(repo, lease["candidateHead"], merged_head):
        raise ValueError("Recorded merge head preserves neither candidate ancestry nor the exact candidate tree")
    if run_git(["merge-base", "--is-ancestor", merged_head, default_head], repo).returncode != 0:
        raise ValueError("Current default branch does not contain the recorded merge head")
    if not Path(lease_path).is_file() or json.loads(Path(lease_path).read_text(encoding="utf-8")) != lease:
        raise ValueError("Run-backed merge lease changed before release")
    Path(lease_path).unlink()


def persisted_run_merge_lease(run_path, handoff):
    """Return the exact launch lease for interrupted merge recovery, if one exists."""
    launch_path, launch, epic_id = run_launch_lease_context(run_path, handoff)
    lease_path = launch_merge_lease_path(launch_path)
    if not lease_path.is_file():
        return None
    lease = json.loads(lease_path.read_text(encoding="utf-8"))
    expected = {
        "schemaVersion": "gauntlet.epic-merge-lease.v1",
        "coverageSha256": launch["coverageSha256"],
        "epicId": epic_id,
        "candidateHead": handoff["binding"]["headSha"],
    }
    if any(lease.get(key) != value for key, value in expected.items()):
        raise ValueError("Persisted merge lease does not match this launch-bound Epic candidate")
    if not nonempty_string(lease.get("baseHead")) or not nonempty_string(lease.get("baseRef")):
        raise ValueError("Persisted merge lease is incomplete")
    return lease_path, lease


def recorded_run_merge_head(run_path):
    manifest = json.loads((Path(run_path) / "manifest.json").read_text(encoding="utf-8"))
    main_sha = manifest.get("release", {}).get("merge", {}).get("main_sha")
    if not re.fullmatch(r"[0-9a-f]{7,64}", main_sha or ""):
        raise ValueError("Execution Run has no valid recorded merge head")
    return main_sha


def load_merge_handoff(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def render_run_pr_body(data):
    epic = data["epic"]
    completion = data["completion"]
    accepted_criteria = data["acceptedCriteria"]
    if isinstance(accepted_criteria, dict):
        accepted_lines = []
        for group, criteria in accepted_criteria.items():
            accepted_lines.extend([f"### {group}", "", *[f"- {item}" for item in criteria], ""])
    else:
        accepted_lines = [*[f"- {item}" for item in accepted_criteria], ""]
    lines = [
        f"## Epic {epic['id']}: {epic['title']}", "",
        f"Implementation state: **{completion['exactState']}**", "",
        "### Scope Areas", "",
        *[f"- `{scope['id']}` — {scope['responsibility']}" for scope in epic["scopeAreas"]], "",
        "## Accepted Criteria", "",
        *accepted_lines,
        "## Changed Paths", "",
        *([f"- `{path}`" for path in data["changedPaths"]] or ["- None recorded."]), "",
        "## Verification", "",
        f"- Exact verified revision: `{completion['exactRevision']}`",
        f"- {completion['verificationSummary'] or 'Final Epic verification passed.'}",
        *[f"- Receipt: `{receipt}`" for receipt in data["verificationReceipts"]], "",
        "## Completion State", "",
        f"- Implemented: {'yes' if completion['implemented'] else 'no'}",
        f"- Merged: {'yes' if completion['merged'] else 'no'}",
        f"- Deployed: {'yes' if completion['deployed'] else 'no'}",
        f"- Production-proved: {'yes' if completion['productionProved'] else 'no'}",
        f"- Complete across applicable stages: {'yes' if completion['complete'] else 'no'}", "",
        "## Deferrals", "",
        *([f"- Cannot verify: {item}" for item in data["deferrals"]["cannotVerify"]] or ["- Cannot verify: none."]),
        *([f"- Non-goal: {item}" for item in data["deferrals"]["nonGoals"]] or ["- Non-goals: none."]), "",
        "## Release Gates", "",
    ]
    for gate in data["releaseGates"]:
        evidence = f" Evidence: {', '.join(item.strip() for item in gate['evidenceRefs'])}." if gate["evidenceRefs"] else ""
        lines.append(
            f"- **{gate['id'].strip()} — {gate['stage'].strip()}**: {gate['status'].strip()} — "
            f"{gate['summary'].strip()} (blocks PR: {'yes' if gate['blocksPr'] else 'no'}; "
            f"blocks overall completion: {'yes' if gate['blocksOverallCompletion'] else 'no'}).{evidence}"
        )
    lines.extend(["", f"<!-- gauntlet-merge-binding: {merge_binding_digest(data)} -->"])
    return "\n".join(lines).rstrip() + "\n"


def render_pr_body(data):
    if data.get("schemaVersion") == "3.0":
        return render_run_pr_body(data)
    solution = data["solution"]
    solution_parts = [solution["outcome"].strip()]
    for label, field in [("Invariants", "invariants"), ("Preserved", "preserved"), ("Non-goals", "nonGoals")]:
        items = solution.get(field, [])
        if items:
            solution_parts.extend(["", f"{label}:", *[f"- {item.strip()}" for item in items]])

    testing = [
        f"- `{item['command'].strip()}` — **{item['result'].strip().upper()}** — {item['proves'].strip()}"
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
        lines.extend(["", "## Security / Risk", "", data["securityRisk"].strip()])
    return "\n".join(lines).rstrip() + "\n"


def projection_changelog_entry(data):
    if data.get("schemaVersion") == "3.0":
        epic = data["epic"]
        return f"Implement {epic['id']}: {epic['title']}."
    return data["changelog"]


def pending_run_merge_gates(handoff):
    return [
        gate for gate in handoff.get("releaseGates", [])
        if gate.get("stage") == "merge" and gate.get("id") != "merge-to-default"
        and gate.get("status") not in {"pass", "not-applicable"}
    ]


def ensure_unreleased_changelog(changelog_path, entry):
    changelog_path = Path(changelog_path)
    bullet = f"- {entry.strip()}"
    if changelog_path.exists():
        original = changelog_path.read_text(encoding="utf-8")
    else:
        original = ""
    if any(line.rstrip() == bullet for line in original.splitlines()):
        return False

    if not original.strip():
        updated = f"# Changelog\n\n## Unreleased\n\n{bullet}\n"
    else:
        lines = original.rstrip().splitlines()
        heading_index = next(
            (index for index, line in enumerate(lines) if line.strip().lower() == "## unreleased"),
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


def run_project_pr(repo, run_path):
    controller = _prd_controller_path()
    if not controller.is_file():
        return None, f"Execution Run projection controller does not exist: {controller}"
    result = run_cmd([sys.executable, str(controller), "project-pr", "--run", str(Path(run_path).resolve())], cwd=repo)
    if result.returncode != 0:
        return None, result.stderr.strip() or result.stdout.strip() or "project-pr failed"
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        return None, f"project-pr did not emit JSON: {error}"
    return data, None


def run_binding_findings(repo, run_path, data):
    findings = []
    binding = data.get("binding") if isinstance(data, dict) else None
    if not isinstance(binding, dict):
        return findings
    expected_run = Path(run_path).resolve().name
    if binding.get("runId") != expected_run:
        findings.append(handoff_finding("run_id_drift", f"Run projection is bound to {binding.get('runId')}, not {expected_run}; run merge prepare again."))
    expected_repository = repository_identity(repo)
    projected_repository = binding.get("repository")
    if isinstance(projected_repository, dict):
        projected_repository = projected_repository.get("identity")
    if projected_repository != expected_repository:
        findings.append(handoff_finding("repository_drift", "Run projection repository identity does not match --git-root; run merge prepare again."))
    if (data.get("completion") or {}).get("merged") is True:
        if git(["cat-file", "-e", f"{binding.get('headSha')}^{{commit}}"], repo).returncode != 0:
            findings.append(handoff_finding("integration_head_missing", "The exact verified Epic head is no longer available in the repository."))
    else:
        current_branch = branch_name(repo)
        if binding.get("branch") != current_branch:
            findings.append(handoff_finding("integration_branch_drift", f"Run projection is bound to branch {binding.get('branch')}, not {current_branch}; run merge prepare again."))
        head = current_head(repo)
        if binding.get("headSha") != head:
            findings.append(handoff_finding("integration_head_drift", f"Run projection is bound to HEAD {binding.get('headSha')}, not {head}; run merge prepare again."))
    return findings


def primary_worktree(repo):
    result = git(["worktree", "list", "--porcelain"], repo)
    if result.returncode != 0:
        return Path(repo).resolve()
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            return Path(line.removeprefix("worktree ")).resolve()
    return Path(repo).resolve()


def branch_bound_run(repo, branch):
    if not branch:
        return None
    common = git(["rev-parse", "--git-common-dir"], repo)
    if common.returncode == 0:
        raw = Path(common.stdout.strip())
        common_path = raw if raw.is_absolute() else (Path(repo).resolve() / raw).resolve()
        registry = common_path / "gauntlet" / "run-bindings.json"
        if registry.is_file():
            try:
                records = json.loads(registry.read_text(encoding="utf-8"))
                record = records.get(branch) if isinstance(records, dict) else None
                candidate = Path(record.get("run", "")).resolve() if isinstance(record, dict) else None
                if candidate and (candidate / "manifest.json").is_file():
                    return candidate
            except (json.JSONDecodeError, OSError):
                return Path("/__gauntlet_invalid_run_binding_registry__")
    roots = []
    for root in [primary_worktree(repo), Path(repo).resolve()]:
        for relative in [Path("local-docs/executions"), Path(".gauntlet/executions"), Path("executions")]:
            candidate = root / relative
            if candidate not in roots:
                roots.append(candidate)
    for root in roots:
        if not root.is_dir():
            continue
        for manifest_path in sorted(root.glob("*/manifest.json")):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            integration = manifest.get("integration") or {}
            if integration.get("branch") == branch and integration.get("pr_strategy") in {"single-final-pr", "review-prs-plus-final"}:
                return manifest_path.parent
    return None


def command_merge_prepare(args):
    repo = Path(args.git_root).resolve()
    handoff_path = merge_input_path(repo, args.handoff) if args.handoff else None
    run_path = merge_input_path(repo, args.run) if args.run else None
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
        "runPath": str(run_path) if run_path else None,
    }
    data = None
    if run_path and handoff_path:
        add_finding(payload, "run_handoff_downgrade_rejected", "fail", "A PRD Execution Run must use the controller's schema 3.0 projection; do not supply a caller-authored handoff.")
    elif run_path:
        data, error = run_project_pr(repo, run_path)
        if error:
            add_finding(payload, "project_pr_projection_failed", "fail", error)
        elif data is not None:
            payload["findings"].extend(validate_run_merge_handoff(data))
            payload["findings"].extend(run_binding_findings(repo, run_path, data))
    elif not handoff_path or not handoff_path.is_file():
        add_finding(payload, "missing_handoff_file", "fail", f"Merge handoff does not exist: {handoff_path}")
    else:
        try:
            data = load_merge_handoff(handoff_path)
        except (json.JSONDecodeError, OSError) as error:
            add_finding(payload, "invalid_handoff_file", "fail", str(error))
            data = None
        if data is not None:
            if data.get("schemaVersion") == "3.0":
                add_finding(payload, "run_projection_requires_run", "fail", "Schema 3.0 is accepted only from `project-pr --run`; use --run instead of --handoff.")
            bound_run = branch_bound_run(repo, branch_name(repo))
            if bound_run:
                add_finding(payload, "run_handoff_downgrade_rejected", "fail", f"Branch {branch_name(repo)} is bound to Execution Run {bound_run}; use --run and schema 3.0.")
            payload["findings"].extend(validate_merge_handoff(data))
    if data is not None:
        payload["title"] = data.get("title")
        if not payload["findings"]:
            payload["changelogEntry"] = projection_changelog_entry(data)
            body_path.parent.mkdir(parents=True, exist_ok=True)
            body_path.write_text(render_pr_body(data), encoding="utf-8")
            payload["changelogChanged"] = ensure_unreleased_changelog(changelog_path, projection_changelog_entry(data))
    payload["status"] = status_for(payload)
    _print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def repository_merge_settings(repo):
    result = gh([
        "repo",
        "view",
        "--json",
        "defaultBranchRef,mergeCommitAllowed,squashMergeAllowed,rebaseMergeAllowed",
    ], repo)
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


def merge_input_path(repo, path):
    path = Path(path)
    return path if path.is_absolute() else repo / path


def load_merge_inputs(args, payload):
    repo = Path(args.git_root).resolve()
    handoff_arg = getattr(args, "handoff", None)
    run_arg = getattr(args, "run", None)
    handoff_path = merge_input_path(repo, handoff_arg) if handoff_arg else None
    run_path = merge_input_path(repo, run_arg) if run_arg else None
    body_path = merge_input_path(repo, args.body)
    data = None
    body = ""
    if git(["rev-parse", "--is-inside-work-tree"], repo).returncode != 0:
        add_finding(payload, "git_root_not_repo", "fail", f"Not a git repository: {repo}")
    if run_path and handoff_path:
        add_finding(payload, "run_handoff_downgrade_rejected", "fail", "A PRD Execution Run must use the controller's schema 3.0 projection; do not supply a caller-authored handoff.")
    elif run_path:
        data, error = run_project_pr(repo, run_path)
        if error:
            add_finding(payload, "project_pr_projection_failed", "fail", error)
        elif data is not None:
            payload["findings"].extend(validate_run_merge_handoff(data))
            payload["findings"].extend(run_binding_findings(repo, run_path, data))
    elif not handoff_path or not handoff_path.is_file():
        add_finding(payload, "missing_handoff_file", "fail", f"Merge handoff does not exist: {handoff_path}")
    else:
        try:
            data = load_merge_handoff(handoff_path)
        except (json.JSONDecodeError, OSError) as error:
            add_finding(payload, "invalid_handoff_file", "fail", str(error))
        if data is not None:
            if data.get("schemaVersion") == "3.0":
                add_finding(payload, "run_projection_requires_run", "fail", "Schema 3.0 is accepted only from `project-pr --run`; use --run instead of --handoff.")
            bound_run = branch_bound_run(repo, branch_name(repo))
            if bound_run:
                add_finding(payload, "run_handoff_downgrade_rejected", "fail", f"Branch {branch_name(repo)} is bound to Execution Run {bound_run}; use --run and schema 3.0.")
            payload["findings"].extend(validate_merge_handoff(data))
    if not body_path.is_file():
        add_finding(payload, "missing_pr_body", "fail", f"PR body does not exist: {body_path}")
    else:
        body = body_path.read_text(encoding="utf-8")
    payload["handoffPath"] = str(handoff_path) if handoff_path else None
    payload["runPath"] = str(run_path) if run_path else None
    payload["bodyPath"] = str(body_path)
    return repo, data, body


def add_existing_pr_blockers(payload, pr):
    if not pr:
        return
    if pr.get("state") != "OPEN":
        add_finding(payload, "pull_request_not_open", "review", f"Pull request is {pr.get('state')}.")
    if pr.get("isDraft"):
        add_finding(payload, "pull_request_is_draft", "review", "Pull request is still a draft.")
    if pr.get("reviewDecision") in {"CHANGES_REQUESTED", "REVIEW_REQUIRED"}:
        add_finding(payload, "pull_request_review_pending", "review", f"Pull request review decision is {pr.get('reviewDecision')}.")
    if pr.get("mergeable") not in {"MERGEABLE", "UNKNOWN"}:
        add_finding(payload, "pull_request_not_mergeable", "review", f"Pull request mergeable state is {pr.get('mergeable')}.")
    check_status, check_message = checks_state(pr.get("statusCheckRollup", []))
    if check_status == "failing":
        add_finding(payload, "pull_request_checks_failing", "review", check_message)


def collect_merge_state(git_root, handoff, body):
    repo = Path(git_root).resolve()
    branch = branch_name(repo)
    settings, settings_error = repository_merge_settings(repo)
    pr, pr_error = current_pr(repo)
    default_branch = ((settings or {}).get("defaultBranchRef") or {}).get("name") or "main"
    default_counts = None
    remote_default = f"origin/{default_branch}"
    if git(["rev-parse", "--verify", remote_default], repo).returncode == 0:
        counts = git(["rev-list", "--left-right", "--count", f"{remote_default}...HEAD"], repo)
        if counts.returncode == 0 and len(counts.stdout.split()) == 2:
            behind, ahead = [int(value) for value in counts.stdout.split()]
            default_counts = {"behind": behind, "ahead": ahead}
    return {
        "repo": str(repo),
        "branch": branch,
        "dirty": dirty_paths(repo),
        "handoff": handoff,
        "body": body,
        "settings": settings,
        "settingsError": settings_error,
        "defaultBranch": default_branch,
        "defaultCounts": default_counts,
        "pr": pr,
        "prError": pr_error,
        "runBacked": handoff.get("schemaVersion") == "3.0" if isinstance(handoff, dict) else False,
    }


def build_merge_plan(state):
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "findings": [],
        "mergePlan": {"canMerge": False, "actions": [], "blockers": [], "warnings": []},
        "branch": state.get("branch"),
        "defaultBranch": state.get("defaultBranch"),
        "pr": state.get("pr"),
        "runBinding": (state.get("handoff") or {}).get("binding") if state.get("runBacked") else None,
    }
    handoff = state.get("handoff") or {}
    branch = state.get("branch") or ""
    if not branch or branch == state.get("defaultBranch") or branch in {"main", "master"}:
        add_finding(payload, "task_branch_required", "fail", "Merge automation requires a named task branch, not the default branch.")
    if state.get("dirty"):
        add_finding(payload, "uncommitted_merge_work", "fail", "Commit or preserve all merge work before creating the PR: " + ", ".join(state["dirty"][:4]))

    if handoff:
        expected_body = render_pr_body(handoff)
        if state.get("body") != expected_body:
            add_finding(payload, "pr_body_out_of_date", "fail", "PR body does not match the current merge handoff; run merge prepare again.")
        bullet = f"- {projection_changelog_entry(handoff).strip()}"
        changelog_path = Path(state["repo"]) / "CHANGELOG.md"
        changelog = changelog_path.read_text(encoding="utf-8") if changelog_path.is_file() else ""
        if not bullet.strip("- ") or sum(line.rstrip() == bullet for line in changelog.splitlines()) != 1:
            add_finding(payload, "changelog_mismatch", "fail", "CHANGELOG.md must contain the exact PR changelog entry once.")

    counts = state.get("defaultCounts")
    if counts and counts.get("behind"):
        severity = "fail" if state.get("runBacked") else "review"
        code = "stale_tested_base" if state.get("runBacked") else "branch_behind_default"
        add_finding(payload, code, severity, f"Task branch is behind origin/{state['defaultBranch']} by {counts['behind']} commit(s); update and verify again before merge.")

    if state.get("settingsError"):
        add_finding(payload, "merge_settings_unverified", "warn", "Could not verify repository merge settings; using merge-commit fallback.")
    merge_method = merge_method_from_settings(state.get("settings"))
    if not merge_method:
        add_finding(payload, "no_allowed_merge_method", "fail", "Repository reports no allowed pull-request merge method.")
    add_existing_pr_blockers(payload, state.get("pr"))
    if state.get("pr"):
        if state["pr"].get("headRefName") != branch:
            add_finding(payload, "pull_request_head_mismatch", "fail", "The existing pull request head does not match the bound integration branch.")
        if state["pr"].get("baseRefName") != state.get("defaultBranch"):
            add_finding(payload, "pull_request_base_mismatch", "fail", "The existing pull request base does not match the repository default branch.")

    payload["status"] = status_for(payload)
    pr = state.get("pr")
    pr_action = {
        "type": "gh_pr_edit" if pr else "gh_pr_create",
        "prNumber": pr.get("number") if pr else None,
    }
    actions = [
        {"type": "git_push", "branch": branch},
        pr_action,
        {"type": "gh_pr_checks_watch", "prNumber": pr.get("number") if pr else None},
        {"type": "gh_pr_merge", "prNumber": pr.get("number") if pr else None, "mergeMethod": merge_method},
        {"type": "verify_default_branch", "branch": state.get("defaultBranch")},
        {"type": "delete_remote_branch", "branch": branch},
    ]
    blockers = [item["code"] for item in payload["findings"] if item["severity"] in {"review", "fail"}]
    warnings = [item["code"] for item in payload["findings"] if item["severity"] == "warn"]
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
        shell["mergePlan"] = {"canMerge": False, "actions": [], "blockers": [item["code"] for item in shell["findings"]], "warnings": []}
        return shell
    state = collect_merge_state(repo, data, body)
    return build_merge_plan(state)


def refreshed_pr_is_mergeable(payload, pr, expected_head=None):
    if not pr:
        add_finding(payload, "pull_request_missing_after_publish", "fail", "Could not find the pull request after publishing it.")
        return False
    before = len(payload["findings"])
    add_existing_pr_blockers(payload, pr)
    if expected_head and pr.get("headRefOid") != expected_head:
        add_finding(payload, "pull_request_head_drift", "fail", "Pull request head no longer matches the revision bound during merge preparation.")
    check_status, check_message = checks_state(pr.get("statusCheckRollup", []))
    if check_status != "passing":
        add_finding(payload, f"pull_request_checks_{check_status}", "fail", check_message)
    return len(payload["findings"]) == before


def wait_for_pr_checks(repo, timeout_seconds=60, poll_seconds=2):
    deadline = time.monotonic() + timeout_seconds
    last_error = None
    while True:
        pr, last_error = current_pr(repo)
        if pr and pr.get("statusCheckRollup"):
            return pr, None
        if time.monotonic() >= deadline:
            return pr, last_error or f"No PR status checks were reported within {timeout_seconds} seconds."
        time.sleep(poll_seconds)


def delete_remote_branch(repo, branch, expected_sha=None, git_runner=None):
    git_runner = git_runner or git
    probe = git_runner(["ls-remote", "--exit-code", "--heads", "origin", branch], repo)
    if probe.returncode == 2:
        return subprocess.CompletedProcess(probe.args, 0, probe.stdout, probe.stderr)
    if probe.returncode != 0:
        return probe
    remote_values = probe.stdout.split()
    remote_sha = remote_values[0] if remote_values else ""
    if expected_sha and remote_sha != expected_sha:
        return subprocess.CompletedProcess(
            probe.args, 1, probe.stdout,
            f"remote branch {branch} changed from expected {expected_sha} to {remote_sha}; refusing cleanup",
        )

    deletion_args = ["push", "origin", f":refs/heads/{branch}"]
    if expected_sha:
        deletion_args.append(f"--force-with-lease=refs/heads/{branch}:{expected_sha}")
    deletion = git_runner(deletion_args, repo)
    if deletion.returncode == 0:
        return deletion

    confirmation = git_runner(["ls-remote", "--exit-code", "--heads", "origin", branch], repo)
    if confirmation.returncode == 2:
        return subprocess.CompletedProcess(deletion.args, 0, deletion.stdout, deletion.stderr)
    return deletion


def execute_merge_plan(payload, git_root, handoff_source, body_path, run_path=None, merge_lease=None):
    repo = Path(git_root).resolve()
    executed = []
    branch = payload.get("branch")
    default_branch = payload.get("defaultBranch") or "main"
    handoff = handoff_source if isinstance(handoff_source, dict) else load_merge_handoff(handoff_source)
    pr = payload.get("pr")
    expected_head = (payload.get("runBinding") or {}).get("headSha") or current_head(repo)
    for action in payload.get("mergePlan", {}).get("actions", []):
        action_type = action["type"]
        if action_type == "git_push":
            result = git(["push", "-u", "origin", f"HEAD:{branch}"], repo)
        elif action_type == "gh_pr_create":
            result = gh([
                "pr", "create", "--title", handoff["title"], "--body-file", str(body_path),
                "--base", default_branch, "--head", branch,
            ], repo)
        elif action_type == "gh_pr_edit":
            result = gh(["pr", "edit", str(pr.get("number")), "--title", handoff["title"], "--body-file", str(body_path)], repo)
        elif action_type == "gh_pr_checks_watch":
            pr, checks_error = wait_for_pr_checks(repo)
            if checks_error:
                add_finding(payload, "pull_request_checks_missing", "fail", checks_error)
                break
            if pr.get("headRefOid") != expected_head:
                add_finding(payload, "pull_request_head_drift", "fail", "Pull request head changed before checks were accepted.")
                break
            action["prNumber"] = pr.get("number")
            result = gh(["pr", "checks", str(pr.get("number")), "--watch"], repo)
        elif action_type == "gh_pr_merge":
            if run_path:
                if not merge_lease:
                    add_finding(payload, "epic_merge_lease_missing", "fail", "Run-backed merge requires the launch-set merge lease.")
                    break
                try:
                    validate_run_merge_lease(repo, merge_lease[0], merge_lease[1])
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    add_finding(payload, "epic_merge_lease_invalid", "fail", str(exc))
                    break
            pr, _ = current_pr(repo)
            if not refreshed_pr_is_mergeable(payload, pr, expected_head):
                break
            if run_path:
                granted, authority_error = _run_authority_granted(repo, run_path, "merge-to-default")
                if not granted:
                    add_finding(payload, "merge_to_default_authority_missing", "fail", authority_error)
                    break
            action["prNumber"] = pr.get("number")
            method = action.get("mergeMethod") or "merge"
            result = gh([
                "pr", "merge", str(pr.get("number")), f"--{method}",
                "--match-head-commit", expected_head,
            ], repo)
        elif action_type == "delete_remote_branch":
            result = delete_remote_branch(repo, branch, expected_sha=expected_head)
        elif action_type == "verify_default_branch":
            fetch = git(["fetch", "origin", default_branch], repo)
            if fetch.returncode != 0:
                result = fetch
            else:
                ancestor = git(["merge-base", "--is-ancestor", expected_head, f"origin/{default_branch}"], repo)
                if ancestor.returncode == 0:
                    result = ancestor
                else:
                    candidate_tree = git(["rev-parse", f"{expected_head}^{{tree}}"], repo)
                    default_tree = git(["rev-parse", f"origin/{default_branch}^{{tree}}"], repo)
                    if candidate_tree.returncode == 0 and default_tree.returncode == 0 and candidate_tree.stdout.strip() == default_tree.stdout.strip():
                        result = subprocess.CompletedProcess(ancestor.args, 0, "tree-equivalent\n", "")
                    else:
                        result = ancestor
        else:
            add_finding(payload, "unknown_merge_action", "fail", f"Unknown merge action: {action_type}")
            break
        if result.returncode != 0:
            add_finding(payload, f"{action_type}_failed", "fail", result.stderr.strip() or result.stdout.strip() or f"{action_type} failed")
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
    if getattr(args, "run", None):
        run_path = merge_input_path(repo, args.run)
        handoff, error = run_project_pr(repo, run_path)
        if error:
            add_finding(payload, "project_pr_projection_failed", "fail", error)
            payload["status"] = status_for(payload)
            _print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]
        payload["findings"].extend(validate_run_merge_handoff(handoff))
        payload["findings"].extend(run_binding_findings(repo, run_path, handoff))
        if handoff.get("binding") != payload.get("runBinding") or render_pr_body(handoff) != body_path.read_text(encoding="utf-8"):
            add_finding(payload, "run_projection_changed_during_execute", "fail", "Execution Run projection changed after planning; run merge prepare again.")
        pending_merge_gates = pending_run_merge_gates(handoff)
        if pending_merge_gates:
            add_finding(
                payload, "run_merge_safeguard_pending", "fail",
                "Run-backed merge has pending controller safeguards: " + ", ".join(gate.get("id", "unknown") for gate in pending_merge_gates),
            )
        payload["status"] = status_for(payload)
        if payload["status"] not in {"pass", "warn"}:
            payload["mergePlan"]["canMerge"] = False
            payload["mergePlan"]["actions"] = []
            _print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]
        granted, authority_error = _run_authority_granted(repo, run_path, "merge-to-default")
        if not granted:
            add_finding(payload, "merge_to_default_authority_missing", "fail", authority_error)
            payload["mergePlan"]["canMerge"] = False
            payload["mergePlan"]["actions"] = []
            payload["status"] = status_for(payload)
            _print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]
        try:
            merge_lease = acquire_run_merge_lease(repo, run_path, handoff)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            add_finding(payload, "epic_merge_lease_failed", "fail", str(exc))
            payload["mergePlan"]["canMerge"] = False
            payload["mergePlan"]["actions"] = []
            payload["status"] = status_for(payload)
            _print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]
    else:
        handoff = merge_input_path(repo, args.handoff)
        run_path = None
        merge_lease = None
    payload = execute_merge_plan(payload, repo, handoff, body_path, run_path=run_path, merge_lease=merge_lease)
    if run_path and payload["status"] in {"pass", "warn"} and any(
        action.get("type") == "verify_default_branch" for action in payload.get("executedActions", [])
    ):
        default_branch = payload.get("defaultBranch") or "main"
        main_result = git(["rev-parse", f"origin/{default_branch}"], repo)
        pr = payload.get("pr") or {}
        pr_reference = str(pr.get("url") or pr.get("number") or "run-backed-project-pr")
        if main_result.returncode != 0:
            add_finding(payload, "record_merge_head_failed", "fail", main_result.stderr.strip() or main_result.stdout.strip())
        else:
            main_sha = main_result.stdout.strip()
            _, record_error = _run_prd_controller(repo, [
                "record-merge", "--run", str(run_path), "--pr", pr_reference,
                "--merged-sha", main_sha, "--main-sha", main_sha,
                "--evidence", f"origin/{default_branch} contains verified head {handoff['binding']['headSha']}",
            ])
            if record_error:
                add_finding(payload, "record_merge_failed", "fail", record_error)
            else:
                _, transition_error = _run_prd_controller(repo, ["transition", "--run", str(run_path), "--to", "merged"])
                if transition_error:
                    add_finding(payload, "record_merge_transition_failed", "fail", transition_error)
                else:
                    payload["runMergeRecorded"] = {"mainSha": main_sha, "pr": pr_reference}
                    try:
                        release_run_merge_lease(repo, merge_lease[0], merge_lease[1], main_sha)
                        payload["mergeLeaseReleased"] = True
                    except (OSError, ValueError, json.JSONDecodeError) as exc:
                        add_finding(payload, "epic_merge_lease_release_failed", "fail", str(exc))
        payload["status"] = status_for(payload)
    _print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_merge_reconcile(args):
    repo = Path(args.git_root).resolve()
    run_path = merge_input_path(repo, args.run)
    payload = {"schemaVersion": "1.0", "status": "pass", "findings": [], "runPath": str(run_path), "reconciled": False}
    handoff, error = run_project_pr(repo, run_path)
    if error:
        add_finding(payload, "project_pr_projection_failed", "fail", error)
    elif validate_run_merge_handoff(handoff):
        payload["findings"].extend(validate_run_merge_handoff(handoff))
    else:
        completion_output, completion_error = _run_prd_controller(repo, ["completion", "--run", str(run_path)])
        if not completion_error:
            try:
                if json.loads(completion_output).get("merged") is True:
                    persisted = persisted_run_merge_lease(run_path, handoff)
                    if persisted:
                        release_run_merge_lease(repo, persisted[0], persisted[1], recorded_run_merge_head(run_path))
                        payload["mergeLeaseReleased"] = True
                    payload["reconciled"] = True
                    payload["alreadyRecorded"] = True
                    _print_payload(payload, args.json)
                    return EXIT_CODES[payload["status"]]
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                add_finding(payload, "merge_reconcile_lease_failed", "fail", str(exc))
                payload["status"] = status_for(payload)
                _print_payload(payload, args.json)
                return EXIT_CODES[payload["status"]]
        binding = handoff["binding"]
        default_result = git(["fetch", "origin"], repo)
        if default_result.returncode != 0:
            add_finding(payload, "merge_reconcile_fetch_failed", "fail", default_result.stderr.strip() or default_result.stdout.strip())
        else:
            settings, settings_error = repository_merge_settings(repo)
            if settings_error:
                add_finding(payload, "merge_reconcile_settings_failed", "fail", settings_error)
            else:
                default_branch = ((settings or {}).get("defaultBranchRef") or {}).get("name") or "main"
                main_result = git(["rev-parse", f"origin/{default_branch}"], repo)
                represented = default_represents_candidate(repo, binding["headSha"], f"origin/{default_branch}")
                merged_pr = gh([
                    "pr", "list", "--head", binding["branch"], "--state", "merged", "--limit", "1",
                    "--json", "number,url,headRefOid,baseRefName",
                ], repo)
                if main_result.returncode != 0 or not represented:
                    add_finding(payload, "merge_not_observed", "fail", "The remote default branch preserves neither verified-head ancestry nor the exact verified candidate tree.")
                elif merged_pr.returncode != 0:
                    add_finding(payload, "merged_pr_lookup_failed", "fail", merged_pr.stderr.strip() or merged_pr.stdout.strip())
                else:
                    records = json.loads(merged_pr.stdout or "[]")
                    pr = records[0] if records else None
                    if not pr or pr.get("headRefOid") != binding["headSha"] or pr.get("baseRefName") != default_branch:
                        add_finding(payload, "merged_pr_identity_mismatch", "fail", "No merged PR matches the verified Epic head and default branch.")
                    else:
                        main_sha = main_result.stdout.strip()
                        pr_reference = str(pr.get("url") or pr.get("number"))
                        try:
                            persisted = persisted_run_merge_lease(run_path, handoff)
                        except (OSError, ValueError, json.JSONDecodeError) as exc:
                            add_finding(payload, "merge_reconcile_lease_failed", "fail", str(exc))
                            persisted = None
                        if persisted is None and not payload["findings"]:
                            add_finding(
                                payload, "merge_lease_not_observed", "review",
                                "The merge is independently observable, but no controller merge lease survived to prove serialized execution.",
                            )
                        _, record_error = _run_prd_controller(repo, [
                            "record-merge", "--run", str(run_path), "--pr", pr_reference,
                            "--merged-sha", main_sha, "--main-sha", main_sha,
                            "--evidence", f"origin/{default_branch} contains verified head {binding['headSha']}",
                        ])
                        if record_error:
                            add_finding(payload, "record_merge_failed", "fail", record_error)
                        else:
                            _, transition_error = _run_prd_controller(repo, ["transition", "--run", str(run_path), "--to", "merged"])
                            if transition_error:
                                add_finding(payload, "record_merge_transition_failed", "fail", transition_error)
                            else:
                                payload.update({"reconciled": True, "mainSha": main_sha, "pr": pr_reference})
                                if persisted:
                                    try:
                                        release_run_merge_lease(repo, persisted[0], persisted[1], main_sha)
                                        payload["mergeLeaseReleased"] = True
                                    except (OSError, ValueError, json.JSONDecodeError) as exc:
                                        add_finding(payload, "merge_reconcile_lease_release_failed", "fail", str(exc))
    payload["status"] = status_for(payload)
    _print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def dirty_paths(repo):
    status = git(["status", "--porcelain", "--untracked-files=all"], repo)
    if status.returncode != 0:
        raise RuntimeError(status.stderr.strip() or "git status failed")
    return [line[3:] if len(line) > 3 else line for line in status.stdout.splitlines() if line.strip()]


def branch_name(repo):
    branch = git(["branch", "--show-current"], repo)
    if branch.returncode != 0:
        return ""
    return branch.stdout.strip()


def upstream_counts(repo):
    upstream = git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], repo)
    if upstream.returncode != 0:
        return None
    counts = git(["rev-list", "--left-right", "--count", "@{u}...HEAD"], repo)
    if counts.returncode != 0:
        raise RuntimeError(counts.stderr.strip() or "could not compare upstream")
    parts = counts.stdout.strip().split()
    if len(parts) != 2:
        raise RuntimeError(f"unexpected upstream count output: {counts.stdout}")
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
            state = check.get("state") or check.get("conclusion") or check.get("status")
            name = check.get("context") or check.get("name") or "status"
            if state not in PASSING_STATUS_STATES:
                failing.append(f"{name}={state}")

    if failing:
        return "failing", "PR checks are failing: " + ", ".join(failing[:4])
    if pending:
        return "pending", "PR checks are still pending: " + ", ".join(pending[:4])
    return "passing", "PR checks passed."


def current_pr(repo):
    result = gh([
        "pr",
        "view",
        "--json",
        "number,state,isDraft,mergeable,mergedAt,statusCheckRollup,url,baseRefName,headRefName,headRefOid,reviewDecision",
    ], cwd=repo)
    if result.returncode != 0:
        return None, result.stderr.strip() or result.stdout.strip()
    return json.loads(result.stdout), None
