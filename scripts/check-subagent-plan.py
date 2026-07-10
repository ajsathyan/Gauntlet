#!/usr/bin/env python3
import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


LOG_NAME = "subagent-plan-log.jsonl"
SUMMARY_NAME = "subagent-plan-summary.json"
VALID_SCHEMA_VERSION = "1.2"
VALID_STATE_ACCESS = {"none", "read-only", "mutates"}
OVERBROAD_PATHS = {"*", "**", "**/*", ".", "./", "/*"}
REQUIRED_SHARED_FIELDS = [
    "projectRoot",
    "acceptedSource",
    "constraints",
    "askUserPolicy",
    "expectedReturn",
]
REQUIRED_LANE_FIELDS = [
    "id",
    "skill",
    "objective",
    "worktreePath",
    "scope",
    "inScope",
    "outOfScope",
    "filesRead",
    "filesWrite",
    "filesAvoid",
    "stateScope",
    "stateAccess",
    "dependencies",
    "consumes",
    "produces",
    "laneConstraints",
    "proof",
    "contextDelta",
]
LEGACY_PACKET_FIELDS = {"taskPacketRef"}
ALLOWED_PLAN_FIELDS = {"schemaVersion", "runId", "shared", "lanes"}
ALLOWED_SHARED_FIELDS = set(REQUIRED_SHARED_FIELDS)
ALLOWED_LANE_FIELDS = set(REQUIRED_LANE_FIELDS)
SECRET_PATTERNS = [
    re.compile(r"(?i)\b[A-Z0-9_]*(SECRET|TOKEN|PASSWORD|API_KEY|PRIVATE_KEY)[A-Z0-9_]*\s*=\s*['\"]?[^\s'\"`]+"),
    re.compile(r"(?i)\b(sk|pk|rk)-(live|test)-[A-Za-z0-9_-]{8,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
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
    wildcard_positions = [
        position
        for position in [pattern.find("*"), pattern.find("?"), pattern.find("[")]
        if position != -1
    ]
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
    return (
        left.startswith(right_prefix)
        or right.startswith(left_prefix)
        or left_prefix.startswith(right_prefix)
        or right_prefix.startswith(left_prefix)
    )


def add_finding(findings, code, message, lane_id=None):
    findings.append({"code": code, "laneId": lane_id, "message": message})


def require_list(value):
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def has_secret(text):
    return any(pattern.search(text or "") for pattern in SECRET_PATTERNS)


def is_overbroad_path(pattern):
    return str(pattern or "").strip() in OVERBROAD_PATHS


def escapes_project(pattern):
    normalized = str(pattern or "").strip()
    if not normalized:
        return False
    path = Path(normalized)
    windows_absolute = re.match(r"^[A-Za-z]:[\\/]", normalized) is not None
    windows_parent = "..\\" in normalized or normalized.endswith("\\..")
    return (
        path.is_absolute()
        or windows_absolute
        or normalized.startswith("~")
        or ".." in path.parts
        or windows_parent
    )


def resolve_project_reference(project_root, reference):
    if not isinstance(reference, str) or not reference.strip():
        return None
    path_part = reference.split("#", 1)[0].strip()
    if not path_part or Path(path_part).is_absolute():
        return None
    candidate = (project_root / path_part).resolve()
    try:
        candidate.relative_to(project_root)
    except ValueError:
        return None
    return candidate


def dependency_names(lane):
    return {normalize_text(item) for item in lane.get("dependencies", []) if isinstance(item, str)}


def dependency_orders(left, right):
    """Recognize a declared ordering hint without treating dependencies as a typed DAG."""
    left_id = normalize_text(left.get("id", ""))
    right_id = normalize_text(right.get("id", ""))
    left_dependencies = dependency_names(left)
    right_dependencies = dependency_names(right)
    return any(
        dependency == right_id or dependency.startswith(f"{right_id} ")
        for dependency in left_dependencies
    ) or any(
        dependency == left_id or dependency.startswith(f"{left_id} ")
        for dependency in right_dependencies
    )


def validate_plan(data, project_root, max_inline_words, max_total_inline_words):
    rejections = []
    warnings = []
    if not isinstance(data, dict):
        add_finding(rejections, "invalid_plan", "plan must be an object")
        return {"rejections": rejections, "warnings": warnings}

    for field in data:
        if field in LEGACY_PACKET_FIELDS:
            add_finding(
                rejections,
                "legacy_packet_field",
                f"{field} is not supported; render the child prompt from the canonical manifest",
            )
        elif field not in ALLOWED_PLAN_FIELDS:
            add_finding(rejections, "unknown_field", f"plan contains unknown field: {field}")

    if data.get("schemaVersion") == "1.1":
        add_finding(
            rejections,
            "legacy_schema_version",
            "schemaVersion 1.1 is legacy; migrate to 1.2 and use the manifest as the sole lane source",
        )
    elif data.get("schemaVersion") != VALID_SCHEMA_VERSION:
        add_finding(
            rejections,
            "unsupported_schema_version",
            f"schemaVersion must be {VALID_SCHEMA_VERSION}",
        )

    run_id = data.get("runId")
    if not isinstance(run_id, str) or not run_id.strip():
        add_finding(rejections, "missing_run_id", "plan must include a non-empty runId")

    shared = data.get("shared")
    if not isinstance(shared, dict):
        add_finding(rejections, "missing_shared", "plan must include a shared object")
        shared = {}
    for field in shared:
        if field in LEGACY_PACKET_FIELDS:
            add_finding(
                rejections,
                "legacy_packet_field",
                f"shared.{field} is not supported; render the child prompt from the canonical manifest",
            )
        elif field not in ALLOWED_SHARED_FIELDS:
            add_finding(rejections, "unknown_field", f"shared contains unknown field: {field}")
    for field in REQUIRED_SHARED_FIELDS:
        if field not in shared:
            add_finding(rejections, "missing_shared_field", f"shared missing required field: {field}")

    for field in ["projectRoot", "acceptedSource", "askUserPolicy", "expectedReturn"]:
        if field in shared and not isinstance(shared[field], str):
            add_finding(rejections, "invalid_shared_field_type", f"shared.{field} must be a string")
        elif field in shared and not shared[field].strip():
            add_finding(rejections, "empty_shared_field", f"shared.{field} must not be empty")
    if "constraints" in shared and not require_list(shared["constraints"]):
        add_finding(rejections, "invalid_shared_field_type", "shared.constraints must be a list of strings")

    if isinstance(shared.get("projectRoot"), str) and shared["projectRoot"].strip():
        declared_root = Path(shared["projectRoot"])
        if not declared_root.is_absolute():
            declared_root = project_root / declared_root
        if declared_root.resolve() != project_root:
            add_finding(
                rejections,
                "project_root_mismatch",
                "shared.projectRoot must resolve to the validated project root",
            )

    if isinstance(shared.get("acceptedSource"), str) and shared["acceptedSource"].strip():
        accepted_source = resolve_project_reference(project_root, shared["acceptedSource"])
        if accepted_source is None:
            add_finding(
                rejections,
                "invalid_accepted_source",
                "shared.acceptedSource must be a relative path inside the project root",
            )
        elif not accepted_source.is_file():
            add_finding(
                rejections,
                "accepted_source_missing",
                f"shared.acceptedSource does not exist: {shared['acceptedSource']}",
            )

    shared_context = "\n".join(
        [
            *(shared.get("constraints", []) if isinstance(shared.get("constraints"), list) else []),
            shared.get("askUserPolicy", "") if isinstance(shared.get("askUserPolicy"), str) else "",
            shared.get("expectedReturn", "") if isinstance(shared.get("expectedReturn"), str) else "",
        ]
    )
    if has_secret(shared_context):
        add_finding(
            rejections,
            "secret_in_shared_context",
            "shared context appears to contain a secret; redact or reference a safe source",
        )

    lanes = data.get("lanes")
    if not isinstance(lanes, list):
        add_finding(rejections, "missing_lanes", "plan must include a lanes array")
        return {"rejections": rejections, "warnings": warnings}
    if not lanes:
        add_finding(rejections, "missing_lanes", "plan must include at least one lane")

    seen_ids = set()
    contexts = {}
    total_context_words = word_count(shared_context)

    for index, lane in enumerate(lanes):
        lane_id = lane.get("id") if isinstance(lane, dict) else f"lane-{index + 1}"
        if not isinstance(lane, dict):
            add_finding(rejections, "invalid_lane", "lane must be an object", lane_id)
            continue

        for field in REQUIRED_LANE_FIELDS:
            if field not in lane:
                add_finding(rejections, "missing_field", f"lane missing required field: {field}", lane_id)
        for field in LEGACY_PACKET_FIELDS:
            if field in lane:
                add_finding(
                    rejections,
                    "legacy_packet_field",
                    f"{field} is not supported; render the child prompt from the canonical manifest",
                    lane_id,
                )
        for field in lane:
            if field not in ALLOWED_LANE_FIELDS and field not in LEGACY_PACKET_FIELDS:
                add_finding(rejections, "unknown_field", f"lane contains unknown field: {field}", lane_id)

        if not isinstance(lane.get("id"), str) or not lane.get("id").strip():
            add_finding(rejections, "invalid_id", "lane id must be a non-empty string", lane_id)
        elif lane["id"] in seen_ids:
            add_finding(rejections, "duplicate_id", f"duplicate lane id: {lane['id']}", lane_id)
        else:
            seen_ids.add(lane["id"])

        for field in ["skill", "objective", "worktreePath", "scope", "stateScope", "stateAccess"]:
            if field in lane and not isinstance(lane[field], str):
                add_finding(rejections, "invalid_field_type", f"{field} must be a string", lane_id)
            elif field in lane and not lane[field].strip():
                add_finding(rejections, "empty_field", f"{field} must not be empty", lane_id)
        if "contextDelta" in lane and not isinstance(lane["contextDelta"], str):
            add_finding(rejections, "invalid_field_type", "contextDelta must be a string", lane_id)

        if lane.get("stateAccess") not in VALID_STATE_ACCESS:
            add_finding(
                rejections,
                "invalid_state_access",
                f"stateAccess must be one of: {', '.join(sorted(VALID_STATE_ACCESS))}",
                lane_id,
            )

        for field in [
            "inScope",
            "outOfScope",
            "filesRead",
            "filesWrite",
            "filesAvoid",
            "dependencies",
            "consumes",
            "produces",
            "laneConstraints",
            "proof",
        ]:
            if field in lane and not require_list(lane[field]):
                add_finding(rejections, "invalid_field_type", f"{field} must be a list of strings", lane_id)
        if isinstance(lane.get("proof"), list) and not lane["proof"]:
            add_finding(rejections, "missing_proof", "lane proof must not be empty", lane_id)

        rendered_metadata = {key: value for key, value in lane.items() if key != "contextDelta"}
        if has_secret(json.dumps(rendered_metadata, ensure_ascii=False)):
            add_finding(
                rejections,
                "secret_in_lane_contract",
                "lane contract appears to contain a secret; redact or summarize before dispatch",
                lane_id,
            )

        lane_context = "\n".join(
            [
                lane.get("contextDelta", "") if isinstance(lane.get("contextDelta"), str) else "",
                *(lane.get("laneConstraints", []) if isinstance(lane.get("laneConstraints"), list) else []),
            ]
        )
        lane_words = word_count(lane_context)
        total_context_words += lane_words
        contexts[lane_id] = lane_context
        if has_secret(lane_context):
            add_finding(
                rejections,
                "secret_in_lane_context",
                "lane context appears to contain a secret; redact or reference a safe source",
                lane_id,
            )
        if lane_words > max_inline_words:
            add_finding(
                warnings,
                "lane_context_too_large",
                f"lane context has {lane_words} words; advisory max is {max_inline_words}",
                lane_id,
            )

        for pattern in lane.get("filesRead", []) if isinstance(lane.get("filesRead"), list) else []:
            if is_overbroad_path(pattern):
                add_finding(
                    warnings,
                    "overbroad_read_scope",
                    f"filesRead contains broad path '{pattern}'; keep it only when whole-repo inspection is intended",
                    lane_id,
                )
        for pattern in lane.get("filesWrite", []) if isinstance(lane.get("filesWrite"), list) else []:
            if escapes_project(pattern):
                add_finding(
                    rejections,
                    "path_outside_project",
                    f"filesWrite must stay project-relative: {pattern}",
                    lane_id,
                )
            if is_overbroad_path(pattern):
                add_finding(
                    rejections,
                    "overbroad_write_scope",
                    f"filesWrite contains overbroad path '{pattern}'; name bounded files or directories",
                    lane_id,
                )
    if total_context_words > max_total_inline_words:
        add_finding(
            warnings,
            "total_context_too_large",
            f"shared plus lane context has {total_context_words} words; advisory max is {max_total_inline_words}",
        )

    for left_index, left in enumerate(lanes):
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
                        add_finding(
                            rejections,
                            "overlapping_writes",
                            f"{left_id} and {right_id} both write overlapping paths: {left_path} / {right_path}",
                        )

            if (
                left.get("stateScope")
                and left.get("stateScope") == right.get("stateScope")
                and "mutates" in {left.get("stateAccess"), right.get("stateAccess")}
                and not dependency_orders(left, right)
            ):
                add_finding(
                    rejections,
                    "shared_mutable_state",
                    f"{left_id} and {right_id} share mutable stateScope: {left.get('stateScope')}",
                )

            left_proof = {normalize_text(item) for item in left.get("proof", []) if isinstance(item, str)}
            right_proof = {normalize_text(item) for item in right.get("proof", []) if isinstance(item, str)}
            duplicates = sorted(item for item in left_proof & right_proof if item)
            if duplicates:
                add_finding(
                    warnings,
                    "duplicate_proof_target",
                    f"{left_id} and {right_id} share proof target: {duplicates[0]}",
                )

    shingle_to_lanes = defaultdict(set)
    for lane_id, context in contexts.items():
        for shingle in shingle_words(context):
            shingle_to_lanes[shingle].add(lane_id)
    duplicate_shingles = [lane_ids for lane_ids in shingle_to_lanes.values() if len(lane_ids) > 1]
    if duplicate_shingles:
        add_finding(
            warnings,
            "duplicated_lane_context",
            f"lane context repeats long text across lanes ({len(duplicate_shingles)} repeated blocks); move common text to shared",
        )

    return {"rejections": rejections, "warnings": warnings}


def render_lane(data, lane_id, max_render_chars):
    lane = next(
        (item for item in data.get("lanes", []) if isinstance(item, dict) and item.get("id") == lane_id),
        None,
    )
    if lane is None:
        raise ValueError(f"lane not found: {lane_id}")

    prompt = {
        "schemaVersion": "1.0",
        "shared": data["shared"],
        "lane": {key: lane[key] for key in REQUIRED_LANE_FIELDS},
        "execution": {
            "routineNarration": "none",
            "safeRetry": "silent only when the next attempt is safe and materially different",
            "stopOn": [
                "repeated failure fingerprint",
                "new authority required",
                "destructive external-state risk",
                "accepted appetite exceeded",
            ],
        },
        "receipt": {
            "status": "Done | Done with concerns | Blocked | Needs decision",
            "changedFiles": [],
            "proof": [],
            "blocker": None,
        },
    }
    output = json.dumps(prompt, ensure_ascii=False, separators=(",", ":")) + "\n"
    if len(output) > max_render_chars:
        raise ValueError(f"rendered lane has {len(output)} characters; max is {max_render_chars}")
    return output


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
    rejection_codes = Counter()
    warning_codes = Counter()
    for record in filtered:
        for rejection in record.get("rejections", []):
            rejection_codes[rejection.get("code", "unknown")] += 1
        for warning in record.get("warnings", []):
            warning_codes[warning.get("code", "unknown")] += 1
    return {
        "schemaVersion": "1.0",
        "runId": run_id or "all",
        "checkedPlans": len(filtered),
        "acceptedPlans": sum(1 for record in filtered if record.get("status") == "accepted"),
        "rejectedPlans": len(rejected),
        "rejectionCount": sum(int(record.get("rejectionCount", 0)) for record in rejected),
        "warningCount": sum(int(record.get("warningCount", 0)) for record in filtered),
        "rejectionsByCode": dict(sorted(rejection_codes.items())),
        "warningsByCode": dict(sorted(warning_codes.items())),
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
        f"{summary['rejectedPlans']} rejected, {summary['rejectionCount']} rejection(s), "
        f"{summary['warningCount']} warning(s)."
    )


def main():
    parser = argparse.ArgumentParser(description="Validate and log Gauntlet subagent plan manifests.")
    parser.add_argument("project_root", type=Path)
    parser.add_argument("plan", type=Path, nargs="?")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--stats", action="store_true", help="Print finding totals from the log instead of validating a plan.")
    parser.add_argument("--max-inline-words", type=int, default=180)
    parser.add_argument("--max-total-inline-words", type=int, default=600)
    parser.add_argument("--render-lane", metavar="LANE_ID", help="Render one compact child prompt after validation.")
    parser.add_argument("--max-render-chars", type=int, default=12000)
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
    result = validate_plan(data, project_root, args.max_inline_words, args.max_total_inline_words)
    rejections = result["rejections"]
    warnings = result["warnings"]
    if args.run_id and data.get("runId") != args.run_id:
        add_finding(rejections, "run_id_mismatch", f"plan runId must match --run-id ({args.run_id})")

    rendered_lane = None
    if args.render_lane and not rejections:
        try:
            rendered_lane = render_lane(data, args.render_lane, args.max_render_chars)
        except ValueError as error:
            add_finding(rejections, "lane_render_failed", str(error), args.render_lane)

    status = "rejected" if rejections else "accepted"
    record_run_id = args.run_id or data.get("runId") or "manual"
    record = {
        "schemaVersion": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "runId": record_run_id,
        "projectRoot": str(project_root),
        "planPath": str(args.plan),
        "status": status,
        "laneCount": len(data.get("lanes", [])) if isinstance(data.get("lanes"), list) else 0,
        "rejectionCount": len(rejections),
        "rejections": rejections,
        "warningCount": len(warnings),
        "warnings": warnings,
    }

    gauntlet_dir.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    records = read_log(log_path)
    summary_path, summary = write_summary(project_root, records, record_run_id)

    if rejections:
        print(f"Subagent plan rejected: {len(rejections)} rejection(s); logged to {log_path.relative_to(project_root)}")
        migration = next(
            (
                finding["message"]
                for finding in rejections
                if finding["code"] in {"legacy_schema_version", "legacy_packet_field"}
            ),
            None,
        )
        if migration:
            print(f"Migration: {migration}")
        print(f"Summary: {summary_path.relative_to(project_root)}")
        raise SystemExit(1)

    if rendered_lane is not None:
        print(rendered_lane, end="")
        return

    if warnings:
        print(f"accepted with {len(warnings)} warning(s)")
        for warning in warnings:
            lane = f" [{warning['laneId']}]" if warning.get("laneId") else ""
            print(f"- {warning['code']}{lane}: {warning['message']}")
    else:
        print("accepted")


if __name__ == "__main__":
    main()
