#!/usr/bin/env python3
"""Render a validated cache-stable prompt for an isolated refactor agent.

The bundled template bytes are the exact static prefix. A canonical, allowlisted
variable assignment is appended once at the end. Exit codes: 0 success, 2 invalid
input or runtime error.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Dict, Iterable


SCHEMA_VERSION = 1
SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = {
    "breakthrough": SKILL_ROOT / "assets" / "breakthrough-agent-packet.md",
    "observable-review": SKILL_ROOT / "assets" / "observable-review-agent-packet.md",
}
PACKET_COMMON = {
    "schemaVersion", "packetType", "contractVersion", "objective", "artifacts",
    "authority", "proofContract", "returnContract", "blockerPolicy", "askUserPolicy",
}
PACKET_EXTRA = {
    "breakthrough": {"userTargets", "priorityOrder"},
    "observable-review": set(),
}
ASSIGNMENT_KEYS = {
    "breakthrough": {"allowed_repository_root", "receipt_destination"},
    "observable-review": {
        "allowed_repository_root", "review_mandate", "assigned_row_ids",
        "allowed_observation_surface", "receipt_destination",
    },
}
REVIEW_MANDATES = {"compatibility", "architecture_metric", "black_box"}
OBSERVATION_SURFACES = {"built-in-browser", "chrome", "computer-use", "api", "cli", "connector"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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


def load_json(path: Path, code: str) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PromptError(code, f"Could not read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PromptError(code, f"{path} must contain a JSON object")
    return value


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def string_list(value: Any, *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(nonempty_string(item) for item in value)
    )


def parse_expected_sha256(value: str) -> str:
    normalized = value.removeprefix("sha256:").lower()
    if not SHA256_RE.fullmatch(normalized):
        raise PromptError("invalid-expected-hash", "Expected packet SHA-256 must contain exactly 64 hexadecimal characters")
    return normalized


def template_version(text: str) -> int:
    match = re.search(r"^Template version: ([1-9][0-9]*)$", text, flags=re.MULTILINE)
    if not match:
        raise PromptError("invalid-template", "Template must declare a positive integer Template version")
    if text.count("## Variable assignment") != 1:
        raise PromptError("invalid-template", "Template must contain exactly one Variable assignment section")
    return int(match.group(1))


def ensure_within(root: Path, path: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PromptError("path-outside-root", f"{label} must stay within the allowed repository root") from exc
    return resolved


def repository_root(path: Path) -> Path:
    completed = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(path), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )
    if completed.returncode != 0:
        raise PromptError("invalid-repository-root", "allowed_repository_root must be a Git work tree")
    return Path(completed.stdout.strip()).resolve()


def validate_assignment(kind: str, value: Dict[str, Any]) -> Dict[str, Any]:
    expected = ASSIGNMENT_KEYS[kind]
    if set(value) != expected:
        missing = sorted(expected - set(value))
        unknown = sorted(set(value) - expected)
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if unknown:
            details.append(f"unknown: {', '.join(unknown)}")
        raise PromptError("invalid-assignment", "Assignment keys are invalid (" + "; ".join(details) + ")")
    for field in ("allowed_repository_root", "receipt_destination"):
        if not nonempty_string(value[field]):
            raise PromptError("invalid-assignment", f"assignment.{field} must be a non-empty string")
    if kind == "observable-review":
        if value["review_mandate"] not in REVIEW_MANDATES:
            raise PromptError("invalid-assignment", "assignment.review_mandate is invalid")
        if value["allowed_observation_surface"] not in OBSERVATION_SURFACES:
            raise PromptError("invalid-assignment", "assignment.allowed_observation_surface is invalid")
        if not string_list(value["assigned_row_ids"]):
            raise PromptError("invalid-assignment", "assignment.assigned_row_ids must be a non-empty string array")
    return value


def validate_packet(kind: str, value: Dict[str, Any], root: Path) -> None:
    expected = PACKET_COMMON | PACKET_EXTRA[kind]
    if set(value) != expected:
        missing = sorted(expected - set(value))
        unknown = sorted(set(value) - expected)
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if unknown:
            details.append(f"unknown: {', '.join(unknown)}")
        raise PromptError("invalid-packet", "Packet keys are invalid (" + "; ".join(details) + ")")
    if value["schemaVersion"] != SCHEMA_VERSION or value["packetType"] != kind:
        raise PromptError("invalid-packet", f"Packet must use schemaVersion {SCHEMA_VERSION} and packetType {kind}")
    for field in ("contractVersion", "objective", "blockerPolicy", "askUserPolicy"):
        if not nonempty_string(value[field]):
            raise PromptError("invalid-packet", f"packet.{field} must be a non-empty string")
    for field in ("proofContract", "returnContract"):
        if not isinstance(value[field], dict) or not value[field]:
            raise PromptError("invalid-packet", f"packet.{field} must be a non-empty object")
    authority = value["authority"]
    if not isinstance(authority, dict) or set(authority) != {"allowed", "forbidden"}:
        raise PromptError("invalid-packet", "packet.authority must contain exactly allowed and forbidden")
    if not string_list(authority["allowed"]) or not string_list(authority["forbidden"]):
        raise PromptError("invalid-packet", "packet.authority allowed and forbidden must be non-empty string arrays")
    if kind == "breakthrough":
        if not string_list(value["userTargets"], allow_empty=True):
            raise PromptError("invalid-packet", "packet.userTargets must be a string array")
        if not string_list(value["priorityOrder"]):
            raise PromptError("invalid-packet", "packet.priorityOrder must be a non-empty string array")
    artifacts = value["artifacts"]
    if not isinstance(artifacts, list) or not artifacts:
        raise PromptError("invalid-packet", "packet.artifacts must be a non-empty array")
    seen = set()
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict) or set(artifact) != {"path", "sha256"}:
            raise PromptError("invalid-packet", f"packet.artifacts[{index}] must contain exactly path and sha256")
        if not nonempty_string(artifact["path"]) or not isinstance(artifact["sha256"], str):
            raise PromptError("invalid-packet", f"packet.artifacts[{index}] has invalid values")
        digest = parse_expected_sha256(artifact["sha256"])
        candidate = Path(artifact["path"])
        candidate = candidate if candidate.is_absolute() else root / candidate
        resolved = ensure_within(root, candidate, f"packet.artifacts[{index}].path")
        if resolved in seen or not resolved.is_file():
            raise PromptError("invalid-packet", f"packet.artifacts[{index}] must identify a unique existing file")
        seen.add(resolved)
        if sha256_bytes(read_bytes(resolved, "invalid-packet")) != digest:
            raise PromptError("artifact-hash-mismatch", f"packet.artifacts[{index}] no longer matches its SHA-256")


def validate_distinct_paths(inputs: Iterable[Path], outputs: Iterable[Path]) -> None:
    input_paths = {path.resolve() for path in inputs}
    output_paths = [path.resolve() for path in outputs]
    if len(output_paths) != len(set(output_paths)):
        raise PromptError("path-collision", "Prompt and metadata outputs must be distinct")
    if any(path in input_paths for path in output_paths):
        raise PromptError("path-collision", "Outputs cannot replace a packet, assignment, or bundled template")


def atomic_write(path: Path, value: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as stream:
                stream.write(value)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except BaseException:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
    except OSError as exc:
        raise PromptError("write-failed", f"Could not write {path}: {exc}") from exc


def render(kind: str, packet: Path, assignment_path: Path, expected_packet_sha256: str) -> tuple[str, Dict[str, Any], Path]:
    template_path = TEMPLATES[kind]
    template_bytes = read_bytes(template_path, "invalid-template")
    packet_bytes = read_bytes(packet, "invalid-packet")
    actual_packet_sha256 = sha256_bytes(packet_bytes)
    if actual_packet_sha256 != parse_expected_sha256(expected_packet_sha256):
        raise PromptError("packet-hash-mismatch", "Packet no longer matches the expected frozen SHA-256")
    try:
        template_text = template_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PromptError("invalid-template", "Template must be UTF-8") from exc
    version = template_version(template_text)
    assignment = validate_assignment(kind, load_json(assignment_path, "invalid-assignment"))
    root = Path(assignment["allowed_repository_root"]).resolve()
    if repository_root(root) != root:
        raise PromptError("invalid-repository-root", "allowed_repository_root must equal the containing Git work-tree root")
    ensure_within(root, packet, "packet")
    ensure_within(root, assignment_path, "assignment")
    validate_packet(kind, load_json(packet, "invalid-packet"), root)
    destination = assignment["receipt_destination"]
    if destination != "return-to-root":
        ensure_within(root, Path(destination), "receipt_destination")
    populated = {
        **assignment,
        "packet_path": str(packet.resolve()),
        "packet_sha256": f"sha256:{actual_packet_sha256}",
    }
    separator = "" if template_text.endswith("\n") else "\n"
    suffix = (
        separator
        + "\n## Populated variable assignment\n\n"
        "This canonical JSON block is volatile and intentionally last.\n\n"
        "```json\n"
        + json.dumps(populated, indent=2, sort_keys=True, ensure_ascii=False)
        + "\n```\n"
    )
    prompt = template_text + suffix
    metadata = {
        "schemaVersion": SCHEMA_VERSION,
        "templateKind": kind,
        "templateVersion": version,
        "templateSha256": sha256_bytes(template_bytes),
        "staticPrefixSha256": sha256_bytes(template_bytes),
        "packetSha256": actual_packet_sha256,
        "promptSha256": sha256_bytes(prompt.encode("utf-8")),
        "contextMode": "none",
        "assignmentPosition": "last",
        "assignmentKeys": sorted(populated),
    }
    return prompt, metadata, root


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Render a validated cache-stable no-history agent prompt.")
    result.add_argument("--template-kind", choices=sorted(TEMPLATES), required=True)
    result.add_argument("--packet", required=True, help="Frozen evidence or observable-review packet JSON path.")
    result.add_argument("--expected-packet-sha256", required=True, help="Frozen packet SHA-256 from refactor-state.json.")
    result.add_argument("--assignment", required=True, help="Allowlisted JSON object containing lane-specific values.")
    result.add_argument("--output", required=True, help="Rendered Markdown prompt path.")
    result.add_argument("--metadata-output", help="Optional JSON metadata receipt path.")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        packet = Path(args.packet)
        assignment = Path(args.assignment)
        output = Path(args.output)
        metadata_output = Path(args.metadata_output) if args.metadata_output else None
        prompt, metadata, root = render(args.template_kind, packet, assignment, args.expected_packet_sha256)
        ensure_within(root, output, "output")
        if metadata_output:
            ensure_within(root, metadata_output, "metadata_output")
        outputs = [output] + ([metadata_output] if metadata_output else [])
        validate_distinct_paths([packet, assignment, TEMPLATES[args.template_kind]], outputs)
        serialized = json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        atomic_write(output, prompt)
        if metadata_output:
            atomic_write(metadata_output, serialized)
        print(serialized, end="")
        return 0
    except PromptError as exc:
        print(json.dumps({"error": {"code": exc.code, "message": str(exc)}}, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
