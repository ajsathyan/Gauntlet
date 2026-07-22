import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from gauntletlib.land.workflow import clean_task_checkout
from gauntletlib.merge.workflow import add_existing_pr_blockers


def completed(args, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args, returncode, stdout, stderr)


class LandWorkflowTests(unittest.TestCase):
    def test_stale_failed_checks_do_not_block_publishing_new_head(self):
        pull_request = {
            "state": "OPEN",
            "isDraft": False,
            "reviewDecision": "",
            "mergeable": "MERGEABLE",
            "headRefOid": "old",
            "statusCheckRollup": [
                {"name": "policy", "status": "COMPLETED", "conclusion": "FAILURE"}
            ],
        }
        stale_payload = {"findings": []}
        add_existing_pr_blockers(stale_payload, pull_request, expected_head="new")
        self.assertEqual(stale_payload["findings"], [])

        current_payload = {"findings": []}
        add_existing_pr_blockers(current_payload, pull_request, expected_head="old")
        self.assertEqual(
            [finding["code"] for finding in current_payload["findings"]],
            ["pull_request_checks_failing"],
        )

    def test_cleanup_preserves_unique_task_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            (repo / "file").write_text("main\n", encoding="utf-8")
            subprocess.run(["git", "add", "file"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "main"], cwd=repo, check=True, capture_output=True)
            landed = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
            ).stdout.strip()
            subprocess.run(["git", "switch", "-c", "task"], cwd=repo, check=True, capture_output=True)
            (repo / "file").write_text("task\n", encoding="utf-8")
            subprocess.run(["git", "commit", "-am", "task"], cwd=repo, check=True, capture_output=True)
            task = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
            ).stdout.strip()

            cleanup, error = clean_task_checkout(repo, repo, "task", "main", task, landed)
            self.assertFalse(cleanup["branchDeleted"])
            self.assertIsNotNone(error)
            assert error is not None
            self.assertIn("does not preserve", error)
            branch = subprocess.run(
                ["git", "branch", "--show-current"], cwd=repo, check=True, capture_output=True, text=True
            ).stdout.strip()
            self.assertEqual(branch, "task")

    def test_cleanup_removes_landed_isolated_worktree_and_branch(self):
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            task_worktree = Path(directory) / "task"
            subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            (repo / "file").write_text("main\n", encoding="utf-8")
            subprocess.run(["git", "add", "file"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "main"], cwd=repo, check=True, capture_output=True)
            subprocess.run(
                ["git", "worktree", "add", "-b", "task", str(task_worktree)],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            (task_worktree / "task").write_text("landed\n", encoding="utf-8")
            subprocess.run(["git", "add", "task"], cwd=task_worktree, check=True)
            subprocess.run(["git", "commit", "-m", "task"], cwd=task_worktree, check=True, capture_output=True)
            task = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=task_worktree,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            subprocess.run(["git", "merge", "--ff-only", "task"], cwd=repo, check=True, capture_output=True)
            landed = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
            ).stdout.strip()

            cleanup, error = clean_task_checkout(
                task_worktree,
                repo,
                "task",
                "main",
                task,
                landed,
            )
            self.assertIsNone(error)
            self.assertEqual(cleanup, {"worktreeRemoved": True, "branchDeleted": True})
            self.assertFalse(task_worktree.exists())
            branches = subprocess.run(
                ["git", "branch", "--list", "task"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.assertEqual(branches, "")
            self.assertEqual(original_cwd, Path.cwd())

    def test_cleanup_keeps_main_worktree_as_cwd_when_task_cwd_is_removed(self):
        original_cwd = Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as directory:
                repo = Path(directory) / "repo"
                task_worktree = Path(directory) / "task"
                subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
                subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
                subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
                (repo / "file").write_text("main\n", encoding="utf-8")
                subprocess.run(["git", "add", "file"], cwd=repo, check=True)
                subprocess.run(["git", "commit", "-m", "main"], cwd=repo, check=True, capture_output=True)
                subprocess.run(
                    ["git", "worktree", "add", "-b", "task", str(task_worktree)],
                    cwd=repo,
                    check=True,
                    capture_output=True,
                )
                (task_worktree / "task").write_text("landed\n", encoding="utf-8")
                subprocess.run(["git", "add", "task"], cwd=task_worktree, check=True)
                subprocess.run(["git", "commit", "-m", "task"], cwd=task_worktree, check=True, capture_output=True)
                task = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=task_worktree,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip()
                subprocess.run(["git", "merge", "--ff-only", "task"], cwd=repo, check=True, capture_output=True)
                landed = subprocess.run(
                    ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
                ).stdout.strip()

                os.chdir(task_worktree)
                cleanup, error = clean_task_checkout(
                    task_worktree,
                    repo,
                    "task",
                    "main",
                    task,
                    landed,
                )

                self.assertIsNone(error)
                self.assertEqual(cleanup, {"worktreeRemoved": True, "branchDeleted": True})
                self.assertEqual(repo.resolve(), Path.cwd())
        finally:
            os.chdir(original_cwd)


def test_land_workflow_behavior():
    case = LandWorkflowTests()
    for name in (
        "test_cleanup_preserves_unique_task_commit",
        "test_cleanup_removes_landed_isolated_worktree_and_branch",
    ):
        getattr(case, name)()


if __name__ == "__main__":
    unittest.main()
