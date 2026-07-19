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
CONTROLLER_ERA_DESTINATIONS = {
    "gauntlet/scripts/prd-run.py",
    "gauntlet/scripts/gauntletlib/run/controller.py",
    "gauntlet/scripts/progress-dashboard.py",
}
LIVE_CONTROLLER_STATES = {
    "discussing",
    "accepted",
    "compiled",
    "executing",
    "integrating",
    "epic_verified",
    "merged",
    "deployed",
    "production_verified",
}
CONTROLLER_MERGE_LEASE_SCHEMA = "gauntlet.epic-merge-lease.v1"


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


def _generated_receipt_entries(receipt: dict, agent_home: Path) -> list[dict]:
    entries = receipt.get("generatedEntries", [])
    if not isinstance(entries, list):
        raise ValueError("Invalid install ownership receipt generated entries")
    prepared = []
    destinations = set()
    for row in entries:
        if not isinstance(row, dict):
            raise ValueError("Invalid install ownership receipt generated entry")
        value = _relative_path(row.get("destination"), "generated receipt destination")
        if value not in GENERATED_DESTINATIONS[:-1]:
            raise ValueError(f"Unsupported generated receipt destination: {value}")
        _generated_destination_path(agent_home, value)
        if value in destinations:
            raise ValueError("Duplicate generated install ownership receipt destination")
        destinations.add(value)
        if not isinstance(row.get("sha256"), str) or len(row["sha256"]) != 64:
            raise ValueError(f"Invalid generated install ownership receipt hash: {value}")
        prepared.append(row)
    return prepared


def _is_controller_era_receipt(receipt: dict | None, agent_home: Path) -> bool:
    if receipt is None:
        return False
    destinations = _receipt_destinations(receipt, agent_home)
    return bool(destinations & CONTROLLER_ERA_DESTINATIONS)


def _controller_merge_lease_state(path: Path) -> str:
    """Return ``active`` or ``released`` for one historical merge lease."""

    try:
        lease = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(
            f"Cannot determine controller merge lease state from {path}: {error}"
        ) from error
    if (
        not isinstance(lease, dict)
        or lease.get("schemaVersion") != CONTROLLER_MERGE_LEASE_SCHEMA
    ):
        raise ValueError(f"Cannot determine controller merge lease state from {path}")

    statuses = []
    for key in ("status", "state"):
        value = lease.get(key)
        if value is not None:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"Cannot determine controller merge lease state from {path}"
                )
            normalized = value.strip().lower()
            if normalized not in {
                "active",
                "acquired",
                "held",
                "inactive",
                "released",
            }:
                raise ValueError(
                    f"Cannot determine controller merge lease state from {path}"
                )
            statuses.append(normalized)
    active_marker = lease.get("active")
    if active_marker is not None and not isinstance(active_marker, bool):
        raise ValueError(f"Cannot determine controller merge lease state from {path}")
    released_at = lease.get("releasedAt")
    if released_at is not None and (
        not isinstance(released_at, str) or not released_at.strip()
    ):
        raise ValueError(f"Cannot determine controller merge lease state from {path}")

    released_status = any(value in {"inactive", "released"} for value in statuses)
    active_status = any(value in {"active", "acquired", "held"} for value in statuses)
    released_marker = active_marker is False or released_at is not None
    if (released_status or released_marker) and not (
        active_marker is True or active_status
    ):
        return "released"
    if released_status or released_marker:
        raise ValueError(
            f"Cannot determine controller merge lease state from {path}: "
            "conflicting active and released markers"
        )

    required = {
        "coverageSha256": 64,
        "epicId": None,
        "candidateHead": None,
        "baseHead": None,
        "baseRef": None,
    }
    for key, length in required.items():
        value = lease.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Cannot determine controller merge lease state from {path}")
        if length is not None and len(value) != length:
            raise ValueError(f"Cannot determine controller merge lease state from {path}")
    return "active"


