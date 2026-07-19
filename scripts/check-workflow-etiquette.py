#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

from gauntletlib.core.findings import add_finding as _add_finding
from gauntletlib.core.findings import status_for
from gauntletlib.core.proc import git
from thread_titles import parse_thread_title


EXIT_CODES = {"pass": 0, "warn": 0, "review": 2, "fail": 1}


def add_finding(findings, code, severity, message, **details):
    _add_finding(findings, code, severity, message, **details)


def read_content(path):
    return Path(path).read_text(encoding="utf-8") if path else ""


def parse_title(title, findings, *, source="title", rename_allowed=False):
    if not title:
        return None
    parsed = {"source": source, **parse_thread_title(title)}
    if parsed["format"] == "current":
        return parsed

    if parsed.get("reason") == "word_limit":
        add_finding(
            findings,
            "title_word_limit",
            "warn" if rename_allowed else "fail",
            "Task title must use plain descriptive text with at most four words.",
            actualWordCount=parsed["actualWordCount"],
            maximumWordCount=parsed["maximumWordCount"],
        )
    else:
        add_finding(
            findings,
            "title_requires_rename" if rename_allowed else "malformed_title",
            "warn" if rename_allowed else "fail",
            "Task title must use plain descriptive text with at most four words and no metadata prefix.",
        )
    return parsed


def followup_blocks(content):
    lines = (content or "").splitlines()
    blocks = []
    index = 0
    while index < len(lines):
        if re.match(r"^\s*Follow-up captured:\s*$", lines[index], re.IGNORECASE):
            block = []
            index += 1
            while index < len(lines) and lines[index].strip():
                block.append(lines[index])
                index += 1
            blocks.append("\n".join(block))
        index += 1
    if not blocks and re.search(
        r"^\s*(?:-\s*)?Strength:\s*strong follow-up\s*$",
        content or "",
        re.IGNORECASE | re.MULTILINE,
    ):
        blocks.append(content or "")
    return blocks


def check_followups(content, archive, archive_anyway, findings):
    if not archive:
        return
    for block in followup_blocks(content):
        strong = re.search(
            r"^\s*(?:-\s*)?Strength:\s*strong follow-up\s*$",
            block,
            re.IGNORECASE | re.MULTILINE,
        )
        resolved = re.search(
            r"^\s*(?:-\s*)?(Status:\s*(resolved|done|closed)|Resolved:\s*(yes|true))\s*$",
            block,
            re.IGNORECASE | re.MULTILINE,
        )
        if strong and not resolved:
            add_finding(
                findings,
                "strong_followup_archived_anyway" if archive_anyway else "strong_followup_open",
                "warn" if archive_anyway else "review",
                "Strong follow-up remains."
                if archive_anyway
                else "Strong follow-up remains; resolve it, continue it separately, or explicitly archive anyway.",
            )


def check_git_state(root, archive, findings):
    actions = []
    if not root or not archive:
        return actions
    repo = Path(root).resolve()
    if not repo.exists():
        add_finding(findings, "git_root_missing", "review", f"Git root does not exist: {repo}.")
        return actions
    if git(["rev-parse", "--is-inside-work-tree"], repo).returncode != 0:
        return actions

    status = git(["status", "--porcelain"], repo)
    if status.returncode != 0:
        add_finding(findings, "git_status_failed", "review", "Could not read Git status.")
        return actions
    dirty = [line for line in status.stdout.splitlines() if line.strip()]
    if dirty:
        paths = [line[3:] if len(line) > 3 else line for line in dirty[:3]]
        suffix = f", and {len(dirty) - len(paths)} more" if len(dirty) > len(paths) else ""
        add_finding(
            findings,
            "dirty_worktree",
            "review",
            f"Worktree has dirty files before archive: {', '.join(paths)}{suffix}.",
        )
        return actions

    upstream = git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], repo)
    if upstream.returncode != 0:
        return actions
    counts = git(["rev-list", "--left-right", "--count", "@{u}...HEAD"], repo)
    if counts.returncode != 0:
        add_finding(findings, "git_upstream_compare_failed", "review", "Could not compare branch with upstream.")
        return actions
    parts = counts.stdout.strip().split()
    if len(parts) != 2:
        return actions
    behind, ahead = (int(part) for part in parts)
    if ahead:
        actions.append({"type": "git_push", "upstream": upstream.stdout.strip(), "ahead": ahead})
    if behind:
        add_finding(
            findings,
            "branch_behind_upstream",
            "review",
            f"Branch is behind upstream by {behind} commit(s); reconcile before archive.",
        )
    return actions


def build_payload(args):
    findings = []
    content = read_content(args.content)
    suggested = parse_title(args.suggested_title, findings, source="suggestedTitle") if args.suggested_title else None
    rename_allowed = bool(args.archive and suggested and suggested.get("format") == "current")
    parsed = parse_title(args.title, findings, rename_allowed=rename_allowed) if args.title else None

    if args.archive and parsed and parsed.get("format") == "malformed" and not rename_allowed:
        add_finding(
            findings,
            "missing_suggested_title",
            "review",
            "Provide a plain suggested title with at most four words before archive.",
        )

    check_followups(content, args.archive, args.archive_anyway, findings)
    git_actions = check_git_state(args.git_root, args.archive, findings)
    status = status_for(findings)
    payload = {
        "schemaVersion": "1.0",
        "status": status,
        "parsedTitle": parsed,
        "suggestedTitle": suggested,
        "findings": findings,
    }

    if args.archive:
        blockers = [item["code"] for item in findings if item["severity"] in {"review", "fail"}]
        warnings = [item["code"] for item in findings if item["severity"] == "warn"]
        actions = []
        if suggested and suggested.get("format") == "current":
            if not parsed or parsed.get("format") != "current" or parsed.get("goal") != suggested.get("goal"):
                actions.append({"type": "set_thread_title", "title": suggested["goal"]})
        actions.extend(git_actions)
        payload["archivePlan"] = {
            "canArchive": status in {"pass", "warn"},
            "requiresReview": status in {"review", "fail"},
            "actions": actions,
            "blockers": blockers,
            "warnings": warnings,
        }
    return payload


def main():
    parser = argparse.ArgumentParser(description="Check task-title and archive etiquette.")
    parser.add_argument("--title")
    parser.add_argument("--suggested-title")
    parser.add_argument("--content", type=Path)
    parser.add_argument("--archive", action="store_true")
    parser.add_argument("--archive-anyway", action="store_true")
    parser.add_argument("--git-root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = build_payload(args)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Workflow etiquette: {payload['status']}")
        for finding in payload["findings"]:
            print(f"- [{finding['severity']}] {finding['code']}: {finding['message']}")
    raise SystemExit(EXIT_CODES[payload["status"]])


if __name__ == "__main__":
    main()
