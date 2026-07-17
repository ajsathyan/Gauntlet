"""Manifest-driven runtime payload synchronization and verification."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path, PurePosixPath

GENERATED_DESTINATIONS = (
    "gauntlet/AGENTS.md",
    "gauntlet/MANIFEST",
    "gauntlet/.install-manifest.json",
)
RECEIPT = Path(GENERATED_DESTINATIONS[-1])


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest(root: Path) -> dict:
    path = root / "MANIFEST"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != "1.0" or not isinstance(payload.get("entries"), list):
        raise ValueError(f"Unsupported install manifest: {path}")
    return payload


def _relative_path(value, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\\" in value
        or value.startswith("/")
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError(f"Invalid {label} path: {value!r}")
    normalized = PurePosixPath(value).as_posix()
    if normalized != value:
        raise ValueError(f"Invalid {label} path: {value!r}")
    return value


def _destination_path(agent_home: Path, value, label: str = "destination") -> Path:
    relative = _relative_path(value, label)
    if not relative.startswith(("gauntlet/", "skills/")):
        raise ValueError(f"Manifest {label} is outside managed namespaces: {relative}")
    if agent_home.is_symlink() or (agent_home.exists() and not agent_home.is_dir()):
        raise ValueError(f"Agent home is not a real directory: {agent_home}")
    base = agent_home.resolve(strict=False)
    destination = agent_home / relative
    resolved = destination.resolve(strict=False)
    if resolved != base and base not in resolved.parents:
        raise ValueError(f"Manifest {label} escapes agent home: {relative}")
    cursor = agent_home
    for part in PurePosixPath(relative).parts[:-1]:
        cursor = cursor / part
        if cursor.is_symlink() or (cursor.exists() and not cursor.is_dir()):
            raise ValueError(
                f"Manifest {label} has a non-directory ancestor: {relative}"
            )
    if destination.is_symlink():
        raise ValueError(f"Manifest {label} is a symlink: {relative}")
    return destination


def _generated_destination_path(agent_home: Path, value: str) -> Path:
    destination = _destination_path(agent_home, value, "generated destination")
    if destination.exists() and not destination.is_file():
        raise ValueError(f"Generated destination is not a file: {value}")
    return destination


def _source_path(root: Path, value) -> Path:
    relative = _relative_path(value, "source")
    source = root / relative
    allowed_root = root
    if relative.startswith("skills/") and not source.exists():
        source = root.parent / relative
        allowed_root = root.parent / "skills"
    try:
        resolved = source.resolve(strict=True)
    except FileNotFoundError as error:
        raise ValueError(f"Missing manifest source: {relative}") from error
    allowed = allowed_root.resolve(strict=True)
    if resolved != allowed and allowed not in resolved.parents:
        raise ValueError(f"Manifest source escapes allowed root: {relative}")
    if not resolved.is_file():
        raise ValueError(f"Manifest source is not a file: {relative}")
    return resolved


def _validated_manifest(root: Path, agent_home: Path) -> tuple[dict, list[tuple[dict, Path, Path]]]:
    manifest = load_manifest(root)
    prepared = []
    destinations = set()
    sources = set()
    for row in manifest["entries"]:
        if not isinstance(row, dict):
            raise ValueError("Manifest entries must be objects")
        source_value = _relative_path(row.get("source"), "source")
        destination_value = _relative_path(row.get("destination"), "destination")
        if source_value in sources or destination_value in destinations:
            raise ValueError("Manifest source and destination paths must be unique")
        sources.add(source_value)
        destinations.add(destination_value)
        if not isinstance(row.get("sha256"), str) or len(row["sha256"]) != 64:
            raise ValueError(f"Invalid manifest hash: {source_value}")
        if not isinstance(row.get("executable"), bool):
            raise ValueError(f"Invalid executable flag: {source_value}")
        prepared.append(
            (
                row,
                _source_path(root, source_value),
                _destination_path(agent_home, destination_value),
            )
        )
    for value in GENERATED_DESTINATIONS:
        _generated_destination_path(agent_home, value)
    generated = manifest.get("generatedDestinations")
    if not isinstance(generated, list) or tuple(generated) != GENERATED_DESTINATIONS:
        raise ValueError("Manifest generated destinations differ from the fixed contract")
    for row in manifest.get("legacyManaged", []):
        if not isinstance(row, dict) or row.get("type") not in {
            "file",
            "retired-file",
            "retired-directory",
        }:
            raise ValueError("Invalid legacy managed metadata")
        _destination_path(agent_home, row.get("destination"), "legacy destination")
    return manifest, prepared


def _atomic_copy(source: Path, destination: Path, executable: bool) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(source.read_bytes())
        os.chmod(temporary, 0o755 if executable else 0o644)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _load_receipt(agent_home: Path) -> dict | None:
    path = agent_home / RECEIPT
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid install ownership receipt: {path}") from error
    if (
        not isinstance(payload, dict)
        or payload.get("schemaVersion") != "1.0"
        or not isinstance(payload.get("entries"), list)
        or not isinstance(payload.get("manifestSha256"), str)
        or len(payload["manifestSha256"]) != 64
    ):
        raise ValueError(f"Invalid install ownership receipt: {path}")
    return payload


def _receipt_destinations(receipt: dict, agent_home: Path) -> set[str]:
    destinations = set()
    for row in receipt["entries"]:
        if not isinstance(row, dict):
            raise ValueError("Invalid install ownership receipt entry")
        value = _relative_path(row.get("destination"), "receipt destination")
        _destination_path(agent_home, value, "receipt destination")
        if value in destinations:
            raise ValueError("Duplicate install ownership receipt destination")
        destinations.add(value)
        if not isinstance(row.get("sha256"), str) or len(row["sha256"]) != 64:
            raise ValueError(f"Invalid install ownership receipt hash: {value}")
    return destinations


def _remove_empty_parents(path: Path, stop: Path) -> None:
    parent = path.parent
    while parent != stop and stop in parent.parents:
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def _safe_stale_file(path: Path, expected_sha: str | None, findings: list[str]) -> None:
    if not path.is_file() and not path.is_symlink():
        return
    if expected_sha and not path.is_symlink() and _sha256(path) == expected_sha:
        path.unlink()
        return
    findings.append(f"preserved modified stale managed file: {path}")


def _safe_stale_directory(path: Path, findings: list[str]) -> None:
    if not path.exists():
        return
    if path.is_dir() and not any(path.iterdir()):
        path.rmdir()
        return
    findings.append(f"preserved non-empty stale managed directory: {path}")


def sync_payload(root: Path, agent_home: Path) -> list[str]:
    manifest, prepared = _validated_manifest(root, agent_home)
    current = {row["destination"]: row for row in manifest["entries"]}
    findings: list[str] = []
    receipt = _load_receipt(agent_home)
    receipt_destinations = _receipt_destinations(receipt, agent_home) if receipt else set()

    # Complete every path, source, symlink, and ownership check before mutation.
    for row, source, destination in prepared:
        if _sha256(source) != row["sha256"]:
            raise ValueError(f"Source payload differs from MANIFEST: {row['source']}")
        if destination.exists() and not destination.is_file():
            raise ValueError(f"Manifest destination is not a file: {row['destination']}")
        if not destination.exists():
            continue
        if receipt:
            if row["destination"] not in receipt_destinations:
                raise ValueError(
                    f"Refusing unowned manifest destination collision: {row['destination']}"
                )
        elif row["destination"].startswith("skills/") and _sha256(destination) != row["sha256"]:
            raise ValueError(
                f"Refusing unowned skill destination collision: {row['destination']}"
            )

    if receipt:
        for row in receipt.get("entries", []):
            destination = row.get("destination")
            if destination and destination not in current:
                path = agent_home / destination
                _safe_stale_file(path, row.get("sha256"), findings)
                _remove_empty_parents(path, agent_home)
    else:
        for row in manifest.get("legacyManaged", []):
            path = agent_home / row["destination"]
            if row["type"] == "retired-directory":
                _safe_stale_directory(path, findings)
            else:
                _safe_stale_file(path, row.get("sha256"), findings)
                _remove_empty_parents(path, agent_home)

    for row, source, destination in prepared:
        if source != destination.resolve(strict=False):
            _atomic_copy(source, destination, row["executable"])

    manifest_destination = agent_home / "gauntlet" / "MANIFEST"
    if (root / "MANIFEST").resolve() != manifest_destination.resolve():
        _atomic_copy(root / "MANIFEST", manifest_destination, False)

    receipt_payload = {
        "schemaVersion": "1.0",
        "entries": [
            {"destination": row["destination"], "sha256": row["sha256"]}
            for row in manifest["entries"]
        ],
        "manifestSha256": _sha256(root / "MANIFEST"),
    }
    receipt_path = agent_home / RECEIPT
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = (json.dumps(receipt_payload, indent=2, sort_keys=True) + "\n").encode()
    if not receipt_path.is_file() or receipt_path.read_bytes() != rendered:
        fd, temporary = tempfile.mkstemp(prefix=f".{receipt_path.name}.", dir=receipt_path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(rendered)
            os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
            os.replace(temporary, receipt_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return findings


def verify_payload(root: Path, agent_home: Path) -> list[str]:
    manifest = load_manifest(root)
    findings = []
    for row in manifest["entries"]:
        path = agent_home / row["destination"]
        if not path.is_file():
            findings.append(f"missing manifest payload: {row['destination']}")
        elif _sha256(path) != row["sha256"]:
            findings.append(f"manifest hash mismatch: {row['destination']}")
    receipt = _load_receipt(agent_home)
    if not receipt or receipt.get("manifestSha256") != _sha256(root / "MANIFEST"):
        findings.append("installed ownership receipt does not match MANIFEST")
    return findings
