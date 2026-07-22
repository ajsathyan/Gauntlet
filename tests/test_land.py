import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from gauntletlib.land.workflow import clean_task_checkout
from gauntletlib.land.workflow import configured_push_workflows
from gauntletlib.land.workflow import monitor_landed_revision
from gauntletlib.land.workflow import select_exact_sha_runs
from gauntletlib.merge.workflow import add_existing_pr_blockers


def completed(args, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args, returncode, stdout, stderr)


class LandWorkflowTests(unittest.TestCase):
    def test_exact_sha_selection_rejects_stale_push_runs(self):
        records = [
            {"databaseId": 1, "event": "push", "headSha": "stale"},
            {"databaseId": 2, "event": "pull_request", "headSha": "landed"},
            {"databaseId": 3, "event": "push", "headSha": "landed"},
        ]
        self.assertEqual(
            [record["databaseId"] for record in select_exact_sha_runs(records, "landed")],
            [3],
        )

    def test_monitor_requires_exact_revision_and_successful_watch(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            workflow = repo / ".github/workflows/ci.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text("on:\n  push:\n    branches:\n      - main\n", encoding="utf-8")
            calls = []

            def fake_gh(args, cwd):
                calls.append(args)
                if args[:2] == ["run", "list"]:
                    return completed(
                        args,
                        stdout=json.dumps(
                            [
                                {"databaseId": 10, "event": "push", "headSha": "old"},
                                {
                                    "databaseId": 11,
                                    "event": "push",
                                    "headSha": "abc",
                                    "status": "completed",
                                    "conclusion": "success",
                                    "workflowName": "ci",
                                },
                            ]
                        ),
                    )
                if args[:2] == ["run", "view"]:
                    return completed(
                        args,
                        stdout=json.dumps(
                            {
                                "databaseId": 11,
                                "event": "push",
                                "headSha": "abc",
                                "status": "completed",
                                "conclusion": "success",
                                "workflowName": "ci",
                            }
                        ),
                    )
                return completed(args)

            result, error = monitor_landed_revision(
                repo,
                "abc",
                "main",
                timeout_seconds=1,
                gh_runner=fake_gh,
                sleep_fn=lambda _: None,
            )
            self.assertIsNone(error)
            self.assertEqual(result["status"], "pass")
            self.assertEqual(
                result["runs"],
                [
                    {
                        "databaseId": 11,
                        "event": "push",
                        "headSha": "abc",
                        "status": "completed",
                        "conclusion": "success",
                        "workflowName": "ci",
                        "watchExitCode": 0,
                    }
                ],
            )
            self.assertIn(["run", "watch", "11", "--exit-status"], calls)
            self.assertIn(
                [
                    "run",
                    "view",
                    "11",
                    "--json",
                    "databaseId,status,conclusion,headSha,event,url,workflowName",
                ],
                calls,
            )

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

    def test_monitor_failure_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            workflow = repo / ".github/workflows/ci.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text("on:\n  push:\n", encoding="utf-8")

            def fake_gh(args, cwd):
                if args[:2] == ["run", "list"]:
                    return completed(
                        args,
                        stdout=json.dumps([{"databaseId": 12, "event": "push", "headSha": "abc", "workflowName": "ci"}]),
                    )
                return completed(args, returncode=1, stderr="failed")

            result, error = monitor_landed_revision(
                repo,
                "abc",
                "main",
                timeout_seconds=1,
                gh_runner=fake_gh,
                sleep_fn=lambda _: None,
            )
            self.assertEqual(result["status"], "fail")
            self.assertEqual(error, "failed")

    def test_push_monitoring_is_not_invented_when_unconfigured(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(configured_push_workflows(Path(directory), "main"), [])

    def test_monitor_waits_for_every_declared_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            root = repo / ".github/workflows"
            root.mkdir(parents=True)
            (root / "one.yml").write_text("name: One\non:\n  push:\n", encoding="utf-8")
            (root / "two.yml").write_text("name: Two\non:\n  push:\n", encoding="utf-8")

            def fake_gh(args, cwd):
                if args[:2] == ["run", "list"]:
                    return completed(
                        args,
                        stdout=json.dumps([
                            {"databaseId": 1, "event": "push", "headSha": "abc", "workflowName": "One"}
                        ]),
                    )
                return completed(args)

            result, error = monitor_landed_revision(
                repo,
                "abc",
                "main",
                timeout_seconds=0,
                gh_runner=fake_gh,
                sleep_fn=lambda _: None,
            )
            self.assertEqual(result["status"], "pending")
            self.assertIsNotNone(error)
            assert error is not None
            self.assertIn("Two", error)

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
        "test_exact_sha_selection_rejects_stale_push_runs",
        "test_monitor_requires_exact_revision_and_successful_watch",
        "test_monitor_failure_is_not_accepted",
        "test_push_monitoring_is_not_invented_when_unconfigured",
        "test_monitor_waits_for_every_declared_workflow",
        "test_cleanup_preserves_unique_task_commit",
        "test_cleanup_removes_landed_isolated_worktree_and_branch",
    ):
        getattr(case, name)()


if __name__ == "__main__":
    unittest.main()
