#!/usr/bin/env python3
"""Install pinned optional sensor tools into a Codex-owned generation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path


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
            _activate(root, generation, existing)
            return existing
    if generation.exists():
        shutil.rmtree(generation)
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
    generation = root / "generations" / receipt.get("currentGeneration", "")
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
    generation_name = receipt.get("currentGeneration")
    if not isinstance(generation_name, str) or not generation_name:
        raise ToolInstallError("sensor tool receipt has no owned generation")
    current = root / "current"
    generation = root / "generations" / generation_name
    if current.is_symlink() and current.resolve() == generation.resolve():
        current.unlink()
    elif current.exists() or current.is_symlink():
        raise ToolInstallError("refusing to remove a changed sensor tool activation")
    shutil.rmtree(generation, ignore_errors=True)
    receipt_path.unlink()
    return {"action": "removed", "generation": generation_name}


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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
