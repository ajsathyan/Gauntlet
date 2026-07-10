#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path


EXIT_CODES = {"pass": 0, "review": 2, "fail": 1}


def sha256(path):
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Compare reviewed Superpowers sources with Gauntlet's attribution map.")
    parser.add_argument("--source", type=Path, required=True, help="Superpowers repository or plugin root")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "docs" / "upstream-superpowers.json",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    source = args.source.resolve()
    manifest_path = args.manifest.resolve()
    findings = []
    changed = []

    if not manifest_path.is_file():
        findings.append({"code": "missing_manifest", "severity": "fail", "path": str(manifest_path)})
        manifest = {}
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    plugin_json = source / ".codex-plugin" / "plugin.json"
    observed_version = None
    if plugin_json.is_file():
        observed_version = json.loads(plugin_json.read_text(encoding="utf-8")).get("version")
    reviewed_version = manifest.get("upstream", {}).get("reviewedVersion")
    if observed_version and reviewed_version and observed_version != reviewed_version:
        findings.append({
            "code": "upstream_version_changed",
            "severity": "review",
            "reviewed": reviewed_version,
            "observed": observed_version,
        })

    for technique in manifest.get("techniques", []):
        relative = technique.get("sourcePath")
        source_skill = technique.get("sourceSkill")
        expected = technique.get("reviewedSha256")
        path = source / str(relative)
        if not path.is_file():
            findings.append({"code": "missing_upstream_source", "severity": "fail", "skill": source_skill, "path": str(relative)})
            continue
        observed = sha256(path)
        if observed != expected:
            item = {
                "skill": source_skill,
                "path": str(relative),
                "reviewedSha256": expected,
                "observedSha256": observed,
                "destinations": technique.get("destinations", []),
                "disposition": technique.get("disposition"),
            }
            changed.append(item)
            findings.append({"code": "upstream_source_changed", "severity": "review", **item})

    if any(item["severity"] == "fail" for item in findings):
        status = "fail"
    elif findings:
        status = "review"
    else:
        status = "pass"

    payload = {
        "schemaVersion": "1.0",
        "status": status,
        "source": str(source),
        "manifest": str(manifest_path),
        "reviewedVersion": reviewed_version,
        "observedVersion": observed_version,
        "changedTechniques": changed,
        "findings": findings,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Superpowers sync check: {status}")
        for finding in findings:
            print(f"- [{finding['severity']}] {finding['code']}: {finding.get('skill', '')}")
    raise SystemExit(EXIT_CODES[status])


if __name__ == "__main__":
    main()
