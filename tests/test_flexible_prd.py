#!/usr/bin/env python3
import argparse
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from support import ROOT
from gauntletlib.launch import workflow as launch_workflow


GAUNTLET_CLI = ROOT / "scripts" / "gauntlet.py"
PRD_RUN = ROOT / "scripts" / "prd-run.py"
SPEC = importlib.util.spec_from_file_location("gauntlet_flexible", GAUNTLET_CLI)
gauntlet = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gauntlet)


def run(args, *, cwd=None, check=True):
    result = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode:
        raise AssertionError(f"command failed ({result.returncode}): {args}\n{result.stdout}\n{result.stderr}")
    return result


def git(repo, *args):
    return run(["git", *args], cwd=repo)


def init_repo(path):
    path.mkdir()
    git(path, "init")
    git(path, "config", "user.email", "gauntlet@example.test")
    git(path, "config", "user.name", "Gauntlet Test")
    (path / "README.md").write_text("# App\n", encoding="utf-8")
    git(path, "add", "README.md")
    git(path, "commit", "-m", "initial")


class FlexiblePrdTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name) / "app"
        init_repo(self.repo)

    def tearDown(self):
        self.temporary.cleanup()

    def cli(self, *args, check=True):
        return run(["python3", str(GAUNTLET_CLI), *args], cwd=self.repo, check=check)

    def promoted_prd(self):
        self.cli("docs", "init", "--project-root", str(self.repo), "--epic-prefix", "APP", "--json")
        created = self.cli(
            "docs", "draft", "create", "--project-root", str(self.repo),
            "--template", "peter-yang", "--title", "Machine labels", "--json",
        )
        draft = Path(json.loads(created.stdout)["draftPath"])
        draft.write_text(
            "# Machine labels\n\n"
            "## Problem\n\nOperators cannot distinguish provisioned machines.\n\n"
            "## Solution\n\nShow the existing stable machine label.\n\n"
            "## Acceptance\n\n- Each row shows its existing stable label.\n"
            "- Provisioning behavior does not change.\n\n"
            "## User-added section\n\nKeep this exact section.\n",
            encoding="utf-8",
        )
        expected = draft.read_bytes()
        promoted = self.cli(
            "docs", "draft", "promote", "--project-root", str(self.repo),
            "--draft", draft.name, "--title", "Machine labels", "--json",
        )
        prd = Path(json.loads(promoted.stdout)["prdPath"])
        self.assertEqual(prd.read_bytes(), expected)
        return prd, expected

    def test_accept_launch_bootstrap_and_run_init_preserve_flexible_document(self):
        prd, expected = self.promoted_prd()
        accepted = self.cli(
            "docs", "epic", "accept", "--project-root", str(self.repo),
            "--epic", "APP-001", "--prd", str(prd), "--json",
        )
        accepted_data = json.loads(accepted.stdout)
        self.assertEqual(accepted_data["status"], "pass")
        self.assertEqual(prd.read_bytes(), expected)
        self.assertIn("| Accepted |", (self.repo / "local-docs" / "INDEX.md").read_text())

        launch, source_text = gauntlet.build_epic_launch_set(prd, ["APP-001"])
        launch_path = self.repo / "local-docs" / "launch.json"
        snapshot = self.repo / "local-docs" / "launch.source.md"
        snapshot.write_text(source_text, encoding="utf-8")
        launch["source"]["snapshotPath"] = str(snapshot)
        launch["epics"]["APP-001"]["taskId"] = "task-app-001"
        gauntlet.write_launch_set(launch_path, launch)
        resolved = gauntlet.resolve_epic_bootstrap(
            launch_path, "APP-001", gauntlet.launch_task_key(launch, "APP-001"),
        )
        self.assertEqual(resolved["epicSection"].encode("utf-8"), expected)
        self.assertIn("## User-added section", resolved["epicSection"])

        executions = self.repo / "local-docs" / "executions"
        initialized = run([
            "python3", str(PRD_RUN), "init", "--executions", str(executions),
            "--run-id", "APP_001_TEST", "--source", str(snapshot),
            "--target", "APP-001", "--launch-set", str(launch_path),
            "--release-contract", "doc_org.md:v2",
        ], cwd=self.repo)
        source_lock = json.loads((Path(initialized.stdout.strip()) / "source-lock.json").read_text())
        self.assertEqual(source_lock["epics"]["APP-001"]["title"], "Machine labels")
        self.assertEqual(
            source_lock["epics"]["APP-001"]["acceptance"]["Product Acceptance"],
            ["Each row shows its existing stable label.", "Provisioning behavior does not change."],
        )
        self.assertEqual(list(source_lock["scope_hashes"]), ["APP-001-S01"])

    def test_acceptance_requires_user_supplied_done_behavior_and_rejects_later_edits(self):
        prd, _ = self.promoted_prd()
        without_acceptance = prd.read_text().replace(
            "## Acceptance\n\n- Each row shows its existing stable label.\n- Provisioning behavior does not change.\n\n",
            "",
        )
        prd.write_text(without_acceptance, encoding="utf-8")
        rejected = self.cli(
            "docs", "epic", "accept", "--project-root", str(self.repo),
            "--epic", "APP-001", "--prd", str(prd), "--json", check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("missing_observable_acceptance", rejected.stdout)

        prd.write_text(without_acceptance + "\n## Done when\n\nThe existing label appears on every row.\n", encoding="utf-8")
        self.cli(
            "docs", "epic", "accept", "--project-root", str(self.repo),
            "--epic", "APP-001", "--prd", str(prd), "--json",
        )
        prd.write_text(prd.read_text() + "\nUnaccepted expansion.\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed after acceptance"):
            gauntlet.build_epic_launch_set(prd, ["APP-001"])

    def test_reconcile_docs_updates_a_flexible_prd_without_an_epic_heading(self):
        prd, _ = self.promoted_prd()
        self.cli(
            "docs", "epic", "accept", "--project-root", str(self.repo),
            "--epic", "APP-001", "--prd", str(prd), "--json",
        )
        launch, source_text = gauntlet.build_epic_launch_set(prd, ["APP-001"])
        launch_path = self.repo / "local-docs" / "launch.json"
        snapshot = self.repo / "local-docs" / "launch.source.md"
        snapshot.write_text(source_text, encoding="utf-8")
        launch["source"]["snapshotPath"] = str(snapshot)
        launch["epics"]["APP-001"].update({
            "taskId": "task-app-001",
            "runPath": str(self.repo / "local-docs" / "executions" / "APP-001-RUN"),
            "status": "implementation-complete",
        })
        gauntlet.write_launch_set(launch_path, launch)
        projection = {
            "available": True,
            "implemented": True,
            "complete": False,
            "exactRevision": "a" * 40,
            "sourceSha256": launch["source"]["sha256"],
        }
        args = argparse.Namespace(
            git_root=self.repo,
            launch_set=launch_path,
            epic="APP-001",
            json=True,
        )

        with mock.patch.object(
            launch_workflow,
            "completion_projection_for_run",
            return_value=projection,
        ), mock.patch.object(launch_workflow, "print_payload") as output:
            self.assertEqual(0, gauntlet.command_epic_tasks_reconcile_docs(args))

        reconciled = prd.read_text(encoding="utf-8")
        self.assertIn("Epic status: Implementation-complete", reconciled)
        self.assertIn("Implemented by: Execution Run APP-001-RUN", reconciled)
        self.assertNotIn("## Epic APP-001", reconciled)
        self.assertTrue(output.call_args.args[0]["reconciled"]["changed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
