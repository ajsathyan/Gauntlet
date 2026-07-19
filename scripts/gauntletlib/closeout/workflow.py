"""Closeout, archive, follow-up, and changelog workflows."""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from gauntletlib.cli import EXIT_CODES
from gauntletlib.contracts import validate_merge_handoff
from gauntletlib.core.findings import add_finding as _add_finding, status_for as _status_for
from gauntletlib.core.proc import gh, git, run_cmd
from gauntletlib.core.redact import has_secret, redact_secrets
from gauntletlib.merge import (
    branch_name,
    build_merge_payload,
    checks_state,
    current_pr,
    dirty_paths,
    ensure_unreleased_changelog,
    execute_merge_plan,
    load_merge_handoff,
    merge_input_path,
    render_pr_body,
    repository_merge_settings,
    upstream_counts,
)
from thread_titles import parse_thread_title

ROOT = Path(__file__).resolve().parents[3]
CHECKER = ROOT / "scripts" / "check-workflow-etiquette.py"
DEFERRED_AGENT_ACTIONS = {"set_thread_title", "present_archive_summary", "archive_thread", "create_thread", "open_browser"}
ARCHIVE_SUMMARY_ALIASES = ["archive summary", "what changed", "change summary"]

_print_payload = None


def configure(*, print_payload):
    global _print_payload
    _print_payload = print_payload

def add_finding(payload, code, severity, message, **details):
    _add_finding(payload.setdefault("findings", []), code, severity, message, **details)

def status_for(payload):
    return _status_for(payload.get("findings", []))

def read_text(path):
    return Path(path).read_text(encoding="utf-8", errors="ignore")

def display_path(root, path):
    path = Path(path)
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def heading_key(line):
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None
    hashes, _, title = stripped.partition(" ")
    if not title or not set(hashes) <= {"#"}:
        return None
    key = re.sub(r"[^a-z0-9]+", " ", title.strip().rstrip("#").lower()).strip()
    return len(hashes), key


def markdown_sections(text):
    sections = {}
    current = None
    for line in text.splitlines():
        parsed = heading_key(line)
        if parsed:
            _, current = parsed
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    return {key: "\n".join(lines).strip() for key, lines in sections.items()}


def find_section(sections, aliases):
    normalized = {re.sub(r"[^a-z0-9]+", " ", alias.lower()).strip() for alias in aliases}
    for key, value in sections.items():
        if key in normalized:
            return value
    return None


def first_nonempty_line(text, fallback="None supplied."):
    for line in (text or "").splitlines():
        clean = line.strip().lstrip("-").strip()
        if clean:
            return clean
    return fallback


def section_bullets(text):
    items = []
    for line in (text or "").splitlines():
        clean = line.strip()
        if clean.startswith("- "):
            items.append(clean[2:].strip())
    if items:
        return items
    return [first_nonempty_line(text)] if (text or "").strip() else []


def archive_summary_from_sections(sections):
    explicit = find_section(sections, ARCHIVE_SUMMARY_ALIASES)
    if explicit:
        return [redact_secrets(item) for item in section_bullets(explicit)[:10]]

    bullets = []
    goal = first_nonempty_line(find_section(sections, ["goal"]) or "", "")
    if goal:
        bullets.append(redact_secrets(goal))
    scope = section_bullets(find_section(sections, ["scope"]) or "")
    bullets.extend(redact_secrets(item) for item in scope[:4])
    verification = section_bullets(find_section(sections, ["verification", "proof"]) or "")
    if verification:
        bullets.append("Verification expected: " + "; ".join(redact_secrets(item) for item in verification[:2]))
    return bullets[:10]


def archive_summary_from_content(path):
    if not path:
        return None, [{"code": "missing_archive_summary_content", "severity": "fail", "message": "Archive requires PR changelog or closeout content with an Archive Summary."}]
    path = Path(path)
    if not path.exists():
        return None, [{"code": "missing_archive_summary_content", "severity": "fail", "message": f"Archive summary content file does not exist: {path}."}]
    text = read_text(path)
    sections = markdown_sections(text)
    raw_summary = find_section(sections, ARCHIVE_SUMMARY_ALIASES)
    if not raw_summary:
        return None, [{"code": "missing_archive_summary", "severity": "fail", "message": f"No Archive Summary section found in {path}."}]
    if has_secret(raw_summary):
        return None, [{"code": "secret_like_archive_summary", "severity": "fail", "message": "Archive Summary contains secret-like content; redact it before archive."}]
    bullets = [redact_secrets(item) for item in section_bullets(raw_summary)[:10]]
    return {"source": "content", "path": str(path), "bullets": bullets}, []


