#!/usr/bin/env python3
"""Preservation-safe installer for Gauntlet-owned Codex custom agents."""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

MANIFEST_VERSION = 1
REQUIRED = {"name", "description", "model", "model_reasoning_effort", "developer_instructions"}
ALLOWED = REQUIRED | {"sandbox_mode"}
EXPECTED = {
    "gauntlet_fast_reader": ("gpt-5.6-luna", "medium"),
    "gauntlet_standard_worker": ("gpt-5.6-sol", "medium"),
    "gauntlet_deep_worker": ("gpt-5.6-sol", "high"),
    "gauntlet_independent_verifier": ("gpt-5.6-sol", "medium"),
    "gauntlet_release_integrator": ("gpt-5.6-terra", "high"),
    "gauntlet_deep_expert_researcher": ("gpt-5.6-sol", "xhigh"),
    "gauntlet_security_reviewer": ("gpt-5.6-sol", "high"),
}


def fail(message):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def authority_attestation(hashes):
    """Bind the read-only reviewer declaration to the installed profile set."""
    profile_set_version = digest(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode())
    return profile_set_version, {
        "profile": "gauntlet_security_reviewer",
        "profileSha256": hashes["gauntlet_security_reviewer.toml"],
        "profileSetVersion": profile_set_version,
        "sandboxMode": "read-only",
    }


def parse_profile(path):
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        fail("Cannot read custom-agent profile {}: {}".format(path, exc))
    fields = {}
    triple = re.compile(r'^([A-Za-z0-9_]+)\s*=\s*"""(.*?)"""\s*$', re.S | re.M)
    stripped = triple.sub(lambda match: "{} = \"<multiline>\"".format(match.group(1)), text)
    for line_number, line in enumerate(stripped.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r'([A-Za-z0-9_]+)\s*=\s*"((?:\\.|[^"\\])*)"', line)
        if not match:
            fail("Unsupported TOML syntax in {}:{}".format(path, line_number))
        key, value = match.groups()
        if key in fields:
            fail("Duplicate field {} in {}".format(key, path))
        fields[key] = value
    for match in triple.finditer(text):
        key = match.group(1)
        if key in fields and fields[key] != "<multiline>":
            fail("Duplicate field {} in {}".format(key, path))
        fields[key] = match.group(2)
    unknown = set(fields) - ALLOWED
    missing = REQUIRED - set(fields)
    if unknown or missing:
        fail("Invalid fields in {} (missing: {}; unknown: {})".format(path, sorted(missing), sorted(unknown)))
    return fields


def load_sources(source):
    if not source.is_dir():
        fail("Missing custom-agent source directory: {}".format(source))
    profiles = {}
    for path in sorted(source.glob("*.toml")):
        if path.name != Path(path.name).name or path.is_symlink() or not path.is_file():
            fail("Unsafe custom-agent source: {}".format(path))
        name = path.stem
        if name not in EXPECTED:
            fail("Unexpected custom-agent profile: {}".format(name))
        fields = parse_profile(path)
        if fields["name"] != name:
            fail("Profile {} must declare the same name as its filename".format(name))
        if (fields["model"], fields["model_reasoning_effort"]) != EXPECTED[name]:
            fail("Profile {} does not match its required model and reasoning effort".format(name))
        if name == "gauntlet_security_reviewer" and fields.get("sandbox_mode") != "read-only":
            fail("gauntlet_security_reviewer must be read-only")
        profiles[path.name] = {"data": path.read_bytes(), "fields": fields}
    if set(path[:-5] for path in profiles) != set(EXPECTED):
        fail("Custom-agent source must contain exactly the seven canonical profiles")
    return profiles


