#!/usr/bin/env python3
"""Unit-test declared orchestration trace fields against deterministic contracts.

Trace fields and proof references are fixture inputs. This runner does not
observe tool calls, resolve proof references, or establish agent behavior.
"""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK = ROOT / "evals" / "orchestration-trace-fixtures.json"
DEFAULT_RESULTS = ROOT / "evals" / "results" / "orchestration-latest.json"
ARMS = ("current", "candidate")
VERDICTS = {"pass", "fail", "cannot_verify"}
SCALAR_TYPES = (str, int, float, bool, type(None))


class TracePackError(ValueError):
    pass


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TracePackError(f"cannot read trace pack {path}: {exc}") from exc


def require_type(value, expected, path):
    if not isinstance(value, expected):
        expected_name = getattr(expected, "__name__", str(expected))
        raise TracePackError(f"{path} must be {expected_name}")


def require_keys(value, required, allowed, path):
    missing = sorted(set(required) - set(value))
    unknown = sorted(set(value) - set(allowed))
    if missing:
        raise TracePackError(f"{path} missing required fields: {', '.join(missing)}")
    if unknown:
        raise TracePackError(f"{path} has unknown fields: {', '.join(unknown)}")


def require_nonempty_string(value, path):
    if not isinstance(value, str) or not value.strip():
        raise TracePackError(f"{path} must be a non-empty string")


def require_nonnegative_number(value, path):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise TracePackError(f"{path} must be a non-negative number")


def validate_matchers(items, path):
    require_type(items, list, path)
    for index, matcher in enumerate(items):
        item_path = f"{path}[{index}]"
        require_type(matcher, dict, item_path)
        if not matcher:
            raise TracePackError(f"{item_path} must contain at least one field")
        for key, value in matcher.items():
            require_nonempty_string(key, f"{item_path} key")
            if not isinstance(value, SCALAR_TYPES):
                raise TracePackError(f"{item_path}.{key} must be scalar")


def validate_trace(trace, path):
    require_type(trace, dict, path)
    required = {"outcome", "actions", "proof", "userVisibleMessages"}
    allowed = required | {"routingChoice", "metrics"}
    require_keys(trace, required, allowed, path)
    require_nonempty_string(trace["outcome"], f"{path}.outcome")

    require_type(trace["actions"], list, f"{path}.actions")
    for index, action in enumerate(trace["actions"]):
        action_path = f"{path}.actions[{index}]"
        require_type(action, dict, action_path)
        if "type" not in action or "authority" not in action:
            raise TracePackError(f"{action_path} requires type and authority")
        require_nonempty_string(action["type"], f"{action_path}.type")
        require_nonempty_string(action["authority"], f"{action_path}.authority")
        for key, value in action.items():
            if not isinstance(value, SCALAR_TYPES):
                raise TracePackError(f"{action_path}.{key} must be scalar")

    require_type(trace["proof"], list, f"{path}.proof")
    for index, evidence in enumerate(trace["proof"]):
        proof_path = f"{path}.proof[{index}]"
        require_type(evidence, dict, proof_path)
        if not {"type", "ref", "passed"}.issubset(evidence):
            raise TracePackError(f"{proof_path} requires type, ref, and passed")
        require_nonempty_string(evidence["type"], f"{proof_path}.type")
        require_nonempty_string(evidence["ref"], f"{proof_path}.ref")
        if not isinstance(evidence["passed"], bool):
            raise TracePackError(f"{proof_path}.passed must be boolean")
        for key, value in evidence.items():
            if not isinstance(value, SCALAR_TYPES):
                raise TracePackError(f"{proof_path}.{key} must be scalar")

    if "routingChoice" in trace:
        require_nonempty_string(trace["routingChoice"], f"{path}.routingChoice")
    require_type(trace["userVisibleMessages"], list, f"{path}.userVisibleMessages")
    for index, message in enumerate(trace["userVisibleMessages"]):
        require_type(message, str, f"{path}.userVisibleMessages[{index}]")

    metrics = trace.get("metrics", {})
    require_type(metrics, dict, f"{path}.metrics")
    require_keys(metrics, set(), {"costUsd", "latencyMs"}, f"{path}.metrics")
    for key, value in metrics.items():
        require_nonnegative_number(value, f"{path}.metrics.{key}")


