"""Manifest-driven runtime installation and ownership."""

from __future__ import annotations

import hashlib
import json
import os
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
    return PurePosixPath(value).as_posix()


def _safe_destination(agent_home: Path, value, label: str = "destination") -> Path:
    relative = _relative_path(value, label)
    if agent_home.is_symlink() or (agent_home.exists() and not agent_home.is_dir()):
        raise ValueError(f"Agent home must be a real directory: {agent_home}")
    root = agent_home.resolve(strict=False)
    destination = root / relative
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Manifest {label} traverses a symlink: {relative}")
    try:
        destination.absolute().relative_to(root)
    except ValueError as error:
        raise ValueError(f"Manifest {label} escapes agent home: {relative}") from error
    return destination


def _generated_destination(agent_home: Path, value: str) -> Path:
    if value not in GENERATED_DESTINATIONS:
        raise ValueError(f"Unsupported generated destination: {value}")
    return _safe_destination(agent_home, value, "generated destination")


def _source_path(root: Path, value) -> Path:
    relative = Path(_relative_path(value, "source"))
    if relative.parts[0] == "skills":
        source_root = root if (root / "skills").is_dir() else root.parent
        source = source_root / relative
        allowed = (source_root / "skills").resolve(strict=True)
    else:
        source = root / relative
        allowed = root.resolve(strict=True)
    try:
        resolved = source.resolve(strict=True)
    except FileNotFoundError as error:
        raise ValueError(f"Missing manifest source: {relative}") from error
    if resolved != allowed and allowed not in resolved.parents:
        raise ValueError(f"Manifest source escapes allowed root: {relative}")
    if not resolved.is_file():
        raise ValueError(f"Manifest source is not a file: {relative}")
    return resolved


def load_manifest(root: Path) -> dict:
    path = root / "MANIFEST"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != "1.0" or not isinstance(payload.get("entries"), list):
        raise ValueError(f"Unsupported install manifest: {path}")
    transfers = payload.get("ownershipTransfers", [])
    if not isinstance(transfers, list):
        raise ValueError("Manifest ownershipTransfers must be a list")
    return payload


def _validated_manifest(root: Path, agent_home: Path):
    manifest = load_manifest(root)
    prepared = []
    sources = set()
    destinations = set()
    for row in manifest["entries"]:
        if not isinstance(row, dict):
            raise ValueError("Manifest entries must be objects")
        source_value = _relative_path(row.get("source"), "source")
        destination_value = _relative_path(row.get("destination"), "destination")
        if source_value in sources or destination_value in destinations:
            raise ValueError("Manifest source and destination paths must be unique")
        if not isinstance(row.get("sha256"), str) or len(row["sha256"]) != 64:
            raise ValueError(f"Invalid manifest hash: {source_value}")
        if not isinstance(row.get("executable"), bool):
            raise ValueError(f"Invalid executable flag: {source_value}")
        sources.add(source_value)
        destinations.add(destination_value)
        prepared.append(
            (
                row,
                _source_path(root, source_value),
                _safe_destination(agent_home, destination_value),
            )
        )
    generated = manifest.get("generatedDestinations")
    if not isinstance(generated, list) or tuple(generated) != GENERATED_DESTINATIONS:
        raise ValueError("Manifest generated destinations differ from the fixed contract")
    transfers = []
    for value in manifest.get("ownershipTransfers", []):
        prefix = _relative_path(value, "ownership transfer")
        if not prefix.startswith("skills/"):
            raise ValueError(f"Ownership transfer must target a skill: {prefix}")
        transfers.append(prefix.rstrip("/") + "/")
    return manifest, prepared, tuple(transfers)


