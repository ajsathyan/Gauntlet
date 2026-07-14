#!/usr/bin/env python3
"""Validate the refactor parity ledger schema and completion state.

Exit codes: 0 valid for requested mode, 1 validation findings, 2 unreadable input.
"""

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Set


SCHEMA_VERSION = 1
AREA_STATUSES = {"resolved", "unresolved"}
DISPOSITIONS = {"preserve", "repair", "consolidate", "remove-artifact", "needs-user-decision"}
RESULTS = {"pass", "intentional-repair", "approved-artifact-removal", "pending", "fail", "blocked"}
FINAL_RESULTS = {"pass", "intentional-repair", "approved-artifact-removal"}
KINDS = {
    "route", "preset", "control", "pipeline", "export", "editor", "saved-workflow", "loading",
    "empty", "error", "accessibility", "integration", "operational", "other",
}
FINAL_BY_DISPOSITION = {
    "preserve": {"pass"},
    "repair": {"intentional-repair", "pass"},
    "consolidate": {"pass"},
    "remove-artifact": {"approved-artifact-removal"},
    "needs-user-decision": set(),
}


def emit(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))


def issue(issues: List[Dict[str, str]], code: str, location: str, message: str) -> None:
    issues.append({"code": code, "location": location, "message": message})


def string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)


def validate(payload: Any, allow_incomplete: bool) -> Dict[str, Any]:
    issues: List[Dict[str, str]] = []
    if not isinstance(payload, dict):
        issue(issues, "invalid-root", "$", "Ledger must be a JSON object.")
        return {"schemaVersion": SCHEMA_VERSION, "valid": False, "mode": "draft" if allow_incomplete else "complete", "issues": issues}
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        issue(issues, "invalid-schema-version", "$.schemaVersion", f"Expected {SCHEMA_VERSION}.")
    areas = payload.get("inventoryAreas")
    rows = payload.get("rows")
    if not isinstance(areas, list) or not areas:
        issue(issues, "missing-inventory-areas", "$.inventoryAreas", "At least one inventory area is required.")
        areas = []
    if not isinstance(rows, list) or not rows:
        issue(issues, "missing-ledger-rows", "$.rows", "At least one parity row is required.")
        rows = []

    area_ids: Set[str] = set()
    rows_per_area: Dict[str, int] = {}
    unresolved = 0
    for index, area in enumerate(areas):
        location = f"$.inventoryAreas[{index}]"
        if not isinstance(area, dict):
            issue(issues, "invalid-inventory-area", location, "Inventory area must be an object.")
            continue
        area_id = area.get("id")
        if not isinstance(area_id, str) or not area_id.strip():
            issue(issues, "invalid-area-id", f"{location}.id", "A non-empty string id is required.")
        elif area_id in area_ids:
            issue(issues, "duplicate-area-id", f"{location}.id", f"Duplicate area id: {area_id}")
        else:
            area_ids.add(area_id)
            rows_per_area[area_id] = 0
        if not isinstance(area.get("title"), str) or not area["title"].strip():
            issue(issues, "invalid-area-title", f"{location}.title", "A non-empty title is required.")
        status = area.get("status")
        if status not in AREA_STATUSES:
            issue(issues, "invalid-area-status", f"{location}.status", "Status must be resolved or unresolved.")
        elif status == "unresolved":
            unresolved += 1
            if not allow_incomplete:
                issue(issues, "unresolved-inventory-area", f"{location}.status", "Completion requires every inventory area to be resolved.")
        evidence = area.get("evidence")
        if not string_list(evidence):
            issue(issues, "invalid-area-evidence", f"{location}.evidence", "Evidence must be a non-empty string array.")

    row_ids: Set[str] = set()
    incomplete = 0
    for index, row in enumerate(rows):
        location = f"$.rows[{index}]"
        if not isinstance(row, dict):
            issue(issues, "invalid-row", location, "Parity row must be an object.")
            continue
        row_id = row.get("id")
        if not isinstance(row_id, str) or not row_id.strip():
            issue(issues, "invalid-row-id", f"{location}.id", "A non-empty string id is required.")
        elif row_id in row_ids:
            issue(issues, "duplicate-row-id", f"{location}.id", f"Duplicate row id: {row_id}")
        else:
            row_ids.add(row_id)
        area_id = row.get("inventoryArea")
        if area_id not in area_ids:
            issue(issues, "unknown-inventory-area", f"{location}.inventoryArea", "Row must reference a declared inventory area.")
        else:
            rows_per_area[area_id] += 1
        if row.get("kind") not in KINDS:
            issue(issues, "invalid-kind", f"{location}.kind", f"Kind must be one of: {', '.join(sorted(KINDS))}.")
        if not isinstance(row.get("name"), str) or not row["name"].strip():
            issue(issues, "invalid-name", f"{location}.name", "A non-empty capability name is required.")
        disposition = row.get("disposition")
        if disposition not in DISPOSITIONS:
            issue(issues, "invalid-disposition", f"{location}.disposition", "Feature removal is not permitted; use an allowed disposition.")
        result = row.get("result")
        if result not in RESULTS:
            issue(issues, "invalid-result", f"{location}.result", f"Result must be one of: {', '.join(sorted(RESULTS))}.")
        elif result not in FINAL_RESULTS:
            incomplete += 1
            if not allow_incomplete:
                issue(issues, "incomplete-row", f"{location}.result", "Completion requires an explicit final parity result.")
        elif disposition in FINAL_BY_DISPOSITION and result not in FINAL_BY_DISPOSITION[disposition]:
            issue(issues, "incompatible-result", f"{location}.result", f"Result {result} is incompatible with {disposition}.")
        if not string_list(row.get("baselineEvidence")):
            issue(issues, "invalid-baseline-evidence", f"{location}.baselineEvidence", "Baseline evidence must be a non-empty string array.")
        parity_evidence = row.get("parityEvidence")
        if not string_list(parity_evidence):
            if not allow_incomplete or result in FINAL_RESULTS:
                issue(issues, "invalid-parity-evidence", f"{location}.parityEvidence", "Final rows require non-empty parity evidence.")

    for area_id, count in sorted(rows_per_area.items()):
        if count == 0:
            issue(issues, "empty-inventory-area", f"$.inventoryAreas[id={area_id}]", "Every declared inventory area needs at least one ledger row.")

    return {
        "schemaVersion": SCHEMA_VERSION,
        "valid": not issues,
        "mode": "draft" if allow_incomplete else "complete",
        "counts": {
            "inventoryAreas": len(areas),
            "unresolvedInventoryAreas": unresolved,
            "rows": len(rows),
            "incompleteRows": incomplete,
        },
        "issues": issues,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Validate a refactor parity-ledger JSON file; completion is required by default.")
    result.add_argument("ledger", help="Parity-ledger JSON path.")
    result.add_argument("--allow-incomplete", action="store_true", help="Validate draft schema while allowing unresolved areas and non-final rows.")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        payload = json.loads(Path(args.ledger).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        emit({"error": {"code": "invalid-ledger", "message": str(exc)}})
        return 2
    report = validate(payload, args.allow_incomplete)
    emit(report)
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
