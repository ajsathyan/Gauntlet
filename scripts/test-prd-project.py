#!/usr/bin/env python3
import argparse
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import gauntlet
from thread_titles import epic_task_title, parse_thread_title, product_task_title


def epic(epic_id, title, *, depends="None", status="Accepted", extra=""):
    return f"""## Epic {epic_id}: {title}

Epic status: {status}
Build ready: yes
Ships independently: yes
Rolls back independently: yes
Depends on: {depends}
Release stages: merge

### Scope Area {epic_id}-S01: Outcome

### Product Acceptance

- The observable outcome passes.
{extra}
"""


class EpicProjectTests(unittest.TestCase):
    def init_git(self, root):
        subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "gauntlet@example.com"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Gauntlet Test"], cwd=root, check=True)
        (root / "README.md").write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "fixture"], cwd=root, check=True, capture_output=True, text=True)

    def write_prd(self, root, target, sections):
        path = root / "product.md"
        path.write_text(
            "# Product\n\nDocument status: Accepted\nImplementation target: " + target + "\n\n" + "\n".join(sections),
            encoding="utf-8",
        )
        return path

    def init_args(self, root, source, launch):
        return argparse.Namespace(
            git_root=root,
            source=source,
            target=[],
            launch_set=launch,
            priority="p1",
            json=True,
        )

    def test_exact_once_ready_launch_and_ambiguous_recovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.write_prd(root, "APP-001, APP-002, APP-003", [
                epic("APP-001", "Account foundation"),
                epic("APP-002", "Usage insights"),
                epic("APP-003", "Guided launch", depends="APP-001@merged"),
            ])
            launch_path = root / "launch.json"
            launch, source_text = gauntlet.build_epic_launch_set(source, [], priority="p1")
            snapshot = root / "launch.source.md"
            snapshot.write_text(source_text, encoding="utf-8")
            launch["source"]["snapshotPath"] = str(snapshot)
            gauntlet.write_launch_set(launch_path, launch)

            plan_args = argparse.Namespace(git_root=root, launch_set=launch_path, json=True)
            with mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_plan(plan_args), 0)
            payload = output.call_args.args[0]
            self.assertEqual([item["title"] for item in payload["actions"]], [
                "p1-auto: implement APP-001 account foundation",
                "p1-auto: implement APP-002 usage insights",
            ])
            self.assertNotIn("APP-003", "\n".join(item["message"] for item in payload["actions"]))

            with mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_plan(plan_args), 0)
            replay = output.call_args.args[0]
            self.assertEqual(replay["actions"], [])
            self.assertEqual({item["epicId"] for item in replay["reconcileRequired"]}, {"APP-001", "APP-002"})

            _, current = gauntlet.load_launch_set(launch_path)
            release_args = argparse.Namespace(
                git_root=root, launch_set=launch_path, epic="APP-001",
                task_key=current["epics"]["APP-001"]["taskKey"], json=True,
            )
            with mock.patch("gauntlet.print_payload"):
                self.assertEqual(gauntlet.command_epic_tasks_release_start(release_args), 0)
            with mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_plan(plan_args), 0)
            self.assertEqual([item["title"] for item in output.call_args.args[0]["actions"]], [
                "p1-auto: implement APP-001 account foundation",
            ])

    def test_record_task_emits_truthful_copy_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.write_prd(root, "APP-001", [epic("APP-001", "Account foundation")])
            launch_path = root / "launch.json"
            launch, source_text = gauntlet.build_epic_launch_set(source, [], priority="p1")
            snapshot = root / "launch.source.md"
            snapshot.write_text(source_text, encoding="utf-8")
            launch["source"]["snapshotPath"] = str(snapshot)
            launch["epics"]["APP-001"]["status"] = "starting"
            gauntlet.write_launch_set(launch_path, launch)
            args = argparse.Namespace(git_root=root, launch_set=launch_path, epic="APP-001", task_id="task-123", json=True)
            with mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_record_task(args), 0)
            events = output.call_args.args[0]["lifecycleEvents"]
            self.assertEqual([item["event"] for item in events], ["epic_start", "aggregate_start"])
            self.assertIn("Time for a break?", events[1]["copy"])
            with mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_record_task(args), 0)
            self.assertEqual(output.call_args.args[0]["lifecycleEvents"], [])

    def test_cycle_missing_dependency_and_non_independent_epic_fail_before_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cycle = self.write_prd(root, "APP-001, APP-002", [
                epic("APP-001", "First outcome", depends="APP-002"),
                epic("APP-002", "Second outcome", depends="APP-001"),
            ])
            with self.assertRaisesRegex(ValueError, "cycle"):
                gauntlet.build_epic_launch_set(cycle, [])
            missing = self.write_prd(root, "APP-001", [epic("APP-001", "First outcome", depends="APP-999")])
            with self.assertRaisesRegex(ValueError, "unknown Epic"):
                gauntlet.build_epic_launch_set(missing, [])
            coupled = root / "coupled.md"
            coupled.write_text(epic("APP-001", "Coupled outcome").replace("Ships independently: yes", "Ships independently: no").join([
                "# Product\n\nImplementation target: APP-001\n\n", ""
            ]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Ships independently"):
                gauntlet.build_epic_launch_set(coupled, [])

    def test_copy_secret_rejection_and_titles(self):
        title = epic_task_title("p1", "APP-001", "Account foundation")
        self.assertEqual(parse_thread_title(title)["format"], "current")
        self.assertEqual(parse_thread_title(product_task_title("p1", "APP"))["format"], "current")
        with self.assertRaisesRegex(ValueError, "secret-like"):
            gauntlet.render_lifecycle_copy("epic_start", {
                "epic_id": "APP-001",
                "epic_title": "TOKEN=supersecretvalue",
                "dependency_note": "None",
            })

    def test_source_snapshot_is_immutable_input_for_queued_packets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.write_prd(root, "APP-001", [epic("APP-001", "Account foundation")])
            launch_path = root / "launch.json"
            launch, source_text = gauntlet.build_epic_launch_set(source, [])
            snapshot = root / "launch.source.md"
            snapshot.write_text(source_text, encoding="utf-8")
            launch["source"]["snapshotPath"] = str(snapshot)
            gauntlet.write_launch_set(launch_path, launch)
            source.write_text("changed canonical source", encoding="utf-8")
            packet = gauntlet.epic_task_packet(launch_path, launch, "APP-001", root)
            self.assertIn("Account foundation", packet)
            self.assertNotIn("changed canonical source", packet)

    def test_only_requires_user_blocker_emits_a_question(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.write_prd(root, "APP-001", [epic("APP-001", "Account foundation")])
            launch_path = root / "launch.json"
            launch, source_text = gauntlet.build_epic_launch_set(source, [])
            snapshot = root / "launch.source.md"
            snapshot.write_text(source_text, encoding="utf-8")
            launch["source"]["snapshotPath"] = str(snapshot)
            launch["epics"]["APP-001"].update({"taskId": "task-123", "status": "in-progress"})
            gauntlet.write_launch_set(launch_path, launch)
            blocker_path = root / "blocker.json"
            base = {
                "classification": "needs-parent",
                "decision": "Choose the data owner",
                "recommendation": "use the existing owner",
                "reason": "it preserves the contract",
                "impact": "the integration boundary",
                "authorityNotGranted": "a production change",
                "question": "Should I use the existing owner?",
            }
            blocker_path.write_text(json.dumps(base), encoding="utf-8")
            args = argparse.Namespace(git_root=root, launch_set=launch_path, epic="APP-001", blocker=blocker_path, json=True)
            with mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_blocker(args), 0)
            self.assertEqual(output.call_args.args[0]["lifecycleEvents"], [])
            base["classification"] = "requires-user"
            blocker_path.write_text(json.dumps(base), encoding="utf-8")
            with mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_blocker(args), 0)
            events = output.call_args.args[0]["lifecycleEvents"]
            self.assertEqual([item["event"] for item in events], ["material_blocker"])
            self.assertIn("One decision needs your call", events[0]["copy"])

    def test_reconcile_marks_implemented_only_from_completion_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.write_prd(root, "APP-001", [epic("APP-001", "Account foundation")])
            launch_path = root / "launch.json"
            launch, source_text = gauntlet.build_epic_launch_set(source, [])
            snapshot = root / "launch.source.md"
            snapshot.write_text(source_text, encoding="utf-8")
            launch["source"]["snapshotPath"] = str(snapshot)
            launch["epics"]["APP-001"].update({"taskId": "task-123", "runPath": str(root / "run"), "status": "in-progress"})
            gauntlet.write_launch_set(launch_path, launch)
            projection = {
                "available": True,
                "implemented": True,
                "merged": False,
                "deployed": False,
                "productionProved": False,
                "complete": False,
                "exactRevision": "a" * 40,
                "verificationSummary": "all canonical acceptance cases passed",
                "pendingGates": [{"stage": "merge"}],
            }
            args = argparse.Namespace(git_root=root, launch_set=launch_path, json=True)
            with mock.patch("gauntlet.completion_projection_for_run", return_value=projection), mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_reconcile(args), 0)
            data = output.call_args.args[0]
            self.assertEqual(data["epics"]["APP-001"]["status"], "implementation-complete")
            self.assertIn("This does not yet prove merge", data["lifecycleEvents"][0]["copy"])

    def test_merge_lease_serializes_and_detects_base_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.init_git(root)
            head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
            source = self.write_prd(root, "APP-001", [epic("APP-001", "Account foundation")])
            launch_path = root / "launch.json"
            launch, source_text = gauntlet.build_epic_launch_set(source, [])
            snapshot = root / "launch.source.md"
            snapshot.write_text(source_text, encoding="utf-8")
            launch["source"]["snapshotPath"] = str(snapshot)
            launch["epics"]["APP-001"].update({"taskId": "task-123", "runPath": str(root / "run"), "status": "implementation-complete"})
            gauntlet.write_launch_set(launch_path, launch)
            projection = {"available": True, "implemented": True, "exactRevision": head}
            args = argparse.Namespace(
                git_root=root, launch_set=launch_path, epic="APP-001",
                candidate_head=head, verified_base=head, json=True,
            )
            with mock.patch("gauntlet.completion_projection_for_run", return_value=projection), mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_merge_lease_acquire(args), 0)
            self.assertEqual(output.call_args.args[0]["mergeLease"]["epicId"], "APP-001")
            args.verified_base = "b" * 40
            with mock.patch("gauntlet.completion_projection_for_run", return_value=projection), mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_merge_lease_acquire(args), 1)
            self.assertIn("advanced", output.call_args.args[0]["findings"][0]["message"])


if __name__ == "__main__":
    unittest.main()
