"""Shared paths, subprocess helpers, and repository fixtures."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
SKILLS = ROOT / "skills" if (ROOT / "skills").exists() else ROOT.parent / "skills"
AGENTS_MD = ROOT / "AGENTS.md" if (ROOT / "AGENTS.md").exists() else ROOT.parent / "AGENTS.md"
ROUTER_MD = ROOT / "router" / "AGENTS.md" if (ROOT / "router" / "AGENTS.md").exists() else AGENTS_MD


def read(path):
    return path.read_text()


def run(args, cwd=None, check=True, input_text=None):
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"{args} failed with {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def assert_contains(text, needle, label):
    if needle not in text:
        raise AssertionError(f"{label} missing: {needle}")


def assert_not_contains(text, needle, label):
    if needle in text:
        raise AssertionError(f"{label} should not contain: {needle}")


def git(args, cwd):
    return run(["git", *args], cwd=cwd)


def init_repo(root):
    root.mkdir()
    git(["init"], cwd=root)
    git(["config", "user.email", "gauntlet@example.test"], cwd=root)
    git(["config", "user.name", "Gauntlet Test"], cwd=root)


def commit_all(root, message):
    git(["add", "."], cwd=root)
    git(["commit", "-m", message], cwd=root)
