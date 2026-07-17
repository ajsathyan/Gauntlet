#!/usr/bin/env python3
import argparse
import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

gauntlet = importlib.import_module("gauntlet")
thread_titles = importlib.import_module("thread_titles")
epic_task_title = thread_titles.epic_task_title
parse_thread_title = thread_titles.parse_thread_title
product_task_title = thread_titles.product_task_title


def epic(epic_id, title, *, depends="None", status="Accepted", extra=""):
    return f"""## Epic {epic_id}: {title}

Epic status: {status}
Build ready: yes
Ships independently: yes
Rolls back independently: yes
Depends on: {depends}
Release stages: merge
High-consequence triggers: none

### Scope Area {epic_id}-S01: Outcome

### Product Acceptance

- The observable outcome passes.
{extra}
"""


class EpicProjectTests(unittest.TestCase):
    def project_pr_projection(self):
        digest = "a" * 64
        revision = "b" * 40
        return {
            "schemaVersion": "3.0",
            "title": "APP-001: implement Account foundation",
            "binding": {
                "branch": "codex/app-001",
                "generation": 3,
                "graphSha256": digest,
                "headSha": revision,
                "epicVerificationSha256": digest,
                "repository": "example/repository",
                "runId": "APP-001-RUN",
                "sourceLockSha256": digest,
            },
            "acceptedCriteria": ["Accounts can be created and read."],
            "changedPaths": ["src/accounts.py"],
            "completion": {
                "complete": False,
                "deployed": False,
                "epicId": "APP-001",
                "exactRevision": revision,
                "exactState": "implementation-complete",
                "implemented": True,
                "merged": False,
                "pendingGates": ["merge"],
                "productionProved": False,
                "sourceSha256": digest,
                "verificationSummary": "Canonical account acceptance passed.",
            },
            "deferrals": {"cannotVerify": [], "nonGoals": ["Production deployment"]},
            "epic": {
                "id": "APP-001",
                "scopeAreas": [{"id": "APP-001-S01", "responsibility": "Account lifecycle"}],
                "title": "Account foundation",
            },
            "releaseGates": [{
                "blocksOverallCompletion": True,
                "blocksPr": False,
                "evidenceRefs": [],
                "id": "merge-to-default",
                "stage": "merge",
                "status": "pending",
                "summary": "The verified Epic head still needs to merge.",
            }],
            "verificationReceipts": ["receipts/final-epic.json"],
        }

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
            native_index = root / "native-index.json"
            native_index.write_text(json.dumps({
                "schemaVersion": 2,
                "query": gauntlet.launch_task_key(current, "APP-001"),
                "threads": [],
                "unavailableHosts": [],
            }), encoding="utf-8")
            release_args = argparse.Namespace(
                git_root=root, launch_set=launch_path, epic="APP-001",
                task_key=gauntlet.launch_task_key(current, "APP-001"),
                native_index=root / "missing-native-index.json", json=True,
            )
            with mock.patch("gauntlet.print_payload"):
                self.assertEqual(gauntlet.command_epic_tasks_release_start(release_args), 1)
            release_args.native_index = native_index
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
            args = argparse.Namespace(
                git_root=root, launch_set=launch_path, epic="APP-001",
                task_key=gauntlet.launch_task_key(launch, "APP-001"), task_id="task-123", json=True,
            )
            dashboard = {
                "status": "running", "started": True,
                "stateFile": str(root / "launch.progress-dashboard.json"),
            }
            with mock.patch("gauntlet.ensure_progress_supervisor", return_value=dashboard), mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_record_task(args), 0)
            events = output.call_args.args[0]["lifecycleEvents"]
            self.assertEqual([item["event"] for item in events], ["epic_start", "aggregate_start"])
            self.assertIn("Time for a break?", events[1]["copy"])
            self.assertEqual("open_browser", output.call_args.args[0]["actions"][0]["type"])
            with mock.patch("gauntlet.ensure_progress_supervisor", return_value={**dashboard, "started": False}), mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_record_task(args), 0)
            self.assertEqual(output.call_args.args[0]["lifecycleEvents"], [])
            self.assertEqual(output.call_args.args[0]["actions"], [])

            _, recorded = gauntlet.load_launch_set(launch_path)
            recorded["epics"]["APP-001"].update({"taskId": None, "status": "planned"})
            gauntlet.write_launch_set(launch_path, recorded)
            with mock.patch("gauntlet.ensure_progress_supervisor", return_value={**dashboard, "started": False}), mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_record_task(args), 1)
            self.assertIn("starting state", output.call_args.args[0]["findings"][0]["message"])
            args.task_key = "wrong-task-key"
            with mock.patch("gauntlet.ensure_progress_supervisor", return_value={**dashboard, "started": False}), mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_record_task(args), 1)
            self.assertIn("task key", output.call_args.args[0]["findings"][0]["message"])

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
            blank = self.write_prd(root, "APP-001", [
                epic("APP-001", "Blank consequence declaration").replace(
                    "High-consequence triggers: none", "High-consequence triggers:",
                ),
            ])
            with self.assertRaisesRegex(ValueError, "literal `none`"):
                gauntlet.build_epic_launch_set(blank, [])

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

    def test_doc_execution_contract_migration_preserves_unmanaged_bytes(self):
        prefix = "# Project-authored policy\n\n"
        body = (
            "## PRD Compilation And Ticket Graph\n\n"
            "Use one fresh final check for the accepted work.\n\n"
        )
        suffix = "## Future Tasks\n\nKeep this project-authored ending.\n"
        legacy = prefix + body + suffix
        start = legacy.index("## PRD Compilation And Ticket Graph\n")
        end = legacy.index("## Future Tasks\n", start)
        legacy_hash = gauntlet.sha256_bytes(legacy[start:end].encode("utf-8"))
        with mock.patch.object(gauntlet, "DOC_EXECUTION_LEGACY_HASHES", {legacy_hash}):
            migrated, state = gauntlet.migrate_doc_execution_contract(legacy)
        self.assertEqual(state, "migrated")
        self.assertEqual(migrated[:migrated.index(gauntlet.DOC_EXECUTION_BLOCK_BEGIN)], prefix)
        self.assertTrue(migrated.endswith(suffix.lstrip("\n")))
        self.assertIn(gauntlet.DOC_EXECUTION_BLOCK_END, migrated)

        customized = legacy.replace("one fresh final check", "a customized final check")
        unchanged, state = gauntlet.migrate_doc_execution_contract(customized)
        self.assertEqual((unchanged, state), (customized, "customized"))

        with tempfile.TemporaryDirectory() as temporary:
            policy = Path(temporary) / "doc_org.md"
            policy.write_text(legacy, encoding="utf-8")
            with mock.patch.object(gauntlet, "DOC_EXECUTION_LEGACY_HASHES", {legacy_hash}):
                findings, migration_required = gauntlet.ensure_doc_execution_contract(
                    {"policyPath": policy}, dry_run=True,
                )
            self.assertTrue(migration_required)
            self.assertEqual(findings[0]["code"], "local_execution_contract_migration_planned")
            self.assertEqual(policy.read_text(encoding="utf-8"), legacy)

    def test_task_packet_is_thin_and_bootstrap_resolves_the_complete_epic(self):
        packet_sizes = []
        fixtures = (
            ("EDGE-009", 20465),
            ("GAUNTLET-005", 44449),
            ("AGORARUNPOD-014", 61897),
        )
        for epic_id, epic_bytes in fixtures:
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                marker = f"semantic-marker-{epic_bytes}"
                base_section = epic(epic_id, "Representative accepted outcome", extra=marker)
                padding = "x" * (epic_bytes - len(base_section.encode("utf-8")))
                epic_section = epic(epic_id, "Representative accepted outcome", extra=marker + padding)
                self.assertEqual(len(epic_section.encode("utf-8")), epic_bytes)
                source = self.write_prd(root, epic_id, [
                    epic_section,
                ])
                launch_root = root / "local-docs" / "epic-launches"
                launch_root.mkdir(parents=True)
                launch_path = launch_root / f"{epic_id}.launch.json"
                launch, source_text = gauntlet.build_epic_launch_set(source, [])
                snapshot = launch_root / f"{epic_id}.source.md"
                snapshot.write_text(source_text, encoding="utf-8")
                launch["source"]["snapshotPath"] = str(snapshot)
                gauntlet.write_launch_set(launch_path, launch)

                packet = gauntlet.epic_task_packet(launch_path, launch, epic_id, root)
                packet_sizes.append(len(packet.encode("utf-8")))
                self.assertLessEqual(packet_sizes[-1], 1200)
                self.assertNotIn(marker, packet)
                self.assertIn('"bootstrap"', packet)
                if epic_id == "EDGE-009":
                    envelope = json.loads(packet.split("<gauntlet_epic_task>\n", 1)[1].split("\n</gauntlet_epic_task>", 1)[0])
                    result = subprocess.run(
                        envelope["bootstrap"]["argv"], cwd=root, capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn(marker, json.loads(result.stdout)["epicSection"])

                args = argparse.Namespace(
                    git_root=root,
                    launch_set=launch_path,
                    epic=epic_id,
                    task_key=gauntlet.launch_task_key(launch, epic_id),
                    source_sha256=launch["source"]["sha256"],
                    coverage_sha256=launch["coverageSha256"],
                    json=True,
                )
                with mock.patch("gauntlet.print_payload") as output:
                    self.assertEqual(gauntlet.command_epic_tasks_bootstrap(args), 0)
                resolved = output.call_args.args[0]
                self.assertEqual(resolved["status"], "pass")
                self.assertIn(marker, resolved["epicSection"])
                self.assertEqual(
                    resolved["epicSectionSha256"],
                    gauntlet.sha256_bytes(resolved["epicSection"].encode("utf-8")),
                )
        self.assertLessEqual(max(packet_sizes) - min(packet_sizes), 64)

    def test_bootstrap_rejects_stale_tampered_missing_or_unavailable_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.write_prd(root, "APP-001", [epic("APP-001", "Account foundation")])
            launch_path = root / "launch.json"
            launch, source_text = gauntlet.build_epic_launch_set(source, [])
            snapshot = root / "launch.source.md"
            snapshot.write_text(source_text, encoding="utf-8")
            launch["source"]["snapshotPath"] = str(snapshot)
            gauntlet.write_launch_set(launch_path, launch)
            base = argparse.Namespace(
                git_root=root,
                launch_set=launch_path,
                epic="APP-001",
                task_key=gauntlet.launch_task_key(launch, "APP-001"),
                source_sha256=launch["source"]["sha256"],
                coverage_sha256=launch["coverageSha256"],
                json=True,
            )

            source.write_text("changed mutable canonical source", encoding="utf-8")
            with mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_bootstrap(base), 0)
            self.assertIn("Account foundation", output.call_args.args[0]["epicSection"])

            stale = argparse.Namespace(**vars(base))
            stale.coverage_sha256 = "0" * 64
            with mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_bootstrap(stale), 1)
            self.assertIn("coverage", output.call_args.args[0]["findings"][0]["message"])

            snapshot.write_text(source_text + "tampered\n", encoding="utf-8")
            with mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_bootstrap(base), 1)
            self.assertIn("source", output.call_args.args[0]["findings"][0]["message"])

            snapshot.unlink()
            with mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_bootstrap(base), 1)
            self.assertEqual(output.call_args.args[0]["status"], "fail")

            unavailable = argparse.Namespace(**vars(base))
            unavailable.launch_set = root / "unavailable-launch.json"
            with mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_bootstrap(unavailable), 1)
            self.assertEqual(output.call_args.args[0]["status"], "fail")
            self.assertFalse((root / "executions").exists())

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
            with mock.patch("gauntlet.completion_projection_for_run", return_value=projection), mock.patch(
                "gauntlet.ensure_progress_supervisor",
                return_value={"status": "unavailable", "started": False, "stateFile": "state"},
            ), mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_reconcile(args), 0)
            data = output.call_args.args[0]
            self.assertEqual(data["epics"]["APP-001"]["status"], "implementation-complete")
            self.assertIn("Pending release gates: merge", data["lifecycleEvents"][0]["copy"])

    def test_canonical_reconciliation_rejects_target_acceptance_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.init_git(root)
            source = self.write_prd(root, "APP-001", [epic("APP-001", "Account foundation")])
            docs = root / "local-docs"
            docs.mkdir()
            index = docs / "INDEX.md"
            index.write_text(
                "| ID | Title | Type | Status | Created | Dependencies | Supersedes | Implementation | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| `APP-001` | Account foundation | PRD | Accepted | now | None | None | Not implemented | Not verified |\n",
                encoding="utf-8",
            )
            launch_path = root / "launch.json"
            launch, source_text = gauntlet.build_epic_launch_set(source, [])
            snapshot = root / "launch.source.md"
            snapshot.write_text(source_text, encoding="utf-8")
            launch["source"]["snapshotPath"] = str(snapshot)
            launch["epics"]["APP-001"].update({"taskId": "task-123", "runPath": str(root / "run"), "status": "implementation-complete"})
            gauntlet.write_launch_set(launch_path, launch)
            projection = {
                "available": True, "implemented": True, "complete": False,
                "exactRevision": "a" * 40, "sourceSha256": launch["source"]["sha256"],
            }
            args = argparse.Namespace(git_root=root, launch_set=launch_path, epic="APP-001", json=True)
            source.write_text(source.read_text(encoding="utf-8") + "\n## Epic APP-999: Unrelated idea\n\nEpic status: Proposed\n", encoding="utf-8")
            with mock.patch("gauntlet.completion_projection_for_run", return_value=projection), mock.patch("gauntlet.print_payload"):
                self.assertEqual(gauntlet.command_epic_tasks_reconcile_docs(args), 0)
            reconciled = source.read_text(encoding="utf-8")
            self.assertIn("Epic status: Implementation-complete", reconciled)
            self.assertIn("APP-999: Unrelated idea", reconciled)

            source.write_text(reconciled.replace("- The observable outcome passes.", "- A materially different outcome passes."), encoding="utf-8")
            before_source = source.read_text(encoding="utf-8")
            before_index = index.read_text(encoding="utf-8")
            with mock.patch("gauntlet.completion_projection_for_run", return_value=projection), mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_reconcile_docs(args), 1)
            self.assertIn("acceptance changed", output.call_args.args[0]["findings"][0]["message"])
            self.assertEqual(source.read_text(encoding="utf-8"), before_source)
            self.assertEqual(index.read_text(encoding="utf-8"), before_index)

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

            gauntlet.launch_merge_lease_path(launch_path).unlink()
            (root / "advance.txt").write_text("advance default\n", encoding="utf-8")
            subprocess.run(["git", "add", "advance.txt"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "advance default"], cwd=root, check=True, capture_output=True, text=True)
            advanced = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
            args.verified_base = advanced
            with mock.patch("gauntlet.completion_projection_for_run", return_value=projection), mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_merge_lease_acquire(args), 1)
            self.assertIn("does not contain", output.call_args.args[0]["findings"][0]["message"])

    def test_persisted_merge_lease_is_bound_to_the_exact_launch_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.write_prd(root, "APP-001", [epic("APP-001", "Account foundation")])
            launch_path = root / "launch.json"
            launch, source_text = gauntlet.build_epic_launch_set(source, [])
            snapshot = root / "launch.source.md"
            snapshot.write_text(source_text, encoding="utf-8")
            run = root / "run"
            run.mkdir()
            launch["source"]["snapshotPath"] = str(snapshot)
            launch["epics"]["APP-001"].update({"taskId": "task-123", "runPath": str(run), "status": "implementation-complete"})
            gauntlet.write_launch_set(launch_path, launch)
            (run / "source-lock.json").write_text(json.dumps({
                "target_epic_ids": ["APP-001"],
                "epics": {"APP-001": {}},
                "launch_set": {
                    "path": str(launch_path),
                    "coverage_sha256": launch["coverageSha256"],
                    "task_id": "task-123",
                },
            }), encoding="utf-8")
            handoff = {"epic": {"id": "APP-001"}, "binding": {"runId": "run", "headSha": "a" * 40}}
            lease = {
                "schemaVersion": "gauntlet.epic-merge-lease.v1",
                "coverageSha256": launch["coverageSha256"],
                "epicId": "APP-001",
                "candidateHead": "a" * 40,
                "baseHead": "b" * 40,
                "baseRef": "origin/main",
            }
            lease_path = gauntlet.launch_merge_lease_path(launch_path)
            lease_path.write_text(json.dumps(lease), encoding="utf-8")
            self.assertEqual(gauntlet.persisted_run_merge_lease(run, handoff), (lease_path, lease))
            handoff["binding"]["headSha"] = "c" * 40
            with self.assertRaisesRegex(ValueError, "does not match"):
                gauntlet.persisted_run_merge_lease(run, handoff)

            old = {**lease, "candidateHead": "c" * 40}
            lease_path.write_text(json.dumps(old), encoding="utf-8")
            handoff["binding"]["headSha"] = "a" * 40
            def fake_git(arguments, _repo):
                if arguments[:3] == ["merge-base", "--is-ancestor", "c" * 40]:
                    return subprocess.CompletedProcess(arguments, 1, "", "")
                if arguments[:2] == ["rev-parse", ("c" * 40) + "^{tree}"]:
                    return subprocess.CompletedProcess(arguments, 0, "old-tree\n", "")
                if arguments[:2] == ["rev-parse", ("b" * 40) + "^{tree}"]:
                    return subprocess.CompletedProcess(arguments, 0, "default-tree\n", "")
                return subprocess.CompletedProcess(arguments, 0, "", "")
            with mock.patch("gauntlet.refresh_default_head", return_value=("b" * 40, "origin/main")), mock.patch("gauntlet.git", side_effect=fake_git):
                _, replaced = gauntlet.acquire_run_merge_lease(root, run, handoff)
            self.assertEqual(replaced["candidateHead"], "a" * 40)
            self.assertEqual(json.loads(lease_path.read_text()), replaced)

            lease_path.write_text(json.dumps(old), encoding="utf-8")
            def squash_git(arguments, _repo):
                if arguments[:3] == ["merge-base", "--is-ancestor", "c" * 40]:
                    return subprocess.CompletedProcess(arguments, 1, "", "")
                if arguments[0] == "rev-parse":
                    return subprocess.CompletedProcess(arguments, 0, "same-tree\n", "")
                return subprocess.CompletedProcess(arguments, 0, "", "")
            with mock.patch("gauntlet.refresh_default_head", return_value=("b" * 40, "origin/main")), mock.patch("gauntlet.git", side_effect=squash_git):
                with self.assertRaisesRegex(ValueError, "already on the default branch"):
                    gauntlet.acquire_run_merge_lease(root, run, handoff)

    def test_squash_lease_recovery_survives_later_default_advancement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.init_git(root)
            candidate = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True,
            ).stdout.strip()
            tree = subprocess.run(
                ["git", "rev-parse", "HEAD^{tree}"], cwd=root, check=True, capture_output=True, text=True,
            ).stdout.strip()
            squashed = subprocess.run(
                ["git", "commit-tree", tree, "-m", "squashed equivalent"],
                cwd=root, check=True, capture_output=True, text=True,
            ).stdout.strip()
            subprocess.run(["git", "update-ref", "refs/heads/main", squashed], cwd=root, check=True)
            (root / "later.txt").write_text("later default work\n", encoding="utf-8")
            subprocess.run(["git", "add", "later.txt"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "later default"], cwd=root, check=True, capture_output=True, text=True)
            lease_path = root / "lease.json"
            lease = {
                "schemaVersion": "gauntlet.epic-merge-lease.v1", "coverageSha256": "a" * 64,
                "epicId": "APP-001", "candidateHead": candidate,
                "baseHead": candidate, "baseRef": "origin/main",
            }
            lease_path.write_text(json.dumps(lease), encoding="utf-8")
            gauntlet.release_run_merge_lease(root, lease_path, lease, squashed)
            self.assertFalse(lease_path.exists())

    def test_project_pr_schema_three_is_generated_facts_only(self):
        projection = self.project_pr_projection()
        self.assertEqual(gauntlet.validate_run_merge_handoff(projection), [])
        body = gauntlet.render_pr_body(projection)
        self.assertIn("Implementation state: **implementation-complete**", body)
        self.assertIn("Merged: no", body)
        self.assertIn("blocks overall completion: yes", body)
        self.assertNotIn("Substantial Changes", body)

        grouped = json.loads(json.dumps(projection))
        grouped["acceptedCriteria"] = {
            "Product Acceptance": ["A returning user understands the current run."],
            "Engineering Acceptance": ["The projection remains deterministic."],
        }
        self.assertEqual(gauntlet.validate_run_merge_handoff(grouped), [])
        grouped_body = gauntlet.render_pr_body(grouped)
        self.assertIn("### Product Acceptance", grouped_body)
        self.assertIn("- The projection remains deterministic.", grouped_body)

        invalid_grouped = json.loads(json.dumps(grouped))
        invalid_grouped["acceptedCriteria"]["Engineering Acceptance"] = []
        self.assertIn("invalid_accepted_criteria", {
            item["code"] for item in gauntlet.validate_run_merge_handoff(invalid_grouped)
        })
        self.assertEqual(gauntlet.projection_changelog_entry(projection), "Implement APP-001: Account foundation.")
        safeguarded = json.loads(json.dumps(projection))
        safeguarded["releaseGates"].append({
            "blocksOverallCompletion": True,
            "blocksPr": False,
            "evidenceRefs": [],
            "id": "dry-run-no-mutation",
            "stage": "merge",
            "status": "pending",
            "summary": "Dry run remains pending.",
        })
        self.assertEqual([item["id"] for item in gauntlet.pending_run_merge_gates(safeguarded)], ["dry-run-no-mutation"])
        self.assertFalse(gauntlet.completion_allows_archive(projection["completion"]))
        archive_ready = json.loads(json.dumps(projection["completion"]))
        archive_ready["complete"] = True
        self.assertTrue(gauntlet.completion_allows_archive(archive_ready))
        retired = {"schemaVersion": "2.0"}
        self.assertTrue(gauntlet.validate_merge_handoff(retired))

        contradictory = json.loads(json.dumps(projection))
        contradictory["completion"].update({
            "implemented": False,
            "merged": True,
            "deployed": True,
            "productionProved": True,
            "complete": True,
            "epicId": "APP-999",
            "exactRevision": None,
            "exactState": "complete",
            "pendingGates": [],
            "sourceSha256": "invalid",
            "verificationSummary": None,
        })
        codes = {item["code"] for item in gauntlet.validate_run_merge_handoff(contradictory)}
        self.assertTrue({
            "contradictory_completion_projection",
            "completion_epic_mismatch",
            "invalid_completion_projection",
        }.issubset(codes))
        invalid_gate = json.loads(json.dumps(projection))
        invalid_gate["releaseGates"][0]["status"] = "trust-me"
        self.assertIn("invalid_release_gate", {
            item["code"] for item in gauntlet.validate_run_merge_handoff(invalid_gate)
        })
        ghost_pending = json.loads(json.dumps(projection))
        ghost_pending["completion"].update({
            "complete": True, "merged": True, "exactState": "complete", "pendingGates": ["ghost"],
        })
        ghost_pending["releaseGates"][0]["status"] = "pass"
        self.assertIn("contradictory_completion_projection", {
            item["code"] for item in gauntlet.validate_run_merge_handoff(ghost_pending)
        })

    def test_merge_only_release_state_closes_without_extra_user_or_model_work(self):
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            manifest_path = run / "manifest.json"
            manifest_path.write_text(json.dumps({
                "state": "merged",
                "release": {
                    "applicability": {"merge": True, "deployment": False, "production-verification": False},
                },
            }), encoding="utf-8")

            def controller(_repo, arguments):
                manifest = json.loads(manifest_path.read_text())
                if arguments[0] == "record-release":
                    stage = arguments[arguments.index("--stage") + 1]
                    manifest["release"][stage] = {"result": "skipped"}
                elif arguments[0] == "transition":
                    manifest["state"] = arguments[arguments.index("--to") + 1]
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                return "", None

            with mock.patch("gauntlet.run_prd_controller", side_effect=controller):
                transitions, error = gauntlet.advance_run_release_state(run, run)
            self.assertIsNone(error)
            self.assertEqual(transitions, [
                "deployment:not-applicable", "deployed",
                "production-verification:not-applicable", "production_verified", "complete",
            ])
            self.assertEqual(json.loads(manifest_path.read_text())["state"], "complete")

    def test_launch_controller_initializes_the_single_epic_run_controller(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.init_git(root)
            subprocess.run(["git", "checkout", "-b", "codex/app-001"], cwd=root, check=True, capture_output=True, text=True)
            source = self.write_prd(root, "APP-001", [epic("APP-001", "Account foundation")])
            launch_path = root / "launch.json"
            launch, source_text = gauntlet.build_epic_launch_set(source, [])
            snapshot = root / "launch.source.md"
            snapshot.write_text(source_text, encoding="utf-8")
            launch["source"]["snapshotPath"] = str(snapshot)
            launch["epics"]["APP-001"].update({"taskId": "task-123", "status": "in-progress"})
            gauntlet.write_launch_set(launch_path, launch)
            result = subprocess.run([
                "python3", str(Path(gauntlet.__file__).with_name("prd-run.py")), "init",
                "--executions", str(root / "executions"),
                "--run-id", "APP-001-RUN",
                "--source", str(snapshot),
                "--target", "APP-001",
                "--launch-set", str(launch_path),
                "--release-contract", "test-contract",
                "--release-stages", "merge",
                "--integration-branch", "codex/app-001",
                "--pr-strategy", "single-final-pr",
            ], cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            lock = json.loads((root / "executions" / "APP-001-RUN" / "source-lock.json").read_text(encoding="utf-8"))
            self.assertEqual(lock["target_epic_ids"], ["APP-001"])
            self.assertEqual(lock["launch_set"]["task_id"], "task-123")
            record_args = argparse.Namespace(
                git_root=root, launch_set=launch_path, epic="APP-001",
                run=root / "executions" / "APP-001-RUN", json=True,
            )
            with mock.patch("gauntlet.ensure_progress_supervisor", return_value={"status": "unavailable", "started": False, "stateFile": "state"}), mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_record_run(record_args), 0)
            self.assertEqual(output.call_args.args[0]["epics"]["APP-001"]["runPath"], str((root / "executions" / "APP-001-RUN").resolve()))

    def test_record_run_starts_one_dashboard_and_returns_browser_action_without_secret(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.write_prd(root, "APP-001", [epic("APP-001", "Account foundation")])
            launch_path = root / "launch.json"
            launch, source_text = gauntlet.build_epic_launch_set(source, [])
            snapshot = root / "launch.source.md"
            snapshot.write_text(source_text, encoding="utf-8")
            launch["source"]["snapshotPath"] = str(snapshot)
            launch["epics"]["APP-001"].update({"taskId": "task-123", "status": "in-progress"})
            run = root / "run"
            run.mkdir()
            (run / "source-lock.json").write_text(json.dumps({
                "target_epic_ids": ["APP-001"],
                "epics": {"APP-001": {}},
                "launch_set": {"path": str(launch_path.resolve()), "coverage_sha256": launch["coverageSha256"], "task_id": "task-123"},
            }))
            gauntlet.write_launch_set(launch_path, launch)
            args = argparse.Namespace(git_root=root, launch_set=launch_path, epic="APP-001", run=run, json=True)
            dashboard = {
                "status": "running", "started": True,
                "stateFile": str(root / "launch.progress-dashboard.json"),
                "launchId": launch["coverageSha256"],
            }
            with mock.patch("gauntlet.ensure_progress_supervisor", return_value=dashboard) as ensure, mock.patch("gauntlet.print_payload") as output:
                self.assertEqual(gauntlet.command_epic_tasks_record_run(args), 0)
            ensure.assert_called_once()
            action = output.call_args.args[0]["actions"][0]
            self.assertEqual("open_browser", action["type"])
            self.assertEqual("codex-in-app-browser", action["surface"])
            self.assertEqual(dashboard["stateFile"], action["stateFile"])
            self.assertNotIn("capability", json.dumps(action).lower())

            with mock.patch("gauntlet.ensure_progress_supervisor", side_effect=OSError("dashboard unavailable")), mock.patch("gauntlet.print_payload") as failed_dashboard:
                self.assertEqual(gauntlet.command_epic_tasks_record_run(args), 0)
            fallback = failed_dashboard.call_args.args[0]
            self.assertEqual("pass", fallback["status"])
            self.assertEqual([], fallback["actions"])
            self.assertEqual(str(run.resolve()), fallback["epics"]["APP-001"]["runPath"])

    def test_progress_source_refresh_discovers_late_run_and_independent_telemetry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            launch_path = root / "launch.json"
            launch = {
                "schemaVersion": gauntlet.EPIC_LAUNCH_SCHEMA,
                "source": {"path": str(root / "prd.md"), "sha256": "a" * 64, "snapshotPath": str(root / "snapshot.md")},
                "targetEpicIds": ["APP-001", "APP-002"],
                "coverageSha256": "b" * 64,
                "aggregateEmittedEvents": [],
                "epics": {
                    "APP-001": {"title": "One", "dependencies": [], "releaseStages": ["merge"], "consequenceTriggers": [],
                                "taskId": "task-1", "runPath": str(root / "run-1"), "status": "in-progress", "blocker": None,
                                "stopDisposition": None, "startReconciliation": None, "emittedEvents": []},
                    "APP-002": {"title": "Two", "dependencies": [], "releaseStages": ["merge"], "consequenceTriggers": [],
                                "taskId": None, "runPath": None, "status": "planned", "blocker": None,
                                "stopDisposition": None, "startReconciliation": None, "emittedEvents": []},
                },
            }
            gauntlet.write_launch_set(launch_path, launch)
            facts = {"schemaVersion": "gauntlet/epic-run-facts/v1", "epicId": "APP-001", "epicTitle": "One",
                     "time": {"protocolVersion": None, "elapsedCoverage": "unavailable", "createdAt": None,
                              "startedAt": None, "updatedAt": None, "terminalAt": None},
                     "progress": None, "operations": [], "owners": [], "release": {"applicability": {"merge": True}}}
            telemetry = {"schemaVersion": "gauntlet/run-telemetry-summary/v1", "coverage": {"status": "partial"},
                         "tokens": {"total_tokens": 10}, "pricing": {"status": "unavailable"}}
            with mock.patch("gauntlet.run_facts_for_progress", return_value=facts), mock.patch("gauntlet.telemetry_for_progress", return_value=telemetry):
                source_path = gauntlet.refresh_progress_source(launch_path, launch, root)
            first = json.loads(source_path.read_text())
            self.assertEqual("APP-002", first["runs"]["APP-002"]["facts"]["epicId"])
            self.assertIsNotNone(first["runs"]["APP-002"]["facts"]["time"]["updatedAt"])
            self.assertEqual("unavailable", first["runs"]["APP-002"]["facts"]["time"]["elapsedCoverage"])
            self.assertEqual(10, first["telemetry"]["APP-001"]["tokens"]["total_tokens"])

            launch["epics"]["APP-002"].update({"taskId": "task-2", "runPath": str(root / "run-2"), "status": "in-progress"})
            changed = dict(facts, epicId="APP-002", epicTitle="Two")
            telemetry["tokens"]["total_tokens"] = 25
            with mock.patch("gauntlet.run_facts_for_progress", side_effect=[facts, changed]), mock.patch("gauntlet.telemetry_for_progress", return_value=telemetry):
                gauntlet.refresh_progress_source(launch_path, launch, root)
            second = json.loads(source_path.read_text())
            self.assertEqual("run-2", second["runs"]["APP-002"]["runId"])
            self.assertEqual(25, second["telemetry"]["APP-001"]["tokens"]["total_tokens"])

            facts_with_owner = dict(facts, owners=[{
                "ownerId": "root", "ownerKind": "parent", "ownerRef": "root",
                "nativeChildId": "task-1", "requestedProfile": None,
                "requestWindow": None,
            }])
            with mock.patch("gauntlet.run_facts_for_progress", return_value=facts_with_owner), mock.patch("gauntlet.telemetry_for_progress", return_value=None):
                gauntlet.refresh_progress_source(launch_path, launch, root)
            failed_refresh = json.loads(source_path.read_text())
            stale = failed_refresh["telemetry"]["APP-001"]
            self.assertEqual(25, stale["tokens"]["total_tokens"])
            self.assertEqual("partial", stale["coverage"]["status"])
            self.assertEqual("stale", stale["coverage"]["freshness"]["status"])
            self.assertEqual(["telemetry-refresh-failed"], stale["coverage"]["limitations"])

            source_path.unlink()
            with mock.patch("gauntlet.run_facts_for_progress", return_value=facts_with_owner), mock.patch("gauntlet.telemetry_for_progress", return_value=None):
                gauntlet.refresh_progress_source(launch_path, launch, root)
            unavailable = json.loads(source_path.read_text())["telemetry"]["APP-001"]
            self.assertIsNone(unavailable["tokens"])
            self.assertEqual("unavailable", unavailable["coverage"]["status"])

    def test_dashboard_terminal_policy_waits_for_every_sibling_and_cleanup_is_idempotent(self):
        launch = {
            "targetEpicIds": ["ONE", "TWO"],
            "epics": {
                "ONE": {"status": "failed"},
                "TWO": {"status": "in-progress"},
            },
        }
        self.assertFalse(gauntlet.progress_launch_terminal(launch, {"ONE": {}, "TWO": {"complete": False}}))
        launch["epics"]["TWO"]["status"] = "stopped"
        self.assertTrue(gauntlet.progress_launch_terminal(launch, {"ONE": {}, "TWO": {}}))
        with mock.patch("gauntlet.progress_dashboard_status", return_value={"status": "stopped"}):
            self.assertEqual("stopped", gauntlet.stop_progress_dashboard(Path("launch.json"))["status"])
            self.assertEqual("stopped", gauntlet.stop_progress_dashboard(Path("launch.json"))["status"])

    def test_existing_dashboard_still_recovers_a_missing_supervisor(self):
        launch = {
            "targetEpicIds": ["ONE"],
            "coverageSha256": "a" * 64,
            "epics": {"ONE": {"status": "in-progress", "runPath": "run"}},
        }
        running = {"status": "running", "stateFile": "state", "pid": 1234}
        with mock.patch("gauntlet.progress_dashboard_status", return_value=running), mock.patch(
            "gauntlet.launch_projections", return_value={"ONE": {"complete": False}},
        ), mock.patch("gauntlet.subprocess.Popen") as spawn:
            result = gauntlet.ensure_progress_supervisor(Path("launch.json"), launch, Path.cwd())
        spawn.assert_called_once()
        self.assertEqual("running", result["status"])
        self.assertFalse(result["started"])

    def test_progress_supervisor_lock_rejects_symlink_without_touching_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            launch = root / "launch.json"
            target = root / "unmanaged.txt"
            target.write_text("keep", encoding="utf-8")
            target.chmod(0o644)
            gauntlet.progress_paths(launch)["supervisorLock"].symlink_to(target)
            args = argparse.Namespace(git_root=root, launch_set=launch, interval=0.5)
            self.assertEqual(0, gauntlet.command_epic_tasks_progress_supervise(args))
            self.assertEqual(0o644, target.stat().st_mode & 0o777)

    def test_runtime_hash_drift_stops_authenticated_owner_before_restart(self):
        launch = {
            "targetEpicIds": ["ONE"],
            "coverageSha256": "a" * 64,
            "epics": {"ONE": {"status": "in-progress", "runPath": "run"}},
        }
        owned = {"status": "running", "pid": 1234, "stateFile": "state"}
        unavailable = {"status": "unavailable", "stateFile": "state"}
        running = {"status": "running", "stateFile": "state", "pid": 5678}
        with mock.patch("gauntlet.authenticated_progress_state", return_value=(Path("state"), owned)), mock.patch(
            "gauntlet.verified_progress_state", return_value=(Path("state"), None),
        ), mock.patch("gauntlet.stop_progress_dashboard") as stop, mock.patch(
            "gauntlet.progress_dashboard_status", side_effect=[unavailable, running],
        ), mock.patch("gauntlet.subprocess.Popen"):
            result = gauntlet.ensure_progress_supervisor(Path("launch.json"), launch, Path.cwd())
        stop.assert_called_once()
        self.assertTrue(result["started"])

    def test_optional_dashboard_status_failure_is_non_blocking(self):
        with mock.patch("gauntlet.progress_dashboard_status", side_effect=OSError("optional dashboard unavailable")):
            result = gauntlet.safely_progress_dashboard_status(Path("launch.json"))
        self.assertEqual("unavailable", result["status"])
        self.assertFalse(result["started"])

    def test_malformed_dashboard_origin_is_rejected_before_transport(self):
        state = {
            "schemaVersion": gauntlet.PROGRESS_STATE_SCHEMA,
            "status": "running",
            "pid": 1234,
            "capability": "opaque-capability",
            "origin": ["http://127.0.0.1:8000"],
        }
        with mock.patch("gauntlet.read_progress_state", return_value=(Path("state"), state)), mock.patch(
            "gauntlet.urllib.request.build_opener",
        ) as opener:
            _, result = gauntlet.authenticated_progress_state(Path("launch.json"))
        self.assertIsNone(result)
        opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
