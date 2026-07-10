#!/usr/bin/env python3
import argparse
from pathlib import Path

from gauntlet_diff_helpers import build_diff_intel, diff_for_file, now_iso, read_json, redact_secrets


MAX_DIFF_LINES_PER_FILE = 80
MAX_CONTEXT_LINES = 40


def bullets(items, empty="None."):
    if not items:
        return empty
    return "\n".join(f"- {item}" for item in items)


def file_summary(changed):
    flags = ", ".join(changed.get("flags", [])) or "code"
    risks = ", ".join(changed.get("riskTriggers", [])) or "none"
    tests = ", ".join(changed.get("testCandidates", [])) or "none found"
    return f"`{changed['path']}` ({changed.get('status', 'M')}; flags: {flags}; risks: {risks}; tests: {tests})"


def display_path(root, path):
    path = Path(path)
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return str(path)


def test_plan_command_summary(command):
    tier = command.get("tier", "check")
    text = command.get("command", "unknown command")
    reason = command.get("reason", "No reason supplied.")
    confidence = command.get("confidence", "unknown")
    return f"`{tier}` `{text}` - {reason} Confidence: `{confidence}`."


def test_plan_section(root, test_plan, test_plan_path):
    if not test_plan:
        return []

    source = display_path(root, test_plan_path)
    commands = [test_plan_command_summary(command) for command in test_plan.get("commands", [])]
    cannot_verify = test_plan.get("cannotVerify", [])
    return [
        "## Test Plan Summary",
        f"Source: `{source}`",
        f"Generated: `{test_plan.get('generatedAt', 'unknown')}`",
        f"Confidence: `{test_plan.get('confidence', 'unknown')}`",
        "",
        "Planned proof only; this section does not mean the commands were run.",
        "",
        "Commands:",
        bullets(commands),
        "",
        "Cannot verify from test plan:",
        bullets(cannot_verify),
        "",
    ]


def context_section(root, path_value, label):
    if not path_value:
        return [], []

    path = Path(path_value)
    if not path.exists():
        return [], [f"{label} path was supplied but not found: {display_path(root, path)}"]

    lines = redact_secrets(path.read_text(encoding="utf-8", errors="ignore")).splitlines()
    if len(lines) > MAX_CONTEXT_LINES:
        lines = lines[:MAX_CONTEXT_LINES] + [f"... {label} excerpt truncated ..."]
    excerpt = "\n".join(lines).strip() or "No content supplied."

    return [
        f"## {label}",
        f"Path: `{display_path(root, path)}`",
        "",
        "Bounded excerpt; inspect the canonical source for full context.",
        "",
        excerpt,
        "",
    ], []


def project_relative_path(root, path):
    if not path:
        return None
    path = Path(path)
    return path if path.is_absolute() else root / path


def invariant_notes(triggers):
    notes = []
    if "auth" in triggers or "permissions" in triggers:
        notes.append("Preserve authentication, authorization, and session invariants on changed paths.")
    if "security-privacy" in triggers:
        notes.append("Verify no secrets, credentials, private data, or unsafe logs are exposed.")
    if "billing" in triggers:
        notes.append("Preserve payment, credit, entitlement, and idempotency behavior.")
    if "persistence" in triggers or "migration" in triggers or "data-integrity" in triggers:
        notes.append("Preserve storage, migration, consistency, and rollback assumptions.")
    if "public-api" in triggers:
        notes.append("Preserve public contract shape, status codes, payloads, and compatibility.")
    if "ui" in triggers:
        notes.append("Check changed UI states, copy, accessibility basics, and the first-value path.")
    if "generated" in triggers:
        notes.append("Confirm generated files are produced from the intended source, not edited as stale output.")
    if not notes:
        notes.append("Protect behavior on changed paths and avoid unrelated scope expansion.")
    return notes


def diff_excerpt(root, changed, base_ref):
    diff = redact_secrets(diff_for_file(root, changed["path"], base_ref))
    lines = diff.splitlines()
    if len(lines) > MAX_DIFF_LINES_PER_FILE:
        lines = lines[:MAX_DIFF_LINES_PER_FILE] + ["... diff excerpt truncated; inspect full diff locally ..."]
    if not lines:
        return f"### `{changed['path']}`\n\nNo diff excerpt available.\n"
    return f"### `{changed['path']}`\n\n```diff\n" + "\n".join(lines) + "\n```\n"


