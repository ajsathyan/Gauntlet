#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import tempfile
from pathlib import Path


PLUGIN_HEADER = '[plugins."superpowers@openai-curated"]'


def disable_plugin(text):
    lines = text.splitlines(keepends=True)
    inside = False
    found_section = False
    found_enabled = False
    changed = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            inside = stripped == PLUGIN_HEADER
            found_section = found_section or inside
            continue
        if inside and re.match(r"^\s*enabled\s*=", line):
            found_enabled = True
            newline = "\n" if line.endswith("\n") else ""
            lines[index] = "enabled = false" + newline
            changed = "true" in line.lower()
            inside = False
    return "".join(lines), found_section, found_enabled, changed


def atomic_write(path, text):
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temp = Path(handle.name)
    os.chmod(temp, mode)
    os.replace(temp, path)


def main():
    parser = argparse.ArgumentParser(description="Retire allowlisted Superpowers skills from an active Codex install.")
    parser.add_argument("--active-skills", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "docs" / "upstream-superpowers.json",
    )
    parser.add_argument("--apply", action="store_true", help="Apply the move and plugin disable; default is dry-run")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    active = args.active_skills.expanduser().resolve()
    archive = args.archive.expanduser().resolve()
    config = args.config.expanduser().resolve()
    manifest_path = args.manifest.resolve()
    findings = []

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    allowlist = manifest.get("retiredSkills", [])
    if not allowlist or not all(isinstance(item, str) and item for item in allowlist):
        findings.append({"code": "invalid_retirement_allowlist", "severity": "fail"})

    if active == archive or active in archive.parents:
        findings.append({"code": "unsafe_archive_path", "severity": "fail"})

    existing = [name for name in allowlist if (active / name).is_dir()]
    conflicts = [name for name in existing if (archive / name).exists()]
    if conflicts:
        findings.append({"code": "archive_conflict", "severity": "fail", "skills": conflicts})

    config_text = config.read_text(encoding="utf-8") if config.is_file() else ""
    disabled_text, plugin_section_found, plugin_enabled_key_found, config_changed = disable_plugin(config_text)
    if not plugin_section_found:
        findings.append({"code": "plugin_section_missing", "severity": "review"})
    elif not plugin_enabled_key_found:
        findings.append({"code": "plugin_enabled_key_missing", "severity": "review"})

    if args.apply and (not plugin_section_found or not plugin_enabled_key_found):
        findings.append({
            "code": "plugin_disablement_unverified",
            "severity": "fail",
            "message": "No skills were moved because the Superpowers plugin could not be deterministically disabled.",
        })

    if args.apply and not any(item["severity"] == "fail" for item in findings):
        moved = []
        try:
            archive.mkdir(parents=True, exist_ok=True)
            for name in existing:
                shutil.move(str(active / name), str(archive / name))
                moved.append(name)
            if plugin_section_found:
                atomic_write(config, disabled_text)
        except OSError as error:
            rollback_failures = []
            for name in reversed(moved):
                try:
                    shutil.move(str(archive / name), str(active / name))
                except OSError as rollback_error:
                    rollback_failures.append({"skill": name, "error": str(rollback_error)})
            findings.append({"code": "retirement_apply_failed", "severity": "fail", "error": str(error)})
            if rollback_failures:
                findings.append({"code": "retirement_rollback_failed", "severity": "fail", "skills": rollback_failures})

    status = "fail" if any(item["severity"] == "fail" for item in findings) else "pass"
    payload = {
        "schemaVersion": "1.0",
        "status": status,
        "applied": bool(args.apply and status == "pass"),
        "activeSkills": str(active),
        "archive": str(archive),
        "retiredSkills": existing,
        "preservedSkillCount": len([path for path in active.iterdir() if path.is_dir() and path.name not in allowlist]) if active.is_dir() else 0,
        "pluginSectionFound": plugin_section_found,
        "pluginEnabledKeyFound": plugin_enabled_key_found,
        "pluginConfigChanged": config_changed,
        "findings": findings,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        action = "retired" if payload["applied"] else "would retire"
        print(f"Superpowers retirement: {status}; {action} {len(existing)} skill(s).")
        print(f"Archive: {archive}")
    raise SystemExit(1 if status == "fail" else 0)


if __name__ == "__main__":
    main()
