#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURES = ROOT / "evals" / "thin-context-fixtures.json"


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


def build_report(root, fixtures_path, traces):
    fixtures = json.loads(fixtures_path.read_text(encoding="utf-8"))
    surfaces = [path_measurement(root, relative) for relative in fixtures["baselineSurfacePaths"]]
    representative = []
    for epic_id, epic_bytes in fixtures["representativeEpicBytes"].items():
        envelope_bytes = 850
        representative.append({
            "epicId": epic_id,
            "epicBytes": epic_bytes,
            "currentTaskBytes": epic_bytes + envelope_bytes,
            "candidateTaskBytes": envelope_bytes,
            "duplicateEstimatedTokens": token_range(epic_bytes),
        })
    return {
        "schemaVersion": "gauntlet.context-audit.v1",
        "surfaces": surfaces,
        "surfaceBytes": sum(item["bytes"] for item in surfaces),
        "representativeLaunches": representative,
        "traceTokens": [
            {"path": str(path), **trace_tokens(path)} for path in traces
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Measure repeated Gauntlet context without changing project state.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--trace", action="append", type=Path, default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_report(args.root.resolve(), args.fixtures.resolve(), args.trace)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print(f"Measured {len(report['surfaces'])} surfaces: {report['surfaceBytes']} bytes")
    for item in report["representativeLaunches"]:
        estimate = item["duplicateEstimatedTokens"]
        print(f"{item['epicId']}: duplicate Epic {item['epicBytes']} bytes (~{estimate['low']}-{estimate['high']} tokens)")


if __name__ == "__main__":
    main()
