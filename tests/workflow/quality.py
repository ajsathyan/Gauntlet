"""Skill-change guard behavior."""

import os
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
