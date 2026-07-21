"""Codex-only installer behavior."""

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from tests.workflow.fixtures import ROOT, SCRIPTS


def run_install(agent_home, *extra, check=True):
    env = os.environ.copy()
    env["AGENT_HOME"] = str(agent_home)
    result = subprocess.run(
        [str(SCRIPTS / "install.sh"), "--target", "codex", "--skip-git-hooks", *extra],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return result


def test_install_preserves_personal_state_and_is_idempotent():
    with tempfile.TemporaryDirectory() as temporary:
        home = Path(temporary) / "codex"
        home.mkdir()
        agents = b"Personal instruction.\n"
        config = b'model = "personal"\n'
        (home / "AGENTS.md").write_bytes(agents)
        (home / "config.toml").write_bytes(config)

        check = run_install(home, "--check", "--instructions-reviewed")
        if check.returncode or sorted(path.name for path in home.iterdir()) != ["AGENTS.md", "config.toml"]:
            raise AssertionError("check mode must be read-only")

        run_install(home, "--instructions-reviewed")
        first_agents = (home / "AGENTS.md").read_bytes()
        first_receipt = (home / "gauntlet" / ".install-manifest.json").read_bytes()
        if not first_agents.startswith(agents):
            raise AssertionError("personal instructions changed")
        if (home / "config.toml").read_bytes() != config:
            raise AssertionError("installer changed unrelated Codex config")
        if first_agents.count(b"BEGIN GAUNTLET MANAGED BLOCK") != 1:
            raise AssertionError("managed router block is not singular")

        installed_router = home / "gauntlet" / "AGENTS.md"
        router_bytes = installed_router.read_bytes()
        installed_router.write_bytes(router_bytes + b"tampered\n")
        verify = subprocess.run(
            [
                "python3",
                str(home / "gauntlet" / "scripts" / "gauntlet.py"),
                "install",
                "verify",
                "--target",
                "codex",
                "--agent-home",
                str(home),
                "--json",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if verify.returncode == 0:
            raise AssertionError("install verify accepted a modified generated router")
        installed_router.write_bytes(router_bytes)

        run_install(home)
        if (home / "AGENTS.md").read_bytes() != first_agents:
            raise AssertionError("repeat install changed router bytes")
        if (home / "gauntlet" / ".install-manifest.json").read_bytes() != first_receipt:
            raise AssertionError("repeat install changed ownership receipt")

        run_install(home, "--uninstall")
        if (home / "AGENTS.md").read_bytes().strip() != agents.strip():
            raise AssertionError("uninstall changed personal instructions")
        if (home / "config.toml").read_bytes() != config:
            raise AssertionError("uninstall changed unrelated config")


def test_install_transfers_personal_skills_and_retires_stale_payload():
    with tempfile.TemporaryDirectory() as temporary:
        home = Path(temporary) / "codex"
        gauntlet = home / "gauntlet"
        gauntlet.mkdir(parents=True)
        entries = []
        names = (
            "craft-customer-email",
            "craft-product-terminology",
            "promotion-scanner",
        )
        for name in names:
            path = home / "skills" / name / "SKILL.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"personal {name}\n")
            entries.append(
                {
                    "destination": f"skills/{name}/SKILL.md",
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
        stale = gauntlet / "stale.txt"
        stale.write_text("stale\n")
        entries.append(
            {
                "destination": "gauntlet/stale.txt",
                "sha256": hashlib.sha256(stale.read_bytes()).hexdigest(),
            }
        )
        old_manifest = gauntlet / "MANIFEST"
        old_manifest.write_text("{}\n")
        receipt = {
            "schemaVersion": "1.0",
            "entries": entries,
            "manifestSha256": hashlib.sha256(old_manifest.read_bytes()).hexdigest(),
        }
        (gauntlet / ".install-manifest.json").write_text(json.dumps(receipt))

        before = {name: (home / "skills" / name / "SKILL.md").read_bytes() for name in names}
        run_install(home)
        if stale.exists():
            raise AssertionError("unchanged stale payload was not retired")
        new_receipt = json.loads((gauntlet / ".install-manifest.json").read_text())
        destinations = {row["destination"] for row in new_receipt["entries"]}
        for name, expected in before.items():
            path = home / "skills" / name / "SKILL.md"
            if path.read_bytes() != expected:
                raise AssertionError(f"personal skill changed: {name}")
            if any(value.startswith(f"skills/{name}/") for value in destinations):
                raise AssertionError(f"personal skill remains Gauntlet-owned: {name}")


def test_install_rejects_malformed_and_modified_owned_state():
    with tempfile.TemporaryDirectory() as temporary:
        real_home = Path(temporary) / "real"
        real_home.mkdir()
        linked_home = Path(temporary) / "linked"
        linked_home.symlink_to(real_home, target_is_directory=True)
        result = run_install(linked_home, "--instructions-reviewed", check=False)
        if result.returncode == 0 or list(real_home.iterdir()):
            raise AssertionError("symlinked agent home must fail without mutation")

    with tempfile.TemporaryDirectory() as temporary:
        home = Path(temporary) / "codex"
        home.mkdir()
        malformed = b"<!-- BEGIN GAUNTLET MANAGED BLOCK -->\nmissing end\n"
        (home / "AGENTS.md").write_bytes(malformed)
        result = run_install(home, check=False)
        if result.returncode == 0 or (home / "AGENTS.md").read_bytes() != malformed:
            raise AssertionError("malformed managed block must fail without mutation")

    with tempfile.TemporaryDirectory() as temporary:
        home = Path(temporary) / "codex"
        path = home / "skills" / "craft-customer-email" / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("modified\n")
        old_manifest = home / "gauntlet" / "MANIFEST"
        old_manifest.parent.mkdir(parents=True)
        old_manifest.write_text("{}\n")
        receipt = {
            "schemaVersion": "1.0",
            "entries": [{"destination": "skills/craft-customer-email/SKILL.md", "sha256": "0" * 64}],
            "manifestSha256": hashlib.sha256(old_manifest.read_bytes()).hexdigest(),
        }
        (home / "gauntlet" / ".install-manifest.json").write_text(json.dumps(receipt))
        before = path.read_bytes()
        result = run_install(home, check=False)
        if result.returncode == 0 or path.read_bytes() != before:
            raise AssertionError("modified ownership transfer must fail closed")
