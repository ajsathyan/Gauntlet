#!/usr/bin/env python3
"""Compare repeated benchmark samples using median and range separation.

The median is robust to isolated noisy runs. Inputs need at least five measured
samples under a complete workload, environment, protocol, and oracle identity.
Exit codes: 0 improvement is proved and target is met (if supplied), 1 runs
are incomparable or improvement is unproved, 2 invalid input.
"""

import argparse
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Any, Dict, List, Optional


SCHEMA_VERSION = 1
PROTOCOL_FIELDS = (
    "command", "machine", "dependencyState", "cachePolicy", "concurrency", "warmups",
    "expensiveRunException",
)
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
        for field in ("command", "machine", "dependencyState", "cachePolicy"):
            if not isinstance(protocol.get(field), str) or not protocol.get(field, "").strip():
                errors.append(f"{label}.protocol.{field} must be a non-empty string")
        if not isinstance(protocol.get("warmups"), int) or isinstance(protocol.get("warmups"), bool) or protocol.get("warmups", -1) < 0:
            errors.append(f"{label}.protocol.warmups must be a non-negative integer")
        if not isinstance(protocol.get("concurrency"), int) or isinstance(protocol.get("concurrency"), bool) or protocol.get("concurrency", 0) < 1:
            errors.append(f"{label}.protocol.concurrency must be a positive integer")
        warmups = protocol.get("warmups")
        cache_policy = protocol.get("cachePolicy")
        if isinstance(warmups, int) and not isinstance(warmups, bool):
            if cache_policy == "cold" and warmups != 0:
                errors.append(f"{label}.protocol.warmups must be 0 for a cold cache policy")
            elif cache_policy != "cold" and warmups < 1:
                errors.append(f"{label}.protocol.warmups must be at least 1 unless cachePolicy is cold")
        if not isinstance(protocol.get("expensiveRunException"), bool):
            errors.append(f"{label}.protocol.expensiveRunException must be boolean")
        elif protocol.get("expensiveRunException") and (
            not isinstance(protocol.get("expensiveRunReason"), str)
            or len(protocol.get("expensiveRunReason", "").strip()) < 10
        ):
            errors.append(f"{label}.protocol.expensiveRunReason must contain a concrete non-empty explanation")
    for field in ("workload", "environment", "oracle"):
        value = payload.get(field)
        if not isinstance(value, dict) or not value:
            errors.append(f"{label}.{field} must be a non-empty object")
    workload = payload.get("workload")
    if isinstance(workload, dict):
        for field in ("id", "inputDigest"):
            if not isinstance(workload.get(field), str) or not workload.get(field, "").strip():
                errors.append(f"{label}.workload.{field} must be a non-empty string")
        if "scale" not in workload or workload.get("scale") is None or isinstance(workload.get("scale"), bool):
            errors.append(f"{label}.workload.scale must identify the measured scale")
    environment = payload.get("environment")
    if isinstance(environment, dict):
        for field in ("os", "architecture", "runtime"):
            if not isinstance(environment.get(field), str) or not environment.get(field, "").strip():
                errors.append(f"{label}.environment.{field} must be a non-empty string")
        flags = environment.get("flags")
        if not isinstance(flags, list) or not all(isinstance(item, str) for item in flags):
            errors.append(f"{label}.environment.flags must be a string array")
    oracle = payload.get("oracle")
    if isinstance(oracle, dict):
        if not isinstance(oracle.get("id"), str) or not oracle.get("id", "").strip():
            errors.append(f"{label}.oracle.id must be a non-empty string")
        if oracle.get("result") != "pass":
            errors.append(f"{label}.oracle.result must equal pass")
        evidence = oracle.get("evidence")
        if not isinstance(evidence, list) or not evidence or not all(isinstance(item, str) and item for item in evidence):
            errors.append(f"{label}.oracle.evidence must be a non-empty string array")
    samples = payload.get("samples")
    minimum_samples = 3 if isinstance(protocol, dict) and protocol.get("expensiveRunException") is True else 5
    if not isinstance(samples, list) or len(samples) < minimum_samples:
        errors.append(f"{label}.samples must contain at least {minimum_samples} measured samples")
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
    for field in ("workload", "environment"):
        if baseline[field] != candidate[field]:
            differences.append({"field": field, "baseline": baseline[field], "candidate": candidate[field]})
    if baseline["oracle"]["id"] != candidate["oracle"]["id"]:
        differences.append({"field": "oracle.id", "baseline": baseline["oracle"]["id"], "candidate": candidate["oracle"]["id"]})
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
    baseline_min, baseline_max = min(baseline["samples"]), max(baseline["samples"])
    candidate_min, candidate_max = min(candidate["samples"]), max(candidate["samples"])
    improved = improvement > 0
    improvement_proved = (
        candidate_max < baseline_min if direction == "lower-is-better"
        else candidate_min > baseline_max
    )
    target_met = improved and improvement_proved and (minimum is None or improvement >= minimum)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "comparable": True,
        "statistic": "median",
        "statisticRationale": "Median summarizes the samples; non-overlapping ranges prove direction beyond observed variation.",
        "samplePolicy": "At least five samples, or three with a declared expensive-run exception; cold protocols use zero warm-ups.",
        "metric": baseline["metric"],
        "sampleCounts": {"baseline": len(baseline["samples"]), "candidate": len(candidate["samples"])},
        "baselineMedian": rounded(baseline_median),
        "candidateMedian": rounded(candidate_median),
        "improvementPercent": rounded(improvement),
        "improvementFactor": rounded(factor),
        "improved": improved,
        "improvementProved": improvement_proved,
        "variability": {
            "method": "directional non-overlapping observed ranges",
            "baseline": {"min": rounded(baseline_min), "max": rounded(baseline_max), "range": rounded(baseline_max - baseline_min)},
            "candidate": {"min": rounded(candidate_min), "max": rounded(candidate_max), "range": rounded(candidate_max - candidate_min)},
        },
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
    if args.minimum_improvement is not None and (not math.isfinite(args.minimum_improvement) or args.minimum_improvement < 0):
        emit({"error": {"code": "invalid-target", "message": "Minimum improvement must be finite and non-negative."}})
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
