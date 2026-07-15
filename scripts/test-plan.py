#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import shlex
from pathlib import Path

from gauntlet_diff_helpers import build_diff_intel, now_iso, read_json, write_json


DURABLE_TRIGGERS = {
    "auth",
    "permissions",
    "billing",
    "migration",
    "persistence",
    "public-api",
    "data-integrity",
    "security-privacy",
    "durable-workflow",
    "shared-domain",
}

EPIC_RUN_FACTS_SCHEMA = "gauntlet/epic-run-facts/v1"
RECEIPT_IDENTITY_FIELDS = (
    "commit",
    "tree",
    "argv",
    "toolchain",
    "fixtures",
    "environment",
)


def package_json(root, package_root):
    path = root / package_root / "package.json" if package_root != "." else root / "package.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def command_for_package(package_root, command):
    if package_root == ".":
        return command
    return f"cd {package_root} && {command}"


def add_command(commands, tier, command, reason, confidence):
    if any(item["command"] == command for item in commands):
        return
    commands.append({
        "tier": tier,
        "command": command,
        "reason": reason,
        "confidence": confidence,
    })


def require_string(value, label):
    if not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value:
        raise ValueError(f"{label} must be a non-empty single-line string")
    return value.strip()


def require_digest(value, label, git_object=False):
    value = require_string(value, label).lower()
    pattern = r"[0-9a-f]{40,64}" if git_object else r"sha256:[0-9a-f]{64}"
    if not re.fullmatch(pattern, value):
        raise ValueError(f"{label} must be a bounded digest")
    return value


def require_argv(value, label):
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty argv list")
    return [require_string(item, f"{label} item") for item in value]


def receipt_identity(run_facts, argv):
    inputs = run_facts.get("verificationIdentity")
    if not isinstance(inputs, dict):
        raise ValueError("Epic Run facts require verificationIdentity")
    return {
        "commit": require_digest(inputs.get("commit"), "verificationIdentity.commit", git_object=True),
        "tree": require_digest(inputs.get("tree"), "verificationIdentity.tree", git_object=True),
        "argv": require_argv(argv, "planned check argv"),
        "toolchain": require_digest(inputs.get("toolchain"), "verificationIdentity.toolchain"),
        "fixtures": require_digest(inputs.get("fixtures"), "verificationIdentity.fixtures"),
        "environment": require_digest(inputs.get("environment"), "verificationIdentity.environment"),
    }


def valid_passing_receipts(run_facts):
    receipts = run_facts.get("verificationReceipts", [])
    if not isinstance(receipts, list):
        raise ValueError("verificationReceipts must be a list")
    valid = []
    for index, receipt in enumerate(receipts):
        if not isinstance(receipt, dict) or receipt.get("result") != "pass":
            continue
        identity = receipt.get("identity")
        if not isinstance(identity, dict) or set(identity) != set(RECEIPT_IDENTITY_FIELDS):
            continue
        try:
            normalized = {
                "commit": require_digest(identity["commit"], f"verificationReceipts[{index}].identity.commit", git_object=True),
                "tree": require_digest(identity["tree"], f"verificationReceipts[{index}].identity.tree", git_object=True),
                "argv": require_argv(identity["argv"], f"verificationReceipts[{index}].identity.argv"),
                "toolchain": require_digest(identity["toolchain"], f"verificationReceipts[{index}].identity.toolchain"),
                "fixtures": require_digest(identity["fixtures"], f"verificationReceipts[{index}].identity.fixtures"),
                "environment": require_digest(identity["environment"], f"verificationReceipts[{index}].identity.environment"),
            }
            receipt_id = require_string(receipt.get("id", f"receipt-{index + 1}"), "receipt id")
        except ValueError:
            continue
        valid.append((receipt_id, normalized))
    return valid


