"""Skill-change guard behavior."""

import os
import subprocess
import shutil
import tempfile
from pathlib import Path

from tests.workflow.fixtures import ROOT, SCRIPTS, assert_contains, run


def test_skill_changes_are_guarded_by_pre_commit():
    hook_installer = SCRIPTS / "install-git-hooks.sh"
    skill_check = SCRIPTS / "run-skill-change-checks.sh"
    for path in (hook_installer, skill_check):
        if not path.exists() or not os.access(path, os.X_OK):
            raise AssertionError(f"missing executable skill guard: {path}")

    with tempfile.TemporaryDirectory() as temporary:
        repo = Path(temporary) / "repo"
        (repo / "scripts").mkdir(parents=True)
        (repo / "skills" / "design").mkdir(parents=True)
        shutil.copy2(skill_check, repo / "scripts" / skill_check.name)
        skill = repo / "skills" / "design" / "SKILL.md"
        skill.write_text("---\nname: design\ndescription: test\n---\n")
        run(["git", "init", "-q"], cwd=repo)
        run(["git", "add", "."], cwd=repo)
        run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "base"], cwd=repo)
        skill.unlink()
        run(["git", "add", "-u"], cwd=repo)
        result = run([str(repo / "scripts" / skill_check.name), "--detect-only"], cwd=repo)
        assert_contains(result.stdout, "Gauntlet skill changes detected: design", "skill deletion guard")

    result = run([str(skill_check), "--changed-files", "skills/design/SKILL.md"], cwd=ROOT)
    assert_contains(result.stdout, "skill structural lint: passed", "retained skill lint")

    with tempfile.TemporaryDirectory() as temporary:
        repo = Path(temporary) / "repo"
        repo.mkdir()
        run(["git", "init", "-q"], cwd=repo)
        hook = repo / ".git" / "hooks" / "pre-commit"
        original = b"#!/usr/bin/env bash\necho user-hook\n"
        hook.write_bytes(original)
        hook.chmod(0o755)
        unavailable_root = Path(temporary) / "runtime-without-dev-tools"
        unavailable_root.mkdir()
        preflight = subprocess.run(
            [
                str(hook_installer),
                "--repo",
                str(repo),
                "--gauntlet-root",
                str(unavailable_root),
                "--check",
            ],
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if preflight.returncode == 0 or hook.read_bytes() != original:
            raise AssertionError("hook preflight accepted a missing runner or mutated the user hook")
        result = subprocess.run(
            [
                str(hook_installer),
                "--repo",
                str(repo),
                "--gauntlet-root",
                str(unavailable_root),
            ],
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode == 0:
            raise AssertionError("hook installer accepted a missing skill-check runner")
        if hook.read_bytes() != original or hook.with_name("pre-commit.gauntlet-backup").exists():
            raise AssertionError("failed hook preflight mutated the existing user hook")

        target_runner = repo / "scripts" / skill_check.name
        target_runner.parent.mkdir()
        shutil.copy2(skill_check, target_runner)
        run(
            [
                str(hook_installer),
                "--repo",
                str(repo),
                "--gauntlet-root",
                str(unavailable_root),
            ],
            cwd=repo,
        )
        backup = hook.with_name("pre-commit.gauntlet-backup")
        if backup.read_bytes() != original:
            raise AssertionError("hook installer did not preserve the existing user hook")
        assert_contains(hook.read_text(), '"$REPO_ROOT/scripts/run-skill-change-checks.sh"', "source-repo hook runner")
