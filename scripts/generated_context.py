#!/usr/bin/env python3
"""Render deterministic, bounded Gauntlet child context without model calls."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = 1
CONTRACT = "gauntlet/generated-context/v1"
FAMILIES = ("implementation", "research", "review")
MANIFEST_KEYS = {
    "schema_version",
    "family",
    "template_version",
    "stable_sources",
    "volatile_sources",
}
SOURCE_KEYS = {"role", "id", "path"}
STABLE_ROLES = {"global", "cohort", "dependency"}
VOLATILE_ROLES = {"ticket", "handoff"}
ROLE_ORDER = {"global": 0, "cohort": 1, "dependency": 2, "ticket": 3, "handoff": 4}
SOURCE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
TEMPLATE_VERSION_RE = re.compile(rb"^Template version: ([1-9][0-9]*)$", re.MULTILINE)
FAMILY_RE = re.compile(rb"^Prompt family: ([a-z][a-z0-9-]*)$", re.MULTILINE)


class ContextError(Exception):
    """A deterministic validation or rendering failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Source:
    role: str
    source_id: str
    path: Path
    content: bytes
    sha256: str
    phase: str


@dataclass(frozen=True)
class RenderedContext:
    prompt: bytes
    stable_prefix: bytes
    metadata: dict[str, Any]
    metadata_bytes: bytes


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _ensure_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContextError("invalid-manifest", f"{label} must be an object")
    return value


def _ensure_within(root: Path, candidate: Path, label: str) -> Path:
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ContextError("source-outside-root", f"{label} must stay within source_root") from exc
    return resolved


def _read_source(root: Path, value: Any, phase: str) -> Source:
    source = _ensure_mapping(value, f"{phase} source")
    if set(source) != SOURCE_KEYS:
        raise ContextError(
            "invalid-source",
            f"{phase} sources must contain exactly: {', '.join(sorted(SOURCE_KEYS))}",
        )
    role = source["role"]
    source_id = source["id"]
    raw_path = source["path"]
    if not isinstance(role, str) or not isinstance(source_id, str) or not isinstance(raw_path, str):
        raise ContextError("invalid-source", "Source role, id, and path must be strings")
    allowed_roles = STABLE_ROLES if phase == "stable" else VOLATILE_ROLES
    if role not in allowed_roles:
        raise ContextError("invalid-source-phase", f"Role {role!r} is not allowed in {phase}_sources")
    if not SOURCE_ID_RE.fullmatch(source_id):
        raise ContextError("invalid-source", f"Source id {source_id!r} is not canonical")
    path_value = Path(raw_path)
    path = _ensure_within(root, path_value if path_value.is_absolute() else root / path_value, "source path")
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ContextError("source-read-failed", f"Could not read source {source_id!r}: {exc}") from exc
    if not content:
        raise ContextError("missing-critical-context", f"Source {source_id!r} is empty")
    try:
        content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContextError("invalid-source-encoding", f"Source {source_id!r} must be UTF-8") from exc
    return Source(role, source_id, path, content, sha256_bytes(content), phase)


def _validate_sources(stable: Sequence[Source], volatile: Sequence[Source]) -> None:
    all_sources = [*stable, *volatile]
    seen_ids: set[str] = set()
    seen_paths: set[Path] = set()
    seen_digests: set[str] = set()
    for source in all_sources:
        if (
            source.source_id in seen_ids
            or source.path in seen_paths
            or source.sha256 in seen_digests
        ):
            raise ContextError(
                "duplicate-source",
                f"Source {source.source_id!r} duplicates an existing id, file, or exact content",
            )
        seen_ids.add(source.source_id)
        seen_paths.add(source.path)
        seen_digests.add(source.sha256)

    counts = {role: sum(source.role == role for source in all_sources) for role in ROLE_ORDER}
    for role in ("global", "ticket", "handoff"):
        if counts[role] != 1:
            raise ContextError(
                "missing-critical-context",
                f"Generated context requires exactly one {role} source; found {counts[role]}",
            )
    if counts["cohort"] > 1:
        raise ContextError(
            "duplicate-cohort-context",
            f"Generated context accepts at most one cohort source; found {counts['cohort']}",
        )


