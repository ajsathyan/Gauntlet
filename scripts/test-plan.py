#!/usr/bin/env python3
import argparse
import json
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


def build_test_plan(project_root, intel):
    root = Path(project_root).resolve()
    commands = []
    cannot_verify = list(intel.get("cannotVerify", []))
    triggers = set(intel.get("riskTriggers", []))
    changed_paths = [item.get("path", "") for item in intel.get("changedFiles", [])]

    if triggers == {"docs-only"}:
        cannot_verify.append("No runtime behavior changed; review rendered docs or generated docs output if applicable.")
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
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    if args.diff_intel:
        intel = read_json(args.diff_intel)
        source_intel = str(args.diff_intel)
    else:
        intel = build_diff_intel(project_root)
        source_path = project_root / ".gauntlet" / "diff-intel.json"
        write_json(source_path, intel)
        source_intel = str(source_path)
    commands, cannot_verify = build_test_plan(project_root, intel)
    payload = {
        "schemaVersion": "1.0",
        "generatedAt": now_iso(),
        "projectRoot": str(project_root),
        "sourceIntel": source_intel,
        "confidence": intel.get("confidence", "low"),
        "commands": commands,
        "cannotVerify": cannot_verify,
    }
    output = args.output or project_root / ".gauntlet" / "test-plan.json"
    write_json(output, payload)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
