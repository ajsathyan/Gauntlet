#!/usr/bin/env python3
"""Measure the small Design/Build/Implement/Verify context surfaces."""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STABLE_PATHS = ("router/AGENTS.md",)
PHASE_PATHS = {
    "design": ("skills/design/SKILL.md",),
    "build": ("skills/planner/SKILL.md",),
    "implement": ("skills/implementer/SKILL.md",),
    "verify": ("skills/verify/SKILL.md",),
}


def token_range(byte_count):
    return {
        "low": round(byte_count / 5),
        "high": round(byte_count / 3.5),
    }


def path_measurement(root, relative):
    path = root / relative
    data = path.read_bytes()
    return {
        "path": relative,
        "bytes": len(data),
        "estimatedTokens": token_range(len(data)),
    }


def trace_tokens(path):
    totals = {"input": 0, "cachedInput": 0, "output": 0, "events": 0}
    if not path:
        return totals
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "token_count":
            continue
        usage = event.get("usage") or event.get("info") or event
        for source, target in (
            ("input_tokens", "input"),
            ("cached_input_tokens", "cachedInput"),
            ("output_tokens", "output"),
        ):
            value = usage.get(source, 0) if isinstance(usage, dict) else 0
            if isinstance(value, int) and not isinstance(value, bool):
                totals[target] += value
        totals["events"] += 1
    return totals


def build_report(root, traces):
    stable = [path_measurement(root, relative) for relative in STABLE_PATHS]
    stable_bytes = sum(item["bytes"] for item in stable)
    phases = []
    phase_only_bytes = 0
    for phase, relative_paths in PHASE_PATHS.items():
        surfaces = [
            path_measurement(root, relative)
            for relative in relative_paths
        ]
        surface_bytes = sum(item["bytes"] for item in surfaces)
        phase_only_bytes += surface_bytes
        phases.append(
            {
                "phase": phase,
                "surfaces": surfaces,
                "phaseBytes": surface_bytes,
                "modelVisibleBytes": stable_bytes + surface_bytes,
                "estimatedTokens": token_range(stable_bytes + surface_bytes),
            }
        )
    unique_bytes = stable_bytes + phase_only_bytes
    repeated_bytes = sum(item["modelVisibleBytes"] for item in phases)
    stable_prefix_savings = repeated_bytes - unique_bytes
    return {
        "schemaVersion": "gauntlet.context-audit.v2",
        "stableSurfaces": stable,
        "stableBytes": stable_bytes,
        "phases": phases,
        "uniqueBytes": unique_bytes,
        "repeatedWithoutStablePrefixBytes": repeated_bytes,
        "stablePrefixSavingsBytes": stable_prefix_savings,
        "stablePrefixSavingsEstimatedTokens": token_range(stable_prefix_savings),
        "traceTokens": [
            {"path": str(path), **trace_tokens(path)} for path in traces
        ],
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Measure Design/Build/Implement/Verify context without "
            "changing project state."
        )
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--trace", action="append", type=Path, default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_report(args.root.resolve(), args.trace)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print(
        "Measured Design/Build/Implement/Verify context: "
        f"{report['uniqueBytes']} unique bytes; "
        f"{report['stablePrefixSavingsBytes']} repeat bytes avoidable with a stable prefix."
    )
    for phase in report["phases"]:
        estimate = phase["estimatedTokens"]
        print(
            f"{phase['phase']}: {phase['modelVisibleBytes']} bytes "
            f"(~{estimate['low']}-{estimate['high']} tokens)"
        )


if __name__ == "__main__":
    main()