def build_review_pack(project_root, intel, test_plan=None, test_plan_path=None, accepted_spec_path=None, plan_path=None, legacy_memory_path=None):
    root = Path(project_root).resolve()
    triggers = intel.get("riskTriggers", [])
    changed_files = intel.get("changedFiles", [])
    cannot_verify = list(intel.get("cannotVerify", []))
    if intel.get("confidence") != "high":
        cannot_verify.append("Diff classification is advisory; confirm surfaces and tests against local repo conventions.")
    accepted_spec_lines, accepted_spec_cannot_verify = context_section(root, accepted_spec_path, "Accepted Spec")
    plan_lines, plan_cannot_verify = context_section(root, plan_path, "Canonical Plan")
    cannot_verify.extend(accepted_spec_cannot_verify + plan_cannot_verify)
    legacy_lines = []
    if legacy_memory_path and not accepted_spec_path:
        legacy_lines, legacy_cannot_verify = context_section(root, legacy_memory_path, "Legacy Implementation Memory")
        cannot_verify.extend(legacy_cannot_verify)
        cannot_verify.append("Deprecated --implementation-memory input used; migrate this context into the accepted spec or canonical plan.")

    sections = [
        "# Gauntlet Review Pack",
        "",
        f"Generated: {now_iso()}",
        f"Project root: `{root}`",
        f"Base ref: `{intel.get('baseRef', 'HEAD')}`",
        f"Confidence: `{intel.get('confidence', 'low')}`",
        "",
        "## Changed Files",
        bullets([file_summary(item) for item in changed_files], "No changed files detected."),
        "",
        "## Risk Triggers",
        bullets([f"`{trigger}`" for trigger in triggers], "None detected."),
        "",
        "## Invariants To Protect",
        bullets(invariant_notes(set(triggers))),
        "",
        "## Known Non-Goals",
        "- Not supplied; do not broaden beyond changed files, directly affected tests, and listed invariants.",
        "",
        "## Proof Already Available",
        "- Not supplied by this generator.",
        "",
        "## Proof Still Needed",
        "- Run `scripts/test-plan.py` or project-local focused checks before claiming behavior is verified.",
        "- Treat missing or low-confidence test mappings as `Cannot verify`, not as proof of safety.",
        "",
        *test_plan_section(root, test_plan, test_plan_path),
        *accepted_spec_lines,
        *plan_lines,
        *legacy_lines,
        "## Cannot verify",
        bullets(cannot_verify, "None from the generator; reviewer should still report missing proof."),
        "",
        "## Diff Excerpts",
    ]

    for changed in changed_files:
        sections.append(diff_excerpt(root, changed, intel.get("baseRef", "HEAD")))

    sections.extend([
        "",
        "## Expected Return Format",
        "- Verdict: `Approved`, `Needs fixes`, `Needs proof`, `Needs decision`, `Blocked`, or `Cannot verify`",
        "- Evidence reviewed",
        "- Findings by P0/P1/P2/P3 with file/line, surface, command, or repro evidence when possible",
        "- Cannot verify: missing proof, why it matters, and the next check",
        "- Residual risk",
        "- Agent next: one concrete action",
        "- Coverage gap candidate: only when reusable guidance is missing",
        "",
    ])
    return "\n".join(sections)


def main():
    parser = argparse.ArgumentParser(description="Generate a bounded, redacted review packet from Gauntlet diff intel.")
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--diff-intel", type=Path, default=None)
    parser.add_argument("--test-plan", type=Path, default=None, help="test-plan JSON to summarize; defaults to .gauntlet/test-plan.json when present")
    parser.add_argument("--no-test-plan", action="store_true", help="do not include an existing test-plan summary")
    parser.add_argument("--accepted-spec", type=Path, default=None, help="accepted spec/context file")
    parser.add_argument("--plan", type=Path, default=None, help="canonical implementation plan file")
    parser.add_argument("--implementation-memory", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    intel = read_json(args.diff_intel) if args.diff_intel else build_diff_intel(project_root)
    test_plan_path = None
    test_plan = None
    if not args.no_test_plan:
        test_plan_path = project_relative_path(project_root, args.test_plan) or project_root / ".gauntlet" / "test-plan.json"
        if test_plan_path.exists():
            test_plan = read_json(test_plan_path)
    accepted_spec_path = project_relative_path(project_root, args.accepted_spec)
    plan_path = project_relative_path(project_root, args.plan)
    legacy_memory_path = project_relative_path(project_root, args.implementation_memory)
    packet = build_review_pack(project_root, intel, test_plan, test_plan_path, accepted_spec_path, plan_path, legacy_memory_path)
    output = args.output or project_root / ".gauntlet" / "review-pack.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(packet, encoding="utf-8")
    print(f"Review pack: {output}")


if __name__ == "__main__":
    main()
