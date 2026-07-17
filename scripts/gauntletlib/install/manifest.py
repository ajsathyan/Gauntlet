"""Manifest-driven runtime payload synchronization and verification."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path

RECEIPT = Path("gauntlet/.install-manifest.json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest(root: Path) -> dict:
    path = root / "MANIFEST"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != "1.0" or not isinstance(payload.get("entries"), list):
        raise ValueError(f"Unsupported install manifest: {path}")
    return payload


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
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


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
    manifest = load_manifest(root)
    current = {row["destination"]: row for row in manifest["entries"]}
    findings: list[str] = []
    receipt = _load_receipt(agent_home)
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

    for row in manifest["entries"]:
        source = root / row["source"]
        if row["source"].startswith("skills/") and not source.exists():
            source = root.parent / row["source"]
        if _sha256(source) != row["sha256"]:
            raise ValueError(f"Source payload differs from MANIFEST: {row['source']}")
        destination = agent_home / row["destination"]
        if source.resolve() != destination.resolve():
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