def _atomic_write(path: Path, data: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_copy(source: Path, destination: Path, executable: bool) -> None:
    _atomic_write(destination, source.read_bytes(), 0o755 if executable else 0o644)


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
    _receipt_rows(payload, agent_home)
    _generated_rows(payload, agent_home)
    return payload


def _receipt_rows(receipt: dict, agent_home: Path) -> dict[str, dict]:
    rows = {}
    for row in receipt["entries"]:
        if not isinstance(row, dict):
            raise ValueError("Invalid install ownership receipt entry")
        destination = _relative_path(row.get("destination"), "receipt destination")
        _safe_destination(agent_home, destination, "receipt destination")
        if destination in rows:
            raise ValueError("Duplicate install ownership receipt destination")
        if not isinstance(row.get("sha256"), str) or len(row["sha256"]) != 64:
            raise ValueError(f"Invalid install ownership receipt hash: {destination}")
        rows[destination] = row
    return rows


def _generated_rows(receipt: dict, agent_home: Path) -> dict[str, dict]:
    rows = {}
    entries = receipt.get("generatedEntries", [])
    if not isinstance(entries, list):
        raise ValueError("Invalid install ownership receipt generated entries")
    for row in entries:
        if not isinstance(row, dict):
            raise ValueError("Invalid generated receipt entry")
        destination = _relative_path(row.get("destination"), "generated receipt destination")
        _generated_destination(agent_home, destination)
        if destination in rows:
            raise ValueError("Duplicate generated receipt destination")
        if not isinstance(row.get("sha256"), str) or len(row["sha256"]) != 64:
            raise ValueError(f"Invalid generated receipt hash: {destination}")
        rows[destination] = row
    return rows


def _remove_empty_parents(path: Path, stop: Path) -> None:
    parent = path.parent
    while parent != stop and stop in parent.parents:
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def _remove_owned_file(path: Path, expected_sha: str, findings: list[str]) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_file() and not path.is_symlink() and _sha256(path) == expected_sha:
        path.unlink()
        return
    findings.append(f"preserved modified stale managed file: {path}")


def preflight_payload(root: Path, agent_home: Path) -> list[str]:
    manifest, prepared, transfers = _validated_manifest(root, agent_home)
    current = {row["destination"]: row for row in manifest["entries"]}
    receipt = _load_receipt(agent_home)
    receipt_rows = _receipt_rows(receipt, agent_home) if receipt else {}
    findings = []

    for row, source, destination in prepared:
        if _sha256(source) != row["sha256"]:
            raise ValueError(f"Source payload differs from MANIFEST: {row['source']}")
        if destination.exists() and not destination.is_file():
            raise ValueError(f"Manifest destination is not a file: {row['destination']}")
        if not destination.exists():
            continue
        installed_sha = _sha256(destination)
        allowed = {row["sha256"]}
        if row["destination"] in receipt_rows:
            allowed.add(receipt_rows[row["destination"]]["sha256"])
        if installed_sha not in allowed:
            owner = "prior-receipt-owned" if row["destination"] in receipt_rows else "unowned"
            raise ValueError(f"Refusing modified {owner} manifest destination: {row['destination']}")

    for destination, row in receipt_rows.items():
        if destination in current:
            continue
        path = _safe_destination(agent_home, destination, "receipt destination")
        transferred = any(destination.startswith(prefix) for prefix in transfers)
        if transferred:
            if not path.is_file() or path.is_symlink() or _sha256(path) != row["sha256"]:
                raise ValueError(f"Cannot safely transfer modified or missing personal skill: {destination}")
            continue
        if path.exists() and (
            not path.is_file() or path.is_symlink() or _sha256(path) != row["sha256"]
        ):
            findings.append(f"preserved modified stale managed file: {path}")

    manifest_path = agent_home / "gauntlet" / "MANIFEST"
    if manifest_path.exists():
        allowed = {_sha256(root / "MANIFEST")}
        if receipt:
            allowed.add(receipt["manifestSha256"])
        if _sha256(manifest_path) not in allowed:
            raise ValueError("Refusing modified installed MANIFEST")
    return findings


def sync_payload(root: Path, agent_home: Path) -> list[str]:
    findings = preflight_payload(root, agent_home)
    manifest, prepared, transfers = _validated_manifest(root, agent_home)
    current = {row["destination"] for row in manifest["entries"]}
    receipt = _load_receipt(agent_home)
    if receipt:
        for destination, row in _receipt_rows(receipt, agent_home).items():
            if destination in current or any(destination.startswith(prefix) for prefix in transfers):
                continue
            path = _safe_destination(agent_home, destination, "receipt destination")
            _remove_owned_file(path, row["sha256"], findings)
            _remove_empty_parents(path, agent_home)

    for row, source, destination in prepared:
        _atomic_copy(source, destination, row["executable"])

    manifest_destination = agent_home / "gauntlet" / "MANIFEST"
    _atomic_copy(root / "MANIFEST", manifest_destination, False)
    receipt_payload = {
        "schemaVersion": "1.0",
        "entries": [
            {"destination": row["destination"], "sha256": row["sha256"]}
            for row in manifest["entries"]
        ],
        "manifestSha256": _sha256(root / "MANIFEST"),
    }
    _atomic_write(
        agent_home / RECEIPT,
        (json.dumps(receipt_payload, indent=2, sort_keys=True) + "\n").encode(),
    )
    return findings


def preflight_generated_payload(agent_home: Path, destination: str, candidate: Path) -> None:
    installed = _generated_destination(agent_home, destination)
    if candidate.is_symlink() or not candidate.is_file():
        raise ValueError(f"Generated payload candidate is not a real file: {candidate}")
    if not installed.exists() or _sha256(installed) == _sha256(candidate):
        return
    receipt = _load_receipt(agent_home)
    owned = _generated_rows(receipt, agent_home).get(destination) if receipt else None
    if owned and _sha256(installed) == owned["sha256"]:
        return
    owner = "prior-receipt-owned" if owned else "unowned"
    raise ValueError(f"Refusing modified {owner} generated destination: {destination}")


def record_generated_payload(agent_home: Path, destination: str) -> None:
    receipt = _load_receipt(agent_home)
    if receipt is None:
        raise ValueError("Cannot record generated payload without an ownership receipt")
    path = _generated_destination(agent_home, destination)
    if not path.is_file():
        raise ValueError(f"Missing generated payload: {destination}")
    rows = _generated_rows(receipt, agent_home)
    rows[destination] = {"destination": destination, "sha256": _sha256(path)}
    receipt["generatedEntries"] = [rows[key] for key in sorted(rows)]
    _atomic_write(
        agent_home / RECEIPT,
        (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode(),
    )


def preflight_uninstall_payload(agent_home: Path):
    receipt = _load_receipt(agent_home)
    if receipt is None:
        return [], _generated_destination(agent_home, "gauntlet/MANIFEST"), ""
    rows = list(_receipt_rows(receipt, agent_home).values()) + list(
        _generated_rows(receipt, agent_home).values()
    )
    prepared = [
        (_safe_destination(agent_home, row["destination"], "receipt destination"), row["sha256"])
        for row in rows
    ]
    return prepared, _generated_destination(agent_home, "gauntlet/MANIFEST"), receipt["manifestSha256"]


def uninstall_payload(agent_home: Path) -> list[str]:
    receipt = _load_receipt(agent_home)
    if receipt is None:
        return ["no Gauntlet payload ownership receipt found; preserved installed files"]
    prepared, manifest_path, manifest_sha = preflight_uninstall_payload(agent_home)
    findings = []
    for path, expected_sha in prepared:
        _remove_owned_file(path, expected_sha, findings)
        _remove_empty_parents(path, agent_home)
    _remove_owned_file(manifest_path, manifest_sha, findings)
    receipt_path = agent_home / RECEIPT
    receipt_path.unlink()
    _remove_empty_parents(receipt_path, agent_home)
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
    elif receipt:
        for destination, row in _generated_rows(receipt, agent_home).items():
            path = _generated_destination(agent_home, destination)
            if not path.is_file():
                findings.append(f"missing generated payload: {destination}")
            elif _sha256(path) != row["sha256"]:
                findings.append(f"generated payload hash mismatch: {destination}")
    return findings