def parse_followups(text):
    followups = []
    lines = (text or "").splitlines()
    index = 0
    while index < len(lines):
        if lines[index].strip().lower() != "follow-up captured:":
            index += 1
            continue
        block = {}
        index += 1
        while index < len(lines):
            line = lines[index].strip()
            if not line:
                break
            if line.lower() == "follow-up captured:":
                index -= 1
                break
            match = re.match(r"-\s*([^:]+):\s*(.*)", line)
            if match:
                key = re.sub(r"[^a-z0-9]+", "_", match.group(1).lower()).strip("_")
                block[key] = match.group(2).strip()
            index += 1
        if block:
            followups.append(block)
        index += 1
    return followups


def pr_for_changelog(repo):
    result = gh([
        "pr",
        "view",
        "--json",
        "number,state,mergedAt,url,title,baseRefName,headRefName,statusCheckRollup",
    ], cwd=repo)
    if result.returncode != 0:
        return None, result.stderr.strip() or result.stdout.strip()
    return json.loads(result.stdout), None


def markdown_list(items, empty="- None."):
    if not items:
        return empty
    return "\n".join(f"- {item}" for item in items)


def build_changelog_markdown(source_path, sections, pr, followups, findings):
    goal = find_section(sections, ["goal"]) or ""
    scope = find_section(sections, ["scope"]) or ""
    archive_summary = archive_summary_from_sections(sections)
    source_files = section_bullets(find_section(sections, [
        "source-of-truth files",
        "source of truth files",
        "source files",
    ]) or "")
    verification = section_bullets(find_section(sections, ["verification", "proof"]) or "")
    stale = find_section(sections, [
        "stale context warning",
        "stale-context warning",
        "stale context",
    ]) or "GitHub, branch, and thread state can change after generation."

    if pr:
        number = pr.get("number")
        url = pr.get("url") or ""
        label = f"[#{number}]({url})" if number and url else f"#{number or 'unknown'}"
        pr_rows = [f"| {label} | {pr.get('state', 'UNKNOWN')} | {redact_secrets(pr.get('title') or 'Untitled PR')} |"]
    else:
        pr_rows = ["| Cannot verify | Unknown | No current PR metadata available. |"]

    followup_lines = []
    for followup in followups:
        topic = redact_secrets(followup.get("topic", "Untitled follow-up"))
        strength = redact_secrets(followup.get("strength", "unknown strength"))
        why = redact_secrets(followup.get("why_it_matters", "No rationale supplied."))
        opener = redact_secrets(followup.get("suggested_opener", "No opener supplied."))
        followup_lines.append(f"- {topic} (`{strength}`): {why} Suggested opener: {opener}")

    cannot_verify = [
        finding["message"]
        for finding in findings
        if finding.get("severity") in {"warn", "review", "fail"}
    ]
    return "\n".join([
        "# PR Changelog",
        "",
        f"Source: `{source_path}`",
        "",
        "## Implementation Summary",
        "",
        first_nonempty_line(redact_secrets(goal)),
        "",
        "## Archive Summary",
        "",
        markdown_list(archive_summary, empty="- Cannot verify chat-level changes from CLI metadata alone. Supply an agent-authored Archive Summary in the PR changelog or closeout content."),
        "",
        "## Scope",
        "",
        redact_secrets(scope or "None supplied."),
        "",
        "## PRs",
        "",
        "| PR | State | Title |",
        "| --- | --- | --- |",
        *pr_rows,
        "",
        "## Source Files",
        "",
        markdown_list([redact_secrets(item) for item in source_files]),
        "",
        "## Verification Expected",
        "",
        markdown_list([redact_secrets(item) for item in verification]),
        "",
        "## Follow-Ups",
        "",
        markdown_list(followup_lines),
        "",
        "## Stale Context Warning",
        "",
        redact_secrets(stale.strip()),
        "",
        "## Cannot Verify",
        "",
        markdown_list(cannot_verify),
        "",
    ])


def repo_relative_scope_path(repo, raw_path):
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = repo / candidate
    candidate = candidate.resolve()
    try:
        return candidate.relative_to(repo).as_posix()
    except ValueError:
        return None


