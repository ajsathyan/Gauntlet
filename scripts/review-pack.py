#!/usr/bin/env python3
import argparse
from pathlib import Path

from gauntlet_diff_helpers import build_diff_intel, diff_for_file, now_iso, read_json, redact_secrets


MAX_DIFF_LINES_PER_FILE = 80


def bullets(items, empty="None."):
    if not items:
        return empty
    return "\n".join(f"- {item}" for item in items)


def file_summary(changed):
    flags = ", ".join(changed.get("flags", [])) or "code"
    risks = ", ".join(changed.get("riskTriggers", [])) or "none"
    tests = ", ".join(changed.get("testCandidates", [])) or "none found"
    return f"`{changed['path']}` ({changed.get('status', 'M')}; flags: {flags}; risks: {risks}; tests: {tests})"


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


def build_review_pack(project_root, intel):
    root = Path(project_root).resolve()
    triggers = intel.get("riskTriggers", [])
    changed_files = intel.get("changedFiles", [])
    cannot_verify = list(intel.get("cannotVerify", []))
    if intel.get("confidence") != "high":
        cannot_verify.append("Diff classification is advisory; confirm surfaces and tests against local repo conventions.")

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
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    intel = read_json(args.diff_intel) if args.diff_intel else build_diff_intel(project_root)
    packet = build_review_pack(project_root, intel)
    output = args.output or project_root / ".gauntlet" / "review-pack.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(packet, encoding="utf-8")
    print(f"Review pack: {output}")


if __name__ == "__main__":
    main()
