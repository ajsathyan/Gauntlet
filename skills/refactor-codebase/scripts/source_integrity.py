#!/usr/bin/env python3
"""Create and compare read-only integrity snapshots of a Git source tree.

Exit codes: 0 success/match, 1 comparison mismatch, 2 invalid input or runtime error.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence


SCHEMA_VERSION = 1


class IntegrityError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def emit(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))


def git(root: Path, args: Sequence[str], *, allow_failure: bool = False) -> str:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    completed = subprocess.run(
        ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    if completed.returncode != 0 and not allow_failure:
        message = completed.stderr.strip() or completed.stdout.strip() or "Git command failed"
        raise IntegrityError("git-command-failed", message)
    return completed.stdout


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def filesystem_record(path: Path) -> Dict[str, Any]:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return {"state": "missing"}
    permissions = format(stat.S_IMODE(metadata.st_mode), "04o")
    if stat.S_ISLNK(metadata.st_mode):
        target = os.readlink(str(path))
        return {
            "state": "present",
            "kind": "symlink",
            "permissions": permissions,
            "target": target,
            "sha256": hashlib.sha256(target.encode("utf-8", errors="surrogateescape")).hexdigest(),
        }
    if stat.S_ISREG(metadata.st_mode):
        return {
            "state": "present",
            "kind": "file",
            "permissions": permissions,
            "size": metadata.st_size,
            "sha256": sha256_file(path),
        }
    if stat.S_ISDIR(metadata.st_mode):
        return {"state": "present", "kind": "directory", "permissions": permissions}
    return {"state": "present", "kind": "other", "permissions": permissions}


def index_entries(root: Path) -> List[Dict[str, str]]:
    raw = git(root, ["ls-files", "--stage", "-z"])
    entries: List[Dict[str, str]] = []
    for record in raw.split("\0"):
        if not record:
            continue
        try:
            metadata, path = record.split("\t", 1)
            mode, object_id, stage = metadata.split(" ", 2)
        except ValueError as exc:
            raise IntegrityError("unexpected-git-output", "Could not parse git ls-files output") from exc
        entries.append({"path": path, "indexMode": mode, "indexObject": object_id, "stage": stage})
    return sorted(entries, key=lambda item: (item["path"], item["stage"]))


def submodule_record(root: Path, entry: Dict[str, str]) -> Dict[str, Any]:
    path = root / entry["path"]
    record: Dict[str, Any] = {
        "path": entry["path"],
        "indexObject": entry["indexObject"],
        "filesystem": filesystem_record(path),
    }
    if path.is_dir():
        head = git(path, ["rev-parse", "--verify", "HEAD"], allow_failure=True).strip()
        status = git(
            path,
            ["status", "--porcelain=v2", "--branch", "--untracked-files=all"],
            allow_failure=True,
        )
        record["head"] = head or None
        record["statusPorcelainV2"] = status.splitlines()
    else:
        record["head"] = None
        record["statusPorcelainV2"] = []
    return record


def snapshot(root: Path) -> Dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise IntegrityError("source-not-directory", f"Source is not a directory: {root}")
    inside = git(root, ["rev-parse", "--is-inside-work-tree"], allow_failure=True).strip()
    if inside != "true":
        raise IntegrityError("not-git-work-tree", f"Source is not a Git work tree: {root}")

    tracked: List[Dict[str, Any]] = []
    submodules: List[Dict[str, Any]] = []
    for entry in index_entries(root):
        if entry["indexMode"] == "160000":
            submodules.append(submodule_record(root, entry))
            continue
        tracked.append({**entry, "filesystem": filesystem_record(root / entry["path"])})

    head = git(root, ["rev-parse", "--verify", "HEAD"], allow_failure=True).strip()
    status_lines = git(
        root,
        ["status", "--porcelain=v2", "--branch", "--untracked-files=all"],
    ).splitlines()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "sourceRoot": str(root),
        "head": head or None,
        "statusPorcelainV2": status_lines,
        "trackedFiles": tracked,
        "submodules": submodules,
        "hashAlgorithm": "sha256",
        "readOnlyGitPolicy": {
            "gitOptionalLocks": False,
            "fsmonitor": False,
            "description": "All Git inspection commands disable optional locks and fsmonitor refreshes.",
        },
    }


def ensure_output_outside_source(output: Path, root: Path) -> None:
    output_resolved = output.resolve()
    root_resolved = root.resolve()
    try:
        output_resolved.relative_to(root_resolved)
    except ValueError:
        return
    raise IntegrityError("output-inside-source", "Snapshot output must be outside the protected source tree")


def write_output(path: Optional[Path], payload: Dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def load_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityError("invalid-snapshot", f"Could not read snapshot: {exc}") from exc
    if not isinstance(value, dict) or value.get("schemaVersion") != SCHEMA_VERSION:
        raise IntegrityError("invalid-snapshot", f"Expected source snapshot schemaVersion {SCHEMA_VERSION}")
    return value


def command_snapshot(args: argparse.Namespace) -> int:
    root = Path(args.source)
    output = Path(args.output) if args.output else None
    if output is not None:
        ensure_output_outside_source(output, root)
    payload = snapshot(root)
    write_output(output, payload)
    emit(payload)
    return 0


def command_compare(args: argparse.Namespace) -> int:
    expected = load_json(Path(args.snapshot))
    actual = snapshot(Path(args.source))
    compared_fields = ["head", "statusPorcelainV2", "trackedFiles", "submodules"]
    changed_fields = [field for field in compared_fields if expected.get(field) != actual.get(field)]
    report = {
        "schemaVersion": SCHEMA_VERSION,
        "match": not changed_fields,
        "changedFields": changed_fields,
        "expectedSourceRoot": expected.get("sourceRoot"),
        "actualSourceRoot": actual.get("sourceRoot"),
        "comparedFields": compared_fields,
    }
    emit(report)
    return 0 if report["match"] else 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Snapshot or compare a Git source tree without mutating its repository state.")
    subparsers = root.add_subparsers(dest="command", required=True)
    take = subparsers.add_parser("snapshot", help="Emit a deterministic source integrity snapshot.")
    take.add_argument("source", help="Protected Git working tree to inspect.")
    take.add_argument("--output", help="Optional JSON path outside the protected source tree.")
    take.set_defaults(handler=command_snapshot)
    compare = subparsers.add_parser("compare", help="Compare a source tree with a prior snapshot.")
    compare.add_argument("source", help="Protected Git working tree to inspect.")
    compare.add_argument("snapshot", help="Prior snapshot JSON file.")
    compare.set_defaults(handler=command_compare)
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        return int(args.handler(args))
    except IntegrityError as exc:
        emit({"error": {"code": exc.code, "message": str(exc)}})
        return 2
    except OSError as exc:
        emit({"error": {"code": "io-error", "message": str(exc)}})
        return 2


if __name__ == "__main__":
    sys.exit(main())