def load_manifest(path):
    if not path.exists():
        return {"schemaVersion": MANIFEST_VERSION, "files": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        fail("Cannot safely read custom-agent ownership manifest {}: {}".format(path, exc))
    if data.get("schemaVersion") != MANIFEST_VERSION or not isinstance(data.get("files"), dict):
        fail("Unsupported custom-agent ownership manifest: {}".format(path))
    for name, value in data["files"].items():
        if Path(name).name != name or not name.endswith(".toml") or not isinstance(value, str):
            fail("Unsafe entry in custom-agent ownership manifest: {}".format(name))
    return data


def inspect(source, agent_home):
    profiles = load_sources(source)
    manifest_path = agent_home / "gauntlet" / "install-agents-codex.json"
    pending_path = agent_home / "gauntlet" / "install-agents-codex.pending.json"
    manifest = load_manifest(manifest_path)
    destination = agent_home / "agents"
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        fail("Refusing unsafe custom-agent destination: {}".format(destination))
    old = manifest["files"]
    intended = {name: digest(profile["data"]) for name, profile in profiles.items()}
    pending = None
    if pending_path.exists():
        try:
            pending = json.loads(pending_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            fail("Cannot recover custom-agent transaction {}: {}".format(pending_path, exc))
        valid_pending = (
            pending.get("schemaVersion") == MANIFEST_VERSION
            and pending.get("intended") == intended
            and (pending.get("base") == old or old == intended)
        ) if isinstance(pending, dict) else False
        if not valid_pending:
            fail("Custom-agent transaction does not match the current source and ownership manifest")
    for name, profile in profiles.items():
        target = destination / name
        if target.exists() or target.is_symlink():
            if name not in old:
                if not pending or target.is_symlink() or not target.is_file() or digest(target.read_bytes()) != intended[name]:
                    fail("Refusing to overwrite unowned custom-agent profile: {}".format(target))
                continue
            allowed_hashes = {old[name]}
            if pending:
                allowed_hashes.add(intended[name])
            if target.is_symlink() or not target.is_file() or digest(target.read_bytes()) not in allowed_hashes:
                fail("Managed custom-agent profile was modified: {}".format(target))
    for name, recorded_hash in old.items():
        if name in profiles:
            continue
        target = destination / name
        if target.exists() or target.is_symlink():
            if target.is_symlink() or not target.is_file() or digest(target.read_bytes()) != recorded_hash:
                fail("Retired managed custom-agent profile was modified: {}".format(target))
    return profiles, manifest_path, pending_path, manifest, destination, pending


def atomic_write(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".{}.".format(path.name), dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def apply(source, agent_home):
    profiles, manifest_path, pending_path, manifest, destination, pending = inspect(source, agent_home)
    hashes = {name: digest(profile["data"]) for name, profile in profiles.items()}
    if pending is None:
        transaction = {"schemaVersion": MANIFEST_VERSION, "base": manifest["files"], "intended": hashes}
        atomic_write(pending_path, (json.dumps(transaction, indent=2, sort_keys=True) + "\n").encode())
    for name in sorted(set(manifest["files"]) - set(profiles)):
        target = destination / name
        if target.exists():
            target.unlink()
    for name, profile in profiles.items():
        target = destination / name
        if not target.exists() or target.read_bytes() != profile["data"]:
            atomic_write(target, profile["data"])
    profile_set_version, security_authority = authority_attestation(hashes)
    rendered = (json.dumps({
        "schemaVersion": MANIFEST_VERSION,
        "profileSetVersion": profile_set_version,
        "securityReviewerAuthority": security_authority,
        "files": hashes,
    }, indent=2, sort_keys=True) + "\n").encode()
    atomic_write(manifest_path, rendered)
    pending_path.unlink()


def verify(source, agent_home):
    profiles, manifest_path, pending_path, manifest, destination, pending = inspect(source, agent_home)
    if pending is not None:
        fail("Custom-agent installation has an incomplete recoverable transaction")
    expected_hashes = {name: digest(profile["data"]) for name, profile in profiles.items()}
    if manifest["files"] != expected_hashes:
        fail("Custom-agent ownership manifest does not match the canonical profiles")
    profile_set_version, security_authority = authority_attestation(expected_hashes)
    if manifest.get("profileSetVersion") != profile_set_version:
        fail("Custom-agent profile-set version does not match the canonical profiles")
    if manifest.get("securityReviewerAuthority") != security_authority:
        fail("Installed security reviewer authority is not validated for this profile-set version")
    for name, expected_hash in expected_hashes.items():
        target = destination / name
        if not target.is_file() or target.is_symlink() or digest(target.read_bytes()) != expected_hash:
            fail("Installed custom-agent profile does not verify: {}".format(target))
    print("Verified {} Gauntlet custom-agent profiles.".format(len(expected_hashes)))


def inspect_remove(agent_home):
    manifest_path = agent_home / "gauntlet" / "install-agents-codex.json"
    pending_path = agent_home / "gauntlet" / "install-agents-codex.pending.json"
    if pending_path.exists():
        fail("Cannot uninstall during an incomplete custom-agent transaction")
    manifest = load_manifest(manifest_path)
    destination = agent_home / "agents"
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        fail("Refusing unsafe custom-agent destination: {}".format(destination))
    return manifest_path, manifest, destination


def remove(agent_home):
    manifest_path, manifest, destination = inspect_remove(agent_home)
    for name, recorded_hash in manifest["files"].items():
        target = destination / name
        if not target.exists():
            continue
        if target.is_symlink() or not target.is_file() or digest(target.read_bytes()) != recorded_hash:
            print(
                "Gauntlet installer finding: preserved modified managed custom-agent profile: {}".format(
                    target
                ),
                file=sys.stderr,
            )
            continue
        target.unlink()
    if manifest_path.exists():
        manifest_path.unlink()
    try:
        destination.rmdir()
    except OSError:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("check", "apply", "verify", "check-remove", "remove")
    )
    parser.add_argument("--source", type=Path)
    parser.add_argument("--agent-home", type=Path, required=True)
    args = parser.parse_args()
    if args.action not in {"check-remove", "remove"} and args.source is None:
        parser.error("--source is required for check, apply, and verify")
    if args.action == "check":
        inspect(args.source, args.agent_home)
    elif args.action == "apply":
        apply(args.source, args.agent_home)
    elif args.action == "verify":
        verify(args.source, args.agent_home)
    elif args.action == "check-remove":
        inspect_remove(args.agent_home)
    else:
        remove(args.agent_home)


if __name__ == "__main__":
    main()