def closeout_fail(payload, code, message):
    add_finding(payload, code, "fail", message)
    payload["status"] = status_for(payload)
    payload["remainingAppActions"] = []
    return payload


def closeout_install_command(repo, args, check=False):
    command = [str(repo / "scripts" / "install.sh"), "--target", args.install_target]
    if check:
        command.append("--check")
    if args.instructions_reviewed:
        command.append("--instructions-reviewed")
    command.extend(["--response-style", args.response_style])
    if args.install_target == "codex":
        command.extend(["--codex-preferences", args.codex_preferences])
    return command


def _closeout_patch_preflight(args):
    repo = Path(args.git_root).resolve()
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "findings": [],
        "commit": None,
        "merge": None,
        "install": None,
        "archive": None,
        "remainingAppActions": [],
    }
    if git(["rev-parse", "--is-inside-work-tree"], repo).returncode != 0:
        closeout_fail(payload, "git_root_not_repo", f"Not a git repository: {repo}")
        _print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]

    if not getattr(args, "handoff", None):
        closeout_fail(payload, "missing_handoff_file", "Closeout requires --handoff.")
        _print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    if not args.stage:
        closeout_fail(payload, "missing_stage_scope", "Closeout requires at least one --stage path.")
        _print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]

    handoff_path = merge_input_path(repo, args.handoff)
    if not handoff_path.is_file():
        closeout_fail(payload, "missing_handoff_file", f"Merge handoff does not exist: {handoff_path}")
        _print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    try:
        handoff = load_merge_handoff(handoff_path)
    except (json.JSONDecodeError, OSError) as error:
        closeout_fail(payload, "invalid_handoff_file", str(error))
        _print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    payload["findings"].extend(validate_merge_handoff(handoff))
    if payload["findings"]:
        payload["status"] = status_for(payload)
        _print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]

    archive_summary, archive_findings = archive_summary_from_content(args.content)
    for finding in archive_findings:
        add_finding(payload, finding["code"], finding["severity"], finding["message"])
    parsed_title = parse_thread_title(args.title)
    parsed_suggestion = parse_thread_title(args.suggested_title) if args.suggested_title else None
    if parsed_title["format"] != "current" and (not parsed_suggestion or parsed_suggestion["format"] != "current"):
        add_finding(
            payload,
            "invalid_archive_title",
            "fail",
            "Provide a descriptive one-to-four-word title or a valid "
            "--suggested-title before closeout begins.",
        )
    if payload["findings"]:
        payload["status"] = status_for(payload)
        _print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    payload["archiveSummary"] = archive_summary

    return args, repo, payload, handoff_path, handoff


def _prepare_patch_closeout(args, repo, payload, handoff_path, handoff):
    settings, settings_error = repository_merge_settings(repo)
    default_branch = ((settings or {}).get("defaultBranchRef") or {}).get("name") or "main"
    task_branch = branch_name(repo)
    if settings_error:
        add_finding(payload, "merge_settings_unverified", "warn", "Could not verify repository merge settings; using the default branch reported by local convention.")
    if not task_branch or task_branch in {default_branch, "main", "master"}:
        closeout_fail(payload, "task_branch_required", "Closeout execute requires a named task branch, not the default branch.")
        _print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]

    scoped_paths = []
    for raw_path in args.stage:
        relative = repo_relative_scope_path(repo, raw_path)
        if relative is None:
            closeout_fail(payload, "stage_path_outside_repo", f"Stage path is outside the repository: {raw_path}")
        elif relative not in scoped_paths:
            scoped_paths.append(relative)
    if payload["status"] == "fail":
        _print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]

    existing_dirty = dirty_paths(repo)
    unscoped_dirty = sorted(set(existing_dirty) - set(scoped_paths))
    if unscoped_dirty:
        closeout_fail(payload, "unscoped_dirty_work", "Closeout refused unrelated or unlisted work: " + ", ".join(unscoped_dirty[:6]))
        _print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]

    if args.install_target != "none":
        install_env = os.environ.copy()
        if args.agent_home:
            install_env["GAUNTLET_AGENT_HOME"] = str(Path(args.agent_home).expanduser())
        install_preflight = subprocess.run(
            closeout_install_command(repo, args, check=True),
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=install_env,
        )
        payload["install"] = {
            "target": args.install_target,
            "applied": False,
            "preflight": install_preflight.returncode == 0,
        }
        if install_preflight.returncode != 0:
            closeout_fail(
                payload,
                "local_install_preflight_failed",
                install_preflight.stderr.strip() or install_preflight.stdout.strip(),
            )
            _print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]

    return args, repo, payload, handoff_path, handoff, default_branch, task_branch, scoped_paths


