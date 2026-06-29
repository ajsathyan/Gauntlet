#!/usr/bin/env python3
import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


LOG_NAME = "subagent-plan-log.jsonl"
SUMMARY_NAME = "subagent-plan-summary.json"
VALID_STATE_ACCESS = {"none", "read-only", "mutates"}
REQUIRED_LANE_FIELDS = [
    "id",
    "skill",
    "scope",
    "filesRead",
    "filesWrite",
    "stateScope",
    "stateAccess",
    "proof",
    "inlineContext",
]


def word_count(text):
    return len(re.findall(r"\b\S+\b", text or ""))


def normalize_text(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def shingle_words(text, size=10):
    words = re.findall(r"\b\S+\b", normalize_text(text))
    if len(words) < size:
        return set()
    return {" ".join(words[index : index + size]) for index in range(len(words) - size + 1)}


def static_prefix(pattern):
    pattern = str(pattern).strip()
    wildcard_positions = [position for position in [pattern.find("*"), pattern.find("?"), pattern.find("[")] if position != -1]
    if wildcard_positions:
        cutoff = min(wildcard_positions)
        slash = pattern.rfind("/", 0, cutoff)
        return pattern[: slash + 1] if slash != -1 else ""
    if pattern.endswith("/"):
        return pattern
    return pattern + ("/" if "." not in Path(pattern).name else "")


def path_overlap(left, right):
    left = str(left).strip()
    right = str(right).strip()
    if not left or not right:
        return False
    if left == right:
        return True
    left_prefix = static_prefix(left)
    right_prefix = static_prefix(right)
    if not left_prefix or not right_prefix:
        return False
    return left.startswith(right_prefix) or right.startswith(left_prefix) or left_prefix.startswith(right_prefix) or right_prefix.startswith(left_prefix)


def add_rejection(rejections, code, message, lane_id=None):
    rejections.append({"code": code, "laneId": lane_id, "message": message})


def require_list(value):
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def validate_plan(data, max_inline_words, max_total_inline_words):
    rejections = []
    lanes = data.get("lanes")
    if not isinstance(lanes, list):
        add_rejection(rejections, "missing_lanes", "plan must include a lanes array")
        return rejections
    if len(lanes) < 2:
        add_rejection(rejections, "not_enough_lanes", "parallel subagent plans need at least two lanes")

    seen_ids = set()
    contexts = {}
    total_inline_words = 0

    for index, lane in enumerate(lanes):
        lane_id = lane.get("id") if isinstance(lane, dict) else f"lane-{index + 1}"
        if not isinstance(lane, dict):
            add_rejection(rejections, "invalid_lane", "lane must be an object", lane_id)
            continue

        for field in REQUIRED_LANE_FIELDS:
            if field not in lane:
                add_rejection(rejections, "missing_field", f"lane missing required field: {field}", lane_id)

        if not isinstance(lane.get("id"), str) or not lane.get("id").strip():
            add_rejection(rejections, "invalid_id", "lane id must be a non-empty string", lane_id)
        elif lane["id"] in seen_ids:
            add_rejection(rejections, "duplicate_id", f"duplicate lane id: {lane['id']}", lane_id)
        else:
            seen_ids.add(lane["id"])

        for field in ["skill", "scope", "stateScope", "stateAccess", "inlineContext"]:
            if field in lane and not isinstance(lane[field], str):
                add_rejection(rejections, "invalid_field_type", f"{field} must be a string", lane_id)

        if lane.get("stateAccess") not in VALID_STATE_ACCESS:
            add_rejection(
                rejections,
                "invalid_state_access",
                f"stateAccess must be one of: {', '.join(sorted(VALID_STATE_ACCESS))}",
                lane_id,
            )

        for field in ["filesRead", "filesWrite", "proof"]:
            if field in lane and not require_list(lane[field]):
                add_rejection(rejections, "invalid_field_type", f"{field} must be a list of strings", lane_id)
        if isinstance(lane.get("proof"), list) and not lane["proof"]:
            add_rejection(rejections, "missing_proof", "lane proof must not be empty", lane_id)

        inline_words = word_count(lane.get("inlineContext", ""))
        total_inline_words += inline_words
        contexts[lane_id] = lane.get("inlineContext", "")
        if inline_words > max_inline_words:
            add_rejection(
                rejections,
                "inline_context_too_large",
                f"inlineContext has {inline_words} words; max is {max_inline_words}",
                lane_id,
            )

    if total_inline_words > max_total_inline_words:
        add_rejection(
            rejections,
            "total_inline_context_too_large",
            f"total inlineContext has {total_inline_words} words; max is {max_total_inline_words}",
        )

    for left_index, left in enumerate(lanes if isinstance(lanes, list) else []):
        if not isinstance(left, dict):
            continue
        for right in lanes[left_index + 1 :]:
            if not isinstance(right, dict):
                continue
            left_id = left.get("id", f"lane-{left_index + 1}")
            right_id = right.get("id", "lane")

            for left_path in left.get("filesWrite", []) if isinstance(left.get("filesWrite"), list) else []:
                for right_path in right.get("filesWrite", []) if isinstance(right.get("filesWrite"), list) else []:
                    if path_overlap(left_path, right_path):
                        add_rejection(
                            rejections,
                            "overlapping_writes",
                            f"{left_id} and {right_id} both write overlapping paths: {left_path} / {right_path}",
                        )

            if (
                left.get("stateScope")
                and left.get("stateScope") == right.get("stateScope")
                and "mutates" in {left.get("stateAccess"), right.get("stateAccess")}
            ):
                add_rejection(
                    rejections,
                    "shared_mutable_state",
                    f"{left_id} and {right_id} share mutable stateScope: {left.get('stateScope')}",
                )

            left_proof = {normalize_text(item) for item in left.get("proof", []) if isinstance(item, str)}
            right_proof = {normalize_text(item) for item in right.get("proof", []) if isinstance(item, str)}
            duplicates = sorted(item for item in left_proof & right_proof if item)
            if duplicates:
                add_rejection(
                    rejections,
                    "duplicate_proof_target",
                    f"{left_id} and {right_id} share proof target: {duplicates[0]}",
                )

    shingle_to_lanes = defaultdict(set)
    for lane_id, context in contexts.items():
        for shingle in shingle_words(context):
            shingle_to_lanes[shingle].add(lane_id)
    duplicate_shingles = [lanes for lanes in shingle_to_lanes.values() if len(lanes) > 1]
    if duplicate_shingles:
        add_rejection(
            rejections,
            "duplicated_inline_context",
            f"inlineContext repeats long text across lanes ({len(duplicate_shingles)} repeated blocks)",
        )

    return rejections


def read_log(log_path):
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def summarize(records, run_id=None):
    filtered = [record for record in records if not run_id or record.get("runId") == run_id]
    rejected = [record for record in filtered if record.get("status") == "rejected"]
    codes = Counter()
    for record in rejected:
        for rejection in record.get("rejections", []):
            codes[rejection.get("code", "unknown")] += 1
    return {
        "schemaVersion": "1.0",
        "runId": run_id or "all",
        "checkedPlans": len(filtered),
        "acceptedPlans": sum(1 for record in filtered if record.get("status") == "accepted"),
        "rejectedPlans": len(rejected),
        "rejectionCount": sum(int(record.get("rejectionCount", 0)) for record in rejected),
        "rejectionsByCode": dict(sorted(codes.items())),
    }


def write_summary(project_root, records, run_id):
    summary = summarize(records, run_id)
    summary_path = project_root / ".gauntlet" / SUMMARY_NAME
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary_path, summary


def print_summary(summary):
    print(
        f"Subagent plans: {summary['checkedPlans']} checked, "
        f"{summary['rejectedPlans']} rejected, {summary['rejectionCount']} rejection(s)."
    )


def main():
    parser = argparse.ArgumentParser(description="Validate and log Gauntlet subagent plan manifests.")
    parser.add_argument("project_root", type=Path)
    parser.add_argument("plan", type=Path, nargs="?")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--stats", action="store_true", help="Print rejection totals from the log instead of validating a plan.")
    parser.add_argument("--max-inline-words", type=int, default=180)
    parser.add_argument("--max-total-inline-words", type=int, default=600)
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    gauntlet_dir = project_root / ".gauntlet"
    log_path = gauntlet_dir / LOG_NAME

    if args.stats:
        records = read_log(log_path)
        summary_path, summary = write_summary(project_root, records, args.run_id)
        print_summary(summary)
        print(f"Summary: {summary_path.relative_to(project_root)}")
        return

    if not args.plan:
        raise SystemExit("plan path is required unless --stats is used")

    data = json.loads(args.plan.read_text(encoding="utf-8"))
    rejections = validate_plan(data, args.max_inline_words, args.max_total_inline_words)
    status = "rejected" if rejections else "accepted"
    record = {
        "schemaVersion": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "runId": args.run_id or "manual",
        "projectRoot": str(project_root),
        "planPath": str(args.plan),
        "status": status,
        "laneCount": len(data.get("lanes", [])) if isinstance(data.get("lanes"), list) else 0,
        "rejectionCount": len(rejections),
        "rejections": rejections,
    }

    gauntlet_dir.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    records = read_log(log_path)
    summary_path, summary = write_summary(project_root, records, record["runId"])

    if rejections:
        print(f"Subagent plan rejected: {len(rejections)} rejection(s); logged to {log_path.relative_to(project_root)}")
        print(f"Summary: {summary_path.relative_to(project_root)}")
        raise SystemExit(1)

    print(f"Subagent plan accepted: {record['laneCount']} lane(s); logged to {log_path.relative_to(project_root)}")
    print_summary(summary)
    print(f"Summary: {summary_path.relative_to(project_root)}")


if __name__ == "__main__":
    main()
