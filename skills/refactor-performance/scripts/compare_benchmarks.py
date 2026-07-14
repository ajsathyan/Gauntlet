#!/usr/bin/env python3
"""Compare repeated benchmark samples using the median.

The median is robust to isolated noisy runs. Inputs need at least five measured
samples after at least one warm-up. Protocol and metric must match exactly.
Exit codes: 0 comparison succeeds and target is met (if supplied), 1 protocols
are incomparable or target is missed, 2 invalid input.
"""

import argparse
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Any, Dict, List, Optional


SCHEMA_VERSION = 1
PROTOCOL_FIELDS = ("command", "machine", "dependencyState", "cachePolicy", "concurrency", "warmups")
DIRECTIONS = {"lower-is-better", "higher-is-better"}


class BenchmarkError(Exception):
    def __init__(self, message: str, details: Optional[List[str]] = None) -> None:
        super().__init__(message)
        self.details = details or []


def emit(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))


def load(path: Path, label: str) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchmarkError(f"Could not read {label}: {exc}") from exc
    errors: List[str] = []
    if not isinstance(payload, dict) or payload.get("schemaVersion") != SCHEMA_VERSION:
        errors.append(f"{label}.schemaVersion must equal {SCHEMA_VERSION}")
        payload = payload if isinstance(payload, dict) else {}
    metric = payload.get("metric")
    if not isinstance(metric, dict):
        errors.append(f"{label}.metric must be an object")
    else:
        for field in ("name", "unit"):
            if not isinstance(metric.get(field), str) or not metric[field].strip():
                errors.append(f"{label}.metric.{field} must be a non-empty string")
        if metric.get("direction") not in DIRECTIONS:
            errors.append(f"{label}.metric.direction must be lower-is-better or higher-is-better")
    protocol = payload.get("protocol")
    if not isinstance(protocol, dict):
        errors.append(f"{label}.protocol must be an object")
    else:
        missing = [field for field in PROTOCOL_FIELDS if field not in protocol]
        if missing:
            errors.append(f"{label}.protocol is missing: {', '.join(missing)}")
        if not isinstance(protocol.get("warmups"), int) or isinstance(protocol.get("warmups"), bool) or protocol.get("warmups", 0) < 1:
            errors.append(f"{label}.protocol.warmups must be at least 1")
        if not isinstance(protocol.get("concurrency"), int) or isinstance(protocol.get("concurrency"), bool) or protocol.get("concurrency", 0) < 1:
            errors.append(f"{label}.protocol.concurrency must be a positive integer")
    samples = payload.get("samples")
    if not isinstance(samples, list) or len(samples) < 5:
        errors.append(f"{label}.samples must contain at least 5 measured samples")
    elif any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) or item <= 0 for item in samples):
        errors.append(f"{label}.samples must contain only finite positive numbers")
    if errors:
        raise BenchmarkError("Benchmark input validation failed", errors)
    return payload


def protocol_differences(baseline: Dict[str, Any], candidate: Dict[str, Any]) -> List[Dict[str, Any]]:
    differences: List[Dict[str, Any]] = []
    for field in sorted(set(baseline) | set(candidate)):
        if baseline.get(field) != candidate.get(field):
            differences.append({"field": field, "baseline": baseline.get(field), "candidate": candidate.get(field)})
    return differences


def rounded(value: float) -> float:
    return round(value, 6)


def compare(baseline: Dict[str, Any], candidate: Dict[str, Any], minimum: Optional[float]) -> Dict[str, Any]:
    metric_matches = baseline["metric"] == candidate["metric"]
    differences = protocol_differences(baseline["protocol"], candidate["protocol"])
    if not metric_matches:
        differences.insert(0, {"field": "metric", "baseline": baseline["metric"], "candidate": candidate["metric"]})
    if differences:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "comparable": False,
            "reason": "Metric or benchmark protocol differs; collect both sample sets under an identical protocol.",
            "protocolDifferences": differences,
        }
    baseline_median = float(statistics.median(baseline["samples"]))
    candidate_median = float(statistics.median(candidate["samples"]))
    direction = baseline["metric"]["direction"]
    if direction == "lower-is-better":
        improvement = (baseline_median - candidate_median) / baseline_median * 100
        factor = baseline_median / candidate_median
    else:
        improvement = (candidate_median - baseline_median) / baseline_median * 100
        factor = candidate_median / baseline_median
    target_met = minimum is None or improvement >= minimum
    return {
        "schemaVersion": SCHEMA_VERSION,
        "comparable": True,
        "statistic": "median",
        "statisticRationale": "Median limits the effect of isolated noisy runs.",
        "samplePolicy": "At least five measured samples after at least one warm-up; warm-ups are excluded from samples.",
        "metric": baseline["metric"],
        "sampleCounts": {"baseline": len(baseline["samples"]), "candidate": len(candidate["samples"])},
        "baselineMedian": rounded(baseline_median),
        "candidateMedian": rounded(candidate_median),
        "improvementPercent": rounded(improvement),
        "improvementFactor": rounded(factor),
        "minimumImprovementPercent": minimum,
        "targetMet": target_met,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Compare repeated benchmark samples with a median and identical-protocol gate.")
    result.add_argument("baseline", help="Baseline benchmark JSON.")
    result.add_argument("candidate", help="Candidate benchmark JSON.")
    result.add_argument("--minimum-improvement", type=float, help="Optional required percentage improvement.")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.minimum_improvement is not None and not math.isfinite(args.minimum_improvement):
        emit({"error": {"code": "invalid-target", "message": "Minimum improvement must be finite."}})
        return 2
    try:
        baseline = load(Path(args.baseline), "baseline")
        candidate = load(Path(args.candidate), "candidate")
    except BenchmarkError as exc:
        emit({"error": {"code": "invalid-benchmark", "message": str(exc), "details": exc.details}})
        return 2
    report = compare(baseline, candidate, args.minimum_improvement)
    emit(report)
    return 0 if report["comparable"] and report.get("targetMet", False) else 1


if __name__ == "__main__":
    sys.exit(main())
