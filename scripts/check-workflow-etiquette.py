#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

from gauntletlib.core.findings import finding as make_finding
from gauntletlib.core.findings import status_for_findings
from gauntletlib.core.processes import git
from thread_titles import parse_thread_title

FIELD_PATTERN = r"^\s*(?:-\s*)?{field}:\s*(.+?)\s*$"
VALID_FIELDS = {
    "Mode": {"Research", "Patch", "Feature", "Release"},
    "Depth": {"Standard", "Deep"},
    "Verification Scope": {"smoke", "delta", "full", "not relevant"},
    "Execution Mode": {"review", "autonomous"},
}
REQUIRED_KICKOFF_FIELDS = []
OPTIONAL_KICKOFF_FIELDS = [
    "Mode",
    "Depth",
    "Verification Scope",
    "Execution Mode",
    "Suggested thread label",
    "Decision Gate",
]
STATUS_ORDER = {"pass": 0, "warn": 1, "review": 2, "fail": 3}
EXIT_CODES = {"pass": 0, "warn": 0, "review": 2, "fail": 1}


def add_finding(findings, code, severity, message, migration_friendly=False, **details):
    extra = {}
    if migration_friendly:
        extra["migrationFriendly"] = True
    extra.update(details)
    findings.append(make_finding(code, severity, message, **extra))


def status_for(findings):
    return status_for_findings(findings, STATUS_ORDER)


def read_content(path):
    if not path:
        return ""
    return Path(path).read_text(encoding="utf-8")


def field_value(content, field):
    pattern = re.compile(FIELD_PATTERN.format(field=re.escape(field)), re.IGNORECASE | re.MULTILINE)
    match = pattern.search(content or "")
    return match.group(1).strip() if match else None


def normalize_execution_mode(value, findings):
    if value == "reviewed":
        add_finding(
            findings,
            "legacy_reviewed_execution_mode",
            "warn",
            "Use 'Execution Mode: review' in new kickoff text; 'reviewed' is accepted during migration.",
            migration_friendly=True,
        )
        return "review"
    return value


def parse_title(
    title,
    findings,
    source="title",
    malformed_severity="fail",
    malformed_code="malformed_title",
    malformed_message=None,
):
    if not title:
        return None

    parsed = {"source": source, **parse_thread_title(title)}
    if parsed["format"] == "current":
        return parsed

    if parsed.get("reason") == "goal_word_count":
        code = malformed_code if malformed_code != "malformed_title" else "title_goal_word_count"
        message = malformed_message or (
            "Thread title goal must contain exactly four whitespace-delimited words; "
            f"found {parsed['actualWordCount']}."
        )
        add_finding(
            findings,
            code,
            malformed_severity,
            message,
            actualWordCount=parsed["actualWordCount"],
            requiredWordCount=parsed["requiredWordCount"],
        )
        return parsed

    add_finding(
        findings,
        malformed_code,
        malformed_severity,
        malformed_message
        or "Thread title must use 'p#: four word goal' or 'p#-auto: four word goal'.",
    )
    return parsed


def check_kickoff(content, parsed_title, findings):
    add_finding(
        findings,
        "kickoff_check_deprecated",
        "warn",
        "The five-field kickoff block is deprecated; classify internally and surface only material transitions.",
        migration_friendly=True,
    )
    if not content:
        return {}, parsed_title

    fields = {field: field_value(content, field) for field in REQUIRED_KICKOFF_FIELDS + OPTIONAL_KICKOFF_FIELDS}
    proof_scope = field_value(content, "Proof Scope")
    if not fields["Verification Scope"] and proof_scope:
        fields["Verification Scope"] = proof_scope
        add_finding(
            findings,
            "legacy_proof_scope",
            "warn",
            "Use 'Verification Scope' in new kickoff text; 'Proof Scope' is accepted during migration.",
            migration_friendly=True,
        )

    raw_execution_mode = fields.get("Execution Mode")
    fields["Execution Mode"] = normalize_execution_mode(raw_execution_mode, findings)
    for field, valid_values in VALID_FIELDS.items():
        value = fields.get(field)
        if value and value not in valid_values:
            add_finding(
                findings,
                f"invalid_{field.lower().replace(' ', '_')}",
                "fail",
                f"{field} must be one of: {', '.join(sorted(valid_values))}.",
            )

    suggested_title = fields.get("Suggested thread label")
    if suggested_title:
        suggested = parse_title(suggested_title, findings, source="suggestedThreadLabel")
        if parsed_title and parsed_title.get("format") != "malformed" and suggested.get("format") != "malformed":
            if suggested_title.strip() != parsed_title.get("raw", "").strip():
                add_finding(
                    findings,
                    "thread_label_mismatch",
                    "warn",
                    "Suggested thread label differs from the current thread title.",
                )
        if not parsed_title:
            parsed_title = suggested

    execution_mode = fields.get("Execution Mode")
    if execution_mode and parsed_title and parsed_title.get("format") == "current":
        title_mode = parsed_title.get("executionMode")
        title_is_auto = title_mode == "autonomous"
        field_is_auto = execution_mode == "autonomous"
        if title_is_auto != field_is_auto:
            add_finding(
                findings,
                "execution_mode_title_mismatch",
                "fail",
                "Execution Mode and title suffix disagree; reserve '-auto' for autonomous execution.",
            )

    return fields, parsed_title