def build_epic_run_test_plan(run_facts, tier, ticket_id=None, invariant_id=None):
    if not isinstance(run_facts, dict) or run_facts.get("schemaVersion") != EPIC_RUN_FACTS_SCHEMA:
        raise ValueError(f"Epic Run facts schemaVersion must be {EPIC_RUN_FACTS_SCHEMA}")
    epic_id = require_string(run_facts.get("epicId"), "epicId")
    if tier not in {"ticket", "shared", "final-epic"}:
        raise ValueError("Epic Run tier must be ticket, shared, or final-epic")
    if tier == "ticket" and not ticket_id:
        raise ValueError("ticket tier requires --ticket")
    checks = run_facts.get("plannedChecks")
    if not isinstance(checks, list):
        raise ValueError("Epic Run facts plannedChecks must be a list")
    receipts = valid_passing_receipts(run_facts)
    commands = []
    reused = []
    for index, check in enumerate(checks):
        if not isinstance(check, dict) or check.get("tier") != tier:
            continue
        ticket_ids = check.get("ticketIds", [])
        if tier == "ticket" and ticket_id not in ticket_ids:
            continue
        if tier == "shared" and invariant_id and check.get("invariantId") != invariant_id:
            continue
        argv = require_argv(check.get("argv"), f"plannedChecks[{index}].argv")
        command = shlex.join(argv)
        identity = receipt_identity(run_facts, argv)
        receipt_ref = next((receipt_id for receipt_id, candidate in receipts if candidate == identity), None)
        if receipt_ref:
            reused.append({
                "checkId": require_string(check.get("id", f"check-{index + 1}"), "check id"),
                "command": command,
                "receiptId": receipt_ref,
                "identitySha256": hashlib.sha256(
                    json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest(),
            })
            continue
        commands.append({
            "tier": tier,
            "command": command,
            "reason": require_string(check.get("reason", "Required by the locked Epic verification plan."), "check reason"),
            "confidence": require_string(check.get("confidence", "high"), "check confidence"),
        })
    cannot_verify = []
    if not commands and not reused:
        cannot_verify.append(f"No {tier} checks were present in the locked Epic Run facts.")
    return {
        "mode": "epic-run",
        "epicId": epic_id,
        "verificationTier": tier,
        "ticketId": ticket_id,
        "invariantId": invariant_id,
        "commands": commands,
        "reusedReceipts": reused,
        "cannotVerify": cannot_verify,
    }


def build_test_plan(project_root, intel):
    root = Path(project_root).resolve()
    commands = []
    cannot_verify = list(intel.get("cannotVerify", []))
    triggers = set(intel.get("riskTriggers", []))
    changed_paths = [item.get("path", "") for item in intel.get("changedFiles", [])]

    if triggers == {"docs-only"}:
        cannot_verify.append("No runtime-code test inferred from a documentation-only diff; review rendered docs or generated docs output if applicable.")
        return commands, cannot_verify

    if not intel.get("changedFiles"):
        cannot_verify.append("No changed files detected; cannot recommend focused tests.")
        return commands, cannot_verify

    if "instruction-surface" in triggers:
        skill_paths = [
            path for path in changed_paths if path.startswith("skills/") and path.endswith("/SKILL.md")
        ]
        skill_change_check = root / "scripts" / "run-skill-change-checks.sh"
        workflow_check = root / "scripts" / "check-gauntlet-workflow.py"
        if skill_paths and skill_change_check.exists():
            add_command(
                commands,
                "focused",
                "scripts/run-skill-change-checks.sh --changed-files " + " ".join(skill_paths),
                "Changed skill instructions need structural coverage, scorer-contract, and lint checks.",
                "high",
            )
        if workflow_check.exists():
            add_command(
                commands,
                "broader",
                "python3 scripts/check-gauntlet-workflow.py",
                "Behavior-bearing instruction surfaces need the repository workflow regression suite.",
                "high",
            )
        if not skill_change_check.exists() and not workflow_check.exists():
            cannot_verify.append(
                "Behavior-bearing instructions changed, but no repository instruction or workflow harness was found. Review the rendered prompt and run a representative forward test."
            )

    package_roots = intel.get("packageRoots") or ["."]
    for changed in intel.get("changedFiles", []):
        for candidate in changed.get("testCandidates", []):
            if candidate.endswith(".py"):
                add_command(
                    commands,
                    "focused",
                    f"python -m pytest {candidate}",
                    f"Python test candidate for {changed['path']}",
                    "medium",
                )

    for package_root in package_roots:
        package = package_json(root, package_root)
        scripts = package.get("scripts", {}) if isinstance(package.get("scripts"), dict) else {}
        if not scripts:
            continue

        for changed in intel.get("changedFiles", []):
            if changed.get("packageRoot") != package_root:
                continue
            for candidate in changed.get("testCandidates", []):
                add_command(
                    commands,
                    "focused",
                    command_for_package(package_root, f"npm test -- {candidate}"),
                    f"Sibling test for {changed['path']}",
                    "high",
                )

        if "lint" in scripts:
            add_command(
                commands,
                "focused",
                command_for_package(package_root, "npm run lint"),
                "Changed code should satisfy the package lint contract.",
                "medium",
            )
        if "typecheck" in scripts:
            add_command(
                commands,
                "focused",
                command_for_package(package_root, "npm run typecheck"),
                "TypeScript changes should satisfy the package typecheck contract.",
                "medium",
            )
        if "test" in scripts and triggers & DURABLE_TRIGGERS:
            add_command(
                commands,
                "broader",
                command_for_package(package_root, "npm test"),
                "Durable or security-sensitive triggers warrant the package test suite.",
                "medium",
            )

    if not commands:
        cannot_verify.append(
            "No focused test mapping found; inspect package scripts, local test naming, or project docs before trusting this plan."
        )

    if "generated" in triggers:
        cannot_verify.append("Generated files changed; verify regeneration with the project-local generator.")

    return commands, cannot_verify


def main():
    parser = argparse.ArgumentParser(description="Recommend bounded checks for the current Gauntlet diff intel.")
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--diff-intel", type=Path, default=None)
    parser.add_argument(
        "--run-facts", type=Path, default=None,
        help="JSON emitted by the Epic Run controller's run-facts --run projection",
    )
    parser.add_argument("--tier", choices=("ticket", "shared", "final-epic"), default=None)
    parser.add_argument("--ticket", default=None)
    parser.add_argument("--invariant", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    reused_receipts = []
    mode = "standalone"
    epic_id = None
    verification_tier = None
    if args.run_facts:
        if not args.tier:
            parser.error("--run-facts requires --tier")
        try:
            run_plan = build_epic_run_test_plan(
                read_json(args.run_facts), args.tier, ticket_id=args.ticket, invariant_id=args.invariant
            )
        except ValueError as exc:
            parser.error(str(exc))
        commands = run_plan["commands"]
        cannot_verify = run_plan["cannotVerify"]
        reused_receipts = run_plan["reusedReceipts"]
        mode = run_plan["mode"]
        epic_id = run_plan["epicId"]
        verification_tier = run_plan["verificationTier"]
        source_intel = str(args.run_facts)
        intel = {"confidence": "high"}
    elif args.diff_intel:
        intel = read_json(args.diff_intel)
        source_intel = str(args.diff_intel)
    else:
        intel = build_diff_intel(project_root)
        source_path = project_root / ".gauntlet" / "diff-intel.json"
        write_json(source_path, intel)
        source_intel = str(source_path)
    if not args.run_facts:
        commands, cannot_verify = build_test_plan(project_root, intel)
    payload = {
        "schemaVersion": "1.0",
        "generatedAt": now_iso(),
        "projectRoot": str(project_root),
        "sourceIntel": source_intel,
        "confidence": intel.get("confidence", "low"),
        "mode": mode,
        "epicId": epic_id,
        "verificationTier": verification_tier,
        "commands": commands,
        "reusedReceipts": reused_receipts,
        "cannotVerify": cannot_verify,
    }
    output = args.output or project_root / ".gauntlet" / "test-plan.json"
    write_json(output, payload)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
