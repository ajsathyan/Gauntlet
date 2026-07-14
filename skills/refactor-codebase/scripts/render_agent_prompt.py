#!/usr/bin/env python3
"""Render a cache-stable isolated-agent prompt from a bundled template.

The complete template is the static prefix. Packet-derived and lane-specific
values are appended once, at the end, in canonical JSON. Exit codes: 0 success,
2 invalid input or runtime error.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict


SCHEMA_VERSION = 1
SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = {
    "breakthrough": SKILL_ROOT / "assets" / "breakthrough-agent-packet.md",
    "observable-review": SKILL_ROOT / "assets" / "observable-review-agent-packet.md",
}


class PromptError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_bytes(path: Path, code: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise PromptError(code, f"Could not read {path}: {exc}") from exc


def load_assignment(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PromptError("invalid-assignment", f"Could not read assignment JSON: {exc}") from exc
    if not isinstance(value, dict) or not value:
        raise PromptError("invalid-assignment", "Assignment JSON must be a non-empty object")
    reserved = sorted({"packet_path", "packet_sha256"} & set(value))
    if reserved:
        raise PromptError("invalid-assignment", f"Assignment cannot override renderer-owned fields: {', '.join(reserved)}")
    return value


def template_version(text: str) -> int:
    match = re.search(r"^Template version: ([1-9][0-9]*)$", text, flags=re.MULTILINE)
    if not match:
        raise PromptError("invalid-template", "Template must declare a positive integer Template version")
    if text.count("## Variable assignment") != 1:
        raise PromptError("invalid-template", "Template must contain exactly one Variable assignment section")
    return int(match.group(1))


def render(kind: str, packet: Path, assignment_path: Path) -> tuple[str, Dict[str, Any]]:
    template_path = TEMPLATES[kind]
    template_bytes = read_bytes(template_path, "invalid-template")
    packet_bytes = read_bytes(packet, "invalid-packet")
    try:
        template_text = template_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PromptError("invalid-template", "Template must be UTF-8") from exc
    version = template_version(template_text)
    try:
        packet_value = json.loads(packet_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PromptError("invalid-packet", "Packet must be a UTF-8 JSON object") from exc
    if not isinstance(packet_value, dict):
        raise PromptError("invalid-packet", "Packet must be a JSON object")
    assignment = load_assignment(assignment_path)
    populated = {
        "packet_path": str(packet.resolve()),
        "packet_sha256": sha256_bytes(packet_bytes),
        **assignment,
    }
    static_prefix = template_text.rstrip() + "\n"
    suffix = (
        "\n## Populated variable assignment\n\n"
        "This canonical JSON block is volatile and intentionally last.\n\n"
        "```json\n"
        + json.dumps(populated, indent=2, sort_keys=True, ensure_ascii=False)
        + "\n```\n"
    )
    prompt = static_prefix + suffix
    metadata = {
        "schemaVersion": SCHEMA_VERSION,
        "templateKind": kind,
        "templateVersion": version,
        "templateSha256": sha256_bytes(template_bytes),
        "staticPrefixSha256": sha256_bytes(static_prefix.encode("utf-8")),
        "packetSha256": sha256_bytes(packet_bytes),
        "promptSha256": sha256_bytes(prompt.encode("utf-8")),
        "contextMode": "none",
        "assignmentPosition": "last",
        "assignmentKeys": sorted(populated),
    }
    return prompt, metadata


def write(path: Path, value: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
    except OSError as exc:
        raise PromptError("write-failed", f"Could not write {path}: {exc}") from exc


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Render a cache-stable no-history agent prompt and integrity metadata.")
    result.add_argument("--template-kind", choices=sorted(TEMPLATES), required=True)
    result.add_argument("--packet", required=True, help="Frozen evidence or observable-review packet path.")
    result.add_argument("--assignment", required=True, help="JSON object containing lane-specific values.")
    result.add_argument("--output", required=True, help="Rendered Markdown prompt path.")
    result.add_argument("--metadata-output", help="Optional JSON metadata receipt path.")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        prompt, metadata = render(args.template_kind, Path(args.packet), Path(args.assignment))
        write(Path(args.output), prompt)
        serialized = json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        if args.metadata_output:
            write(Path(args.metadata_output), serialized)
        print(serialized, end="")
        return 0
    except PromptError as exc:
        print(json.dumps({"error": {"code": exc.code, "message": str(exc)}}, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
