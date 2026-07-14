#!/usr/bin/env python3
"""Behavior tests for prd-run.py."""

from __future__ import annotations

import json
import hashlib
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
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "run/RUN1"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo, check=True)
        (self.repo / "tracked.txt").write_text("clean\n")
        subprocess.run(["git", "add", "tracked.txt"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "initial"], cwd=self.repo, check=True)
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

    def run_command(self, *args: str, ok: bool = True, env=None, cwd=None) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(["python3", str(SCRIPT), *args], text=True, capture_output=True, cwd=cwd or self.repo, env={**os.environ, **(env or {})})
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
        self.finish_dispatched(ticket, agent, attempt=attempt)

    def finish_dispatched(self, ticket: str, agent: str, attempt: int = 1) -> None:
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

    def test_init_records_parent_integration_policy_and_resume_state(self) -> None:
        integration = self.manifest()["integration"]
        self.assertEqual(integration, {
            "branch": "run/RUN1",
            "merge_executor": "parent-after-user-authority",
            "mode": "parent-branch",
            "pr_strategy": "single-final-pr",
        })
        resume = (self.run / "resume.md").read_text()
        self.assertIn("Integration branch: run/RUN1", resume)
        self.assertIn("PR strategy: single-final-pr", resume)
        common = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"], cwd=self.repo,
            text=True, capture_output=True, check=True,
        ).stdout.strip()
        registry = Path(common) if Path(common).is_absolute() else (self.repo / common).resolve()
        bindings = json.loads((registry / "gauntlet" / "run-bindings.json").read_text())
        self.assertEqual(Path(bindings["run/RUN1"]["run"]).resolve(), self.run.resolve())

    def test_init_accepts_named_branch_and_rejects_default_branch(self) -> None:
        self.run_command(
            "init", "--executions", str(self.root / "executions"), "--run-id", "NAMEDRUN", "--source", str(self.source),
            "--target", "E1", "--release-contract", "doc_org.md:v1", "--integration-branch", "codex/EDGE-001",
        )
        named = json.loads((self.root / "executions" / "NAMEDRUN" / "manifest.json").read_text())
        self.assertEqual(named["integration"]["branch"], "codex/EDGE-001")
        self.run_command(
            "init", "--executions", str(self.root / "executions"), "--run-id", "MAINRUN", "--source", str(self.source),
            "--target", "E1", "--release-contract", "doc_org.md:v1", "--integration-branch", "main", ok=False,
        )
        self.assertFalse((self.root / "executions" / "MAINRUN").exists())

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
        self.assertNotIn("single-final-pr", first)
        self.assertNotIn("run/RUN1", first)
        self.assertLess(first.index("# Global context"), first.index("# Cohort C1 context"))
        self.assertLess(first.index("# Cohort C1 context"), first.index("# Assigned ticket"))
        self.assertIn("handoffs/T1.r1.a1.receipt.json", first)
        metadata = json.loads((self.run / "handoffs" / "T1.r1.a1.context.json").read_text())
        self.assertEqual(metadata["contract"], "gauntlet/generated-context/v1")
        self.assertNotIn(str(self.run), json.dumps(metadata))
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

    def test_lane_claims_and_materializes_multiple_compatible_tickets(self) -> None:
        value = graph()
        value["tickets"][0]["affinity"] = ["balance"]
        value["tickets"][1].update({"dependencies": [], "affinity": ["balance"]})
        self.write_graph(value)
        self.compile_and_start()
        self.run_command(
            "claim-lane", "--run", str(self.run), "--lane", "wrong-lane", "--agent", "agent-a",
            "--attempt", "1", "--affinity", "view", "--ticket", "T1", "--ticket", "T2", ok=False,
        )
        self.assertEqual(self.manifest()["lanes"], {})
        self.run_command(
            "claim-lane", "--run", str(self.run), "--lane", "balance-lane", "--agent", "agent-a",
            "--attempt", "1", "--affinity", "balance", "--ticket", "T1", "--ticket", "T2",
        )
        current = self.manifest()
        self.assertEqual(current["lanes"]["balance-lane"]["ticket_ids"], ["T1", "T2"])
        self.assertEqual(current["tickets"]["T1"]["lease"]["lane"], "balance-lane")
        self.assertEqual(current["tickets"]["T2"]["lease"]["lane"], "balance-lane")

        result = json.loads(self.run_command("materialize-lane", "--run", str(self.run), "--lane", "balance-lane").stdout)
        self.assertEqual([item["ticket"] for item in result["tickets"]], ["T1", "T2"])
        self.assertEqual(len({item["stable_prefix_sha256"] for item in result["tickets"]}), 1)
        for item in result["tickets"]:
            self.assertTrue((self.run / item["bundle"]).is_file())
            self.assertTrue((self.run / item["metadata"]).is_file())

    def test_lane_sibling_stall_does_not_block_integration_or_dependency_release(self) -> None:
        value = graph()
        value["tickets"][0]["affinity"] = ["balance"]
        value["tickets"][1].update({"dependencies": [], "affinity": ["balance"]})
        third = dict(value["tickets"][1])
        third.update({
            "id": "T3", "title": "Consume balance", "dependencies": ["T1"],
            "affinity": ["consumer"], "ownership": ["src/consumer.py"],
            "source_files": ["src/consumer.py"],
        })
        value["tickets"].append(third)
        value["cohorts"]["C1"]["ticket_ids"].append("T3")
        self.write_graph(value)
        self.compile_and_start()
        self.run_command(
            "claim-lane", "--run", str(self.run), "--lane", "balance-lane", "--agent", "agent-a",
            "--attempt", "1", "--affinity", "balance", "--ticket", "T1", "--ticket", "T2",
        )

        blocked = self.root / "T2-blocked.json"
        blocked.write_text(json.dumps({
            "agent": "agent-a", "attempt": 1, "changed_paths": [], "evidence": [], "outputs": [],
            "revision": 1, "risks": ["Fixture unavailable"], "status": "blocked",
            "summary": "T2 cannot proceed in this attempt.", "ticket": "T2",
        }))
        self.run_command("record-receipt", "--run", str(self.run), "--ticket", "T2", "--receipt", str(blocked))
        self.finish_dispatched("T1", "agent-a")
        current = self.manifest()
        self.assertEqual(current["tickets"]["T1"]["status"], "integrated")
        self.assertEqual(current["tickets"]["T2"]["status"], "blocked")
        self.assertEqual(current["tickets"]["T3"]["status"], "ready")

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
        events = [json.loads(line) for line in (self.run / "events.jsonl").read_text().splitlines()]
        self.assertEqual([item["sequence"] for item in events], list(range(1, len(events) + 1)))

    def test_event_journal_recovers_uncommitted_append_and_partial_tail(self) -> None:
        value = graph()
        value["tickets"][0]["affinity"] = ["balance"]
        value["tickets"][1].update({"dependencies": [], "affinity": ["balance"]})
        self.write_graph(value)
        self.compile_and_start()
        events = self.run / "events.jsonl"
        committed = events.read_bytes()
        self.run_command(
            "claim-lane", "--run", str(self.run), "--lane", "balance-lane", "--agent", "agent-a",
            "--attempt", "1", "--affinity", "balance", "--ticket", "T1", "--ticket", "T2", ok=False,
            env={"PRD_RUN_FAIL_EVENT_AFTER": "lane_claimed"},
        )
        self.assertGreater(len(events.read_bytes()), len(committed))
        self.assertNotIn("balance-lane", self.manifest()["lanes"])
        self.run_command("resume", "--run", str(self.run))
        self.assertEqual(events.read_bytes(), committed)
        self.run_command(
            "claim-lane", "--run", str(self.run), "--lane", "balance-lane", "--agent", "agent-a",
            "--attempt", "1", "--affinity", "balance", "--ticket", "T1", "--ticket", "T2",
        )
        with events.open("ab") as handle:
            handle.write(b'{"action":"partial')
        self.run_command("ready", "--run", str(self.run))
        parsed = [json.loads(line) for line in events.read_text().splitlines()]
        self.assertEqual(len(parsed), self.manifest()["event_sequence"])

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

    def test_repeated_noop_reconciliation_does_not_duplicate_events(self) -> None:
        self.compile_and_start()
        before_manifest = self.manifest()
        before_events = (self.run / "events.jsonl").read_bytes()
        first = json.loads(self.run_command(
            "reconcile", "--run", str(self.run), "--source", str(self.source), "--graph", str(self.graph),
        ).stdout)
        second = json.loads(self.run_command(
            "reconcile", "--run", str(self.run), "--source", str(self.source), "--graph", str(self.graph),
        ).stdout)
        self.assertEqual(first, {"changed_scopes": [], "invalidated_tickets": []})
        self.assertEqual(second, first)
        self.assertEqual((self.run / "events.jsonl").read_bytes(), before_events)
        self.assertEqual(self.manifest()["generation"], before_manifest["generation"])

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
        self.run_command("record-authority", "--run", str(self.run), "--capability", "merge-to-default", "--source", "User authorized merge.")
        self.run_command("record-merge", "--run", str(self.run), "--pr", "PR-123", "--merged-sha", revision, "--main-sha", revision, "--evidence", "git-main-check")
        merge_record = self.manifest()["release"]["merge"]
        self.assertEqual(merge_record["integration_branch"], "run/RUN1")
        self.assertEqual(merge_record["pr_strategy"], "single-final-pr")
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
        subprocess.run(["git", "checkout", "-qb", "run/RUN2"], cwd=self.repo, check=True)
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
        legacy_manifest = self.manifest()
        legacy_manifest["integration"].pop("pr_strategy")
        legacy_lock_path = self.run / "source-lock.json"
        legacy_lock = json.loads(legacy_lock_path.read_text())
        legacy_lock.pop("repository_identity")
        legacy_lock_path.write_text(json.dumps(legacy_lock, indent=2, sort_keys=True) + "\n")
        legacy_manifest["source_lock_sha256"] = hashlib.sha256(legacy_lock_path.read_bytes()).hexdigest()
        (self.run / "manifest.json").write_text(json.dumps(legacy_manifest, indent=2, sort_keys=True) + "\n")
        subprocess.run(["git", "checkout", "-q", "run/RUN1"], cwd=self.repo, check=True)
        prd = self.run / "evidence" / "prd-independent.md"
        prd.write_text("# Full PRD proof\n\nIndependently checked all target outcomes.\n")
        self.run_command("verify-prd", "--run", str(self.run), "--result", "pass", "--summary", "Target verified.", "--evidence", str(prd))
        self.transition("prd_verified")
        revision = "b" * 40
        self.run_command("record-authority", "--run", str(self.run), "--capability", "merge-to-default", "--source", "User authorized merge.")
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

    def test_pr_strategy_is_frozen_and_review_units_are_exact_and_dependency_safe(self) -> None:
        self.run_command(
            "init", "--executions", str(self.root / "executions"), "--run-id", "REVIEWRUN",
            "--source", str(self.source), "--target", "E1", "--release-contract", "doc_org.md:v1",
            "--pr-strategy", "review-prs-plus-final",
        )
        review_run = self.root / "executions" / "REVIEWRUN"
        self.run_command("transition", "--run", str(review_run), "--to", "accepted")
        value = graph()
        value["review_units"] = {
            "RU2": {"dependencies": ["RU1"], "ticket_ids": ["T2"]},
            "RU1": {"dependencies": [], "ticket_ids": ["T1"]},
        }
        self.write_graph(value)
        self.run_command("compile", "--run", str(review_run), "--graph", str(self.graph))
        manifest = json.loads((review_run / "manifest.json").read_text())
        self.assertEqual(list(manifest["review_units"]), ["RU1", "RU2"])
        self.assertEqual(manifest["tickets"]["T1"]["review_unit_id"], "RU1")
        self.assertEqual(manifest["tickets"]["T2"]["review_unit_id"], "RU2")

        self.run_command("transition", "--run", str(review_run), "--to", "executing")
        for capability in ("push-review-branch", "open-review-pr"):
            self.run_command(
                "record-authority", "--run", str(review_run), "--capability", capability,
                "--source", "Review flow authorized.",
            )
        open_ru2 = (
            "review-unit", "--run", str(review_run), "--unit", "RU2", "--action", "opened",
            "--branch", "review/RU2", "--pr", "PR-2",
        )
        for dependency_state in ("pending", "opened", "checked", "merge-locked"):
            current = json.loads((review_run / "manifest.json").read_text())
            current["review_units"]["RU1"]["state"] = dependency_state
            (review_run / "manifest.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
            self.run_command(*open_ru2, ok=False)
            self.assertEqual(json.loads((review_run / "manifest.json").read_text())["review_units"]["RU2"]["state"], "pending")

        current = json.loads((review_run / "manifest.json").read_text())
        current["review_units"]["RU1"]["state"] = "pending"
        current["review_units"]["RU2"].update({"state": "opened", "branch": "review/RU2", "pr": "PR-2"})
        (review_run / "manifest.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        before = (review_run / "manifest.json").read_bytes()
        self.run_command(*open_ru2)
        self.assertEqual((review_run / "manifest.json").read_bytes(), before)
        self.run_command(
            "review-unit", "--run", str(review_run), "--unit", "RU2", "--action", "opened",
            "--branch", "review/RU2-changed", "--pr", "PR-2", ok=False,
        )

        for dependency_state in ("merged", "verified", "cleanup-eligible", "cleaned"):
            current = json.loads((review_run / "manifest.json").read_text())
            current["review_units"]["RU1"]["state"] = dependency_state
            current["review_units"]["RU2"] = {
                "dependencies": ["RU1"], "state": "pending", "ticket_ids": ["T2"],
            }
            (review_run / "manifest.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
            self.run_command(*open_ru2)
            self.assertEqual(json.loads((review_run / "manifest.json").read_text())["review_units"]["RU2"]["state"], "opened")

        for mutation in ("missing", "duplicate", "dependency", "extra_dependency", "cycle"):
            run_id = f"BAD{mutation.upper()}"
            self.run_command(
                "init", "--executions", str(self.root / "executions"), "--run-id", run_id,
                "--source", str(self.source), "--target", "E1", "--release-contract", "doc_org.md:v1",
                "--pr-strategy", "review-prs-plus-final",
            )
            bad_run = self.root / "executions" / run_id
            self.run_command("transition", "--run", str(bad_run), "--to", "accepted")
            bad = graph()
            if mutation == "missing":
                bad["review_units"] = {"RU1": {"dependencies": [], "ticket_ids": ["T1"]}}
            elif mutation == "duplicate":
                bad["review_units"] = {
                    "RU1": {"dependencies": [], "ticket_ids": ["T1", "T2"]},
                    "RU2": {"dependencies": ["RU1"], "ticket_ids": ["T2"]},
                }
            elif mutation == "dependency":
                bad["review_units"] = {
                    "RU1": {"dependencies": [], "ticket_ids": ["T1"]},
                    "RU2": {"dependencies": [], "ticket_ids": ["T2"]},
                }
            elif mutation == "extra_dependency":
                bad["tickets"][1]["dependencies"] = []
                bad["review_units"] = {
                    "RU1": {"dependencies": [], "ticket_ids": ["T1"]},
                    "RU2": {"dependencies": ["RU1"], "ticket_ids": ["T2"]},
                }
            else:
                bad["review_units"] = {
                    "RU1": {"dependencies": ["RU2"], "ticket_ids": ["T1"]},
                    "RU2": {"dependencies": ["RU1"], "ticket_ids": ["T2"]},
                }
            self.write_graph(bad)
            self.run_command("compile", "--run", str(bad_run), "--graph", str(self.graph), ok=False)

    def test_review_metadata_never_changes_child_bundle_bytes(self) -> None:
        self.compile_and_start()
        self.run_command("claim", "--run", str(self.run), "--ticket", "T1", "--agent", "agent-a", "--attempt", "1")
        single = self.run_command("materialize-ticket", "--run", str(self.run), "--ticket", "T1").stdout

        self.run_command(
            "init", "--executions", str(self.root / "executions"), "--run-id", "REVIEWBYTES",
            "--source", str(self.source), "--target", "E1", "--release-contract", "doc_org.md:v1",
            "--pr-strategy", "review-prs-plus-final",
        )
        review_run = self.root / "executions" / "REVIEWBYTES"
        self.run_command("transition", "--run", str(review_run), "--to", "accepted")
        value = graph()
        value["review_units"] = {"RU1": {"dependencies": [], "ticket_ids": ["T1", "T2"]}}
        self.write_graph(value)
        self.run_command("compile", "--run", str(review_run), "--graph", str(self.graph))
        self.run_command("transition", "--run", str(review_run), "--to", "executing")
        for capability in ("push-review-branch", "open-review-pr"):
            self.run_command("record-authority", "--run", str(review_run), "--capability", capability, "--source", "Review flow authorized.")
        self.run_command(
            "review-unit", "--run", str(review_run), "--unit", "RU1", "--action", "opened",
            "--branch", "review/RU1", "--pr", "PR-1",
        )
        self.run_command("claim", "--run", str(review_run), "--ticket", "T1", "--agent", "agent-a", "--attempt", "1")
        review = self.run_command("materialize-ticket", "--run", str(review_run), "--ticket", "T1").stdout
        self.assertEqual(single.replace(str(self.run), "<RUN>"), review.replace(str(review_run), "<RUN>"))
        self.assertNotIn("RU1", review)
        self.assertNotIn("review-prs-plus-final", review)

    def test_source_lock_records_canonical_epic_and_scope_names(self) -> None:
        lock = json.loads((self.run / "source-lock.json").read_text())
        self.assertEqual(lock["epics"]["E1"]["title"], "Balance")
        self.assertEqual(lock["epics"]["E1"]["scope_areas"]["E1-S1"]["responsibility"], "Balance behavior")

    def test_review_unit_transitions_are_idempotent_and_reject_stale_base(self) -> None:
        subprocess.run(["git", "checkout", "-qb", "run/REVIEWSTATE"], cwd=self.repo, check=True)
        self.run_command(
            "init", "--executions", str(self.root / "executions"), "--run-id", "REVIEWSTATE",
            "--source", str(self.source), "--target", "E1", "--release-contract", "doc_org.md:v1",
            "--pr-strategy", "review-prs-plus-final",
        )
        self.run = self.root / "executions" / "REVIEWSTATE"
        value = graph(); value["review_units"] = {"RU1": {"dependencies": [], "ticket_ids": ["T1", "T2"]}}
        self.write_graph(value)
        self.transition("accepted")
        self.run_command("compile", "--run", str(self.run), "--graph", str(self.graph))
        self.transition("executing")
        for capability in ("push-review-branch", "open-review-pr", "merge-to-integration"):
            self.run_command("record-authority", "--run", str(self.run), "--capability", capability, "--source", "User authorized implementation PR flow.")
        opened = ("review-unit", "--run", str(self.run), "--unit", "RU1", "--action", "opened", "--branch", "review/RU1", "--pr", "PR-1")
        self.run_command(*opened); before = (self.run / "manifest.json").read_bytes(); self.run_command(*opened)
        self.assertEqual((self.run / "manifest.json").read_bytes(), before)
        proof = self.run / "evidence" / "ru1-check.md"; proof.write_text("# Review check\n\nTests passed against the named merge tree.\n")
        base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo, text=True, capture_output=True, check=True).stdout.strip()
        tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=self.repo, text=True, capture_output=True, check=True).stdout.strip()
        head = subprocess.run(
            ["git", "commit-tree", tree, "-p", base, "-m", "review head"],
            cwd=self.repo, text=True, capture_output=True, check=True,
        ).stdout.strip()
        legacy_tested_merge = subprocess.run(
            ["git", "commit-tree", tree, "-p", base, "-p", head, "-m", "legacy synthetic merge"],
            cwd=self.repo, text=True, capture_output=True, check=True,
        ).stdout.strip()
        self.run_command(
            "review-unit", "--run", str(self.run), "--unit", "RU1", "--action", "checked",
            "--head-sha", head[:8], "--tested-base-sha", base[:8], "--tested-merge-sha", legacy_tested_merge[:8],
            "--proof-command", "python3 test.py", "--proof-result", "pass", "--proof-evidence", str(proof),
        )
        legacy = self.manifest()
        self.assertEqual(legacy["review_units"]["RU1"]["check"]["head_sha"], head)
        self.assertEqual(legacy["review_units"]["RU1"]["check"]["tested_base_sha"], base)
        self.assertEqual(legacy["review_units"]["RU1"]["check"]["tested_tree_sha"], tree)
        legacy["review_units"]["RU1"]["check"]["tested_merge_sha"] = legacy_tested_merge
        legacy["review_units"]["RU1"]["check"].pop("tested_tree_sha")
        (self.run / "manifest.json").write_text(json.dumps(legacy, indent=2, sort_keys=True) + "\n")
        status = json.loads(self.run_command("review-unit-status", "--run", str(self.run), "--unit", "RU1").stdout)
        self.assertEqual(status["unit"]["tickets"][0]["epicId"], "E1")
        self.assertTrue(status["authority"]["merge-to-integration"])
        self.run_command("review-unit", "--run", str(self.run), "--unit", "RU1", "--action", "merge-locked", "--current-base-sha", head, ok=False)
        self.assertEqual(self.manifest()["review_units"]["RU1"]["state"], "checked")
        self.run_command("review-unit", "--run", str(self.run), "--unit", "RU1", "--action", "merge-locked", "--current-base-sha", base)
        newer_base = subprocess.run(
            ["git", "commit-tree", tree, "-p", base, "-m", "new integration base"],
            cwd=self.repo, text=True, capture_output=True, check=True,
        ).stdout.strip()
        self.run_command(
            "review-unit", "--run", str(self.run), "--unit", "RU1", "--action", "checked",
            "--head-sha", head, "--tested-base-sha", newer_base, "--tested-tree-sha", tree,
            "--proof-command", "python3 test.py", "--proof-result", "pass", "--proof-evidence", str(proof),
            ok=False,
        )
        fresh_proof = self.run / "evidence" / "ru1-recheck.md"
        fresh_proof.write_text("# Review recheck\n\nFresh tests passed against the changed base and synthetic tree.\n")
        self.run_command(
            "review-unit", "--run", str(self.run), "--unit", "RU1", "--action", "checked",
            "--head-sha", head, "--tested-base-sha", newer_base, "--tested-tree-sha", tree,
            "--proof-command", "python3 test.py", "--proof-result", "pass", "--proof-evidence", str(fresh_proof),
        )
        self.assertEqual(self.manifest()["review_units"]["RU1"]["state"], "checked")
        base = newer_base
        self.run_command("review-unit", "--run", str(self.run), "--unit", "RU1", "--action", "merge-locked", "--current-base-sha", base)
        merge = subprocess.run(
            ["git", "commit-tree", tree, "-p", base, "-p", head, "-m", "merge review unit"],
            cwd=self.repo, text=True, capture_output=True, check=True,
        ).stdout.strip()
        subprocess.run(["git", "update-ref", "refs/heads/run/REVIEWSTATE", merge], cwd=self.repo, check=True)
        self.run_command("review-unit", "--run", str(self.run), "--unit", "RU1", "--action", "merged", "--merge-sha", merge, "--merged-tree-sha", "d" * 40, ok=False)
        self.assertEqual(self.manifest()["review_units"]["RU1"]["state"], "merge-locked")
        self.run_command("review-unit", "--run", str(self.run), "--unit", "RU1", "--action", "merged", "--merge-sha", merge, "--merged-tree-sha", tree)
        verified = self.run / "evidence" / "ru1-verified.md"; verified.write_text("# Verified\n\nIntegration branch contains the reviewed merge.\n")
        self.run_command("review-unit", "--run", str(self.run), "--unit", "RU1", "--action", "verified", "--evidence", str(verified), "--summary", "Reviewed merge is present.")
        self.run_command("review-unit", "--run", str(self.run), "--unit", "RU1", "--action", "cleanup-eligible")
        self.run_command("review-unit", "--run", str(self.run), "--unit", "RU1", "--action", "cleaned")
        self.assertEqual(self.manifest()["review_units"]["RU1"]["state"], "cleaned")

    def test_project_pr_is_closed_deterministic_and_bound_to_clean_repository(self) -> None:
        self.compile_and_start(); self.complete("T1", "agent-a"); self.complete("T2", "agent-b")
        self.transition("integrating")
        cohort = self.run / "evidence" / "cohort-project.md"; cohort.write_text("# Cohort\n\nAPI and view agree.\n")
        self.run_command("verify-cohort", "--run", str(self.run), "--cohort", "C1", "--result", "pass", "--evidence", str(cohort))
        self.transition("cohort_verified")
        prd = self.run / "evidence" / "prd-project.md"; prd.write_text("# PRD\n\nAll locked outcomes passed independent checks.\n")
        self.run_command("verify-prd", "--run", str(self.run), "--result", "pass", "--summary", "All outcomes passed.", "--evidence", str(prd))
        self.transition("prd_verified")
        summary = self.root / "summary.json"
        malformed = {
            "title": "balance: make values canonical", "problem": "Balances could disagree across surfaces.",
            "solution": {"outcome": "Canonical values.", "invariants": [], "preserved": [], "nonGoals": []},
            "changelog": "Make account balances consistent.",
            "testing": [{"command": "python3 test.py", "result": "pass", "proves": "Behavior agrees."}],
            "securityRisk": None,
        }
        summary.write_text(json.dumps(malformed))
        self.run_command("record-project-summary", "--run", str(self.run), "--artifact", str(summary), ok=False)
        self.assertFalse((self.run / "release" / "project-summary.json").exists())
        summary.write_text(json.dumps({
            "title": "balance: make values canonical",
            "problem": {"context": "Balances could disagree across surfaces.", "impact": "Users could see conflicting account state."},
            "solution": {
                "outcome": "Use one canonical calculation and render its result.",
                "invariants": ["Stored and rendered balances agree."],
                "preserved": ["Persistence format remains unchanged."],
                "nonGoals": ["Redesigning the account page."],
            },
            "changelog": "Make account balances consistent across API and view.",
            "testing": [{"command": "python3 scripts/test-prd-run.py", "result": "pass", "proves": "Independent PRD and cohort checks passed."}],
            "securityRisk": None,
        }))
        self.run_command("record-project-summary", "--run", str(self.run), "--artifact", str(summary))
        outcome = self.root / "outcome.json"
        outcome.write_text(json.dumps({
            "epicId": "E1", "title": "Balance", "outcome": "Balances now agree across supported surfaces.",
            "scopeAreas": [
                {"scopeAreaId": "E1-S1", "responsibility": "Balance behavior", "outcome": "The canonical calculator returns the expected value.", "claim": "Calculation is canonical.", "proofLayer": "prd", "evidenceRefs": ["evidence/prd-project.md"], "cannotVerify": []},
                {"scopeAreaId": "E1-S2", "responsibility": "Presentation behavior", "outcome": "The view renders the canonical value.", "claim": "Presentation matches calculation.", "proofLayer": "cohort", "evidenceRefs": ["evidence/cohort-project.md"], "cannotVerify": []},
            ], "decisions": [], "risks": [],
        }))
        self.run_command("record-epic-outcome", "--run", str(self.run), "--artifact", str(outcome))
        self.run_command("record-authority", "--run", str(self.run), "--capability", "open-final-pr", "--source", "User requested the final PR.")
        self.run_command(
            "record-merge", "--run", str(self.run), "--pr", "PR-NOT-AUTHORIZED", "--merged-sha", "d" * 40,
            "--main-sha", "d" * 40, "--evidence", "none", ok=False,
        )

        first = self.run_command("project-pr", "--run", str(self.run)).stdout
        second = self.run_command("project-pr", "--run", str(self.run)).stdout
        self.assertEqual(first, second)
        projected = json.loads(first)
        self.assertEqual(projected["schemaVersion"], "2.0")
        self.assertEqual(set(projected), {"schemaVersion", "title", "problem", "solution", "changelog", "testing", "securityRisk", "substantialChanges", "releaseGates", "binding"})
        self.assertEqual(projected["binding"]["branch"], "run/RUN1")
        self.assertEqual(projected["problem"]["impact"], "Users could see conflicting account state.")
        self.assertIsNone(projected["securityRisk"])
        self.assertEqual(projected["testing"][0]["result"], "pass")
        self.assertEqual([item["scopeAreaId"] for item in projected["substantialChanges"][0]["scopeAreas"]], ["E1-S1", "E1-S2"])
        (self.repo / "untracked.txt").write_text("dirty\n")
        self.run_command("project-pr", "--run", str(self.run), ok=False)
        (self.repo / "untracked.txt").unlink()

        unrelated = self.root / "unrelated"; unrelated.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "run/RUN1"], cwd=unrelated, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=unrelated, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=unrelated, check=True)
        (unrelated / "tracked.txt").write_text("clean\n")
        subprocess.run(["git", "add", "tracked.txt"], cwd=unrelated, check=True)
        subprocess.run(["git", "commit", "-qm", "unrelated"], cwd=unrelated, check=True)
        self.run_command("project-pr", "--run", str(self.run), cwd=unrelated, ok=False)

        subprocess.run(["git", "commit", "--allow-empty", "-qm", "post-verification change"], cwd=self.repo, check=True)
        self.run_command("project-pr", "--run", str(self.run), ok=False)


if __name__ == "__main__":
    unittest.main()
