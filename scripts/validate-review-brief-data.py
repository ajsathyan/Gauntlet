#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

HANDLE_RE = re.compile(r"^(RB|CU|N|P)-[0-9]{3,}$")
ENUMS = {
    "priority": {"P0", "P1", "P2", "P3"},
    "role": {"PM", "Design", "Eng", "QA", "Cross-functional"},
    "reviewState": {"Needs decision", "Needs proof", "Blocked", "Ready for final scan", "Done", "Tombstoned"},
    "workState": {"Backlog", "Ready", "In Progress", "In Review", "Blocked", "Done"},
    "proofStatus": {"Missing", "Partial", "Passed", "Failed", "Not Applicable"},
    "confidence": {"High confidence", "Needs judgment", "Risk unclear", "Proof missing"},
    "noteKind": {"Decision", "Deviation", "Tradeoff", "Open question", "Assumption"},
    "proofKind": {"Test", "Screenshot", "Benchmark", "Log", "Manual check", "Static analysis"},
}


def fail(message):
    print(f"review-brief-data invalid: {message}", file=sys.stderr)
    raise SystemExit(1)


def require(record, fields, label):
    for field in fields:
        if field not in record:
            fail(f"{label} missing {field}")


def check_handle(value, label):
    if not isinstance(value, str) or not HANDLE_RE.match(value):
        fail(f"{label} has invalid handle {value!r}")


def flatten_links(record):
    links = record.get("links", {})
    found = []
    if not isinstance(links, dict):
        fail(f"{record.get('id', '<unknown>')} links must be an object")
    for value in links.values():
        if isinstance(value, list):
            found.extend(value)
        elif value:
            found.append(value)
    if "linkedReviewItems" in record:
        found.extend(record["linkedReviewItems"])
    return found


def valid_asset_path(path):
    if not isinstance(path, str):
        return False
    if "://" in path or path.startswith("/") or ".." in Path(path).parts:
        return False
    return path.startswith("review-brief-assets/")


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "review-brief-data.json")
    data = json.loads(path.read_text())

    require(data, ["schemaVersion", "generatedAt", "brief", "reviewItems", "changeUnits", "notes", "proof"], "top-level data")
    if data["schemaVersion"] != "1.0":
        fail(f"unsupported schemaVersion {data['schemaVersion']!r}")

    for key in ["reviewItems", "changeUnits", "notes", "proof"]:
        if not isinstance(data[key], list):
            fail(f"{key} must be an array")

    records = data["reviewItems"] + data["changeUnits"] + data["notes"] + data["proof"]
    handles = set()
    for record in records:
        check_handle(record.get("id"), "record")
        if record["id"] in handles:
            fail(f"duplicate handle {record['id']}")
        handles.add(record["id"])

    for item in data["reviewItems"]:
        require(item, ["id", "title", "priority", "role", "reviewState", "workState", "proofStatus", "confidence", "why", "decisionNeeded", "agentNext", "links"], item.get("id", "review item"))
        for field in ["priority", "role", "reviewState", "workState", "proofStatus", "confidence"]:
            if item[field] not in ENUMS[field]:
                fail(f"{item['id']} has invalid {field}: {item[field]!r}")
        if item["reviewState"] == "Done" and item["proofStatus"] not in {"Passed", "Not Applicable"}:
            fail(f"{item['id']} is Done without passed or not-applicable proof")

    for unit in data["changeUnits"]:
        require(unit, ["id", "title", "reason", "changedFiles", "linkedReviewItems"], unit.get("id", "change unit"))

    for note in data["notes"]:
        require(note, ["id", "kind", "text", "links"], note.get("id", "note"))
        if note["kind"] not in ENUMS["noteKind"]:
            fail(f"{note['id']} has invalid kind: {note['kind']!r}")

    for proof in data["proof"]:
        require(proof, ["id", "kind", "status", "summary", "proves", "doesNotProve"], proof.get("id", "proof"))
        if proof["kind"] not in ENUMS["proofKind"]:
            fail(f"{proof['id']} has invalid kind: {proof['kind']!r}")
        if proof["status"] not in ENUMS["proofStatus"]:
            fail(f"{proof['id']} has invalid status: {proof['status']!r}")
        if proof.get("assetPath") and not valid_asset_path(proof["assetPath"]):
            fail(f"{proof['id']} has invalid assetPath")

    for record in records:
        for linked in flatten_links(record):
            check_handle(linked, f"{record['id']} link")
            if linked not in handles:
                fail(f"{record['id']} links missing handle {linked}")

    print(f"review-brief-data valid: {path}")


if __name__ == "__main__":
    main()