def preflight_product_cutover(
    agent_home: Path,
    project_roots: list[Path],
    *,
    confirmed_no_unscanned_live_work: bool = False,
) -> list[str]:
    """Reject a controller-era upgrade when detectable execution work is live.

    Detection is intentionally bounded to explicitly supplied project roots. Each
    root is inspected at local-docs/executions/*/manifest.json and for historical
    **/*.merge-lease.json files. Historical state is never changed.
    """

    receipt = _load_receipt(agent_home)
    if not _is_controller_era_receipt(receipt, agent_home):
        return []
    if not project_roots and not confirmed_no_unscanned_live_work:
        raise ValueError(
            "Controller-era Gauntlet is installed. Product-cut installation requires "
            "at least one --cutover-project-root to inspect, or "
            "--confirm-no-live-controller-work after checking every other project. "
            "The installer can only detect local-docs/executions/*/manifest.json "
            "and **/*.merge-lease.json under project roots you "
            "explicitly provide."
        )

    live = []
    findings = []
    seen = set()
    for supplied in project_roots:
        root = supplied.expanduser().absolute()
        if root in seen:
            continue
        seen.add(root)
        if root.is_symlink() or not root.is_dir():
            raise ValueError(f"Cutover project root must be a real directory: {root}")
        local_docs = root / "local-docs"
        if local_docs.exists() and (
            local_docs.is_symlink() or not local_docs.is_dir()
        ):
            raise ValueError(f"Unsafe controller document directory: {local_docs}")
        executions = root / "local-docs" / "executions"
        if executions.exists():
            if executions.is_symlink() or not executions.is_dir():
                raise ValueError(f"Unsafe controller execution directory: {executions}")
            for manifest_path in sorted(executions.glob("*/manifest.json")):
                if manifest_path.is_symlink() or not manifest_path.is_file():
                    raise ValueError(f"Unsafe controller run manifest: {manifest_path}")
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise ValueError(
                        f"Cannot determine controller run state from {manifest_path}: {error}"
                    ) from error
                if not isinstance(manifest, dict) or not isinstance(manifest.get("state"), str):
                    raise ValueError(
                        f"Cannot determine controller run state from {manifest_path}"
                    )
                state = manifest["state"]
                if state in LIVE_CONTROLLER_STATES:
                    live.append(f"{manifest_path.parent.name} ({state})")
                elif state != "complete":
                    findings.append(
                        f"preserved historical controller run with legacy state {state}: "
                        f"{manifest_path.parent}"
                    )
        for lease_path in sorted(root.rglob("*.merge-lease.json")):
            if lease_path.is_symlink() or not lease_path.is_file():
                raise ValueError(f"Unsafe controller merge lease: {lease_path}")
            state = _controller_merge_lease_state(lease_path)
            if state == "active":
                live.append(f"{lease_path} (active merge lease)")
            else:
                findings.append(
                    "preserved released historical controller merge lease: "
                    f"{lease_path}"
                )
    if live:
        raise ValueError(
            "Refusing product cut while controller-era work is live: "
            + ", ".join(live)
            + ". Complete or explicitly close those runs before installing."
        )
    return findings


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
    receipt_rows = (
        {row["destination"]: row for row in receipt["entries"]}
        if receipt
        else {}
    )
    legacy_hashes: dict[str, set[str]] = {}
    for row in manifest.get("legacyManaged", []):
        destination = row.get("destination")
        expected_sha = row.get("sha256")
        if (
            isinstance(destination, str)
            and isinstance(expected_sha, str)
            and len(expected_sha) == 64
        ):
            legacy_hashes.setdefault(destination, set()).add(expected_sha)

    # Complete every path, source, symlink, and ownership check before mutation.
    for row, source, destination in prepared:
        if _sha256(source) != row["sha256"]:
            raise ValueError(f"Source payload differs from MANIFEST: {row['source']}")
        if destination.exists() and not destination.is_file():
            raise ValueError(f"Manifest destination is not a file: {row['destination']}")
        if not destination.exists():
            continue
        installed_sha = _sha256(destination)
        allowed_hashes = {
            row["sha256"],
            *legacy_hashes.get(row["destination"], set()),
        }
        if receipt:
            if row["destination"] in receipt_destinations:
                allowed_hashes.add(receipt_rows[row["destination"]]["sha256"])
            if installed_sha not in allowed_hashes:
                if row["destination"] in receipt_destinations:
                    raise ValueError(
                        "Refusing modified prior-receipt-owned manifest destination: "
                        f"{row['destination']}"
                    )
                raise ValueError(
                    f"Refusing unowned manifest destination collision: {row['destination']}"
                )
        elif installed_sha not in allowed_hashes:
            raise ValueError(
                f"Refusing unowned manifest destination collision: {row['destination']}"
            )

    manifest_destination = agent_home / "gauntlet" / "MANIFEST"
    if manifest_destination.exists():
        installed_manifest_sha = _sha256(manifest_destination)
        allowed_manifest_hashes = {
            _sha256(root / "MANIFEST"),
            *legacy_hashes.get("gauntlet/MANIFEST", set()),
        }
        if receipt:
            allowed_manifest_hashes.add(receipt["manifestSha256"])
        if installed_manifest_sha not in allowed_manifest_hashes:
            owner = "prior-receipt-owned" if receipt else "unowned"
            raise ValueError(
                f"Refusing modified {owner} generated destination: gauntlet/MANIFEST"
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


def preflight_generated_payload(
    agent_home: Path,
    destination: str,
    candidate: Path,
    *,
    legacy_container: Path | None = None,
) -> None:
    """Reject replacement of modified or unowned installer-rendered bytes."""

    installed = _generated_destination_path(agent_home, destination)
    if candidate.is_symlink() or not candidate.is_file():
        raise ValueError(f"Generated payload candidate is not a real file: {candidate}")
    if not installed.exists():
        return
    candidate_sha = _sha256(candidate)
    installed_sha = _sha256(installed)
    if installed_sha == candidate_sha:
        return
    receipt = _load_receipt(agent_home)
    if receipt is not None:
        generated = {
            row["destination"]: row
            for row in _generated_receipt_entries(receipt, agent_home)
        }
        owned = generated.get(destination)
        if owned is not None and installed_sha == owned["sha256"]:
            return
        if owned is not None:
            raise ValueError(
                f"Refusing modified prior-receipt-owned generated destination: "
                f"{destination}"
            )
    elif legacy_container is not None and legacy_container.is_file():
        installed_bytes = installed.read_bytes()
        container_bytes = legacy_container.read_bytes()
        if (
            installed_bytes
            and b"<!-- BEGIN GAUNTLET MANAGED BLOCK -->" not in container_bytes
            and b"<!-- END GAUNTLET MANAGED BLOCK -->" not in container_bytes
            and container_bytes.count(installed_bytes) == 1
        ):
            return
    raise ValueError(f"Refusing unowned generated destination collision: {destination}")


def record_generated_payload(agent_home: Path, destination: str) -> None:
    """Add an installer-rendered file to the ownership receipt after it is written."""

    receipt = _load_receipt(agent_home)
    if receipt is None:
        raise ValueError("Cannot record generated payload without an ownership receipt")
    path = _generated_destination_path(agent_home, destination)
    if not path.is_file():
        raise ValueError(f"Missing generated payload: {destination}")
    entries = {
        row["destination"]: row
        for row in _generated_receipt_entries(receipt, agent_home)
    }
    entries[destination] = {"destination": destination, "sha256": _sha256(path)}
    receipt["generatedEntries"] = [entries[key] for key in sorted(entries)]
    receipt_path = agent_home / RECEIPT
    rendered = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    fd, temporary = tempfile.mkstemp(prefix=f".{receipt_path.name}.", dir=receipt_path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(rendered)
        os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        os.replace(temporary, receipt_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def uninstall_payload(agent_home: Path) -> list[str]:
    """Remove only byte-identical files named by the installation receipt."""

    receipt = _load_receipt(agent_home)
    if receipt is None:
        return ["no Gauntlet payload ownership receipt found; preserved installed files"]
    prepared, manifest_path, manifest_sha = preflight_uninstall_payload(agent_home)
    findings: list[str] = []

    for path, expected_sha in prepared:
        _safe_stale_file(path, expected_sha, findings)
        _remove_empty_parents(path, agent_home)
    _safe_stale_file(manifest_path, manifest_sha, findings)

    receipt_path = agent_home / RECEIPT
    receipt_path.unlink()
    _remove_empty_parents(receipt_path, agent_home)
    return findings


def preflight_uninstall_payload(
    agent_home: Path,
) -> tuple[list[tuple[Path, str]], Path, str]:
    """Validate every receipt-owned path without changing installed state."""

    receipt = _load_receipt(agent_home)
    if receipt is None:
        return [], _generated_destination_path(agent_home, "gauntlet/MANIFEST"), ""
    _receipt_destinations(receipt, agent_home)
    generated = _generated_receipt_entries(receipt, agent_home)
    rows = list(receipt["entries"]) + generated
    prepared = [
        (
            _destination_path(agent_home, row["destination"], "receipt destination"),
            row["sha256"],
        )
        for row in rows
    ]
    return (
        prepared,
        _generated_destination_path(agent_home, "gauntlet/MANIFEST"),
        receipt["manifestSha256"],
    )


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
