#!/usr/bin/env python3
"""Behavior tests for prd-run.py."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("prd-run.py")


def graph(scope_one: str = "Account balance behavior", ticket_one: str = "Implement balance") -> dict:
    return {
        "version": 1,
        "scope_areas": ["E1-S1", "E1-S2"],
        "shared_context": {
            "global": "Preserve unrelated work and use repository conventions.",
            "cohorts": {"C1": "The stored balance and rendered balance must agree."},
        },
        "cohorts": {"C1": {"invariant": "Stored and rendered balances agree.", "ticket_ids": ["T1", "T2"]}},
        "tickets": [
            {
                "id": "T1", "epic_id": "E1", "title": ticket_one,
                "objective": "Implement the canonical balance calculation.",
                "scope_area_ids": ["E1-S1"], "cohort_id": "C1", "dependencies": [],
                "ownership": ["src/balance.py"], "constraints": ["Do not change persistence."],
                "acceptance": ["The external calculator returns the expected balance."],
                "proof": {
                    "claim": "The calculator returns the canonical balance.",
                    "oracle": "Compare public API results with independently calculated fixtures.",
                    "wrong_case": "A stale cached balance differs from the fixture and must fail.",
                    "non_effects": ["Persistence format remains unchanged."],
                },
                "return_contract": "Return changed paths and test evidence.",
                "ask_parent_policy": "Ask only if the persistence contract must change.",
                "source_files": ["src/balance.py"],
            },
            {
                "id": "T2", "epic_id": "E1", "title": "Render balance",
                "objective": "Render the canonical balance in the account view.",
                "scope_area_ids": ["E1-S2"], "cohort_id": "C1", "dependencies": ["T1"],
                "ownership": ["src/view.py"], "constraints": [],
                "acceptance": ["The public view shows the API balance."],
                "proof": {
                    "claim": "The account view shows the canonical balance.",
                    "oracle": "Exercise the public view and compare its value with the API result.",
                    "wrong_case": "A view using a hard-coded value must disagree and fail.",
                    "non_effects": ["Other account fields remain unchanged."],
                },
                "return_contract": "Return changed paths and black-box evidence.",
                "ask_parent_policy": "Ask only if the public view contract is ambiguous.",
                "source_files": ["src/view.py"],
            },
        ],
    }


class PrdRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "prd.md"
        self.source.write_text(
            "# PRD\n\nImplementation target: E1\n\n## Epic E1: Balance\n\nEpic status: Accepted\n\n"
            "### Scope Area E1-S1: Balance behavior\n\nInitial balance requirements.\n\n"
            "### Scope Area E1-S2: Presentation behavior\n\nInitial presentation requirements.\n"
        )
        self.graph = self.root / "graph.json"
        self.write_graph(graph())
        self.run_command(
            "init", "--executions", str(self.root / "executions"), "--run-id", "RUN1", "--source", str(self.source),
            "--target", "E1", "--release-contract", "doc_org.md:v1", "--release-stages", "merge,deployment,production-verification",
        )
        self.run = self.root / "executions" / "RUN1"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_graph(self, value: dict) -> None:
        self.graph.write_text(json.dumps(value))

    def run_command(self, *args: str, ok: bool = True, env=None) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(["python3", str(SCRIPT), *args], text=True, capture_output=True, env={**os.environ, **(env or {})})
        if ok and result.returncode:
            self.fail(f"command failed: {args}\nstdout={result.stdout}\nstderr={result.stderr}")
        if not ok and result.returncode == 0:
            self.fail(f"command unexpectedly succeeded: {args}")
        return result

    def transition(self, state: str) -> None:
        self.run_command("transition", "--run", str(self.run), "--to", state)

    def compile_and_start(self) -> None:
        self.transition("accepted")
        self.run_command("compile", "--run", str(self.run), "--graph", str(self.graph))
        self.transition("executing")

    def manifest(self) -> dict:
        return json.loads((self.run / "manifest.json").read_text())

    def complete(self, ticket: str, agent: str, attempt: int = 1) -> None:
        self.run_command("claim", "--run", str(self.run), "--ticket", ticket, "--agent", agent, "--attempt", str(attempt))
        evidence = self.run / "evidence" / f"{ticket}.r{self.manifest()['tickets'][ticket]['revision']}.a{attempt}.md"
        evidence.write_text(f"# Evidence {ticket}\n\nObserved behavior through the public interface.\n")
        revision = self.manifest()["tickets"][ticket]["revision"]
        receipt = self.root / f"{ticket}-receipt.json"
        receipt.write_text(json.dumps({
            "agent": agent, "attempt": attempt, "changed_paths": [f"src/{ticket}.py"],
            "evidence": [str(evidence.relative_to(self.run))], "outputs": [f"contract:{ticket}"],
            "revision": revision, "risks": [], "status": "complete",
            "summary": f"Completed {ticket} and observed its external behavior.", "ticket": ticket,
        }))
        self.run_command("record-receipt", "--run", str(self.run), "--ticket", ticket, "--receipt", str(receipt))
        parent_evidence = self.run / "evidence" / f"{ticket}-parent.md"
        parent_evidence.write_text(f"# Parent verification {ticket}\n\nIndependently reran the public behavior oracle.\n")
        self.run_command(
            "integrate", "--run", str(self.run), "--ticket", ticket,
            "--evidence", str(parent_evidence), "--summary", "Parent independently verified the ticket oracle.",
        )

    def test_init_creates_canonical_artifacts_and_validates_order(self) -> None:
        expected = {
            "source-lock.json", "manifest.json", "shared-context", "resume.md", "events.jsonl",
            "tickets", "receipts", "evidence", "cohorts", "release",
        }
        self.assertTrue(expected.issubset({item.name for item in self.run.iterdir()}))
        self.run_command("transition", "--run", str(self.run), "--to", "compiled", ok=False)
        self.assertEqual(self.manifest()["state"], "discussing")

    def test_init_interruption_leaves_no_partial_run_and_can_retry(self) -> None:
        self.run_command(
            "init", "--executions", str(self.root / "executions"), "--run-id", "INITRETRY", "--source", str(self.source),
            "--target", "E1", "--release-contract", "doc_org.md:v1", ok=False,
            env={"PRD_RUN_FAIL_INIT_AFTER": "source-lock"},
        )
        self.assertFalse((self.root / "executions" / "INITRETRY").exists())
        self.assertFalse(list((self.root / "executions").glob(".INITRETRY.init-*")))
        self.run_command(
            "init", "--executions", str(self.root / "executions"), "--run-id", "INITRETRY", "--source", str(self.source),
            "--target", "E1", "--release-contract", "doc_org.md:v1",
        )
        self.assertTrue((self.root / "executions" / "INITRETRY" / "manifest.json").is_file())

    def test_compile_materialize_is_deterministic_bounded_and_ticket_last(self) -> None:
        self.compile_and_start()
        self.run_command("claim", "--run", str(self.run), "--ticket", "T1", "--agent", "agent-a", "--attempt", "1")
        first = self.run_command("materialize-ticket", "--run", str(self.run), "--ticket", "T1").stdout
        second = self.run_command("materialize-ticket", "--run", str(self.run), "--ticket", "T1").stdout
        self.assertEqual(first, second)
        self.assertNotIn("Initial requirements", first)
        self.assertNotIn('"event_sequence"', first)
        self.assertNotIn("T2: Render balance", first)
        self.assertLess(first.index("# Global context"), first.index("# Cohort C1 context"))
        self.assertLess(first.index("# Cohort C1 context"), first.index("# Assigned ticket"))
        self.assertIn("handoffs/T1.r1.a1.receipt.json", first)
        manifest_before = (self.run / "manifest.json").read_text()
        self.run_command("materialize-ticket", "--run", str(self.run), "--ticket", "T1", "--output", str(self.run / "manifest.json"), ok=False)
        self.assertEqual((self.run / "manifest.json").read_text(), manifest_before)
        self.assertTrue(first.rstrip().endswith("```"))

    def test_compile_interruption_recovers_before_retry(self) -> None:
        self.transition("accepted")
        self.run_command(
            "compile", "--run", str(self.run), "--graph", str(self.graph), ok=False,
            env={"PRD_RUN_FAIL_COMPILE_AFTER": "global-context"},
        )
        self.assertTrue((self.run / ".compile-backup").is_dir())
        self.run_command("compile", "--run", str(self.run), "--graph", str(self.graph))
        self.assertFalse((self.run / ".compile-backup").exists())
        self.assertEqual(self.manifest()["state"], "compiled")
        self.run_command(
            "init", "--executions", str(self.root / "executions"), "--run-id", "RUNPOST", "--source", str(self.source),
            "--target", "E1", "--release-contract", "doc_org.md:v1",
        )
        post = self.root / "executions" / "RUNPOST"
        self.run_command("transition", "--run", str(post), "--to", "accepted")
        self.run_command(
            "compile", "--run", str(post), "--graph", str(self.graph), ok=False,
            env={"PRD_RUN_FAIL_COMPILE_AFTER": "manifest"},
        )
        self.assertTrue((post / ".compile-backup").is_dir())
        self.run_command("resume", "--run", str(post))
        self.assertFalse((post / ".compile-backup").exists())
        self.assertEqual(json.loads((post / "manifest.json").read_text())["state"], "compiled")

    def test_leases_dependencies_receipts_and_immutable_revisions(self) -> None:
        self.compile_and_start()
        self.run_command("claim", "--run", str(self.run), "--ticket", "T2", "--agent", "agent-b", "--attempt", "1", ok=False)
        self.assertEqual(self.manifest()["tickets"]["T2"]["status"], "waiting")
        self.complete("T1", "agent-a")
        self.assertEqual(self.manifest()["tickets"]["T2"]["status"], "ready")
        self.run_command("claim", "--run", str(self.run), "--ticket", "T2", "--agent", "agent-b", "--attempt", "1")
        bundle = self.run_command("materialize-ticket", "--run", str(self.run), "--ticket", "T2").stdout
        self.assertIn("contract:T1", bundle)
        ticket_file = self.run / self.manifest()["tickets"]["T2"]["ticket_file"]
        ticket_file.write_text(ticket_file.read_text() + "tampered\n")
        self.run_command("materialize-ticket", "--run", str(self.run), "--ticket", "T2", ok=False)
        self.assertEqual(self.manifest()["tickets"]["T2"]["lease"], {"agent": "agent-b", "attempt": 1})

    def test_receipt_requires_matching_lease_and_real_local_evidence(self) -> None:
        self.compile_and_start()
        self.run_command("claim", "--run", str(self.run), "--ticket", "T1", "--agent", "agent-a", "--attempt", "2")
        receipt = self.root / "bad.json"
        receipt.write_text(json.dumps({
            "agent": "different-agent", "attempt": 2, "changed_paths": [], "evidence": ["evidence/missing.md"],
            "outputs": [], "revision": 1, "risks": [], "status": "complete", "summary": "Done", "ticket": "T1",
        }))
        self.run_command("record-receipt", "--run", str(self.run), "--ticket", "T1", "--receipt", str(receipt), ok=False)
        self.assertFalse(any((self.run / "receipts").iterdir()))
        receipt_data = json.loads(receipt.read_text())
        receipt_data["agent"] = "agent-a"
        receipt.write_text(json.dumps(receipt_data))
        self.run_command("record-receipt", "--run", str(self.run), "--ticket", "T1", "--receipt", str(receipt), ok=False)
        receipt_data["evidence"] = ["manifest.json"]
        receipt.write_text(json.dumps(receipt_data))
        self.run_command("record-receipt", "--run", str(self.run), "--ticket", "T1", "--receipt", str(receipt), ok=False)
        self.assertEqual(self.manifest()["tickets"]["T1"]["status"], "dispatched")

    def test_integration_requires_distinct_parent_verification(self) -> None:
        self.compile_and_start()
        self.run_command("claim", "--run", str(self.run), "--ticket", "T1", "--agent", "agent-a", "--attempt", "1")
        child_evidence = self.run / "evidence" / "T1.r1.a1.md"
        child_evidence.write_text("# Child evidence\n\nObserved the public result.\n")
        receipt = self.root / "T1-receipt.json"
        receipt.write_text(json.dumps({
            "agent": "agent-a", "attempt": 1, "changed_paths": ["src/T1.py"],
            "evidence": ["evidence/T1.r1.a1.md"], "outputs": ["contract:T1"], "revision": 1,
            "risks": [], "status": "complete", "summary": "Completed T1.", "ticket": "T1",
        }))
        self.run_command("record-receipt", "--run", str(self.run), "--ticket", "T1", "--receipt", str(receipt))
        self.run_command(
            "integrate", "--run", str(self.run), "--ticket", "T1",
            "--evidence", str(child_evidence), "--summary", "Reused child evidence.", ok=False,
        )
        copied = self.run / "evidence" / "T1-parent-copy.md"
        copied.write_bytes(child_evidence.read_bytes())
        self.run_command(
            "integrate", "--run", str(self.run), "--ticket", "T1",
            "--evidence", str(copied), "--summary", "Copied child evidence.", ok=False,
        )
        self.assertEqual(self.manifest()["tickets"]["T1"]["status"], "completed")

    def test_graph_is_bound_to_locked_target_and_scope_areas(self) -> None:
        self.transition("accepted")
        invalid = graph()
        invalid["tickets"][0]["epic_id"] = "E2"
        self.write_graph(invalid)
        self.run_command("compile", "--run", str(self.run), "--graph", str(self.graph), ok=False)
        self.assertFalse((self.run / "ticket-graph.json").exists())
        proposed = self.root / "proposed.md"
        proposed.write_text(
            "# PRD\n\nImplementation target: E2\n\n## Epic E2: Proposed\n\nEpic status: Proposed\n\n"
            "### Scope Area E2-S1: Proposed behavior\n\nNot accepted.\n"
        )
        self.run_command(
            "init", "--executions", str(self.root / "executions"), "--run-id", "BADRUN", "--source", str(proposed),
            "--target", "E2", "--release-contract", "doc_org.md:v1", ok=False,
        )
        self.assertFalse((self.root / "executions" / "BADRUN").exists())
        duplicate = self.root / "duplicate.md"
        duplicate.write_text(
            "# PRD\n\nImplementation target: E1\n\n## Epic E1: First\n\nEpic status: Accepted\n\n"
            "### Scope Area E1-S1: First\n\nOne.\n\n## Epic E1: Duplicate\n\nEpic status: Accepted\n\n"
            "### Scope Area E1-S1: Duplicate\n\nTwo.\n"
        )
        self.run_command(
            "init", "--executions", str(self.root / "executions"), "--run-id", "DUPRUN", "--source", str(duplicate),
            "--target", "E1", "--release-contract", "doc_org.md:v1", ok=False,
        )
        duplicate_scope = self.root / "duplicate-scope.md"
        duplicate_scope.write_text(
            "# PRD\n\nImplementation target: E1\n\n## Epic E1: First\n\nEpic status: Accepted\n\n"
            "### Scope Area E1-S1: First\n\nOne.\n\n### Scope Area E1-S1: Duplicate\n\nTwo.\n"
        )
        self.run_command(
            "init", "--executions", str(self.root / "executions"), "--run-id", "DUPSCOPERUN", "--source", str(duplicate_scope),
            "--target", "E1", "--release-contract", "doc_org.md:v1", ok=False,
        )

    def test_one_active_ticket_per_agent_and_ready_queue_order(self) -> None:
        value = graph()
        value["tickets"][0].update({"affinity": ["balance"], "interface_first": False, "priority": 10})
        value["tickets"][1].update({"dependencies": [], "affinity": ["view"], "interface_first": True, "priority": 100})
        self.write_graph(value)
        self.compile_and_start()
        ready = json.loads(self.run_command("ready", "--run", str(self.run)).stdout)
        self.assertEqual(ready[0]["ticket"], "T2")
        affinity = json.loads(self.run_command("ready", "--run", str(self.run), "--affinity", "balance").stdout)
        self.assertEqual(affinity[0]["ticket"], "T1")
        self.run_command("claim", "--run", str(self.run), "--ticket", "T1", "--agent", "agent-a", "--attempt", "1")
        self.run_command("claim", "--run", str(self.run), "--ticket", "T2", "--agent", "agent-a", "--attempt", "1", ok=False)
        self.assertEqual(self.manifest()["tickets"]["T2"]["status"], "ready")

    def test_concurrent_parent_commands_preserve_both_claims(self) -> None:
        value = graph(); value["tickets"][1]["dependencies"] = []
        self.write_graph(value); self.compile_and_start()
        commands = [
            ["python3", str(SCRIPT), "claim", "--run", str(self.run), "--ticket", "T1", "--agent", "agent-a", "--attempt", "1"],
            ["python3", str(SCRIPT), "claim", "--run", str(self.run), "--ticket", "T2", "--agent", "agent-b", "--attempt", "1"],
        ]
        processes = [subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for command in commands]
        results = [process.communicate() + (process.returncode,) for process in processes]
        self.assertEqual([item[2] for item in results], [0, 0], results)
        current = self.manifest()
        self.assertEqual(current["tickets"]["T1"]["status"], "dispatched")
        self.assertEqual(current["tickets"]["T2"]["status"], "dispatched")

    def test_pinned_receipt_tamper_stops_future_commands(self) -> None:
        self.compile_and_start()
        self.complete("T1", "agent-a")
        receipt = self.run / "receipts" / "T1.r1.a1.json"
        receipt.write_text(receipt.read_text() + "\n")
        self.run_command("ready", "--run", str(self.run), ok=False)

    def test_reconcile_interruption_rolls_back_before_retry(self) -> None:
        self.compile_and_start()
        changed = graph(scope_one="Revised account balance behavior")
        self.write_graph(changed)
        self.source.write_text(
            "# PRD\n\nImplementation target: E1\n\n## Epic E1: Balance\n\nEpic status: Accepted\n\n"
            "### Scope Area E1-S1: Balance behavior\n\nRevised balance requirements.\n\n"
            "### Scope Area E1-S2: Presentation behavior\n\nInitial presentation requirements.\n"
        )
        self.run_command(
            "reconcile", "--run", str(self.run), "--source", str(self.source), "--graph", str(self.graph),
            ok=False, env={"PRD_RUN_FAIL_RECONCILE_AFTER": "source-lock"},
        )
        self.assertTrue((self.run / ".reconcile-backup").is_dir())
        self.run_command("reconcile", "--run", str(self.run), "--source", str(self.source), "--graph", str(self.graph))
        self.assertFalse((self.run / ".reconcile-backup").exists())
        self.assertEqual(self.manifest()["tickets"]["T1"]["revision"], 2)
        self.source.write_text(
            "# PRD\n\nImplementation target: E1\n\n## Epic E1: Balance\n\nEpic status: Accepted\n\n"
            "### Scope Area E1-S1: Balance behavior\n\nThird balance requirements.\n\n"
            "### Scope Area E1-S2: Presentation behavior\n\nInitial presentation requirements.\n"
        )
        self.run_command(
            "reconcile", "--run", str(self.run), "--source", str(self.source), "--graph", str(self.graph),
            ok=False, env={"PRD_RUN_FAIL_RECONCILE_AFTER": "manifest"},
        )
        self.assertTrue((self.run / ".reconcile-backup").is_dir())
        self.run_command("resume", "--run", str(self.run))
        self.assertFalse((self.run / ".reconcile-backup").exists())
        self.assertEqual(self.manifest()["tickets"]["T1"]["revision"], 3)
        (self.run / ".reconcile-backup.tmp").mkdir()
        self.run_command("resume", "--run", str(self.run))
        self.assertFalse((self.run / ".reconcile-backup.tmp").exists())

    def test_reconcile_rejects_tampered_source_lock_authority(self) -> None:
        self.compile_and_start()
        lock_path = self.run / "source-lock.json"
        lock = json.loads(lock_path.read_text()); lock["release_contract"] = "TAMPERED"
        lock_path.write_text(json.dumps(lock))
        self.source.write_text(
            "# PRD\n\nImplementation target: E1\n\n## Epic E1: Balance\n\nEpic status: Accepted\n\n"
            "### Scope Area E1-S1: Balance behavior\n\nLegitimate revised requirements.\n\n"
            "### Scope Area E1-S2: Presentation behavior\n\nInitial presentation requirements.\n"
        )
        self.run_command("reconcile", "--run", str(self.run), "--source", str(self.source), "--graph", str(self.graph), ok=False)
        self.assertEqual(self.manifest()["generation"], 1)

    def test_blocked_receipt_can_be_retried_only_with_a_new_attempt(self) -> None:
        self.compile_and_start()
        self.run_command("claim", "--run", str(self.run), "--ticket", "T1", "--agent", "agent-a", "--attempt", "1")
        receipt = self.root / "blocked.json"
        receipt.write_text(json.dumps({
            "agent": "agent-a", "attempt": 1, "changed_paths": [], "evidence": [], "outputs": [],
            "revision": 1, "risks": ["Missing local service"], "status": "blocked",
            "summary": "The required local service was unavailable.", "ticket": "T1",
        }))
        self.run_command("record-receipt", "--run", str(self.run), "--ticket", "T1", "--receipt", str(receipt))
        self.run_command("claim", "--run", str(self.run), "--ticket", "T1", "--agent", "agent-a", "--attempt", "1", ok=False)
        self.assertEqual(self.manifest()["tickets"]["T1"]["lease"], {"agent": "agent-a", "attempt": 1})
        self.run_command("claim", "--run", str(self.run), "--ticket", "T1", "--agent", "agent-b", "--attempt", "2")
        lease = self.manifest()["tickets"]["T1"]["lease"]
        self.assertEqual(lease, {"agent": "agent-b", "attempt": 2})
        evidence = self.run / "evidence" / "T1.r1.a2.md"
        evidence.write_text("# Retry evidence\n\nThe second attempt passed the public behavior oracle.\n")
        receipt.write_text(json.dumps({
            "agent": "agent-b", "attempt": 2, "changed_paths": ["src/T1.py"],
            "evidence": [str(evidence)], "outputs": ["contract:T1"], "revision": 1,
            "risks": [], "status": "complete", "summary": "Retry completed.", "ticket": "T1",
        }))
        self.run_command("record-receipt", "--run", str(self.run), "--ticket", "T1", "--receipt", str(receipt))
        parent = self.run / "evidence" / "T1-parent-retry.md"
        parent.write_text("# Parent retry verification\n\nIndependently reran the public oracle.\n")
        self.run_command("integrate", "--run", str(self.run), "--ticket", "T1", "--evidence", str(parent), "--summary", "Parent verified retry.")
        self.assertTrue((self.run / "receipts" / "T1.r1.a1.json").is_file())
        self.assertTrue((self.run / "receipts" / "T1.r1.a2.json").is_file())

    def test_selective_invalidation_revises_affected_ticket_and_dependents(self) -> None:
        self.compile_and_start()
        original_t1 = self.manifest()["tickets"]["T1"]["ticket_sha256"]
        changed_graph = graph(scope_one="Revised account balance behavior")
        changed_graph["shared_context"]["cohorts"]["C1"] = "Revised cohort contract."
        self.write_graph(changed_graph)
        self.source.write_text(
            "# PRD\n\nImplementation target: E1\n\n## Epic E1: Balance\n\nEpic status: Accepted\n\n"
            "### Scope Area E1-S1: Balance behavior\n\nRevised balance requirements.\n\n"
            "### Scope Area E1-S2: Presentation behavior\n\nInitial presentation requirements.\n"
        )
        locked = self.run_command("materialize-ticket", "--run", str(self.run), "--ticket", "T1", ok=False)
        self.assertEqual(locked.stdout, "")
        result = self.run_command("reconcile", "--run", str(self.run), "--source", str(self.source), "--graph", str(self.graph))
        report = json.loads(result.stdout)
        self.assertEqual(report["changed_scopes"], ["E1-S1"])
        self.assertEqual(report["invalidated_tickets"], ["T1", "T2"])
        current = self.manifest()
        self.assertEqual(current["tickets"]["T1"]["revision"], 2)
        self.assertEqual(current["tickets"]["T2"]["revision"], 2)
        self.assertNotEqual(current["tickets"]["T1"]["ticket_sha256"], original_t1)
        self.assertTrue((self.run / "tickets" / "T1.r1.md").exists())
        self.assertTrue((self.run / "tickets" / "T1.r2.md").exists())
        self.assertEqual(current["shared_context"]["cohorts"]["C1"], "shared-context/c1-v2.md")
        self.assertTrue((self.run / "shared-context" / "c1-v1.md").exists())
        self.assertTrue((self.run / "shared-context" / "c1-v2.md").exists())
        old_revision = self.run / "tickets" / "T1.r1.md"
        old_revision.write_text(old_revision.read_text() + "tampered\n")
        immutable = self.run_command("materialize-ticket", "--run", str(self.run), "--ticket", "T1", ok=False)
        self.assertEqual(immutable.stdout, "")

    def test_cohort_and_release_gates_require_structured_passes(self) -> None:
        self.compile_and_start()
        self.complete("T1", "agent-a")
        self.complete("T2", "agent-b")
        self.transition("integrating")
        self.run_command("transition", "--run", str(self.run), "--to", "cohort_verified", ok=False)
        self.assertEqual(self.manifest()["state"], "integrating")
        cohort_evidence = self.run / "evidence" / "cohort.md"
        cohort_evidence.write_text("# Cohort proof\n\nThe public API and view returned the same independently expected value.\n")
        self.run_command("verify-cohort", "--run", str(self.run), "--cohort", "C1", "--result", "pass", "--evidence", str(cohort_evidence))
        self.transition("cohort_verified")
        self.run_command("transition", "--run", str(self.run), "--to", "prd_verified", ok=False)
        self.assertEqual(self.manifest()["state"], "cohort_verified")
        prd_evidence = self.run / "evidence" / "prd.md"
        prd_evidence.write_text("# Full PRD proof\n\nIndependently exercised every accepted outcome and non-effect.\n")
        self.run_command("verify-prd", "--run", str(self.run), "--result", "pass", "--summary", "All acceptance behavior observed.", "--evidence", str(prd_evidence))
        self.transition("prd_verified")
        revision = "a" * 40
        self.run_command("record-merge", "--run", str(self.run), "--pr", "PR-123", "--merged-sha", revision, "--main-sha", revision, "--evidence", "git-main-check")
        self.transition("merged")
        self.run_command("record-release", "--run", str(self.run), "--stage", "deployment", "--result", "fail", "--summary", "Deployment verification failed.", "--evidence", "deployment-failure-1")
        self.run_command("record-release", "--run", str(self.run), "--stage", "deployment", "--result", "pass", "--summary", "Retried without rollback.", "--evidence", "deployment-id-1", "--revision", revision, ok=False)
        self.run_command("record-rollback", "--run", str(self.run), "--trigger", "Deployment verification failed", "--action", "Restore prior release", "--result", "pass", "--evidence", "rollback-id-1")
        self.run_command("record-release", "--run", str(self.run), "--stage", "deployment", "--result", "pass", "--summary", "Exact merged revision deployed.", "--evidence", "deployment-id-1", "--revision", revision)
        self.transition("deployed")
        self.run_command("record-release", "--run", str(self.run), "--stage", "production-verification", "--result", "pass", "--summary", "Production behavior observed.", "--evidence", "production-check-1")
        self.transition("production_verified")
        self.transition("complete")
        self.assertEqual(self.manifest()["state"], "complete")

    def test_non_deploy_run_records_reasoned_skips_without_fake_production(self) -> None:
        self.run_command(
            "init", "--executions", str(self.root / "executions"), "--run-id", "RUN2", "--source", str(self.source),
            "--target", "E1", "--release-contract", "doc_org.md:v1", "--release-stages", "merge",
        )
        self.run = self.root / "executions" / "RUN2"
        self.compile_and_start()
        self.complete("T1", "agent-a"); self.complete("T2", "agent-b")
        self.transition("integrating")
        cohort = self.run / "evidence" / "cohort-independent.md"
        cohort.write_text("# Cohort proof\n\nIndependently compared the public API and view.\n")
        self.run_command("verify-cohort", "--run", str(self.run), "--cohort", "C1", "--result", "pass", "--evidence", str(cohort))
        self.transition("cohort_verified")
        prd = self.run / "evidence" / "prd-independent.md"
        prd.write_text("# Full PRD proof\n\nIndependently checked all target outcomes.\n")
        self.run_command("verify-prd", "--run", str(self.run), "--result", "pass", "--summary", "Target verified.", "--evidence", str(prd))
        self.transition("prd_verified")
        revision = "b" * 40
        self.run_command("record-merge", "--run", str(self.run), "--pr", "PR-124", "--merged-sha", revision, "--main-sha", revision, "--evidence", "git-main-check")
        self.transition("merged")
        self.run_command("record-release", "--run", str(self.run), "--stage", "deployment", "--result", "skipped", "--summary", "The accepted PRD has no deployment.", "--evidence", "source-lock release applicability")
        self.transition("deployed")
        self.run_command("record-release", "--run", str(self.run), "--stage", "production-verification", "--result", "skipped", "--summary", "No production mutation occurred.", "--evidence", "source-lock release applicability")
        self.transition("production_verified"); self.transition("complete")
        self.assertEqual(self.manifest()["release"]["deployment"]["result"], "skipped")

    def test_graph_rejects_cycles_and_meaningless_identical_wrong_case(self) -> None:
        self.transition("accepted")
        invalid = graph()
        invalid["tickets"][0]["dependencies"] = ["T2"]
        self.write_graph(invalid)
        self.run_command("compile", "--run", str(self.run), "--graph", str(self.graph), ok=False)
        self.assertEqual(self.manifest()["tickets"], {})
        invalid = graph()
        invalid["tickets"][0]["proof"]["wrong_case"] = invalid["tickets"][0]["proof"]["oracle"]
        self.write_graph(invalid)
        self.run_command("compile", "--run", str(self.run), "--graph", str(self.graph), ok=False)
        self.assertFalse((self.run / "ticket-graph.json").exists())


if __name__ == "__main__":
    unittest.main()
