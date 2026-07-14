#!/usr/bin/env python3
"""Deterministically map Gauntlet Ticket routing fields to a Codex profile."""

import argparse
import json
import sys

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
        return "gauntlet-security-reviewer"
    if work == "release" or fields["proof"] == "release":
        return "gauntlet-release-integrator"
    if work == "verification" or fields["proof"] == "behavioral":
        return "gauntlet-independent-verifier"
    if work == "research":
        if fields["complexity"] == "deep" or fields["risk"] == "consequential":
            return "gauntlet-deep-expert-researcher"
        return None
    if work == "scan" and fields["authority"] == "read-only" and (
        fields["proof"] == "source" or fields["context_shape"] == "high-volume"
    ):
        return "gauntlet-fast-reader"
    if work == "implementation" and fields["complexity"] == "deep":
        return "gauntlet-deep-worker"
    if work == "implementation" and fields["authority"] == "local-write" and fields["complexity"] in {"routine", "standard"}:
        return "gauntlet-standard-worker"
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key, allowed in VALUES.items():
        parser.add_argument("--" + key.replace("_", "-"), choices=sorted(allowed), required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    fields = {key: getattr(args, key) for key in VALUES}
    try:
        profile = select(fields)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    payload = {"schemaVersion": "1.0", "routing": fields, "profile": profile, "status": "delegate" if profile else "stay-parent"}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif profile:
        print(profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
