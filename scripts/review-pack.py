#!/usr/bin/env python3
import argparse
from pathlib import Path

from gauntlet_diff_helpers import build_diff_intel, diff_for_file, now_iso, read_json, redact_secrets


MAX_DIFF_LINES_PER_FILE = 80
MAX_CONTEXT_LINES = 40
MAX_PROOF_CONTEXTS = 4
GAP_REVIEW_PHASES = ("pre-build", "integrated")


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


def build_review_pack(
    project_root,
    intel,
    test_plan=None,
    test_plan_path=None,
    accepted_spec_path=None,
    plan_path=None,
    *,
    phase="integrated",
    maturity="not supplied",
    proof_context_paths=None,
):
    root = Path(project_root).resolve()
    if phase not in GAP_REVIEW_PHASES:
        raise ValueError(f"phase must be one of {', '.join(GAP_REVIEW_PHASES)}")
    if not isinstance(maturity, str) or not maturity.strip():
        raise ValueError("maturity must be a non-empty string")
    triggers = intel.get("riskTriggers", [])
    changed_files = intel.get("changedFiles", [])
    cannot_verify = list(intel.get("cannotVerify", []))
    if intel.get("confidence") != "high":
        cannot_verify.append("Diff classification is advisory; confirm surfaces and tests against local repo conventions.")
    accepted_spec_lines, accepted_spec_cannot_verify = context_section(root, accepted_spec_path, "Accepted Spec")
    plan_lines, plan_cannot_verify = context_section(root, plan_path, "Ephemeral Implementation Plan")
    cannot_verify.extend(accepted_spec_cannot_verify + plan_cannot_verify)
    proof_context_paths = list(proof_context_paths or [])
    if len(proof_context_paths) > MAX_PROOF_CONTEXTS:
        raise ValueError(f"at most {MAX_PROOF_CONTEXTS} proof context files may be supplied")
    proof_context_lines = []
    for index, proof_path in enumerate(proof_context_paths, start=1):
        lines, missing = context_section(root, proof_path, f"Proof Context {index}")
        proof_context_lines.extend(lines)
        cannot_verify.extend(missing)
    sections = [
        "# Integrated Review Pack",
        "",
        f"Generated: {now_iso()}",
        f"Project root: `{root}`",
        f"Base ref: `{intel.get('baseRef', 'HEAD')}`",
        f"Phase: `{phase}`",
        f"Declared maturity: `{redact_secrets(maturity.strip())}`",
        f"Confidence: `{intel.get('confidence', 'low')}`",
        "",
        "Review only concrete missed accepted behavior, regressions, and failure paths at the declared maturity. Ordinary review cannot alter accepted scope.",
        "Do not run an external-practice or state-of-the-art review automatically. Use locked consequence specialist lenses only for explicit high-consequence triggers.",
        "Generic hardening with no practical effect at this maturity may be omitted.",
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
        *proof_context_lines,
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
        "- Return at most three material findings in this pass.",
        "- For each finding: ID, concrete missed behavior/regression/failure path, practical effect, smallest response, affected accepted work, and one terminal disposition.",
        "- Terminal disposition must be exactly `fixed`, `ask-user`, `deferred`, or `omitted`.",
        "- `ask-user` blocks only the affected work. `deferred` and `omitted` close the finding but are not fixes.",
        "- Return no finding for generic advice without a concrete practical effect at the declared maturity.",
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
    parser.add_argument("--plan", type=Path, default=None, help="optional ephemeral implementation-plan file")
    parser.add_argument("--phase", choices=GAP_REVIEW_PHASES, default="integrated", help="review phase")
    parser.add_argument("--maturity", default="not supplied", help="declared product maturity for proportional review")
    parser.add_argument("--proof-context", type=Path, action="append", default=[], help="bounded proof context file; repeat up to four times")
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
    proof_context_paths = [project_relative_path(project_root, path) for path in args.proof_context]
    try:
        packet = build_review_pack(
            project_root, intel, test_plan, test_plan_path, accepted_spec_path,
            plan_path,
            phase=args.phase, maturity=args.maturity, proof_context_paths=proof_context_paths,
        )
    except ValueError as exc:
        parser.error(str(exc))
    output = args.output or project_root / ".gauntlet" / "review-pack.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(packet, encoding="utf-8")
    print(f"Review pack: {output}")


if __name__ == "__main__":
    main()