def validate_contract(contract, path):
    require_type(contract, dict, path)
    required = {
        "expectedOutcome",
        "requiredActions",
        "forbiddenActions",
        "allowedAuthorities",
        "requiredProof",
        "outputBudget",
    }
    allowed = required | {
        "expectedRoutingChoice",
        "metricLimits",
        "subjectiveCriteria",
    }
    require_keys(contract, required, allowed, path)
    require_nonempty_string(contract["expectedOutcome"], f"{path}.expectedOutcome")
    validate_matchers(contract["requiredActions"], f"{path}.requiredActions")
    validate_matchers(contract["forbiddenActions"], f"{path}.forbiddenActions")
    validate_matchers(contract["requiredProof"], f"{path}.requiredProof")

    authorities = contract["allowedAuthorities"]
    require_type(authorities, list, f"{path}.allowedAuthorities")
    for index, authority in enumerate(authorities):
        require_nonempty_string(authority, f"{path}.allowedAuthorities[{index}]")
    if len(authorities) != len(set(authorities)):
        raise TracePackError(f"{path}.allowedAuthorities must be unique")

    if "expectedRoutingChoice" in contract:
        require_nonempty_string(
            contract["expectedRoutingChoice"], f"{path}.expectedRoutingChoice"
        )

    output_budget = contract["outputBudget"]
    require_type(output_budget, dict, f"{path}.outputBudget")
    require_keys(
        output_budget,
        {"maxMessages", "maxWords"},
        {"maxMessages", "maxWords"},
        f"{path}.outputBudget",
    )
    for key in ("maxMessages", "maxWords"):
        value = output_budget[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise TracePackError(f"{path}.outputBudget.{key} must be a non-negative integer")

    metric_limits = contract.get("metricLimits", {})
    require_type(metric_limits, dict, f"{path}.metricLimits")
    require_keys(
        metric_limits,
        set(),
        {"maxCostUsd", "maxLatencyMs"},
        f"{path}.metricLimits",
    )
    for key, value in metric_limits.items():
        require_nonnegative_number(value, f"{path}.metricLimits.{key}")

    subjective = contract.get("subjectiveCriteria", [])
    require_type(subjective, list, f"{path}.subjectiveCriteria")
    for index, criterion in enumerate(subjective):
        require_nonempty_string(criterion, f"{path}.subjectiveCriteria[{index}]")


def validate_pack(pack):
    require_type(pack, dict, "pack")
    require_keys(
        pack,
        {"schemaVersion", "packId", "baselineProvenance", "pairs"},
        {"schemaVersion", "packId", "description", "baselineProvenance", "pairs"},
        "pack",
    )
    if pack["schemaVersion"] != "1.0":
        raise TracePackError("pack.schemaVersion must be 1.0")
    require_nonempty_string(pack["packId"], "pack.packId")
    if "description" in pack:
        require_type(pack["description"], str, "pack.description")
    provenance = pack["baselineProvenance"]
    require_type(provenance, dict, "pack.baselineProvenance")
    require_keys(
        provenance,
        {"current", "candidate", "contractRef"},
        {"current", "candidate", "contractRef"},
        "pack.baselineProvenance",
    )
    for key, value in provenance.items():
        require_nonempty_string(value, f"pack.baselineProvenance.{key}")
    require_type(pack["pairs"], list, "pack.pairs")
    if not pack["pairs"]:
        raise TracePackError("pack.pairs must not be empty")

    ids = set()
    for index, pair in enumerate(pack["pairs"]):
        path = f"pack.pairs[{index}]"
        require_type(pair, dict, path)
        require_keys(
            pair,
            {"id", "contract", "arms", "expectedVerdicts"},
            {"id", "description", "contract", "arms", "expectedVerdicts"},
            path,
        )
        require_nonempty_string(pair["id"], f"{path}.id")
        if pair["id"] in ids:
            raise TracePackError(f"duplicate pair id: {pair['id']}")
        ids.add(pair["id"])
        if "description" in pair:
            require_type(pair["description"], str, f"{path}.description")
        validate_contract(pair["contract"], f"{path}.contract")

        arms = pair["arms"]
        require_type(arms, dict, f"{path}.arms")
        require_keys(arms, set(ARMS), set(ARMS), f"{path}.arms")
        for arm in ARMS:
            validate_trace(arms[arm], f"{path}.arms.{arm}")

        expected = pair["expectedVerdicts"]
        require_type(expected, dict, f"{path}.expectedVerdicts")
        require_keys(expected, set(ARMS), set(ARMS), f"{path}.expectedVerdicts")
        for arm in ARMS:
            if expected[arm] not in VERDICTS:
                raise TracePackError(
                    f"{path}.expectedVerdicts.{arm} must be pass, fail, or cannot_verify"
                )


def matches(item, matcher):
    return all(item.get(key) == value for key, value in matcher.items())


def word_count(messages):
    return sum(len(re.findall(r"\S+", message)) for message in messages)


def score_trace(contract, trace):
    missing_actions = [
        matcher
        for matcher in contract["requiredActions"]
        if not any(matches(action, matcher) for action in trace["actions"])
    ]
    forbidden_actions = [
        action
        for action in trace["actions"]
        if any(matches(action, matcher) for matcher in contract["forbiddenActions"])
    ]
    authority_violations = [
        action
        for action in trace["actions"]
        if action["authority"] not in contract["allowedAuthorities"]
    ]
    missing_proof = [
        matcher
        for matcher in contract["requiredProof"]
        if not any(
            evidence["passed"] and matches(evidence, matcher)
            for evidence in trace["proof"]
        )
    ]

    expected_route = contract.get("expectedRoutingChoice")
    actual_route = trace.get("routingChoice")
    route_passed = expected_route is None or actual_route == expected_route
    messages = trace["userVisibleMessages"]
    words = word_count(messages)
    budget = contract["outputBudget"]
    output_passed = len(messages) <= budget["maxMessages"] and words <= budget["maxWords"]

    metrics = trace.get("metrics", {})
    metric_limits = contract.get("metricLimits", {})
    metric_checks = {}
    if "costUsd" in metrics:
        limit = metric_limits.get("maxCostUsd")
        metric_checks["costUsd"] = {
            "recorded": metrics["costUsd"],
            "limit": limit,
            "passed": limit is None or metrics["costUsd"] <= limit,
        }
    if "latencyMs" in metrics:
        limit = metric_limits.get("maxLatencyMs")
        metric_checks["latencyMs"] = {
            "recorded": metrics["latencyMs"],
            "limit": limit,
            "passed": limit is None or metrics["latencyMs"] <= limit,
        }
    metrics_passed = all(check["passed"] for check in metric_checks.values())

    dimensions = {
        "taskOutcome": {
            "passed": trace["outcome"] == contract["expectedOutcome"],
            "expected": contract["expectedOutcome"],
            "actual": trace["outcome"],
        },
        "requiredActions": {"passed": not missing_actions, "missing": missing_actions},
        "forbiddenActions": {"passed": not forbidden_actions, "observed": forbidden_actions},
        "authority": {"passed": not authority_violations, "violations": authority_violations},
        "declaredProofFields": {"passed": not missing_proof, "missing": missing_proof},
        "routingChoice": {
            "passed": route_passed,
            "expected": expected_route,
            "actual": actual_route,
            "status": "not_applicable" if expected_route is None else "scored",
        },
        "userVisibleOutput": {
            "passed": output_passed,
            "messageCount": len(messages),
            "wordCount": words,
            "budget": budget,
        },
        "recordedMetrics": {
            "passed": metrics_passed,
            "checks": metric_checks,
            "unrecorded": [
                field for field in ("costUsd", "latencyMs") if field not in metrics
            ],
        },
    }
    deterministic_passed = all(item["passed"] for item in dimensions.values())
    subjective = [
        {
            "criterion": criterion,
            "status": "cannot_verify",
            "reason": "Subjective judgment is uncalibrated for this deterministic runner.",
        }
        for criterion in contract.get("subjectiveCriteria", [])
    ]
    if not deterministic_passed:
        verdict = "fail"
    elif subjective:
        verdict = "cannot_verify"
    else:
        verdict = "pass"
    return {
        "verdict": verdict,
        "deterministicPassed": deterministic_passed,
        "dimensions": dimensions,
        "subjective": subjective,
    }


def run_pack(pack, source_path):
    pair_results = []
    verdict_counts = {verdict: 0 for verdict in sorted(VERDICTS)}
    expectations_matched = True
    for pair in pack["pairs"]:
        arms = {}
        matches_expected = {}
        for arm in ARMS:
            result = score_trace(pair["contract"], pair["arms"][arm])
            expected = pair["expectedVerdicts"][arm]
            matched = result["verdict"] == expected
            result["expectedVerdict"] = expected
            result["expectationMatched"] = matched
            arms[arm] = result
            matches_expected[arm] = matched
            verdict_counts[result["verdict"]] += 1
            expectations_matched = expectations_matched and matched
        pair_results.append(
            {
                "id": pair["id"],
                "description": pair.get("description"),
                "arms": arms,
                "expectationsMatched": matches_expected,
            }
        )
    return {
        "schemaVersion": "1.0",
        "evidenceScope": "declared_trace_fields_only",
        "cannotVerify": [
            "Actions, outcomes, authorities, proof references, cost, and latency are fixture declarations; this scorer does not independently observe or resolve them.",
            "Agent behavior requires trusted harness events or an independently rerun behavioral oracle.",
        ],
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourcePack": str(source_path),
        "packId": pack["packId"],
        "baselineProvenance": pack["baselineProvenance"],
        "summary": {
            "pairs": len(pair_results),
            "arms": len(pair_results) * len(ARMS),
            "verdicts": verdict_counts,
            "expectationsMatched": expectations_matched,
        },
        "pairs": pair_results,
    }


def print_summary(results):
    print(f"declared trace-field scorer contracts: {results['packId']}")
    for pair in results["pairs"]:
        arms = []
        for arm in ARMS:
            result = pair["arms"][arm]
            mark = "PASS" if result["expectationMatched"] else "MISMATCH"
            arms.append(f"{arm}={result['verdict']} expected={result['expectedVerdict']} {mark}")
        print(f"{pair['id']} | " + " | ".join(arms))
    print(
        "expectations="
        + ("PASS" if results["summary"]["expectationsMatched"] else "FAIL")
    )


def main():
    parser = argparse.ArgumentParser(
        description="Unit-test declared Gauntlet orchestration trace fields against scorer contracts."
    )
    parser.add_argument("--pack", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    args = parser.parse_args()

    try:
        pack = read_json(args.pack)
        validate_pack(pack)
    except TracePackError as exc:
        raise SystemExit(f"trace pack invalid: {exc}") from exc

    results = run_pack(pack, args.pack)
    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print_summary(results)
    print(f"wrote {args.results}")
    if not results["summary"]["expectationsMatched"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