def load_template(template_root: Path, family: str, version: int) -> bytes:
    if family not in FAMILIES:
        raise ContextError("unsupported-family", f"Unsupported prompt family: {family!r}")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ContextError("unsupported-template-version", "template_version must be a positive integer")
    path = template_root / f"{family}-v{version}.md"
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ContextError("template-read-failed", f"Could not read template {path.name}: {exc}") from exc
    if len(content) >= 2048 or b"\n\n\n\n" in content:
        raise ContextError("padding-forbidden", f"Template {path.name} contains forbidden padding")
    if b"{{" in content or b"${" in content:
        raise ContextError("invalid-template", "Templates must be literal stable prefixes without interpolation")
    if not content.endswith(b"\n"):
        raise ContextError("invalid-template", "Templates must end with a newline")
    version_match = TEMPLATE_VERSION_RE.search(content)
    family_match = FAMILY_RE.search(content)
    if not version_match or int(version_match.group(1)) != version:
        raise ContextError("invalid-template", "Template version declaration does not match its filename")
    if not family_match or family_match.group(1).decode("ascii") != family:
        raise ContextError("invalid-template", "Prompt family declaration does not match its filename")
    try:
        content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContextError("invalid-template", "Templates must be UTF-8") from exc
    return content


def _section(title: str, content: bytes) -> bytes:
    terminator = b"" if content.endswith(b"\n") else b"\n"
    return f"# {title}\n\n".encode("utf-8") + content + terminator + b"\n"


def _ordered(sources: Iterable[Source]) -> list[Source]:
    return sorted(sources, key=lambda source: (ROLE_ORDER[source.role], source.source_id))


def render_manifest(
    manifest_value: Mapping[str, Any],
    *,
    source_root: Path,
    template_root: Path,
) -> RenderedContext:
    """Validate a manifest and render its exact prompt and privacy-safe receipt."""

    manifest = _ensure_mapping(manifest_value, "manifest")
    if "provenance" in manifest:
        raise ContextError(
            "untrusted-provenance-claim",
            "Callers cannot supply provenance or authentication claims; the renderer computes plain digests",
        )
    if "padding" in manifest:
        raise ContextError("padding-forbidden", "Generated context does not accept padding")
    if set(manifest) != MANIFEST_KEYS:
        missing = sorted(MANIFEST_KEYS - set(manifest))
        unknown = sorted(set(manifest) - MANIFEST_KEYS)
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if unknown:
            details.append("unknown: " + ", ".join(unknown))
        raise ContextError("invalid-manifest", "Manifest fields are invalid (" + "; ".join(details) + ")")
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise ContextError("unsupported-schema-version", f"schema_version must be {SCHEMA_VERSION}")
    family = manifest["family"]
    version = manifest["template_version"]
    if not isinstance(family, str):
        raise ContextError("unsupported-family", "family must be a string")
    if not isinstance(manifest["stable_sources"], list) or not isinstance(manifest["volatile_sources"], list):
        raise ContextError("invalid-manifest", "stable_sources and volatile_sources must be arrays")

    root = source_root.resolve()
    template_bytes = load_template(template_root.resolve(), family, version)
    stable_sources = [_read_source(root, item, "stable") for item in manifest["stable_sources"]]
    volatile_sources = [_read_source(root, item, "volatile") for item in manifest["volatile_sources"]]
    _validate_sources(stable_sources, volatile_sources)
    stable_sources = _ordered(stable_sources)
    volatile_sources = _ordered(volatile_sources)

    global_source = next(source for source in stable_sources if source.role == "global")
    cohort_source = next((source for source in stable_sources if source.role == "cohort"), None)
    dependencies = [source for source in stable_sources if source.role == "dependency"]
    ticket_source = next(source for source in volatile_sources if source.role == "ticket")
    handoff_source = next(source for source in volatile_sources if source.role == "handoff")

    dependency_content = (
        b"None.\n"
        if not dependencies
        else b"".join(_section(f"Dependency {source.source_id}", source.content) for source in dependencies)
    )
    stable_prefix = (
        template_bytes
        + b"\n"
        + _section("Global context", global_source.content)
        + _section("Cohort context", cohort_source.content if cohort_source else b"None.\n")
        + _section("Dependency contracts", dependency_content)
        + b"# Assigned ticket (variable context follows)\n\n"
    )
    prompt = (
        stable_prefix
        + ticket_source.content
        + (b"" if ticket_source.content.endswith(b"\n") else b"\n")
        + b"\n# Receipt handoff (attempt-specific context follows)\n\n"
        + handoff_source.content
        + (b"" if handoff_source.content.endswith(b"\n") else b"\n")
    )

    source_metadata = [
        {
            "bytes": len(source.content),
            "id": source.source_id,
            "phase": source.phase,
            "role": source.role,
            "sha256": source.sha256,
        }
        for source in [*stable_sources, *volatile_sources]
    ]
    metadata = {
        "contract": CONTRACT,
        "family": family,
        "prompt_bytes": len(prompt),
        "prompt_sha256": sha256_bytes(prompt),
        "provenance": {
            "authenticated": False,
            "method": "local-byte-digest",
        },
        "schema_version": SCHEMA_VERSION,
        "sources": source_metadata,
        "stable_prefix_bytes": len(stable_prefix),
        "stable_prefix_sha256": sha256_bytes(stable_prefix),
        "template_sha256": sha256_bytes(template_bytes),
        "template_version": version,
        "volatile_position": "last",
    }
    return RenderedContext(prompt, stable_prefix, metadata, canonical_json(metadata))


