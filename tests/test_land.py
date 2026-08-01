import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gauntletlib.land.workflow import clean_task_checkout
from gauntletlib.merge.workflow import (
    add_existing_pr_blockers,
    execute_merge_plan,
    required_pr_checks,
    required_checks_state,
    wait_for_pr_checks,
)


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
            "requiredStatusChecks": [
                {"name": "policy", "state": "FAILURE", "bucket": "fail"}
            ],
            "requiredStatusChecksError": None,
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

    def test_optional_failed_checks_do_not_block(self):
        pull_request = {
            "state": "OPEN",
            "isDraft": False,
            "reviewDecision": "",
            "mergeable": "MERGEABLE",
            "headRefOid": "head",
            "statusCheckRollup": [
                {"name": "optional", "status": "COMPLETED", "conclusion": "FAILURE"}
            ],
            "requiredStatusChecks": [],
            "requiredStatusChecksError": None,
        }
        payload = {"findings": []}

        add_existing_pr_blockers(payload, pull_request, expected_head="head")

        self.assertEqual(payload["findings"], [])

    def test_required_check_discovery_failure_is_distinct_from_none_configured(self):
        base = {
            "state": "OPEN",
            "isDraft": False,
            "reviewDecision": "",
            "mergeable": "MERGEABLE",
            "headRefOid": "head",
        }
        no_checks = {
            **base,
            "requiredStatusChecks": [],
            "requiredStatusChecksError": None,
        }
        discovery_failed = {
            **base,
            "requiredStatusChecks": None,
            "requiredStatusChecksError": "API unavailable",
        }
        no_checks_payload = {"findings": []}
        failed_payload = {"findings": []}

        add_existing_pr_blockers(no_checks_payload, no_checks, expected_head="head")
        add_existing_pr_blockers(failed_payload, discovery_failed, expected_head="head")

        self.assertEqual(no_checks_payload["findings"], [])
        self.assertEqual(
            [finding["code"] for finding in failed_payload["findings"]],
            ["pull_request_required_checks_unresolved"],
        )

    def test_required_check_states_cover_passing_pending_and_failing(self):
        cases = [
            ("pass", "SUCCESS", "passing"),
            ("pending", "PENDING", "pending"),
            ("fail", "FAILURE", "failing"),
        ]
        for bucket, state, expected in cases:
            with self.subTest(bucket=bucket):
                observed, _ = required_checks_state(
                    {
                        "requiredStatusChecks": [
                            {"name": "policy", "state": state, "bucket": bucket}
                        ],
                        "requiredStatusChecksError": None,
                    }
                )
                self.assertEqual(observed, expected)

    def test_required_check_discovery_uses_required_filter_and_accepts_empty_json(self):
        with patch(
            "gauntletlib.merge.workflow.gh",
            return_value=completed([], stdout="[]"),
        ) as gh_mock:
            checks, error, reported = required_pr_checks(Path("/repo"), 17)

        self.assertEqual(checks, [])
        self.assertIsNone(error)
        self.assertFalse(reported)
        self.assertEqual(
            gh_mock.call_args.args[0],
            [
                "pr",
                "checks",
                "17",
                "--required",
                "--json",
                "bucket,name,state",
            ],
        )

    def test_required_check_discovery_reports_api_failure(self):
        with patch(
            "gauntletlib.merge.workflow.gh",
            return_value=completed([], returncode=1, stderr="API unavailable"),
        ):
            checks, error, reported = required_pr_checks(Path("/repo"), 17)

        self.assertIsNone(checks)
        self.assertEqual(error, "API unavailable")
        self.assertFalse(reported)

    def test_required_check_discovery_accepts_cli_no_checks_result(self):
        with patch(
            "gauntletlib.merge.workflow.gh",
            return_value=completed(
                [],
                returncode=1,
                stderr="no required checks reported on the 'task' branch",
            ),
        ):
            checks, error, reported = required_pr_checks(Path("/repo"), 17)

        self.assertEqual(checks, [])
        self.assertIsNone(error)
        self.assertFalse(reported)

    def test_zero_required_checks_do_not_wait(self):
        pull_request = {
            "number": 17,
            "requiredStatusChecks": [],
            "requiredStatusChecksError": None,
            "requiredStatusChecksReported": False,
        }
        with patch(
            "gauntletlib.merge.workflow.current_pr",
            return_value=(pull_request, None),
        ) as current_pr_mock, patch("gauntletlib.merge.workflow.time.sleep") as sleep_mock:
            observed, error = wait_for_pr_checks(Path("/repo"), timeout_seconds=0)

        self.assertIs(observed, pull_request)
        self.assertIsNone(error)
        current_pr_mock.assert_called_once()
        sleep_mock.assert_not_called()

    def test_required_check_registration_supersedes_initial_empty_result(self):
        unreported = {
            "number": 17,
            "requiredStatusChecks": [],
            "requiredStatusChecksError": None,
            "requiredStatusChecksReported": False,
        }
        pending = {
            "number": 17,
            "requiredStatusChecks": [
                {"name": "policy", "state": "PENDING", "bucket": "pending"}
            ],
            "requiredStatusChecksError": None,
            "requiredStatusChecksReported": True,
        }
        with patch(
            "gauntletlib.merge.workflow.current_pr",
            side_effect=[(unreported, None), (pending, None)],
        ), patch(
            "gauntletlib.merge.workflow.time.monotonic", side_effect=[0, 0]
        ), patch("gauntletlib.merge.workflow.time.sleep") as sleep_mock:
            observed, error = wait_for_pr_checks(
                Path("/repo"), timeout_seconds=1, poll_seconds=0
            )

        self.assertIs(observed, pending)
        self.assertIsNone(error)
        sleep_mock.assert_called_once_with(0)

    def test_check_watch_filters_to_required_checks(self):
        pull_request = {
            "number": 17,
            "headRefOid": "candidate",
            "requiredStatusChecks": [
                {"name": "policy", "state": "PENDING", "bucket": "pending"}
            ],
            "requiredStatusChecksError": None,
        }
        payload = {
            "findings": [],
            "branch": "task",
            "defaultBranch": "main",
            "candidate": {"commit": "candidate", "tree": "tree"},
            "repositoryContext": {
                "headRemote": "origin",
                "baseRemote": "origin",
                "baseRepository": "owner/repo",
            },
            "mergePlan": {"actions": [{"type": "gh_pr_checks_watch"}]},
        }
        handoff = {"sourceBinding": {"base": "base"}}
        with patch(
            "gauntletlib.merge.workflow.current_head", return_value="candidate"
        ), patch(
            "gauntletlib.merge.workflow.current_tree", return_value="tree"
        ), patch(
            "gauntletlib.merge.workflow.wait_for_pr_checks",
            return_value=(pull_request, None),
        ), patch(
            "gauntletlib.merge.workflow.gh", return_value=completed([])
        ) as gh_mock:
            result = execute_merge_plan(payload, Path("/repo"), handoff, Path("body"))

        self.assertEqual(result["status"], "pass")
        self.assertEqual(
            gh_mock.call_args.args[0],
            ["pr", "checks", "17", "--watch", "--required"],
        )

    def test_zero_required_checks_skip_watch_command(self):
        pull_request = {
            "number": 17,
            "headRefOid": "candidate",
            "requiredStatusChecks": [],
            "requiredStatusChecksError": None,
        }
        payload = {
            "findings": [],
            "branch": "task",
            "defaultBranch": "main",
            "candidate": {"commit": "candidate", "tree": "tree"},
            "repositoryContext": {
                "headRemote": "origin",
                "baseRemote": "origin",
                "baseRepository": "owner/repo",
            },
            "mergePlan": {"actions": [{"type": "gh_pr_checks_watch"}]},
        }
        handoff = {"sourceBinding": {"base": "base"}}
        with patch(
            "gauntletlib.merge.workflow.current_head", return_value="candidate"
        ), patch(
            "gauntletlib.merge.workflow.current_tree", return_value="tree"
        ), patch(
            "gauntletlib.merge.workflow.wait_for_pr_checks",
            return_value=(pull_request, None),
        ), patch("gauntletlib.merge.workflow.gh") as gh_mock:
            result = execute_merge_plan(payload, Path("/repo"), handoff, Path("body"))

        self.assertEqual(result["status"], "pass")
        gh_mock.assert_not_called()

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
    for name in sorted(name for name in dir(case) if name.startswith("test_")):
        getattr(case, name)()


if __name__ == "__main__":
    unittest.main()
