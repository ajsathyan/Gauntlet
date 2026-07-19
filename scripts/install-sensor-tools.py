#!/usr/bin/env python3
"""Install pinned sensor tools into a machine-local Codex-owned generation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath


SCHEMA = "gauntlet.sensor-tools/v1"
RECEIPT_SCHEMA = "gauntlet.sensor-tools-receipt/v1"


class ToolInstallError(RuntimeError):
    pass


def _sha256(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(path: Path):
    raw = path.read_bytes()
    value = json.loads(raw)
    if (
        not isinstance(value, dict)
        or value.get("schema") != SCHEMA
        or not isinstance(value.get("python"), str)
        or not isinstance(value.get("tools"), dict)
    ):
        raise ToolInstallError(f"invalid sensor tool manifest: {path}")
    expected = {"coverage", "gitleaks", "semgrep"}
    if set(value["tools"]) != expected:
        raise ToolInstallError("sensor tool manifest must define coverage, gitleaks, and semgrep")
    for name, tool in value["tools"].items():
        if (
            not isinstance(tool, dict)
            or not isinstance(tool.get("version"), str)
            or tool.get("kind") not in {"uv-tool", "release-archive"}
        ):
            raise ToolInstallError(f"invalid sensor tool manifest entry: {name}")
    return raw, value


def _platform_key():
    system = platform.system().lower()
    machine = platform.machine().lower()
    aliases = {
        "aarch64": "arm64",
        "amd64": "x86_64",
        "x64": "x86_64",
    }
    machine = aliases.get(machine, machine)
    key = f"{system}-{machine}"
    if system not in {"darwin", "linux"} or machine not in {"arm64", "x86_64"}:
        raise ToolInstallError(f"unsupported sensor tool platform: {key}")
    return key


def _run(arguments, *, env=None):
    result = subprocess.run(
        arguments,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode:
        raise ToolInstallError(
            f"command failed ({result.returncode}): {' '.join(arguments)}\n"
            + result.stdout[-2000:]
        )
    return result.stdout.strip()


def _install_uv_tool(uv, generation, python_version, name, version):
    env = os.environ.copy()
    env["UV_TOOL_DIR"] = str(generation / "uv-tools")
    env["UV_TOOL_BIN_DIR"] = str(generation / "bin")
    env["UV_PYTHON_INSTALL_DIR"] = str(generation / "python")
    _run(
        [
            uv,
            "tool",
            "install",
            "--python",
            python_version,
            "--python-preference",
            "managed",
            "--reinstall",
            f"{name}=={version}",
        ],
        env=env,
    )


def _download(url, destination):
    with urllib.request.urlopen(url, timeout=120) as response:
        with destination.open("wb") as output:
            shutil.copyfileobj(response, output)


def _install_gitleaks(generation, tool, base_url):
    key = _platform_key()
    asset = tool.get("assets", {}).get(key)
    if (
        not isinstance(asset, dict)
        or not isinstance(asset.get("name"), str)
        or not isinstance(asset.get("sha256"), str)
    ):
        raise ToolInstallError(f"gitleaks has no verified asset for {key}")
    archive = generation / asset["name"]
    url = (
        f"{base_url.rstrip('/')}/{asset['name']}"
        if base_url
        else (
            "https://github.com/gitleaks/gitleaks/releases/download/"
            f"v{tool['version']}/{asset['name']}"
        )
    )
    _download(url, archive)
    if _sha256(archive) != asset["sha256"]:
        raise ToolInstallError("gitleaks archive checksum mismatch")
    with tarfile.open(archive, "r:gz") as bundle:
        members = [
            member
            for member in bundle.getmembers()
            if member.isfile() and Path(member.name).name == "gitleaks"
        ]
        if len(members) != 1:
            raise ToolInstallError("gitleaks archive must contain one executable")
        stream = bundle.extractfile(members[0])
        if stream is None:
            raise ToolInstallError("gitleaks executable could not be extracted")
        target = generation / "bin" / "gitleaks"
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as output:
            shutil.copyfileobj(stream, output)
        os.chmod(target, 0o755)
    archive.unlink()


def _verify_version(binary, arguments, expected):
    output = _run([str(binary), *arguments])
    if expected not in output:
        raise ToolInstallError(
            f"{binary.name} version mismatch: expected {expected}, got {output}"
        )
    return " ".join(output.split())[:300]


def _receipt(root, generation_name, manifest_sha, tools):
    return {
        "schema": RECEIPT_SCHEMA,
        "manifestSha256": manifest_sha,
        "currentGeneration": generation_name,
        "tools": tools,
        "root": str(root),
    }


def _owned_generation(root, receipt):
    generation_name = receipt.get("currentGeneration")
    if (
        not isinstance(generation_name, str)
        or len(generation_name) != 16
        or any(character not in "0123456789abcdef" for character in generation_name)
    ):
        raise ToolInstallError("sensor tool receipt has no valid owned generation")
    return generation_name, root / "generations" / generation_name


def _relative_content_path(value):
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\\" in value
        or value.startswith("/")
        or any(part in {"", ".", ".."} for part in value.split("/"))
        or PurePosixPath(value).as_posix() != value
    ):
        raise ToolInstallError(f"invalid sensor tool ownership path: {value!r}")
    return value


def _generation_contents(generation):
    if generation.is_symlink() or not generation.is_dir():
        raise ToolInstallError(f"sensor tool generation is missing: {generation}")
    contents = []
    for path in sorted(generation.rglob("*")):
        relative = path.relative_to(generation).as_posix()
        if path.is_symlink():
            contents.append(
                {
                    "kind": "symlink",
                    "path": relative,
                    "target": os.readlink(path),
                }
            )
        elif path.is_dir():
            contents.append({"kind": "directory", "path": relative})
        elif path.is_file():
            contents.append(
                {
                    "executable": bool(path.stat().st_mode & 0o111),
                    "kind": "file",
                    "path": relative,
                    "sha256": _sha256(path),
                }
            )
        else:
            raise ToolInstallError(
                f"unsupported sensor tool generation entry: {relative}"
            )
    return contents


def _receipt_contents(receipt):
    rows = receipt.get("contents")
    if not isinstance(rows, list):
        raise ToolInstallError(
            "sensor tool receipt has no content ownership manifest; "
            "preserving the existing generation"
        )
    contents = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ToolInstallError("invalid sensor tool content ownership entry")
        path = _relative_content_path(row.get("path"))
        if path in seen:
            raise ToolInstallError(
                f"duplicate sensor tool content ownership path: {path}"
            )
        seen.add(path)
        kind = row.get("kind")
        if kind == "file":
            if (
                not isinstance(row.get("sha256"), str)
                or len(row["sha256"]) != 64
                or not isinstance(row.get("executable"), bool)
            ):
                raise ToolInstallError(
                    f"invalid sensor tool file ownership entry: {path}"
                )
        elif kind == "symlink":
            if not isinstance(row.get("target"), str):
                raise ToolInstallError(
                    f"invalid sensor tool symlink ownership entry: {path}"
                )
        elif kind != "directory":
            raise ToolInstallError(
                f"invalid sensor tool content ownership kind: {path}"
            )
        contents.append(row)
    return sorted(contents, key=lambda row: row["path"])


def _content_drift(expected, actual):
    expected_by_path = {row["path"]: row for row in expected}
    actual_by_path = {row["path"]: row for row in actual}
    findings = []
    for path in sorted(expected_by_path.keys() - actual_by_path.keys()):
        findings.append(f"missing owned content: {path}")
    for path in sorted(expected_by_path.keys() & actual_by_path.keys()):
        if expected_by_path[path] != actual_by_path[path]:
            findings.append(f"modified owned content: {path}")
    for path in sorted(actual_by_path.keys() - expected_by_path.keys()):
        findings.append(f"unknown generation content: {path}")
    return findings


def _verify_owned_generation(generation, receipt):
    expected = _receipt_contents(receipt)
    findings = _content_drift(expected, _generation_contents(generation))
    if findings:
        raise ToolInstallError(
            "sensor tool generation content drift: " + "; ".join(findings)
        )
    return expected


def _remove_owned_generation(generation, receipt):
    expected = _receipt_contents(receipt)
    try:
        actual = _generation_contents(generation)
    except ToolInstallError:
        return [f"preserved missing or unsafe owned generation: {generation}"]
    actual_by_path = {row["path"]: row for row in actual}
    expected_by_path = {row["path"]: row for row in expected}
    findings = []

    for path in sorted(actual_by_path.keys() - expected_by_path.keys()):
        findings.append(f"preserved unknown generation content: {path}")
    for path in sorted(actual_by_path.keys() & expected_by_path.keys()):
        if actual_by_path[path] != expected_by_path[path]:
            findings.append(f"preserved modified owned content: {path}")

    non_directories = [
        row for row in expected if row["kind"] in {"file", "symlink"}
    ]
    for row in sorted(
        non_directories,
        key=lambda value: len(PurePosixPath(value["path"]).parts),
        reverse=True,
    ):
        path = generation / row["path"]
        actual_row = actual_by_path.get(row["path"])
        if actual_row == row:
            path.unlink()

    directories = [row for row in expected if row["kind"] == "directory"]
    for row in sorted(
        directories,
        key=lambda value: len(PurePosixPath(value["path"]).parts),
        reverse=True,
    ):
        path = generation / row["path"]
        if path.is_dir() and not path.is_symlink():
            try:
                path.rmdir()
            except OSError:
                pass
    try:
        generation.rmdir()
    except OSError:
        pass
    return findings


def _preserve_predecessor_generation(root, generation_name, generation):
    """Move an unverifiable predecessor generation out of the install namespace."""

    if not generation.exists() and not generation.is_symlink():
        return [
            "predecessor receipt generation is already missing; "
            "no generation content was removed"
        ]
    preserved_root = root / "preserved-generations"
    if preserved_root.is_symlink() or (
        preserved_root.exists() and not preserved_root.is_dir()
    ):
        raise ToolInstallError(
            f"cannot preserve predecessor sensor tools at {preserved_root}"
        )
    preserved_root.mkdir(parents=True, exist_ok=True)
    preserved = preserved_root / generation_name
    suffix = 1
    while preserved.exists() or preserved.is_symlink():
        preserved = preserved_root / f"{generation_name}-{suffix}"
        suffix += 1
    os.replace(generation, preserved)
    return [
        "preserved predecessor receipt generation without deleting unverifiable "
        f"content: {preserved}"
    ]


def _atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(value, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _activate(root, generation, receipt, receipt_writer=_atomic_json):
    current = root / "current"
    if current.exists() and not current.is_symlink():
        raise ToolInstallError("refusing to replace a non-symlink sensor tool activation")
    previous_target = os.readlink(current) if current.is_symlink() else None
    temporary = root / ".current.tmp"
    temporary.unlink(missing_ok=True)
    os.symlink(generation, temporary)
    os.replace(temporary, current)
    try:
        receipt_writer(root / "receipt.json", receipt)
    except BaseException:
        rollback = root / ".current.rollback"
        rollback.unlink(missing_ok=True)
        if previous_target is None:
            current.unlink(missing_ok=True)
        else:
            os.symlink(previous_target, rollback)
            os.replace(rollback, current)
        raise
    finally:
        temporary.unlink(missing_ok=True)


def install(args):
    agent_home = args.agent_home.expanduser().resolve()
    root = agent_home / "gauntlet-tools"
    manifest_raw, manifest = _load_manifest(args.manifest)
    manifest_sha = hashlib.sha256(manifest_raw).hexdigest()
    generation_name = manifest_sha[:16]
    generation = root / "generations" / generation_name
    receipt_path = root / "receipt.json"
    if generation.is_dir() and receipt_path.is_file():
        existing = json.loads(receipt_path.read_text(encoding="utf-8"))
        if (
            existing.get("schema") == RECEIPT_SCHEMA
            and existing.get("manifestSha256") == manifest_sha
            and existing.get("currentGeneration") == generation_name
        ):
            _verify_owned_generation(generation, existing)
            _activate(root, generation, existing)
            return existing
    if generation.exists():
        raise ToolInstallError(
            "refusing to replace an existing sensor tool generation without "
            "a matching verified content ownership manifest"
        )
    generation.mkdir(parents=True)
    try:
        for name in ("semgrep", "coverage"):
            tool = manifest["tools"][name]
            _install_uv_tool(
                args.uv,
                generation,
                manifest["python"],
                name,
                tool["version"],
            )
        _install_gitleaks(
            generation,
            manifest["tools"]["gitleaks"],
            args.gitleaks_base_url,
        )
        versions = {
            "semgrep": _verify_version(
                generation / "bin" / "semgrep",
                ["--version"],
                manifest["tools"]["semgrep"]["version"],
            ),
            "coverage": _verify_version(
                generation / "bin" / "coverage",
                ["--version"],
                manifest["tools"]["coverage"]["version"],
            ),
            "gitleaks": _verify_version(
                generation / "bin" / "gitleaks",
                ["version"],
                manifest["tools"]["gitleaks"]["version"],
            ),
        }
        receipt = _receipt(root, generation_name, manifest_sha, versions)
        receipt["contents"] = _generation_contents(generation)
        _activate(root, generation, receipt)
        return receipt
    except BaseException:
        current = root / "current"
        active_generation = (
            current.is_symlink()
            and current.resolve() == generation.resolve()
        )
        if not active_generation:
            shutil.rmtree(generation, ignore_errors=True)
        raise


def verify(args):
    root = args.agent_home.expanduser().resolve() / "gauntlet-tools"
    receipt_path = root / "receipt.json"
    if not receipt_path.is_file():
        raise ToolInstallError("sensor tool receipt is missing")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    _, generation = _owned_generation(root, receipt)
    current = root / "current"
    if (
        receipt.get("schema") != RECEIPT_SCHEMA
        or not generation.is_dir()
        or not current.is_symlink()
        or current.resolve() != generation.resolve()
    ):
        raise ToolInstallError("sensor tool ownership receipt does not match active tools")
    manifest_raw, manifest = _load_manifest(args.manifest)
    if receipt.get("manifestSha256") != hashlib.sha256(manifest_raw).hexdigest():
        raise ToolInstallError("sensor tool manifest differs from the active generation")
    _verify_owned_generation(generation, receipt)
    _verify_version(
        current / "bin" / "semgrep",
        ["--version"],
        manifest["tools"]["semgrep"]["version"],
    )
    _verify_version(
        current / "bin" / "coverage",
        ["--version"],
        manifest["tools"]["coverage"]["version"],
    )
    _verify_version(
        current / "bin" / "gitleaks",
        ["version"],
        manifest["tools"]["gitleaks"]["version"],
    )
    return receipt


def remove(args):
    root = args.agent_home.expanduser().resolve() / "gauntlet-tools"
    receipt_path = root / "receipt.json"
    if not receipt_path.is_file():
        return {"action": "absent"}
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise ToolInstallError("refusing to remove tools without a valid ownership receipt")
    generation_name, generation = _owned_generation(root, receipt)
    predecessor_receipt = "contents" not in receipt
    current = root / "current"
    active_owned_generation = (
        current.is_symlink() and current.resolve() == generation.resolve()
    )
    if not active_owned_generation and (current.exists() or current.is_symlink()):
        raise ToolInstallError("refusing to remove a changed sensor tool activation")
    if predecessor_receipt:
        findings = _preserve_predecessor_generation(
            root,
            generation_name,
            generation,
        )
    else:
        findings = _remove_owned_generation(generation, receipt)
    if active_owned_generation:
        current.unlink()
    receipt_path.unlink()
    for directory in (root / "generations", root):
        try:
            directory.rmdir()
        except OSError:
            pass
    return {
        "action": "removed",
        "findings": findings,
        "generation": generation_name,
    }


def build_parser():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("install", "verify", "remove"):
        command = commands.add_parser(name)
        command.add_argument("--agent-home", type=Path, required=True)
        command.add_argument(
            "--manifest",
            type=Path,
            default=root / "config" / "sensor-tools.json",
        )
        command.add_argument("--json", action="store_true")
        if name == "install":
            command.add_argument("--uv", default=shutil.which("uv") or "uv")
            command.add_argument("--gitleaks-base-url")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "install":
            result = install(args)
        elif args.command == "verify":
            result = verify(args)
        else:
            result = remove(args)
    except (OSError, ValueError, json.JSONDecodeError, ToolInstallError) as error:
        payload = {"status": "fail", "message": str(error)}
        print(json.dumps(payload, indent=2) if args.json else payload["message"])
        return 1
    payload = {"status": "pass", **result}
    print(json.dumps(payload, indent=2) if args.json else f"Sensor tools: {payload['status']}")
    if not args.json:
        for finding in payload.get("findings", []):
            print(f"Sensor tool removal finding: {finding}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