def _execute_patch_closeout(args, repo, payload, handoff_path, handoff, default_branch, task_branch, scoped_paths):
    body_handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix="-gauntlet-pr.md")
    body_path = Path(body_handle.name)
    body_handle.write(render_pr_body(handoff))
    body_handle.close()
    try:
        ensure_unreleased_changelog(repo / "CHANGELOG.md", handoff["changelog"])
        commit_scope = [*scoped_paths, "CHANGELOG.md"]
        dirty_after_prepare = dirty_paths(repo)
        unscoped_after_prepare = sorted(set(dirty_after_prepare) - set(commit_scope))
        if unscoped_after_prepare:
            closeout_fail(payload, "unscoped_dirty_work", "Closeout preparation produced or found unlisted work: " + ", ".join(unscoped_after_prepare[:6]))
            _print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]

        paths_to_add = [path for path in commit_scope if path in dirty_after_prepare]
        if paths_to_add:
            add_result = git(["add", "--", *paths_to_add], repo)
            if add_result.returncode != 0:
                closeout_fail(payload, "git_add_failed", add_result.stderr.strip() or add_result.stdout.strip())
                _print_payload(payload, args.json)
                return EXIT_CODES[payload["status"]]
        cached = git(["diff", "--cached", "--name-only"], repo)
        cached_paths = [line.strip() for line in cached.stdout.splitlines() if line.strip()]
        if cached.returncode != 0:
            closeout_fail(payload, "git_diff_cached_failed", cached.stderr.strip() or cached.stdout.strip())
            _print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]
        unexpected_cached = sorted(set(cached_paths) - set(commit_scope))
        if unexpected_cached:
            closeout_fail(payload, "unscoped_staged_work", "Closeout refused staged paths outside the explicit scope: " + ", ".join(unexpected_cached[:6]))
            _print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]
        if cached_paths:
            commit_result = git(["commit", "-m", handoff["title"]], repo)
            if commit_result.returncode != 0:
                closeout_fail(payload, "git_commit_failed", commit_result.stderr.strip() or commit_result.stdout.strip())
                _print_payload(payload, args.json)
                return EXIT_CODES[payload["status"]]
            commit_oid = git(["rev-parse", "HEAD"], repo).stdout.strip()
            payload["commit"] = {"oid": commit_oid, "subject": handoff["title"], "paths": cached_paths, "created": True}
        else:
            fetch_default = git(["fetch", "origin", default_branch], repo)
            committed = git(["diff", "--name-only", f"origin/{default_branch}...HEAD"], repo) if fetch_default.returncode == 0 else fetch_default
            committed_paths = [line.strip() for line in committed.stdout.splitlines() if line.strip()]
            tip_subject = git(["log", "-1", "--pretty=%s"], repo).stdout.strip()
            unexpected_committed = sorted(set(committed_paths) - set(commit_scope))
            if committed.returncode != 0 or not committed_paths or tip_subject != handoff["title"] or unexpected_committed:
                details = ", ".join(unexpected_committed[:6]) if unexpected_committed else "no matching scoped closeout commit"
                closeout_fail(payload, "closeout_resume_mismatch", "Closeout cannot safely resume this branch: " + details)
                _print_payload(payload, args.json)
                return EXIT_CODES[payload["status"]]
            commit_oid = git(["rev-parse", "HEAD"], repo).stdout.strip()
            payload["commit"] = {"oid": commit_oid, "subject": tip_subject, "paths": committed_paths, "created": False}

        merge_args = argparse.Namespace(git_root=repo, handoff=handoff_path, body=body_path, json=True)
        merge_payload = build_merge_payload(merge_args)
        if merge_payload["status"] in {"pass", "warn"}:
            merge_payload = execute_merge_plan(merge_payload, repo, handoff_path, body_path)
        payload["merge"] = merge_payload
        payload["findings"].extend(merge_payload.get("findings", []))
        payload["status"] = status_for(payload)
        if payload["status"] not in {"pass", "warn"}:
            payload["remainingAppActions"] = []
            _print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]

        fetch = git(["fetch", "origin", default_branch], repo)
        switch = git(["switch", default_branch], repo) if fetch.returncode == 0 else fetch
        pull = git(["pull", "--ff-only", "origin", default_branch], repo) if switch.returncode == 0 else switch
        delete_local = git(["branch", "-d", task_branch], repo) if pull.returncode == 0 else pull
        for code, result in [
            ("fetch_default_failed", fetch),
            ("switch_default_failed", switch),
            ("pull_default_failed", pull),
            ("delete_local_branch_failed", delete_local),
        ]:
            if result.returncode != 0:
                closeout_fail(payload, code, result.stderr.strip() or result.stdout.strip())
                _print_payload(payload, args.json)
                return EXIT_CODES[payload["status"]]

        if args.install_target != "none":
            install_env = os.environ.copy()
            if args.agent_home:
                install_env["GAUNTLET_AGENT_HOME"] = str(Path(args.agent_home).expanduser())
            install_result = subprocess.run(
                closeout_install_command(repo, args),
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=install_env,
            )
            payload["install"] = {
                "target": args.install_target,
                "applied": install_result.returncode == 0,
                "preflight": True,
            }
            if install_result.returncode != 0:
                closeout_fail(payload, "local_install_failed", install_result.stderr.strip() or install_result.stdout.strip())
                _print_payload(payload, args.json)
                return EXIT_CODES[payload["status"]]
        else:
            payload["install"] = {"target": "none", "applied": False}

        archive_args = argparse.Namespace(
            title=args.title,
            suggested_title=args.suggested_title,
            content=args.content,
            git_root=repo,
            require_kickoff=False,
            require_assumptions=False,
            archive_anyway=False,
            confirm_git_risk=False,
            allow_dirty=[],
            json=True,
        )
        archive_payload = build_archive_payload(archive_args)
        if archive_payload["status"] in {"pass", "warn"}:
            archive_payload = execute_archive_actions(archive_payload, repo)
        payload["archive"] = archive_payload
        payload["findings"].extend(archive_payload.get("findings", []))
        payload["status"] = status_for(payload)
        payload["remainingAppActions"] = archive_payload.get("remainingAppActions", []) if payload["status"] in {"pass", "warn"} else []
        _print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    finally:
        body_path.unlink(missing_ok=True)


