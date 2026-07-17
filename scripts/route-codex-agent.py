#!/usr/bin/env python3
"""Deterministically map Gauntlet Ticket routing fields to a Codex profile."""

import argparse
import json
import sys
from pathlib import Path

VALUES = {
    "work_class": {"scan", "implementation", "verification", "research", "release"},
    "complexity": {"routine", "standard", "deep"},
    "risk": {"ordinary", "consequential"},
    "authority": {"read-only", "local-write", "merge", "deploy", "production"},
    "proof": {"source", "behavioral", "integration", "security", "release"},
    "context_shape": {"bounded", "high-volume"},
}


def select(fields):
    for key, allowed in VALUES.items():
        if fields.get(key) not in allowed:
            raise ValueError("{} must be one of: {}".format(key, ", ".join(sorted(allowed))))
    work = fields["work_class"]
    if work == "verification" and fields["proof"] == "security":
        return None
    if work == "release" or fields["proof"] == "release":
        return "gauntlet_release_integrator"
    if work == "verification" or fields["proof"] == "behavioral":
        return "gauntlet_independent_verifier"
    if work == "research":
        if fields["complexity"] == "deep" or fields["risk"] == "consequential":
            return "gauntlet_deep_expert_researcher"
        return None
    if work == "scan" and fields["authority"] == "read-only" and (
        fields["proof"] == "source" or fields["context_shape"] == "high-volume"
    ):
        return "gauntlet_fast_reader"
    if work == "implementation" and fields["complexity"] == "deep":
        return "gauntlet_deep_worker"
    if work == "implementation" and fields["authority"] == "local-write" and fields["complexity"] in {"routine", "standard"}:
        return "gauntlet_standard_worker"
    return None


def circuit_block(circuit_file, codex_version, profile):
    if not circuit_file:
        return None
    if not codex_version:
        raise ValueError("--codex-version is required with --circuit-file")
    if not circuit_file.exists():
        return None
    if circuit_file.is_symlink() or not circuit_file.is_file():
        raise ValueError("routing circuit state is unsafe")
    try:
        state = json.loads(circuit_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError("routing circuit state is unreadable: {}".format(exc))
    if state.get("schemaVersion") != 1 or not isinstance(state.get("versions"), dict):
        raise ValueError("routing circuit state has an unsupported schema")
    for version in (codex_version, "unknown"):
        version_state = state["versions"].get(version, {})
        blocked = version_state.get("blockedProfiles", {}) if isinstance(version_state, dict) else {}
        if isinstance(blocked, dict) and profile in blocked:
            entry = blocked[profile]
            return {
                "version": version,
                "taxonomy": sorted(entry.get("taxonomy", [])) if isinstance(entry, dict) else [],
            }
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key, allowed in VALUES.items():
        parser.add_argument("--" + key.replace("_", "-"), choices=sorted(allowed), required=True)
    parser.add_argument("--circuit-file", type=Path)
    parser.add_argument("--codex-version")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    fields = {key: getattr(args, key) for key in VALUES}
    try:
        security_cli = fields["work_class"] == "verification" and fields["proof"] == "security"
        profile = select(fields)
        blocked = circuit_block(args.circuit_file, args.codex_version, profile) if profile else None
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if blocked:
        payload = {
            "schemaVersion": "1.0",
            "routing": fields,
            "profile": profile,
            "status": "circuit-open",
            "circuit": blocked,
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print("dispatch circuit is open for {} on Codex {}".format(profile, blocked["version"]), file=sys.stderr)
        return 3
    payload = {
        "schemaVersion": "1.0",
        "routing": fields,
        "profile": profile,
        "status": "codex-cli" if security_cli else ("delegate" if profile else "stay-parent"),
    }
    if security_cli:
        payload["runner"] = "security-review"
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif security_cli:
        print("security-review")
    elif profile:
        print(profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