def check_assumptions(content, autonomous, findings):
    if not autonomous:
        return
    if not re.search(r"^\s*Assumptions Made:\s*$", content or "", re.IGNORECASE | re.MULTILINE):
        add_finding(
            findings,
            "missing_assumptions_made",
            "fail",
            "Autonomous execution requires an 'Assumptions Made' closeout before adoption or archive.",
        )
        return

    for label in ["Assumptions made", "Ambiguity handled", "Verification"]:
        pattern = re.compile(FIELD_PATTERN.format(field=re.escape(label)), re.IGNORECASE | re.MULTILINE)
        if not pattern.search(content or ""):
            add_finding(
                findings,
                f"missing_assumptions_{label.lower().replace(' ', '_')}",
                "fail",
                f"Autonomous execution assumptions are missing '{label}:'.",
            )


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
    if not blocks and re.search(r"^\s*(?:-\s*)?Strength:\s*strong follow-up\s*$", content or "", re.IGNORECASE | re.MULTILINE):
        blocks.append(content or "")
    return blocks


def check_followups(content, archive, archive_anyway, findings):
    if not archive:
        return
    for block in followup_blocks(content):
        strong = re.search(r"^\s*(?:-\s*)?Strength:\s*strong follow-up\s*$", block, re.IGNORECASE | re.MULTILINE)
        if not strong:
            continue
        resolved = re.search(
            r"^\s*(?:-\s*)?(Status:\s*(resolved|done|closed)|Resolved:\s*(yes|true))\s*$",
            block,
            re.IGNORECASE | re.MULTILINE,
        )
        if not resolved:
            if archive_anyway:
                add_finding(
                    findings,
                    "strong_followup_archived_anyway",
                    "warn",
                    "Strong follow-up remains, but archive-anyway was selected.",
                )
            else:
                add_finding(
                    findings,
                    "strong_followup_open",
                    "review",
                    "Strong follow-up remains; offer complete here, create same-repo chat with context, or archive anyway.",
                )