def command_closeout_execute(args):
    result = _closeout_patch_preflight(args)
    if isinstance(result, int):
        return result
    result = _prepare_patch_closeout(*result)
    if isinstance(result, int):
        return result
    return _execute_patch_closeout(*result)


def run_checker(args):
    cmd = [str(CHECKER), "--archive", "--json"]
    if args.title:
        cmd += ["--title", args.title]
    if getattr(args, "suggested_title", None):
        cmd += ["--suggested-title", args.suggested_title]
    if getattr(args, "content", None):
        cmd += ["--content", str(args.content)]
    if getattr(args, "require_kickoff", False):
        cmd.append("--require-kickoff")
    if getattr(args, "require_assumptions", False):
        cmd.append("--require-assumptions")
    if getattr(args, "archive_anyway", False):
        cmd.append("--archive-anyway")

    result = run_cmd(cmd, cwd=ROOT)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"workflow etiquette checker did not emit JSON: {error}\n{result.stdout}\n{result.stderr}") from error


def _archive_git_preflight(repo, payload, args):
    actions = []
    if not repo:
        return actions

    repo = Path(repo).resolve()
    inside = git(["rev-parse", "--is-inside-work-tree"], repo)
    if inside.returncode != 0:
        return actions

    allow_dirty = {str(Path(path)) for path in getattr(args, "allow_dirty", [])}
    dirty = dirty_paths(repo)
    if dirty:
        unexpected_dirty = [path for path in dirty if path not in allow_dirty]
        if not unexpected_dirty:
            add_finding(
                payload,
                "dirty_worktree_allowlisted",
                "warn",
                "Dirty files are explicitly allowlisted for this archive: " + ", ".join(dirty[:4]) + ".",
            )
        elif getattr(args, "confirm_git_risk", False):
            add_finding(
                payload,
                "git_risk_confirmed",
                "warn",
                "User confirmed archive can proceed even though git has unpreserved work: "
                + ", ".join(unexpected_dirty[:4])
                + ".",
            )
        else:
            add_finding(
                payload,
                "dirty_worktree",
                "review",
                "Worktree has uncommitted or untracked files: " + ", ".join(unexpected_dirty[:4]) + ".",
            )
            add_finding(
                payload,
                "git_risk_confirmation_required",
                "review",
                "Ask the user to confirm whether this unpreserved work should be left out of git before archiving.",
            )
            return actions

    branch = branch_name(repo)
    counts = upstream_counts(repo)
    if counts and counts["behind"]:
        add_finding(
            payload,
            "branch_behind_upstream",
            "review",
            f"Branch is behind {counts['upstream']} by {counts['behind']} commit(s).",
        )
        return actions

    defaultish = branch in {"main", "master"}
    if defaultish:
        if counts and counts["ahead"]:
            if getattr(args, "confirm_git_risk", False):
                add_finding(
                    payload,
                    "default_branch_ahead_confirmed",
                    "warn",
                    "User confirmed archive can proceed even though the default branch has unpushed commits.",
                )
            else:
                add_finding(
                    payload,
                    "default_branch_ahead",
                    "review",
                    f"Default branch has {counts['ahead']} unpushed commit(s); push or confirm abandonment before archive.",
                )
                add_finding(
                    payload,
                    "git_risk_confirmation_required",
                    "review",
                    "Ask the user to confirm before archiving with unpushed default-branch commits.",
                )
        return actions

    if counts and counts["ahead"]:
        actions.append({"type": "git_push", "upstream": counts["upstream"], "ahead": counts["ahead"]})
        add_finding(
            payload,
            "branch_push_needed_before_pr_merge",
            "review",
            "Branch has local commits that must be pushed before PR checks can be trusted.",
        )
        return actions

    return actions, repo, branch


