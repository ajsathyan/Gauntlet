"""Skill-change guard workflow case."""

import os
import shutil
import tempfile
from pathlib import Path

from tests.workflow.fixtures import ROOT, SCRIPTS, assert_contains, run


def test_skill_changes_are_guarded_by_pre_commit():
    hook_installer = SCRIPTS / "install-git-hooks.sh"
    skill_check = SCRIPTS / "run-skill-change-checks.sh"
    for path in [hook_installer, skill_check]:
        if not path.exists() or not os.access(path, os.X_OK):
            raise AssertionError(f"missing executable skill-change guard: {path}")
    assert_contains(skill_check.read_text(), "--diff-filter=ACMRD", "skill deletion guard")

    with tempfile.TemporaryDirectory() as tmp:
        deletion_repo = Path(tmp) / "deletion-repo"
        (deletion_repo / "scripts").mkdir(parents=True)
        (deletion_repo / "skills" / "refactor-codebase" / "assets").mkdir(parents=True)
        copied_check = deletion_repo / "scripts" / "run-skill-change-checks.sh"
        shutil.copy2(skill_check, copied_check)
        deleted_asset = deletion_repo / "skills" / "refactor-codebase" / "assets" / "packet.md"
        deleted_asset.write_text("frozen packet\n")
        run(["git", "init", "-q"], cwd=deletion_repo)
        run(["git", "add", "."], cwd=deletion_repo)
        run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "fixture"],
            cwd=deletion_repo,
        )
        deleted_asset.unlink()
        run(["git", "add", "-u"], cwd=deletion_repo)
        deletion = run([str(copied_check), "--detect-only"], cwd=deletion_repo)
        assert_contains(
            deletion.stdout,
            "Gauntlet skill changes detected: refactor-codebase",
            "staged skill deletion guard",
        )

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        run(["git", "init"], cwd=repo)
        run([str(hook_installer), "--repo", str(repo), "--gauntlet-root", str(ROOT)])
        hook = repo / ".git" / "hooks" / "pre-commit"
        if not hook.exists() or not os.access(hook, os.X_OK):
            raise AssertionError("pre-commit hook was not installed")
        hook_text = hook.read_text()
        for marker in ["GAUNTLET SKILL CHECKS", "run-skill-change-checks.sh"]:
            assert_contains(hook_text, marker, "pre-commit hook")

    for args in [[str(skill_check)], [str(skill_check), "--changed-files", "README.md"]]:
        result = run(args, cwd=ROOT)
        if "No Gauntlet skill changes detected" not in result.stdout:
            raise AssertionError("non-skill changes should skip skill text coverage")

    result = run([str(skill_check), "--changed-files", "skills/planner/SKILL.md"], cwd=ROOT)
    for marker in ["Gauntlet skill changes detected", "structural lint: planner", "skill structural lint: passed"]:
        assert_contains(result.stdout, marker, "skill change checks")

    result = run(
        [
            str(skill_check),
            "--changed-files",
            "skills/refactor-codebase/assets/breakthrough-agent-packet.md",
        ],
        cwd=ROOT,
    )
    for marker in [
        "Gauntlet skill changes detected",
        "structural lint: refactor-codebase",
        "skill structural lint: passed",
    ]:
        assert_contains(result.stdout + result.stderr, marker, "refactor asset change checks")