def atomic_write(path: Path, content: bytes) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, path)
        except BaseException:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise
    except OSError as exc:
        raise ContextError("write-failed", f"Could not write {path}: {exc}") from exc


def _load_manifest(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContextError("invalid-manifest", f"Could not read manifest: {exc}") from exc
    return _ensure_mapping(value, "manifest")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Render bounded, cache-oriented Gauntlet child context.")
    result.add_argument("--manifest", required=True, help="Versioned generated-context manifest JSON")
    result.add_argument("--source-root", required=True, help="Root containing all source files")
    result.add_argument("--template-root", default=str(Path(__file__).resolve().parents[1] / "templates" / "generated-context"))
    result.add_argument("--output", required=True, help="Rendered Markdown output")
    result.add_argument("--metadata-output", required=True, help="Privacy-safe metadata JSON output")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        source_root = Path(args.source_root).resolve()
        manifest_argument = Path(args.manifest)
        manifest_path = _ensure_within(
            source_root,
            manifest_argument if manifest_argument.is_absolute() else source_root / manifest_argument,
            "manifest",
        )
        output_argument = Path(args.output)
        output = _ensure_within(
            source_root,
            output_argument if output_argument.is_absolute() else source_root / output_argument,
            "output",
        )
        metadata_argument = Path(args.metadata_output)
        metadata_output = _ensure_within(
            source_root,
            metadata_argument if metadata_argument.is_absolute() else source_root / metadata_argument,
            "metadata output",
        )
        if output == metadata_output:
            raise ContextError("output-collision", "Prompt and metadata outputs must differ")
        result = render_manifest(
            _load_manifest(manifest_path),
            source_root=source_root,
            template_root=Path(args.template_root),
        )
        protected = {manifest_path}
        manifest = _load_manifest(manifest_path)
        for item in [*manifest["stable_sources"], *manifest["volatile_sources"]]:
            source_path = Path(item["path"])
            protected.add(_ensure_within(source_root, source_path if source_path.is_absolute() else source_root / source_path, "source path"))
        protected.add((Path(args.template_root).resolve() / f"{manifest['family']}-v{manifest['template_version']}.md").resolve())
        if output in protected or metadata_output in protected:
            raise ContextError("output-collision", "Outputs cannot replace manifest or source inputs")
        atomic_write(output, result.prompt)
        atomic_write(metadata_output, result.metadata_bytes)
        sys.stdout.buffer.write(result.metadata_bytes)
        return 0
    except ContextError as exc:
        print(json.dumps({"error": {"code": exc.code, "message": str(exc)}}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