def check_git_state(root, archive, findings):
    actions = []
    if not root or not archive:
        return actions
    repo = Path(root).resolve()
    if not repo.exists():
        add_finding(findings, "git_root_missing", "review", f"Git root does not exist: {repo}.")
        return actions
    inside = git(["rev-parse", "--is-inside-work-tree"], repo)
    if inside.returncode != 0:
        return actions

    status = git(["status", "--porcelain"], repo)
    if status.returncode != 0:
        add_finding(findings, "git_status_failed", "review", "Could not read git status for archive check.")
        return actions
    dirty_lines = [line for line in status.stdout.splitlines() if line.strip()]
    if dirty_lines:
        sample_paths = [line[3:] if len(line) > 3 else line for line in dirty_lines[:3]]
        sample = ", ".join(sample_paths)
        if len(dirty_lines) > len(sample_paths):
            sample = f"{sample}, and {len(dirty_lines) - len(sample_paths)} more"
        add_finding(
            findings,
            "dirty_worktree",
            "review",
            f"Worktree has dirty files before archive: {sample}.",
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
    behind, ahead = [int(part) for part in parts]
    if ahead:
        actions.append({"type": "git_push", "upstream": upstream.stdout.strip(), "ahead": ahead})
    if behind:
        add_finding(
            findings,
            "branch_behind_upstream",
            "review",
            f"Branch is behind upstream by {behind} commit(s); reconcile before automatic archive.",
        )
    return actions


def build_archive_plan(args, parsed_title, suggested_title, git_actions, findings, status):
    if not args.archive:
        return None

    actions = []
    blockers = [
        finding["code"]
        for finding in findings
        if finding.get("severity") in {"review", "fail"}
    ]
    warnings = [
        finding["code"]
        for finding in findings
        if finding.get("severity") == "warn"
    ]

    if suggested_title and suggested_title.get("format") == "current":
        current_raw = parsed_title.get("raw") if parsed_title else None
        if current_raw != suggested_title["raw"]:
            actions.append({"type": "set_thread_title", "title": suggested_title["raw"]})

    actions.extend(git_actions)

    return {
        "canArchive": status in {"pass", "warn"},
        "requiresReview": status in {"review", "fail"},
        "actions": actions,
        "blockers": blockers,
        "warnings": warnings,
    }


def build_payload(args):
    findings = []
    content = read_content(args.content)
    title = args.title
    suggested_title = parse_title(args.suggested_title, findings, source="suggestedTitle") if args.suggested_title else None
    if title and args.archive and suggested_title:
        parsed_title = parse_title(
            title,
            findings,
            malformed_severity="warn",
            malformed_code="title_requires_rename",
            malformed_message="Thread title does not start with 'p#:' or 'p#-auto:'; archive plan will rename it first.",
        )
    else:
        parsed_title = parse_title(title, findings) if title else None

    if args.archive and title and parsed_title and parsed_title.get("format") == "malformed" and not suggested_title:
        add_finding(
            findings,
            "missing_suggested_title",
            "review",
            "Archive requested for an unlabeled thread; provide --suggested-title so the thread can be renamed before archive.",
        )

    fields = {}
    if args.require_kickoff:
        fields, parsed_title = check_kickoff(content, parsed_title, findings)

    execution_mode = fields.get("Execution Mode") or field_value(content, "Execution Mode")
    effective_execution_mode = (
        execution_mode
        or (suggested_title.get("executionMode") if suggested_title and suggested_title.get("format") != "malformed" else None)
        or (parsed_title.get("executionMode") if parsed_title and parsed_title.get("format") != "malformed" else None)
    )
    autonomous = effective_execution_mode == "autonomous"
    if args.require_assumptions:
        check_assumptions(content, autonomous, findings)
    check_followups(content, args.archive, args.archive_anyway, findings)
    git_actions = check_git_state(args.git_root, args.archive, findings)

    status = status_for(findings)
    payload = {
        "schemaVersion": "1.0",
        "status": status,
        "parsedTitle": parsed_title,
        "suggestedTitle": suggested_title,
        "effectiveExecutionMode": effective_execution_mode,
        "decisionGate": fields.get("Decision Gate") or field_value(content, "Decision Gate"),
        "kickoffFields": fields,
        "findings": findings,
    }
    archive_plan = build_archive_plan(args, parsed_title, suggested_title, git_actions, findings, status)
    if archive_plan is not None:
        payload["archivePlan"] = archive_plan
    return payload


def print_text(payload):
    print(f"Workflow etiquette: {payload['status']}")
    for finding in payload["findings"]:
        print(f"- [{finding['severity']}] {finding['code']}: {finding['message']}")


def main():
    parser = argparse.ArgumentParser(description="Check deterministic Workflow Etiquette fields and archive blockers.")
    parser.add_argument("--title", default=None, help="Thread title to validate.")
    parser.add_argument("--suggested-title", default=None, help="Suggested title to use when archive should rename first.")
    parser.add_argument("--content", type=Path, default=None, help="Markdown/text content to scan.")
    parser.add_argument("--require-kickoff", action="store_true", help="Deprecated compatibility check; warns without requiring kickoff fields.")
    parser.add_argument("--require-assumptions", action="store_true", help="Require autonomous Assumptions Made fields.")
    parser.add_argument("--archive", action="store_true", help="Check archive-time review blockers.")
    parser.add_argument("--archive-anyway", action="store_true", help="Do not pause archive for unresolved strong follow-ups.")
    parser.add_argument("--git-root", type=Path, default=None, help="Git repo root to classify for archive.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    args = parser.parse_args()

    payload = build_payload(args)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print_text(payload)
    raise SystemExit(EXIT_CODES[payload["status"]])


if __name__ == "__main__":
    main()