def _archive_pr_actions(actions, repo, branch, payload, args):
    pr, error = current_pr(repo)
    if not pr:
        if getattr(args, "confirm_git_risk", False):
            add_finding(
                payload,
                "missing_pull_request_confirmed",
                "warn",
                "User confirmed archive can proceed without a merged pull request for this branch.",
            )
            return actions
        add_finding(
            payload,
            "missing_pull_request",
            "review",
            f"No pull request found for branch {branch}: {error or 'unknown gh error'}.",
        )
        add_finding(
            payload,
            "git_risk_confirmation_required",
            "review",
            "Ask the user to confirm before archiving work that is not merged through a PR.",
        )
        return actions

    if pr.get("state") == "MERGED" or pr.get("mergedAt"):
        return actions
    if pr.get("state") != "OPEN":
        add_finding(payload, "pull_request_not_open", "review", f"Pull request is {pr.get('state')}.")
        return actions
    if pr.get("isDraft"):
        add_finding(payload, "pull_request_is_draft", "review", "Pull request is still a draft.")
        return actions
    if pr.get("reviewDecision") in {"CHANGES_REQUESTED", "REVIEW_REQUIRED"}:
        add_finding(
            payload,
            "pull_request_review_pending",
            "review",
            f"Pull request review decision is {pr.get('reviewDecision')}.",
        )
        return actions
    if pr.get("mergeable") not in {"MERGEABLE", "UNKNOWN"}:
        add_finding(payload, "pull_request_not_mergeable", "review", f"Pull request mergeable state is {pr.get('mergeable')}.")
        return actions

    check_status, check_message = checks_state(pr.get("statusCheckRollup", []))
    if check_status != "passing":
        add_finding(payload, f"pull_request_checks_{check_status}", "review", check_message)
        return actions

    actions.append({
        "type": "gh_pr_merge",
        "prNumber": pr.get("number"),
        "url": pr.get("url"),
        "mergeMethod": "merge",
        "deleteBranch": True,
    })
    return actions


def github_archive_actions(repo, payload, args):
    result = _archive_git_preflight(repo, payload, args)
    if isinstance(result, list):
        return result
    actions, repo, branch = result
    return _archive_pr_actions(actions, repo, branch, payload, args)


def rebuild_archive_plan(payload, git_actions):
    prior_plan = payload.get("archivePlan") or {}
    prior_actions = prior_plan.get("actions") or []
    prefix_actions = []
    for action in prior_actions:
        if action.get("type") not in {"git_push", "archive_thread", "present_archive_summary"}:
            prefix_actions.append(action)

    status = status_for(payload)
    payload["status"] = status
    blockers = [
        finding["code"]
        for finding in payload.get("findings", [])
        if finding.get("severity") in {"review", "fail"}
    ]
    warnings = [
        finding["code"]
        for finding in payload.get("findings", [])
        if finding.get("severity") == "warn"
    ]
    actions = []
    if status in {"pass", "warn"}:
        summary = payload.get("archiveSummary") or {}
        bullets = summary.get("bullets") or []
        actions = [*prefix_actions, *git_actions]
        actions.append({
            "type": "present_archive_summary",
            "heading": "Archive Summary",
            "bullets": bullets,
        })
        actions.append({"type": "archive_thread"})

    payload["archivePlan"] = {
        "canArchive": status in {"pass", "warn"},
        "requiresReview": status in {"review", "fail"},
        "actions": actions,
        "blockers": blockers,
        "warnings": warnings,
    }
    return payload


