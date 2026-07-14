#!/usr/bin/env python3
"""Behavior tests for prd-run.py."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("prd-run.py")


def graph(scope_one: str = "Account balance behavior", ticket_one: str = "Implement balance") -> dict:
    return {
        "version": 1,
        "scope_areas": {"SA1": scope_one, "SA2": "Presentation behavior"},
        "shared_context": {
            "global": "Preserve unrelated work and use repository conventions.",
            "cohorts": {"C1": "The stored balance and rendered balance must agree."},
        },
        "cohorts": {"C1": {"invariant": "Stored and rendered balances agree.", "ticket_ids": ["T1", "T2"]}},
        "tickets": [
            {
                "id": "T1", "epic_id": "E1", "title": ticket_one,
                "objective": "Implement the canonical balance calculation.",
                "scope_area_ids": ["SA1"], "cohort_id": "C1", "dependencies": [],
                "ownership": ["src/balance.py"], "constraints": ["Do not change persistence."],
                "acceptance": ["The external calculator returns the expected balance."],
                "proof": {
                    "claim": "The calculator returns the canonical balance.",
                    "oracle": "Compare public API results with independently calculated fixtures.",
                    "wrong_case": "A stale cached balance differs from the fixture and must fail.",
                    "non_effects": ["Persistence format remains unchanged."],
                },
                "return_contract": "Return changed paths and test evidence.",
                "ask_user_policy": "Ask only if the persistence contract must change.",
                "source_files": ["src/balance.py"],
            },
            {
                "id": "T2", "epic_id": "E1", "title": "Render balance",
                "objective": "Render the canonical balance in the account view.",
                "scope_area_ids": ["SA2"], "cohort_id": "C1", "dependencies": ["T1"],
                "ownership": ["src/view.py"], "constraints": [],
                "acceptance": ["The public view shows the API balance."],
                "proof": {
                    "claim": "The account view shows the canonical balance.",
                    "oracle": "Exercise the public view and compare its value with the API result.",
                    "wrong_case": "A view using a hard-coded value must disagree and fail.",
                    "non_effects": ["Other account fields remain unchanged."],
                },
                "return_contract": "Return changed paths and black-box evidence.",
                "ask_user_policy": "Ask only if the public view contract is ambiguous.",
                "source_files": ["src/view.py"],
            },
        ],
    }


class PrdRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "prd.md"
        self.source.write_text("# PRD\n\n## E1\n\nInitial requirements.\n")
        self.graph = self.root / "graph.json"
        self.write_graph(graph())
        self.run_command("init", "--executions", str(self.root / "executions"), "--run-id", "RUN1", "--source", str(self.source))
        self.run = self.root / "executions" / "RUN1"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_graph(self, value: dict) -> None:
        self.graph.write_text(json.dumps(value))

    def run_command(self, *args: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(["python3", str(SCRIPT), *args], text=True, capture_output=True)
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
        evidence = self.run / "evidence" / f"{ticket}.md"
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
        self.run_command("integrate", "--run", str(self.run), "--ticket", ticket)

    def test_init_creates_canonical_artifacts_and_validates_order(self) -> None:
        expected = {
            "source-lock.json", "manifest.json", "shared-context", "resume.md", "events.jsonl",
            "tickets", "receipts", "evidence", "cohorts", "release",
        }
        self.assertTrue(expected.issubset({item.name for item in self.run.iterdir()}))
        self.run_command("transition", "--run", str(self.run), "--to", "compiled", ok=False)
        self.assertEqual(self.manifest()["state"], "discussing")

    def test_compile_materialize_is_deterministic_bounded_and_ticket_last(self) -> None:
        self.compile_and_start()
        first = self.run_command("materialize-ticket", "--run", str(self.run), "--ticket", "T1").stdout
        second = self.run_command("materialize-ticket", "--run", str(self.run), "--ticket", "T1").stdout
        self.assertEqual(first, second)
        self.assertNotIn("Initial requirements", first)
        self.assertNotIn('"event_sequence"', first)
        self.assertNotIn("T2: Render balance", first)
        self.assertLess(first.index("# Global context"), first.index("# Cohort C1 context"))
        self.assertLess(first.index("# Cohort C1 context"), first.index("# Assigned ticket"))
        self.assertTrue(first.rstrip().endswith("Ask only if the persistence contract must change."))

    def test_leases_dependencies_receipts_and_immutable_revisions(self) -> None:
        self.compile_and_start()
        self.run_command("claim", "--run", str(self.run), "--ticket", "T2", "--agent", "agent-b", "--attempt", "1", ok=False)
        self.assertEqual(self.manifest()["tickets"]["T2"]["status"], "waiting")
        self.complete("T1", "agent-a")
        self.assertEqual(self.manifest()["tickets"]["T2"]["status"], "ready")
        bundle = self.run_command("materialize-ticket", "--run", str(self.run), "--ticket", "T2").stdout
        self.assertIn("contract:T1", bundle)
        ticket_file = self.run / self.manifest()["tickets"]["T2"]["ticket_file"]
        ticket_file.write_text(ticket_file.read_text() + "tampered\n")
        self.run_command("claim", "--run", str(self.run), "--ticket", "T2", "--agent", "agent-b", "--attempt", "1", ok=False)
        self.assertIsNone(self.manifest()["tickets"]["T2"]["lease"])

    def test_receipt_requires_matching_lease_and_real_local_evidence(self) -> None:
        self.compile_and_start()
        self.run_command("claim", "--run", str(self.run), "--ticket", "T1", "--agent", "agent-a", "--attempt", "2")
        receipt = self.root / "bad.json"
        receipt.write_text(json.dumps({
            "agent": "different-agent", "attempt": 2, "changed_paths": [], "evidence": ["evidence/missing.md"],
            "outputs": [], "revision": 1, "risks": [], "status": "complete", "summary": "Done", "ticket": "T1",
        }))
        self.run_command("record-receipt", "--run", str(self.run), "--ticket", "T1", "--receipt", str(receipt), ok=False)
        self.assertFalse((self.run / "receipts" / "T1.r1.json").exists())
        receipt_data = json.loads(receipt.read_text())
        receipt_data["agent"] = "agent-a"
        receipt.write_text(json.dumps(receipt_data))
        self.run_command("record-receipt", "--run", str(self.run), "--ticket", "T1", "--receipt", str(receipt), ok=False)
        self.assertEqual(self.manifest()["tickets"]["T1"]["status"], "dispatched")

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

    def test_selective_invalidation_revises_affected_ticket_and_dependents(self) -> None:
        self.compile_and_start()
        original_t1 = self.manifest()["tickets"]["T1"]["ticket_sha256"]
        changed_graph = graph(scope_one="Revised account balance behavior")
        changed_graph["shared_context"]["cohorts"]["C1"] = "Revised cohort contract."
        self.write_graph(changed_graph)
        self.source.write_text("# PRD\n\n## E1\n\nRevised requirements.\n")
        locked = self.run_command("materialize-ticket", "--run", str(self.run), "--ticket", "T1", ok=False)
        self.assertEqual(locked.stdout, "")
        result = self.run_command("reconcile", "--run", str(self.run), "--source", str(self.source), "--graph", str(self.graph))
        report = json.loads(result.stdout)
        self.assertEqual(report["changed_scopes"], ["SA1"])
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
        self.run_command("record-release", "--run", str(self.run), "--stage", "integration", "--result", "pass", "--summary", "All acceptance behavior observed.", "--evidence", "evidence/cohort.md")
        self.transition("prd_verified")
        self.transition("merged")
        self.run_command("record-release", "--run", str(self.run), "--stage", "deployment", "--result", "pass", "--summary", "Exact merged revision deployed.", "--evidence", "deployment-id-1")
        self.transition("deployed")
        self.run_command("record-release", "--run", str(self.run), "--stage", "production-verification", "--result", "pass", "--summary", "Production behavior observed.", "--evidence", "production-check-1")
        self.transition("production_verified")
        self.transition("complete")
        self.assertEqual(self.manifest()["state"], "complete")

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