def build_archive_payload(args):
    original_content = getattr(args, "content", None)
    temporary_content = None
    if original_content and str(original_content) == "-":
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write(sys.stdin.read())
            temporary_content = Path(handle.name)
        args.content = temporary_content

    try:
        payload = run_checker(args)
        summary, findings = archive_summary_from_content(
            getattr(args, "content", None)
        )
        for finding in findings:
            add_finding(payload, finding["code"], finding["severity"], finding["message"])
        payload["archiveSummary"] = summary or {
            "source": "fallback",
            "bullets": [
                "Cannot verify chat-level changes from CLI metadata alone. Supply the PR changelog or closeout content with an Archive Summary.",
            ],
        }
        git_actions = []
        if status_for(payload) in {"pass", "warn"}:
            git_actions = github_archive_actions(args.git_root, payload, args)
        return rebuild_archive_plan(payload, git_actions)
    finally:
        args.content = original_content
        if temporary_content:
            temporary_content.unlink(missing_ok=True)


def execute_archive_actions(payload, git_root):
    executed = []
    remaining_app = []
    for action in payload.get("archivePlan", {}).get("actions", []):
        action_type = action.get("type")
        if action_type in DEFERRED_AGENT_ACTIONS:
            remaining_app.append(action)
        elif action_type == "git_push":
            result = git(["push"], git_root)
            if result.returncode != 0:
                add_finding(payload, "git_push_failed", "fail", result.stderr.strip() or result.stdout.strip())
                break
            executed.append(action)
        elif action_type == "gh_pr_merge":
            pr_number = str(action.get("prNumber"))
            result = gh(["pr", "merge", pr_number, "--merge", "--delete-branch"], git_root)
            if result.returncode != 0:
                add_finding(payload, "gh_pr_merge_failed", "fail", result.stderr.strip() or result.stdout.strip())
                break
            executed.append(action)
        else:
            add_finding(payload, "unknown_archive_action", "fail", f"Unknown archive action: {action_type}")
            break

    payload["status"] = status_for(payload)
    payload["executedActions"] = executed
    payload["remainingAppActions"] = remaining_app if payload["status"] in {"pass", "warn"} else []
    return payload


def command_archive_plan(args):
    payload = build_archive_payload(args)
    _print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_archive_execute(args):
    payload = build_archive_payload(args)
    if payload["status"] not in {"pass", "warn"}:
        _print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    payload = execute_archive_actions(payload, args.git_root)
    _print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_followup_note(args):
    lines = [
        "Follow-up captured:",
        f"- Topic: {args.topic}",
        f"- Strength: {args.strength}",
        f"- Why it matters: {args.why}",
        f"- Context already known: {args.context}",
        f"- Suggested opener: {args.opener}",
    ]
    print("\n".join(lines))
    return 0


def command_changelog_pr(args):
    source_paths = [path for path in [args.accepted_spec, args.plan] if path]
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "source": str(source_paths[0]) if source_paths else "",
        "sources": [str(path) for path in source_paths],
        "findings": [],
        "pr": None,
        "markdown": "",
    }
    if not source_paths:
        add_finding(payload, "missing_changelog_source", "fail", "Provide --accepted-spec and/or --plan.")
    missing_paths = [Path(path) for path in source_paths if not Path(path).exists()]
    for path in missing_paths:
        add_finding(payload, "missing_changelog_source", "fail", f"Changelog source does not exist: {path}")
    if payload["findings"] and any(item["severity"] == "fail" for item in payload["findings"]):
        payload["status"] = status_for(payload)
        payload["markdown"] = build_changelog_markdown(", ".join(str(path) for path in source_paths) or "missing", {}, None, [], payload["findings"])
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(payload["markdown"])
        return EXIT_CODES[payload["status"]]

    paths = [Path(path) for path in source_paths]
    text = "\n\n".join(read_text(path) for path in paths)
    sections = markdown_sections(text)
    followups = parse_followups(text)

    repo = Path(args.git_root).resolve()
    inside = git(["rev-parse", "--is-inside-work-tree"], repo)
    pr = None
    if inside.returncode != 0:
        add_finding(payload, "git_root_not_repo", "warn", f"Cannot verify PR metadata because {repo} is not a git repo.")
    else:
        pr, error = pr_for_changelog(repo)
        if pr:
            payload["pr"] = {
                "number": pr.get("number"),
                "state": pr.get("state"),
                "url": pr.get("url"),
                "title": pr.get("title"),
                "baseRefName": pr.get("baseRefName"),
                "headRefName": pr.get("headRefName"),
                "mergedAt": pr.get("mergedAt"),
            }
        else:
            add_finding(payload, "cannot_verify_pr_metadata", "warn", f"Could not verify current PR metadata: {error or 'unknown gh error'}.")

    payload["status"] = status_for(payload)
    source_display = ", ".join(display_path(Path.cwd().resolve(), path) for path in paths)
    payload["markdown"] = build_changelog_markdown(source_display, sections, pr, followups, payload["findings"])
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload["markdown"], encoding="utf-8")
        payload["output"] = str(output)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(payload["markdown"])
    return EXIT_CODES[payload["status"]]


def followup_from_args(args):
    if args.content:
        if not args.content.exists():
            return {}, [{"code": "missing_followup_file", "severity": "fail", "message": f"Follow-up content file does not exist: {args.content}."}]
        followups = parse_followups(read_text(args.content))
        if followups:
            return followups[0], []
        return {}, [{"code": "missing_followup_block", "severity": "fail", "message": f"No follow-up block found in {args.content}."}]
    required = {
        "topic": args.topic,
        "strength": args.strength,
        "why_it_matters": args.why,
        "context_already_known": args.context,
        "suggested_opener": args.opener,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        return {}, [{"code": "missing_followup_fields", "severity": "fail", "message": "Missing follow-up fields: " + ", ".join(missing) + "."}]
    return required, []


def command_followup_thread(args):
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "findings": [],
        "actions": [],
    }
    parsed_title = parse_thread_title(args.title)
    if parsed_title["format"] == "malformed":
        if parsed_title.get("reason") == "goal_word_count":
            add_finding(
                payload,
                "title_goal_word_count",
                "fail",
                "Thread title must contain one to four words; "
                f"found {parsed_title['actualWordCount']}.",
                actualWordCount=parsed_title["actualWordCount"],
                requiredWordCount=parsed_title["requiredWordCount"],
            )
        else:
            add_finding(
                payload,
                "malformed_thread_title",
                "fail",
                "Thread title must be a plain descriptive one-to-four-word title.",
            )

    followup, findings = followup_from_args(args)
    for finding in findings:
        add_finding(payload, finding["code"], finding["severity"], finding["message"])
    if followup and has_secret("\n".join(followup.values())):
        add_finding(
            payload,
            "secret_like_followup_content",
            "fail",
            "Follow-up content contains secret-like text; redact it before creating a thread packet.",
        )

    if payload["findings"]:
        payload["status"] = status_for(payload)
    else:
        source_line = f"Source thread: {args.source_thread}" if args.source_thread else "Source thread: not supplied"
        message = "\n".join([
            followup.get("suggested_opener", ""),
            "",
            "Follow-up captured:",
            f"- Topic: {followup.get('topic', '')}",
            f"- Strength: {followup.get('strength', '')}",
            f"- Why it matters: {followup.get('why_it_matters', '')}",
            f"- Context already known: {followup.get('context_already_known', '')}",
            f"- Suggested opener: {followup.get('suggested_opener', '')}",
            f"- {source_line}",
        ]).strip()
        payload["actions"].append({
            "type": "create_thread",
            "title": args.title,
            "cwd": str(Path(args.cwd).resolve()) if args.cwd else str(Path.cwd().resolve()),
            "message": message,
        })
        payload["status"] = status_for(payload)

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Follow-up thread packet: {payload['status']}")
        for action in payload.get("actions", []):
            print(f"- action: {action['type']} title={action['title']}")
        for finding in payload.get("findings", []):
            print(f"- [{finding['severity']}] {finding['code']}: {finding['message']}")
    return EXIT_CODES[payload["status"]]
