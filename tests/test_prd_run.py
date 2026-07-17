#!/usr/bin/env python3
"""Focused behavioral tests for the single-Epic Execution Run controller."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import runpy
import re
import subprocess
import tempfile
import unittest

from support import SCRIPTS


SCRIPT = SCRIPTS / "prd-run.py"
LAUNCH_SCHEMA = "gauntlet.epic-launch.v1"
VERIFICATION_SCHEMA = "gauntlet.verification-receipt.v1"
GAP_REVIEW_SCHEMA = "gauntlet.epic-gap-review.v1"
GAP_CANDIDATE_SCHEMA = "gauntlet.coverage-gap-candidate.v1"


def object_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def consequence_review(*triggers: str) -> dict:
    return {
        "required": True,
        "triggers": list(triggers),
        "lenses": [
            {"id": "authority-security", "charter": "Review authority and security boundaries."},
            {"id": "failure-recovery", "charter": "Review failure handling and recovery."},
            {"id": "black-box", "charter": "Review externally observable behavior."},
        ],
    }


def graph(*, with_cohort: bool = False, review: dict | None = None) -> dict:
    cohort = "C1" if with_cohort else None
    return {
        "version": 1,
        "verification_identity": {
            "toolchain": "sha256:" + "c" * 64,
            "fixtures": "sha256:" + "d" * 64,
            "environment": "sha256:" + "b" * 64,
        },
        "review": review or {"required": False, "triggers": [], "lenses": []},
        "planned_checks": [
            {
                "id": "ticket-T1", "tier": "ticket", "ticket_ids": ["T1"],
                "argv": ["python3", "-m", "unittest", "balance"],
                "reason": "Prove the balance behavior after T1.",
            },
            {
                "id": "final-E1", "tier": "final-epic", "ticket_ids": ["T1", "T2"],
                "argv": ["python3", "-m", "unittest"],
                "reason": "Verify canonical Epic acceptance on the integrated tree.",
            },
        ],
        "scope_areas": ["E1-S1", "E1-S2"],
        "shared_context": {
            "global": "Keep the public balance contract stable.",
            "cohorts": {"C1": "The API and view share one balance invariant."} if with_cohort else {},
        },
        "cohorts": {
            "C1": {"invariant": "API and view expose the same balance.", "ticket_ids": ["T1", "T2"]}
        } if with_cohort else {},
        "tickets": [
            {
                "id": "T1", "epic_id": "E1", "title": "Calculate balance",
                "objective": "Expose the canonical account balance.",
                "scope_area_ids": ["E1-S1"], "cohort_id": cohort, "dependencies": [],
                "ownership": ["src/balance.py"], "constraints": ["Do not change persistence."],
                "acceptance": ["The external calculator returns the expected balance."],
                "proof": {
                    "claim": "The calculator returns the canonical balance.",
                    "oracle": "Compare public API results with independently calculated fixtures.",
                    "wrong_case": "A stale cached balance differs from the fixture and must fail.",
                    "non_effects": ["Persistence remains unchanged."],
                },
                "return_contract": "Return changed paths and test evidence.",
                "ask_parent_policy": "Ask only if persistence must change.",
                "source_files": ["src/balance.py"],
            },
            {
                "id": "T2", "epic_id": "E1", "title": "Render balance",
                "objective": "Render the canonical balance in the account view.",
                "scope_area_ids": ["E1-S2"], "cohort_id": cohort, "dependencies": ["T1"],
                "ownership": ["src/view.py"], "constraints": [],
                "acceptance": ["The public view shows the API balance."],
                "proof": {
                    "claim": "The account view shows the canonical balance.",
                    "oracle": "Compare the public view with the API result.",
                    "wrong_case": "A hard-coded view value must disagree and fail.",
                    "non_effects": ["Other account fields remain unchanged."],
                },
                "return_contract": "Return changed paths and black-box evidence.",
                "ask_parent_policy": "Ask only if the view contract is ambiguous.",
                "source_files": ["src/view.py"],
            },
        ],
    }


class PrdRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = "2026-07-16T12:00:00Z"
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "run/RUN1"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo, check=True)
        (self.repo / "tracked.txt").write_text("clean\n")
        subprocess.run(["git", "add", "tracked.txt"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "initial"], cwd=self.repo, check=True)
        subprocess.run(["git", "branch", "main", "HEAD"], cwd=self.repo, check=True)

        self.canonical = self.root / "prd.md"
        self.snapshot = self.root / "prd.locked.md"
        content = (
            "# PRD\n\nImplementation target: E1\n\n"
            "## Epic E1: Balance\n\nEpic status: Accepted\n\nHigh-consequence triggers: none\n\n"
            "### Scope Area E1-S1: Balance behavior\n\nInitial balance requirements.\n\n"
            "### Scope Area E1-S2: Presentation behavior\n\nInitial presentation requirements.\n\n"
            "### Product Acceptance\n\n- The public balance is correct.\n\n"
            "### Design Acceptance\n\n- The balance is readable.\n\n"
            "### Engineering Acceptance\n\n- The exact integrated revision passes final verification.\n\n"
            "### Non-goals\n\n- Replacing persistence.\n\n"
            "### Cannot Verify\n\n- Provider deployment is repository-owned.\n"
        )
        self.canonical.write_text(content)
        self.snapshot.write_text(content)
        self.launch = self.root / "launch.json"
        self.write_launch_set()
        self.graph = self.root / "graph.json"
        self.graph.write_text(json.dumps(graph()))
        self.init_run()
        self.run = self.root / "executions" / "RUN1"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def command(
        self,
        *args: str,
        ok: bool = True,
        cwd: Path | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PRD_RUN_NOW"] = self.clock
        environment.update(extra_env or {})
        result = subprocess.run(
            ["python3", str(SCRIPT), *args],
            cwd=cwd or self.repo,
            text=True,
            capture_output=True,
            env=environment,
        )
        if ok and result.returncode:
            self.fail(f"command failed: {args}\nstdout={result.stdout}\nstderr={result.stderr}")
        if not ok and result.returncode == 0:
            self.fail(f"command unexpectedly succeeded: {args}")
        return result

    def write_launch_set(self, *, target_ids: list[str] | None = None, epics: dict | None = None) -> dict:
        target_ids = target_ids or ["E1"]
        default_epics = {
            epic_id: {
                "title": "Balance" if epic_id == "E1" else "History",
                "dependencies": [],
                "releaseStages": ["deployment", "merge", "production-verification"],
                "consequenceTriggers": [],
                "taskId": f"task-{epic_id.lower()}",
                "runPath": None,
                "status": "starting",
                "blocker": None,
                "stopDisposition": None,
                "startReconciliation": None,
                "emittedEvents": [],
            }
            for epic_id in target_ids
        }
        epics = epics or default_epics
        source = {
            "path": str(self.canonical.resolve()),
            "sha256": hashlib.sha256(self.snapshot.read_bytes()).hexdigest(),
            "snapshotPath": str(self.snapshot.resolve()),
        }
        coverage = {
            "epics": {
                epic_id: {
                    "dependencies": sorted(epics[epic_id]["dependencies"], key=lambda item: (item["epicId"], item["boundary"])),
                    "releaseStages": sorted(epics[epic_id]["releaseStages"]),
                    "consequenceTriggers": sorted(epics[epic_id]["consequenceTriggers"]),
                    "title": epics[epic_id]["title"],
                }
                for epic_id in sorted(epics)
            },
            "schemaVersion": LAUNCH_SCHEMA,
            "source": {"path": source["path"], "sha256": source["sha256"]},
            "targetEpicIds": sorted(target_ids),
        }
        launch = {
            "schemaVersion": LAUNCH_SCHEMA,
            "source": source,
            "targetEpicIds": target_ids,
            "coverageSha256": object_hash(coverage),
            "epics": epics,
            "aggregateEmittedEvents": [],
        }
        self.launch.write_text(json.dumps(launch))
        return launch

    def init_run(self, *, run_id: str = "RUN1", stages: str = "merge,deployment,production-verification", ok: bool = True, extra: list[str] | None = None):
        return self.command(
            "init", "--executions", str(self.root / "executions"), "--run-id", run_id,
            "--source", str(self.snapshot), "--target", "E1", "--launch-set", str(self.launch),
            "--release-contract", "doc_org.md:v2", "--release-stages", stages,
            "--request-start-ordinal", "10",
            *(extra or []), ok=ok,
        )

    def manifest(self) -> dict:
        return json.loads((self.run / "manifest.json").read_text())

    def transition(self, state: str, *, ok: bool = True, request_end_ordinal: int | None = None) -> None:
        extra = ["--request-end-ordinal", str(request_end_ordinal)] if request_end_ordinal is not None else []
        self.command("transition", "--run", str(self.run), "--to", state, *extra, ok=ok)

    def compile_and_start(self, *, value: dict | None = None) -> None:
        if value is not None:
            self.graph.write_text(json.dumps(value))
        self.transition("accepted")
        self.command("compile", "--run", str(self.run), "--graph", str(self.graph))
        self.transition("executing")

    def restart_with_consequence(self, trigger: str) -> None:
        subprocess.run(["git", "switch", "-c", "run/RUN2"], cwd=self.repo, check=True, capture_output=True, text=True)
        content = self.snapshot.read_text().replace(
            "High-consequence triggers: none",
            f"High-consequence triggers: {trigger}",
        )
        self.canonical.write_text(content)
        self.snapshot.write_text(content)
        self.write_launch_set(epics={
            "E1": {
                "title": "Balance", "dependencies": [],
                "releaseStages": ["deployment", "merge", "production-verification"],
                "consequenceTriggers": [trigger], "taskId": "task-e1", "runPath": None,
                "status": "starting", "blocker": None, "stopDisposition": None, "startReconciliation": None, "emittedEvents": [],
            },
        })
        self.init_run(run_id="RUN2")
        self.run = self.root / "executions" / "RUN2"

    def revision(self) -> tuple[str, str]:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo, text=True, capture_output=True, check=True).stdout.strip()
        tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=self.repo, text=True, capture_output=True, check=True).stdout.strip()
        return commit, tree

    def verification_receipt(self, name: str, *, result: str = "pass", oracle: str = "a" * 64, environment: str = "b" * 64) -> Path:
        evidence = self.run / "evidence" / f"{name}.md"
        evidence.write_text(f"# {name}\n\nObserved the public behavior.\n")
        commit, tree = self.revision()
        path = self.root / f"{name}.json"
        path.write_text(json.dumps({
            "schemaVersion": VERIFICATION_SCHEMA,
            "result": result,
            "summary": f"{name} {result} on the exact revision.",
            "evidence": [str(evidence.relative_to(self.run))],
            "identity": {
                "commitSha": commit,
                "treeSha": tree,
                "argv": ["python3", "-m", "unittest", name],
                "toolchainSha256": "c" * 64,
                "fixturesSha256": "d" * 64,
                "oracleSha256": oracle,
                "environmentSha256": environment,
            },
        }))
        return path

    def complete_ticket(self, ticket: str, agent: str) -> None:
        self.command(
            "claim", "--run", str(self.run), "--ticket", ticket, "--agent", agent, "--attempt", "1",
            "--native-child-id", f"child-{ticket.lower()}", "--request-start-ordinal", "20",
        )
        evidence = self.run / "evidence" / f"{ticket}.r1.a1.md"
        evidence.write_text(f"# Child evidence {ticket}\n\nObserved public behavior.\n")
        receipt = self.root / f"{ticket}.child.json"
        receipt.write_text(json.dumps({
            "agent": agent, "attempt": 1, "changed_paths": [f"src/{ticket}.py"],
            "evidence": [str(evidence.relative_to(self.run))], "outputs": [f"contract:{ticket}"],
            "revision": 1, "risks": [], "status": "complete", "summary": f"Completed {ticket}.", "ticket": ticket,
        }))
        self.command(
            "record-receipt", "--run", str(self.run), "--ticket", ticket, "--receipt", str(receipt),
            "--request-end-ordinal", "25",
        )

    def finish_ticket(self, ticket: str, agent: str) -> None:
        self.complete_ticket(ticket, agent)
        parent = self.verification_receipt(f"{ticket}-parent")
        self.command(
            "integrate", "--run", str(self.run), "--ticket", ticket,
            "--verification-receipt", str(parent),
        )

    def finish_implementation(self, *, final_result: str = "pass") -> Path:
        self.finish_ticket("T1", "agent-a")
        self.finish_ticket("T2", "agent-b")
        self.transition("integrating")
        lock = json.loads((self.run / "source-lock.json").read_text())
        final = self.verification_receipt(
            f"final-{final_result}",
            result=final_result,
            oracle=lock["epics"]["E1"]["section_sha256"],
        )
        self.command("verify-epic", "--run", str(self.run), "--verification-receipt", str(final))
        return final

    def grant(self, capability: str) -> None:
        self.command(
            "record-authority", "--run", str(self.run), "--capability", capability,
            "--source", "User implementation authority in source task",
        )

    def consequence_oracle(self, *, lens: str | None = None, safeguard: str | None = None) -> str:
        policy = self.manifest()["consequence_review"]["policy"]
        return object_hash({
            "schemaVersion": "gauntlet.consequence-proof.v1",
            "triggers": policy["triggers"],
            **({"lens": lens} if lens is not None else {"safeguard": safeguard}),
        })

    def record_consequence_reviews(self, *, result: str = "pass") -> None:
        for lens in ("authority-security", "failure-recovery", "black-box"):
            receipt = self.verification_receipt(
                f"review-{lens}-{result}", result=result, oracle=self.consequence_oracle(lens=lens),
            )
            self.command(
                "record-review", "--run", str(self.run), "--lens", lens,
                "--verification-receipt", str(receipt),
            )

    def record_safeguard(self, kind: str, *, result: str = "pass", ok: bool = True):
        receipt = self.verification_receipt(
            f"safeguard-{kind}-{result}", result=result, oracle=self.consequence_oracle(safeguard=kind),
        )
        return self.command(
            "record-safeguard", "--run", str(self.run), "--kind", kind,
            "--verification-receipt", str(receipt), ok=ok,
        )

    def gap_review(
        self,
        pass_number: int,
        findings: list[dict],
        *,
        phase: str = "pre-build",
        maturity: str = "early-internal",
        ok: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        review = self.root / f"gap-review-{pass_number}-{phase}.json"
        review.write_text(json.dumps({
            "schemaVersion": GAP_REVIEW_SCHEMA,
            "phase": phase,
            "pass": pass_number,
            "maturity": maturity,
            "context": {
                "source": ["source-lock.json"],
                "plan": ["ticket-graph.json"],
                "diff": ["git diff --stat"] if phase == "integrated" else [],
                "proof": ["focused test receipt"] if phase == "integrated" else [],
            },
            "findings": findings,
        }))
        return self.command(
            "record-gap-review", "--run", str(self.run), "--review", str(review), ok=ok,
        )

    @staticmethod
    def gap_finding(
        finding_id: str,
        disposition: str,
        affected_work: list[str],
        *,
        missed: str = "The accepted balance regression is not covered.",
        effect: str = "A user can see the wrong balance.",
        response: str = "Add the focused regression and correct the calculator.",
    ) -> dict:
        return {
            "id": finding_id,
            "missedBehavior": missed,
            "practicalEffect": effect,
            "smallestResponse": response,
            "disposition": disposition,
            "affectedWork": affected_work,
        }

    def finish_consequence_implementation(self) -> None:
        self.finish_ticket("T1", "agent-a")
        self.finish_ticket("T2", "agent-b")
        self.transition("integrating")
        self.record_consequence_reviews()
        lock = json.loads((self.run / "source-lock.json").read_text())
        final = self.verification_receipt("final-consequence", oracle=lock["epics"]["E1"]["section_sha256"])
        self.command("verify-epic", "--run", str(self.run), "--verification-receipt", str(final))
        self.transition("epic_verified")

    def test_init_requires_complete_launch_membership_and_rejects_multi_epic_run(self) -> None:
        lock = json.loads((self.run / "source-lock.json").read_text())
        self.assertEqual(["E1"], lock["target_epic_ids"])
        self.assertEqual("task-e1", lock["launch_set"]["task_id"])
        self.assertEqual(str(self.canonical.resolve()), lock["canonical_source_path"])

        bad = json.loads(self.launch.read_text())
        bad["coverageSha256"] = "0" * 64
        self.launch.write_text(json.dumps(bad))
        result = self.init_run(run_id="BADHASH", ok=False)
        self.assertIn("coverageSha256", result.stderr)

        self.write_launch_set()
        result = self.command(
            "init", "--executions", str(self.root / "executions"), "--run-id", "MULTI",
            "--source", str(self.snapshot), "--target", "E1", "--target", "E2",
            "--launch-set", str(self.launch), "--release-contract", "doc_org.md:v2", ok=False,
        )
        self.assertIn("exactly one target Epic", result.stderr)
        help_text = self.command("init", "--help").stdout
        self.assertIn("immutable launch-set.source.md", help_text)

    def test_old_run_schema_and_retired_authored_summary_commands_fail(self) -> None:
        lock_path = self.run / "source-lock.json"
        lock = json.loads(lock_path.read_text())
        lock.pop("launch_set")
        lock_path.write_text(json.dumps(lock))
        result = self.command("completion", "--run", str(self.run), ok=False)
        self.assertIn("unsupported Execution Run schema", result.stderr)

        retired = self.command("record-project-summary", "--run", str(self.run), ok=False)
        self.assertIn("invalid choice", retired.stderr)
        retired = self.command("verify-prd", "--run", str(self.run), ok=False)
        self.assertIn("invalid choice", retired.stderr)

    def test_new_run_has_coherent_timestamped_events_and_fixed_progress_units(self) -> None:
        initialized = self.manifest()
        self.assertEqual("2026-07-16T12:00:00Z", initialized["time"]["created_at"])
        self.assertIsNone(initialized["time"]["started_at"])
        self.assertTrue(all(
            item["timestamp"] == "2026-07-16T12:00:00Z"
            for item in map(json.loads, (self.run / "events.jsonl").read_text().splitlines())
        ))

    def test_production_release_units_follow_executable_gate_order(self) -> None:
        functions = runpy.run_path(str(SCRIPT))
        value = graph(review=consequence_review("production-authority"))
        manifest = {"release": {"applicability": {"deployment": True, "production-verification": True}}}
        units = {item["id"]: item for item in functions["progress_unit_specs"](value, manifest)}
        self.assertEqual(
            ["verify:final-epic", "ship:safeguard:dry-run-no-mutation"],
            units["ship:merge"]["dependencies"],
        )
        self.assertEqual(["ship:merge"], units["ship:deployment"]["dependencies"])
        self.assertEqual(["ship:deployment"], units["ship:safeguard:bounded-live"]["dependencies"])
        self.assertEqual(
            ["ship:deployment", "ship:safeguard:bounded-live", "ship:safeguard:rollback-readiness"],
            units["ship:production-verification"]["dependencies"],
        )

        self.clock = "2026-07-16T12:01:00Z"
        self.transition("accepted")
        self.clock = "2026-07-16T12:02:00Z"
        self.command("compile", "--run", str(self.run), "--graph", str(self.graph))
        compiled = self.manifest()
        unit_ids = [item["id"] for item in compiled["progress"]["units"]]
        units = {item["id"]: item for item in compiled["progress"]["units"]}
        self.assertEqual(len(unit_ids), len(set(unit_ids)))
        self.assertEqual(compiled["progress"]["denominator_sha256"], object_hash({
            "policyVersion": "gauntlet.progress-policy.v1",
            "schemaVersion": "gauntlet.progress-units.v1",
            "unitIds": unit_ids,
        }))
        self.assertTrue(all(item["status"] == "queued" for item in compiled["operations"].values()))
        self.assertTrue(all(item["queued_at"] == self.clock for item in compiled["operations"].values()))
        self.assertEqual(["integrate:ticket:T1"], units["build:ticket:T2"]["dependencies"])
        self.assertEqual(["build:ticket:T2"], units["integrate:ticket:T2"]["dependencies"])
        self.assertIn("integrate:ticket:T2", units["verify:final-epic"]["dependencies"])
        self.assertIn("verify:epic-gap-review", units["verify:final-epic"]["dependencies"])
        self.assertEqual(
            ["integrate:ticket:T1", "integrate:ticket:T2"],
            units["verify:epic-gap-review"]["dependencies"],
        )
        self.assertEqual(["verify:final-epic"], units["ship:merge"]["dependencies"])

        self.clock = "2026-07-16T12:03:00Z"
        self.transition("executing")
        facts = json.loads(self.command("run-facts", "--run", str(self.run)).stdout)
        self.assertEqual("in-progress", facts["completion"]["exactState"])
        self.assertEqual("complete", facts["time"]["elapsedCoverage"])
        self.assertEqual(self.clock, facts["time"]["startedAt"])
        self.assertEqual(self.clock, facts["time"]["updatedAt"])
        self.assertEqual(compiled["progress"]["denominator_sha256"], facts["progress"]["denominatorSha256"])
        self.assertTrue(all(
            re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", item["timestamp"])
            for item in map(json.loads, (self.run / "events.jsonl").read_text().splitlines())
        ))

    def test_timestamp_less_run_stays_elapsed_unavailable_when_new_events_arrive(self) -> None:
        self.transition("accepted")
        self.command("compile", "--run", str(self.run), "--graph", str(self.graph))
        manifest = self.manifest()
        manifest.pop("time")
        manifest.pop("operations")
        manifest.pop("progress")
        manifest.pop("request_owners")
        (self.run / "manifest.json").write_text(json.dumps(manifest))
        old_events = []
        for line in (self.run / "events.jsonl").read_text().splitlines():
            record = json.loads(line)
            record.pop("timestamp", None)
            old_events.append(json.dumps(record, sort_keys=True, separators=(",", ":")))
        (self.run / "events.jsonl").write_text("\n".join(old_events) + "\n")

        self.clock = "2026-07-16T13:00:00Z"
        self.transition("executing")
        mixed = self.manifest()
        self.assertIsNone(mixed["time"]["created_at"])
        self.assertIsNone(mixed["time"]["protocol_version"])
        self.assertIsNone(mixed["time"]["started_at"])
        self.assertEqual(self.clock, mixed["time"]["updated_at"])
        facts = json.loads(self.command("run-facts", "--run", str(self.run)).stdout)
        self.assertEqual("unavailable", facts["time"]["elapsedCoverage"])
        self.assertIsNone(facts["time"]["startedAt"])
        self.assertIsNone(facts["progress"])
        self.assertEqual([], facts["operations"])
        events = [json.loads(line) for line in (self.run / "events.jsonl").read_text().splitlines()]
        self.assertNotIn("timestamp", events[0])
        self.assertEqual(self.clock, events[-1]["timestamp"])

    def test_interrupted_integration_recovers_one_running_operation_attempt(self) -> None:
        self.compile_and_start()
        self.complete_ticket("T1", "agent-a")
        verification = self.verification_receipt("T1-interrupted-parent")
        self.clock = "2026-07-16T14:00:00Z"
        interrupted = self.command(
            "integrate", "--run", str(self.run), "--ticket", "T1",
            "--verification-receipt", str(verification), ok=False,
            extra_env={"PRD_RUN_FAIL_EVENT_AFTER": "ticket_integrated"},
        )
        self.assertIn("injected event interruption", interrupted.stderr)
        running = self.manifest()["operations"]["integrate:ticket:T1"]
        self.assertEqual("running", running["status"])
        self.assertEqual(1, running["attempt"])
        self.assertEqual(self.clock, running["started_at"])

        self.clock = "2026-07-16T14:01:00Z"
        self.command(
            "integrate", "--run", str(self.run), "--ticket", "T1",
            "--verification-receipt", str(verification),
        )
        recovered = self.manifest()["operations"]["integrate:ticket:T1"]
        self.assertEqual("pass", recovered["status"])
        self.assertEqual(1, recovered["attempt"])
        self.assertEqual("2026-07-16T14:00:00Z", recovered["started_at"])
        self.assertEqual(self.clock, recovered["finished_at"])
        self.assertEqual(["pass"], [item["status"] for item in recovered["attempts"]])

    def test_interrupted_final_verification_recovers_without_losing_running_fact(self) -> None:
        self.compile_and_start()
        self.finish_ticket("T1", "agent-a")
        self.finish_ticket("T2", "agent-b")
        self.transition("integrating")
        lock = json.loads((self.run / "source-lock.json").read_text())
        verification = self.verification_receipt(
            "final-interrupted",
            oracle=lock["epics"]["E1"]["section_sha256"],
        )
        self.clock = "2026-07-16T15:00:00Z"
        self.command(
            "verify-epic", "--run", str(self.run), "--verification-receipt", str(verification),
            ok=False, extra_env={"PRD_RUN_FAIL_EVENT_AFTER": "epic_verified"},
        )
        running = self.manifest()["operations"]["verify:final-epic"]
        self.assertEqual("running", running["status"])
        self.assertEqual(self.clock, running["started_at"])

        self.clock = "2026-07-16T15:02:00Z"
        self.command("verify-epic", "--run", str(self.run), "--verification-receipt", str(verification))
        recovered = self.manifest()["operations"]["verify:final-epic"]
        self.assertEqual("pass", recovered["status"])
        self.assertEqual(1, recovered["attempt"])
        self.assertEqual("2026-07-16T15:00:00Z", recovered["started_at"])
        self.assertEqual(self.clock, recovered["finished_at"])

    def test_ticket_retry_preserves_denominator_and_both_owner_windows(self) -> None:
        self.compile_and_start()
        denominator = self.manifest()["progress"]["denominator_sha256"]
        self.command(
            "claim", "--run", str(self.run), "--ticket", "T1", "--agent", "agent-a", "--attempt", "1",
            "--native-child-id", "child-one", "--request-start-ordinal", "30",
        )
        evidence = self.run / "evidence" / "T1.r1.a1-blocked.md"
        evidence.write_text("# Blocked\n\nThe first owner returned a bounded blocker.\n")
        receipt = self.root / "T1-blocked.json"
        receipt.write_text(json.dumps({
            "agent": "agent-a", "attempt": 1, "changed_paths": [],
            "evidence": [str(evidence.relative_to(self.run))], "outputs": [],
            "revision": 1, "risks": [], "status": "blocked", "summary": "Blocked.", "ticket": "T1",
        }))
        reversed_window = self.command(
            "record-receipt", "--run", str(self.run), "--ticket", "T1", "--receipt", str(receipt),
            "--request-end-ordinal", "29", ok=False,
        )
        self.assertIn("must not precede", reversed_window.stderr)
        self.command(
            "record-receipt", "--run", str(self.run), "--ticket", "T1", "--receipt", str(receipt),
            "--request-end-ordinal", "31",
        )
        self.command(
            "claim", "--run", str(self.run), "--ticket", "T1", "--agent", "agent-b", "--attempt", "2",
            "--native-child-id", "child-two", "--request-start-ordinal", "32",
        )
        facts = json.loads(self.command("run-facts", "--run", str(self.run)).stdout)
        self.assertEqual(denominator, facts["progress"]["denominatorSha256"])
        first = next(item for item in facts["owners"] if item["ownerId"] == "ticket:T1:r1:a1")
        second = next(item for item in facts["owners"] if item["ownerId"] == "ticket:T1:r1:a2")
        self.assertEqual((30, 31), (
            first["requestWindow"]["startOrdinal"], first["requestWindow"]["endOrdinal"],
        ))
        self.assertEqual(32, second["requestWindow"]["startOrdinal"])
        self.assertIsNone(second["requestWindow"]["endOrdinal"])

    def test_zero_cohorts_materializes_bounded_context(self) -> None:
        self.compile_and_start()
        self.command("claim", "--run", str(self.run), "--ticket", "T1", "--agent", "agent-a", "--attempt", "1")
        bundle = self.command("materialize-ticket", "--run", str(self.run), "--ticket", "T1").stdout
        self.assertIn("# Cohort context\n\nNone.", bundle)
        self.assertIn("Cohort: None", bundle)
        self.assertNotIn("Presentation behavior", bundle)

    def test_parent_verification_uses_exact_identity_not_different_prose(self) -> None:
        self.compile_and_start()
        self.command("claim", "--run", str(self.run), "--ticket", "T1", "--agent", "agent-a", "--attempt", "1")
        evidence = self.run / "evidence" / "T1.r1.a1.md"
        evidence.write_text("# Shared evidence\n\nOne observation may support two fresh receipts.\n")
        child = self.root / "child.json"
        child.write_text(json.dumps({
            "agent": "agent-a", "attempt": 1, "changed_paths": ["src/T1.py"],
            "evidence": ["evidence/T1.r1.a1.md"], "outputs": [], "revision": 1,
            "risks": [], "status": "complete", "summary": "Done.", "ticket": "T1",
        }))
        self.command("record-receipt", "--run", str(self.run), "--ticket", "T1", "--receipt", str(child))
        parent = self.verification_receipt("parent-same-evidence")
        raw = json.loads(parent.read_text())
        raw["evidence"] = ["evidence/T1.r1.a1.md"]
        raw["identity"]["commitSha"] = "0" * 40
        parent.write_text(json.dumps(raw))
        result = self.command(
            "integrate", "--run", str(self.run), "--ticket", "T1",
            "--verification-receipt", str(parent), ok=False,
        )
        self.assertIn("exact integrated commit and tree", result.stderr)
        raw["identity"]["commitSha"] = self.revision()[0]
        parent.write_text(json.dumps(raw))
        self.command(
            "integrate", "--run", str(self.run), "--ticket", "T1",
            "--verification-receipt", str(parent),
        )
        identity = self.manifest()["tickets"]["T1"]["integration_verification"]["identity"]
        self.assertEqual("b" * 64, identity["environmentSha256"])
        self.assertEqual(["python3", "-m", "unittest", "parent-same-evidence"], identity["argv"])

    def test_declared_cohort_runs_once_and_final_epic_verification_is_fresh(self) -> None:
        self.compile_and_start(value=graph(with_cohort=True))
        self.finish_ticket("T1", "agent-a")
        self.finish_ticket("T2", "agent-b")
        self.transition("integrating")
        cohort = self.verification_receipt("cohort-C1")
        self.command("verify-cohort", "--run", str(self.run), "--cohort", "C1", "--verification-receipt", str(cohort))
        lock = json.loads((self.run / "source-lock.json").read_text())
        final = self.verification_receipt("final", oracle=lock["epics"]["E1"]["section_sha256"])
        self.command("verify-epic", "--run", str(self.run), "--verification-receipt", str(final))
        self.transition("epic_verified")
        completion = json.loads(self.command("completion", "--run", str(self.run)).stdout)
        self.assertTrue(completion["implemented"])
        self.assertEqual(self.revision()[0], completion["exactRevision"])
        self.assertEqual("E1", completion["epicId"])

        (self.repo / "tracked.txt").write_text("cohort refresh\n")
        subprocess.run(["git", "add", "tracked.txt"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "refresh after cohort verification"], cwd=self.repo, check=True)
        stale_final = self.verification_receipt("stale-cohort-final", oracle=lock["epics"]["E1"]["section_sha256"])
        rejected = self.command(
            "verify-epic", "--run", str(self.run), "--verification-receipt", str(stale_final), ok=False,
        )
        self.assertIn("exact-revision passing Cohorts", rejected.stderr)
        refreshed_cohort = self.verification_receipt("cohort-C1-refreshed")
        self.command("verify-cohort", "--run", str(self.run), "--cohort", "C1", "--verification-receipt", str(refreshed_cohort))
        refreshed_final = self.verification_receipt("final-refreshed-cohort", oracle=lock["epics"]["E1"]["section_sha256"])
        self.command("verify-epic", "--run", str(self.run), "--verification-receipt", str(refreshed_final))
        refreshed_completion = json.loads(self.command("completion", "--run", str(self.run)).stdout)
        self.assertEqual(self.revision()[0], refreshed_completion["exactRevision"])

    def test_failed_or_stale_final_verification_cannot_claim_implementation(self) -> None:
        self.compile_and_start()
        denominator = self.manifest()["progress"]["denominator_sha256"]
        self.finish_implementation(final_result="fail")
        failed_operation = self.manifest()["operations"]["verify:final-epic"]
        self.assertEqual("fail", failed_operation["status"])
        self.assertEqual(1, failed_operation["attempt"])
        failed = json.loads(self.command("completion", "--run", str(self.run)).stdout)
        self.assertFalse(failed["implemented"])
        self.assertIsNone(failed["exactRevision"])
        self.assertIn("final-epic-verification", failed["pendingGates"])
        self.transition("epic_verified", ok=False)

        lock = json.loads((self.run / "source-lock.json").read_text())
        passed = self.verification_receipt("final-pass", oracle=lock["epics"]["E1"]["section_sha256"])
        self.command("verify-epic", "--run", str(self.run), "--verification-receipt", str(passed))
        retried = self.manifest()
        self.assertEqual(denominator, retried["progress"]["denominator_sha256"])
        self.assertEqual("pass", retried["operations"]["verify:final-epic"]["status"])
        self.assertEqual(["fail", "pass"], [
            item["status"] for item in retried["operations"]["verify:final-epic"]["attempts"]
        ])
        self.transition("epic_verified")
        (self.repo / "tracked.txt").write_text("advanced\n")
        subprocess.run(["git", "add", "tracked.txt"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "advance after verification"], cwd=self.repo, check=True)
        stale = json.loads(self.command("completion", "--run", str(self.run)).stdout)
        self.assertFalse(stale["implemented"])
        self.assertIsNone(stale["exactRevision"])
        self.grant("open-final-pr")
        result = self.command("project-pr", "--run", str(self.run), ok=False)
        self.assertIn("exact revision", result.stderr)
        refreshed = self.verification_receipt(
            "final-refreshed", oracle=lock["epics"]["E1"]["section_sha256"],
        )
        self.command("verify-epic", "--run", str(self.run), "--verification-receipt", str(refreshed))
        current = json.loads(self.command("completion", "--run", str(self.run)).stdout)
        self.assertTrue(current["implemented"])
        self.assertEqual(self.revision()[0], current["exactRevision"])

    def test_project_pr_is_deterministic_generated_facts_without_authored_outcomes(self) -> None:
        self.compile_and_start()
        self.finish_implementation()
        self.transition("epic_verified")
        self.grant("open-final-pr")
        first = self.command("project-pr", "--run", str(self.run)).stdout
        second = self.command("project-pr", "--run", str(self.run)).stdout
        self.assertEqual(first, second)
        facts = json.loads(first)
        self.assertEqual("3.0", facts["schemaVersion"])
        self.assertEqual("E1: implement Balance", facts["title"])
        self.assertEqual("E1", facts["epic"]["id"])
        self.assertEqual(["src/T1.py", "src/T2.py"], facts["changedPaths"])
        self.assertTrue(facts["completion"]["implemented"])
        self.assertFalse(facts["completion"]["merged"])
        self.assertIn("Provider deployment is repository-owned.", facts["deferrals"]["cannotVerify"])
        self.assertEqual(3, len(facts["verificationReceipts"]))
        self.assertFalse((self.run / "outcomes").exists())
        self.assertNotIn("problem", facts)
        self.assertNotIn("substantialChanges", facts)

        run_facts = json.loads(self.command("run-facts", "--run", str(self.run)).stdout)
        self.assertEqual("gauntlet/epic-run-facts/v1", run_facts["schemaVersion"])
        self.assertEqual("E1", run_facts["epicId"])
        self.assertEqual(self.revision()[0], run_facts["verificationIdentity"]["commit"])
        self.assertEqual("sha256:" + "c" * 64, run_facts["verificationIdentity"]["toolchain"])
        self.assertEqual("final-epic", run_facts["plannedChecks"][-1]["tier"])
        self.assertEqual(3, len(run_facts["verificationReceipts"]))
        self.assertEqual({"parent", "delegated"}, {item["ownerKind"] for item in run_facts["owners"]})
        root_owner = next(item for item in run_facts["owners"] if item["ownerId"] == "root")
        self.assertEqual("task-e1", root_owner["nativeChildId"])
        self.assertEqual({
            "endOrdinal": None,
            "endedAt": None,
            "startOrdinal": 10,
            "startedAt": "2026-07-16T12:00:00Z",
        }, root_owner["requestWindow"])
        delegated = [item for item in run_facts["owners"] if item["ownerKind"] == "delegated"]
        self.assertEqual({20}, {item["requestWindow"]["startOrdinal"] for item in delegated})
        self.assertEqual({25}, {item["requestWindow"]["endOrdinal"] for item in delegated})
        self.assertEqual("not-required", run_facts["review"]["status"])
        self.assertEqual([], run_facts["review"]["results"])
        self.assertTrue(all(
            item["status"] == "not-required"
            for item in run_facts["release"]["safeguards"].values()
        ))

        revision = self.revision()[0]
        self.grant("merge-to-default")
        self.command(
            "record-merge", "--run", str(self.run), "--pr", "PR-1",
            "--merged-sha", revision, "--main-sha", revision,
            "--evidence", "main contains the exact verified candidate",
        )
        self.transition("merged")
        subprocess.run(["git", "switch", "main"], cwd=self.repo, check=True, capture_output=True, text=True)
        (self.repo / "post-merge-local.txt").write_text("unrelated local state\n", encoding="utf-8")
        later = json.loads(self.command("project-pr", "--run", str(self.run)).stdout)
        self.assertTrue(later["completion"]["merged"])
        self.assertEqual(revision, later["binding"]["headSha"])
        self.assertFalse(any(gate["id"] == "consequence-review" for gate in facts["releaseGates"]))

    def test_completion_keeps_release_dimensions_separate_and_reconciles_merge(self) -> None:
        self.compile_and_start()
        self.finish_implementation()
        self.transition("epic_verified")
        revision = self.revision()[0]
        self.grant("merge-to-default")
        merge_args = (
            "record-merge", "--run", str(self.run), "--pr", "PR-123",
            "--merged-sha", revision, "--main-sha", revision, "--evidence", "github-main",
        )
        self.command(*merge_args)
        self.command(*merge_args)
        self.transition("merged")
        merged = json.loads(self.command("completion", "--run", str(self.run)).stdout)
        self.assertTrue(merged["merged"])
        self.assertFalse(merged["deployed"])
        self.assertFalse(merged["productionProved"])

        self.grant("deploy-production")
        self.command(
            "record-release", "--run", str(self.run), "--stage", "deployment", "--result", "pass",
            "--summary", "Exact merged revision deployed.", "--evidence", "deploy-1", "--revision", revision,
        )
        self.transition("deployed")
        deployed = json.loads(self.command("completion", "--run", str(self.run)).stdout)
        self.assertTrue(deployed["deployed"])
        self.assertFalse(deployed["productionProved"])

        self.grant("verify-production")
        self.command(
            "record-release", "--run", str(self.run), "--stage", "production-verification", "--result", "pass",
            "--summary", "Production oracle passed.", "--evidence", "production-1", "--revision", revision,
        )
        self.transition("production_verified")
        self.clock = "2026-07-16T16:00:00Z"
        self.transition("complete", request_end_ordinal=99)
        complete = json.loads(self.command("completion", "--run", str(self.run)).stdout)
        self.assertTrue(complete["productionProved"])
        self.assertTrue(complete["complete"])
        self.assertEqual([], complete["pendingGates"])
        self.assertEqual(hashlib.sha256(self.snapshot.read_bytes()).hexdigest(), complete["sourceSha256"])
        terminal_facts = json.loads(self.command("run-facts", "--run", str(self.run)).stdout)
        self.assertEqual(self.clock, terminal_facts["time"]["terminalAt"])
        root_owner = next(item for item in terminal_facts["owners"] if item["ownerId"] == "root")
        self.assertEqual(self.clock, root_owner["requestWindow"]["endedAt"])
        self.assertEqual(99, root_owner["requestWindow"]["endOrdinal"])

    def test_not_applicable_release_stages_must_close_explicitly(self) -> None:
        subprocess.run(["git", "checkout", "-qb", "run/NODEPLOY"], cwd=self.repo, check=True)
        self.init_run(run_id="NODEPLOY", stages="merge")
        self.run = self.root / "executions" / "NODEPLOY"
        self.compile_and_start()
        self.finish_implementation()
        self.transition("epic_verified")
        revision = self.revision()[0]
        self.grant("merge-to-default")
        self.command(
            "record-merge", "--run", str(self.run), "--pr", "PR-124",
            "--merged-sha", revision, "--main-sha", revision, "--evidence", "github-main",
        )
        self.transition("merged")
        before = json.loads(self.command("completion", "--run", str(self.run)).stdout)
        self.assertFalse(before["complete"])
        self.assertIn("deployment-not-applicable-record", before["pendingGates"])
        self.command(
            "record-release", "--run", str(self.run), "--stage", "deployment", "--result", "skipped",
            "--summary", "Deployment is not applicable.", "--evidence", "source-lock",
        )
        self.transition("deployed")
        self.command(
            "record-release", "--run", str(self.run), "--stage", "production-verification", "--result", "skipped",
            "--summary", "Production proof is not applicable.", "--evidence", "source-lock",
        )
        self.transition("production_verified")
        self.transition("complete")
        after = json.loads(self.command("completion", "--run", str(self.run)).stdout)
        self.assertTrue(after["complete"])
        self.assertFalse(after["deployed"])
        self.assertFalse(after["productionProved"])

    def test_consequence_policy_rejects_false_generic_duplicate_and_missing_panels(self) -> None:
        self.transition("accepted")
        invalid = []
        false_required = consequence_review("billing-paid-actions")
        false_required["required"] = False
        invalid.append((false_required, "review.required=true"))

        generic = consequence_review("billing-paid-actions")
        generic["lenses"][0]["id"] = "generic-review"
        invalid.append((generic, "requires exactly"))

        duplicate = consequence_review("billing-paid-actions")
        duplicate["lenses"][2]["id"] = "black-box"
        duplicate["lenses"][1]["id"] = "black-box"
        invalid.append((duplicate, "distinct lens IDs"))

        missing = consequence_review("billing-paid-actions")
        missing["lenses"].pop()
        invalid.append((missing, "requires exactly"))

        arbitrary = consequence_review("this-seems-risky")
        invalid.append((arbitrary, "canonical high-consequence categories"))

        for review, message in invalid:
            with self.subTest(message=message):
                self.graph.write_text(json.dumps(graph(review=review)))
                result = self.command("compile", "--run", str(self.run), "--graph", str(self.graph), ok=False)
                self.assertIn(message, result.stderr)

    def test_epic_gap_review_enforces_three_by_three_and_terminal_dispositions(self) -> None:
        self.compile_and_start()

        too_many = [self.gap_finding(f"GAP{index}", "fixed", ["T1"]) for index in range(1, 5)]
        result = self.gap_review(1, too_many, ok=False)
        self.assertIn("at most 3 findings", result.stderr)

        invalid = self.gap_finding("GAP1", "recommended", ["T1"])
        result = self.gap_review(1, [invalid], ok=False)
        self.assertIn("terminal disposition", result.stderr)

        expanded = self.gap_finding("GAP1", "ask-user", ["NEW-SCOPE"])
        result = self.gap_review(1, [expanded], ok=False)
        self.assertIn("cannot alter accepted scope", result.stderr)

        fixed = self.gap_finding("REGRESSION", "fixed", ["T1"])
        omitted = self.gap_finding(
            "HARDENING", "omitted", ["T2"],
            missed="Generic production hardening could be added.",
            effect="No practical effect for this early internal tool.",
            response="Omit the generic hardening at the declared maturity.",
        )
        deferred = self.gap_finding("LATER", "deferred", ["T2"])
        self.gap_review(1, [fixed, omitted, deferred])
        self.gap_review(2, [])
        self.gap_review(3, [])

        status = json.loads(self.command("gap-review-status", "--run", str(self.run)).stdout)
        self.assertEqual(["REGRESSION"], status["dispositions"]["fixed"])
        self.assertEqual(["HARDENING"], status["dispositions"]["omitted"])
        self.assertEqual(["LATER"], status["dispositions"]["deferred"])
        self.assertNotIn("HARDENING", status["dispositions"]["fixed"])
        self.assertNotIn("LATER", status["dispositions"]["fixed"])

        result = self.gap_review(4, [], ok=False)
        self.assertIn("at most 3 passes", result.stderr)

    def test_gap_review_ask_user_blocks_only_affected_work_and_can_be_resolved(self) -> None:
        value = graph()
        value["tickets"][1]["dependencies"] = []
        self.compile_and_start(value=value)

        question = self.gap_finding("QUESTION", "ask-user", ["T1"])
        self.gap_review(1, [question])
        ready = json.loads(self.command("ready", "--run", str(self.run)).stdout)
        self.assertEqual(["T2"], [item["ticket"] for item in ready])
        result = self.command(
            "claim", "--run", str(self.run), "--ticket", "T1", "--agent", "agent-a", "--attempt", "1",
            ok=False,
        )
        self.assertIn("blocked by Epic gap review", result.stderr)

        resolved = self.gap_finding(
            "QUESTION", "fixed", ["T1"],
            response="Use the user's answer without changing the accepted scope.",
        )
        self.gap_review(2, [resolved])
        ready = json.loads(self.command("ready", "--run", str(self.run)).stdout)
        self.assertEqual(["T1", "T2"], sorted(item["ticket"] for item in ready))
        status = json.loads(self.command("gap-review-status", "--run", str(self.run)).stdout)
        self.assertEqual([], status["blockedWork"])
        self.assertEqual(["QUESTION"], status["dispositions"]["fixed"])

    def test_integrated_gap_review_accepts_bounded_context_and_blocks_affected_acceptance(self) -> None:
        self.compile_and_start()
        self.finish_ticket("T1", "agent-a")
        self.finish_ticket("T2", "agent-b")
        self.transition("integrating")

        question = self.gap_finding("INTEGRATED", "ask-user", ["T2"])
        self.gap_review(1, [question], phase="integrated")
        self.assertEqual("fail", self.manifest()["operations"]["verify:epic-gap-review"]["status"])
        lock = json.loads((self.run / "source-lock.json").read_text())
        final = self.verification_receipt("gap-final", oracle=lock["epics"]["E1"]["section_sha256"])
        result = self.command(
            "verify-epic", "--run", str(self.run), "--verification-receipt", str(final), ok=False,
        )
        self.assertIn("ask-user", result.stderr)

        self.gap_review(2, [self.gap_finding("INTEGRATED", "fixed", ["T2"])], phase="integrated")
        self.assertEqual("pass", self.manifest()["operations"]["verify:epic-gap-review"]["status"])
        self.command("verify-epic", "--run", str(self.run), "--verification-receipt", str(final))

    def test_reusable_gap_candidate_is_upserted_and_projected_without_a_model_handoff(self) -> None:
        self.compile_and_start()
        coverage = self.root / "coverage-gaps.md"
        coverage.write_text("# Coverage Gaps\n\n<!-- GAP CANDIDATES -->\n", encoding="utf-8")
        candidate = self.root / "gap-candidate.json"
        value = {
            "schemaVersion": GAP_CANDIDATE_SCHEMA,
            "id": "auto",
            "title": "Missing private-dashboard distinction guidance",
            "surface": "product shaping",
            "seenIn": ["RUN1"],
            "gap": "No reusable guidance tells shaping agents to preserve existing distinguishing signals.",
            "why": "An inferred boundary can erase the only useful distinction in an internal tool.",
            "suggestedDestination": "reference",
            "needsHuman": "Decide whether repeated evidence warrants reusable guidance.",
        }
        candidate.write_text(json.dumps(value), encoding="utf-8")
        added = json.loads(self.command(
            "record-gap-candidate", "--run", str(self.run),
            "--candidate", str(candidate), "--coverage-gaps", str(coverage),
        ).stdout)
        self.assertEqual(added["id"], "GAP-001")
        self.assertEqual(added["action"], "added")
        self.assertEqual(coverage.read_text().count("## GAP-001:"), 1)

        value["why"] = "The same failure can silently lengthen or distort implementation."
        candidate.write_text(json.dumps(value), encoding="utf-8")
        updated = json.loads(self.command(
            "record-gap-candidate", "--run", str(self.run),
            "--candidate", str(candidate), "--coverage-gaps", str(coverage),
        ).stdout)
        self.assertEqual(updated["id"], "GAP-001")
        self.assertEqual(updated["action"], "updated")
        self.assertEqual(coverage.read_text().count("## GAP-001:"), 1)
        status = json.loads(self.command("gap-review-status", "--run", str(self.run)).stdout)
        self.assertEqual([item["id"] for item in status["candidates"]], ["GAP-001"])
        completion = json.loads(self.command("completion", "--run", str(self.run)).stdout)
        self.assertEqual(completion["gapReview"]["candidates"][0]["id"], "GAP-001")

    def test_final_verification_rejects_mismatched_and_stale_consequence_reviews(self) -> None:
        self.restart_with_consequence("credentials-auth-permissions")
        self.compile_and_start(value=graph(review=consequence_review("credentials-auth-permissions")))
        self.finish_ticket("T1", "agent-a")
        self.finish_ticket("T2", "agent-b")
        self.transition("integrating")

        wrong = self.verification_receipt(
            "review-wrong-commit", oracle=self.consequence_oracle(lens="authority-security"),
        )
        raw = json.loads(wrong.read_text())
        raw["identity"]["commitSha"] = "0" * 40
        wrong.write_text(json.dumps(raw))
        result = self.command(
            "record-review", "--run", str(self.run), "--lens", "authority-security",
            "--verification-receipt", str(wrong), ok=False,
        )
        self.assertIn("exact integrated commit and tree", result.stderr)

        wrong_oracle = self.verification_receipt("review-wrong-oracle")
        result = self.command(
            "record-review", "--run", str(self.run), "--lens", "authority-security",
            "--verification-receipt", str(wrong_oracle), ok=False,
        )
        self.assertIn("controller-owned oracle", result.stderr)

        self.record_consequence_reviews()
        (self.repo / "tracked.txt").write_text("new candidate\n")
        subprocess.run(["git", "add", "tracked.txt"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "advance candidate"], cwd=self.repo, check=True)
        lock = json.loads((self.run / "source-lock.json").read_text())
        final = self.verification_receipt("final-after-review", oracle=lock["epics"]["E1"]["section_sha256"])
        result = self.command(
            "verify-epic", "--run", str(self.run), "--verification-receipt", str(final), ok=False,
        )
        self.assertIn("exact candidate revision", result.stderr)

    def test_ticket_graph_cannot_omit_locked_consequence_triggers(self) -> None:
        self.restart_with_consequence("billing-paid-actions")
        self.transition("accepted")
        self.graph.write_text(json.dumps(graph()))
        result = self.command("compile", "--run", str(self.run), "--graph", str(self.graph), ok=False)
        self.assertIn("must exactly match", result.stderr)
        self.graph.write_text(json.dumps(graph(review=consequence_review("billing-paid-actions"))))
        self.command("compile", "--run", str(self.run), "--graph", str(self.graph))

    def test_consequence_dry_run_live_authority_and_bounded_evidence_are_enforced(self) -> None:
        self.restart_with_consequence("billing-paid-actions")
        self.compile_and_start(value=graph(review=consequence_review("billing-paid-actions")))
        self.finish_consequence_implementation()
        revision = self.revision()[0]
        self.grant("open-final-pr")
        pr_facts = json.loads(self.command("project-pr", "--run", str(self.run)).stdout)
        gate_status = {item["id"]: item["status"] for item in pr_facts["releaseGates"]}
        self.assertEqual("pass", gate_status["consequence-review"])
        self.assertEqual("pending", gate_status["dry-run-no-mutation"])

        self.grant("merge-to-default")
        merge = (
            "record-merge", "--run", str(self.run), "--pr", "PR-CONSEQUENCE",
            "--merged-sha", revision, "--main-sha", revision, "--evidence", "default-ref",
        )
        result = self.command(*merge, ok=False)
        self.assertIn("dry-run-no-mutation", result.stderr)
        self.record_safeguard("dry-run-no-mutation", result="fail")
        result = self.command(*merge, ok=False)
        self.assertIn("is fail", result.stderr)
        self.record_safeguard("dry-run-no-mutation")
        self.command(*merge)
        self.command(*merge)
        self.transition("merged")

        deploy = (
            "record-release", "--run", str(self.run), "--stage", "deployment", "--result", "pass",
            "--summary", "Exact revision deployed.", "--evidence", "provider-deploy", "--revision", revision,
        )
        self.assertIn("deploy-production", self.command(*deploy, ok=False).stderr)
        self.grant("deploy-production")
        self.assertIn("perform-paid-action", self.command(*deploy, ok=False).stderr)
        self.grant("perform-paid-action")
        self.command(*deploy)
        self.transition("deployed")

        production = (
            "record-release", "--run", str(self.run), "--stage", "production-verification", "--result", "pass",
            "--summary", "Bounded production oracle passed.", "--evidence", "provider-canary", "--revision", revision,
        )
        self.assertIn("verify-production", self.command(*production, ok=False).stderr)
        self.grant("verify-production")
        self.assertIn("bounded-live", self.command(*production, ok=False).stderr)
        self.record_safeguard("bounded-live")
        self.assertIn("rollback-readiness", self.command(*production, ok=False).stderr)
        self.record_safeguard("rollback-readiness")
        self.command(*production)

        rollback = (
            "record-rollback", "--run", str(self.run), "--trigger", "canary-failure",
            "--action", "restore previous revision", "--result", "pass", "--evidence", "rollback-log",
        )
        self.assertIn("execute-rollback", self.command(*rollback, ok=False).stderr)
        facts = json.loads(self.command("run-facts", "--run", str(self.run)).stdout)
        self.assertEqual("gauntlet/epic-run-facts/v1", facts["schemaVersion"])
        self.assertEqual("pass", facts["review"]["status"])
        self.assertTrue(all(item["status"] == "pass" for item in facts["release"]["safeguards"].values()))

    def test_record_merge_rejects_nonexistent_stale_and_unrelated_main_but_replays_valid_fact(self) -> None:
        (self.repo / "tracked.txt").write_text("candidate commit\n")
        subprocess.run(["git", "add", "tracked.txt"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "candidate"], cwd=self.repo, check=True)
        self.compile_and_start()
        self.finish_implementation()
        self.transition("epic_verified")
        self.grant("merge-to-default")
        head = self.revision()[0]
        old_main = subprocess.run(
            ["git", "rev-parse", "refs/heads/main"], cwd=self.repo, text=True, capture_output=True, check=True,
        ).stdout.strip()

        nonexistent = self.command(
            "record-merge", "--run", str(self.run), "--pr", "PR-X", "--merged-sha", "f" * 40,
            "--main-sha", "f" * 40, "--evidence", "default-ref", ok=False,
        )
        self.assertIn("cannot resolve", nonexistent.stderr)
        stale = self.command(
            "record-merge", "--run", str(self.run), "--pr", "PR-X", "--merged-sha", head,
            "--main-sha", head, "--evidence", "default-ref", ok=False,
        )
        self.assertIn("currently observed default-branch ref", stale.stderr)
        unrelated = self.command(
            "record-merge", "--run", str(self.run), "--pr", "PR-X", "--merged-sha", old_main,
            "--main-sha", old_main, "--evidence", "default-ref", ok=False,
        )
        self.assertIn("neither verified-head ancestry nor the exact verified candidate tree", unrelated.stderr)

        subprocess.run(["git", "update-ref", "refs/heads/main", head], cwd=self.repo, check=True)
        valid = (
            "record-merge", "--run", str(self.run), "--pr", "PR-X", "--merged-sha", head,
            "--main-sha", head, "--evidence", "default-ref",
        )
        self.command(*valid)
        self.command(*valid)

    def test_record_merge_accepts_squash_tree_equivalence(self) -> None:
        self.compile_and_start()
        self.finish_implementation()
        self.transition("epic_verified")
        self.grant("merge-to-default")
        verified = self.revision()[0]
        tree = subprocess.run(
            ["git", "rev-parse", f"{verified}^{{tree}}"], cwd=self.repo,
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        squashed = subprocess.run(
            ["git", "commit-tree", tree, "-m", "squashed equivalent"], cwd=self.repo,
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        subprocess.run(["git", "update-ref", "refs/heads/main", squashed], cwd=self.repo, check=True)
        self.command(
            "record-merge", "--run", str(self.run), "--pr", "PR-SQUASH",
            "--merged-sha", squashed, "--main-sha", squashed,
            "--evidence", "merged PR head and exact candidate tree",
        )
        self.assertEqual("tree-equivalence", self.manifest()["release"]["merge"]["verification_method"])

    def test_graph_rejects_unknown_optional_cohort_and_cycles(self) -> None:
        self.transition("accepted")
        value = graph()
        value["tickets"][0]["cohort_id"] = "MISSING"
        self.graph.write_text(json.dumps(value))
        result = self.command("compile", "--run", str(self.run), "--graph", str(self.graph), ok=False)
        self.assertIn("unknown cohort", result.stderr)

        value = graph()
        value["tickets"][0]["dependencies"] = ["T2"]
        self.graph.write_text(json.dumps(value))
        result = self.command("compile", "--run", str(self.run), "--graph", str(self.graph), ok=False)
        self.assertIn("cycle", result.stderr)

    def test_reconcile_invalidates_without_changing_denominator_and_membership_requires_superseding_run(self) -> None:
        self.compile_and_start()
        self.finish_ticket("T1", "agent-a")
        before = self.manifest()
        denominator = before["progress"]["denominator_sha256"]
        self.assertEqual("pass", before["operations"]["integrate:ticket:T1"]["status"])

        changed = self.snapshot.read_text().replace(
            "Initial balance requirements.",
            "Changed balance requirements.",
        )
        self.snapshot.write_text(changed)
        self.canonical.write_text(changed)
        result = json.loads(self.command(
            "reconcile", "--run", str(self.run), "--source", str(self.snapshot),
            "--graph", str(self.graph),
        ).stdout)
        self.assertEqual(["T1", "T2"], result["invalidated_tickets"])
        reconciled = self.manifest()
        self.assertEqual(denominator, reconciled["progress"]["denominator_sha256"])
        integration = reconciled["operations"]["integrate:ticket:T1"]
        self.assertEqual("queued", integration["status"])
        self.assertEqual(["pass"], [item["status"] for item in integration["attempts"]])
        self.assertEqual(2, reconciled["tickets"]["T1"]["revision"])

        self.graph.write_text(json.dumps(graph(with_cohort=True)))
        rejected = self.command(
            "reconcile", "--run", str(self.run), "--source", str(self.snapshot),
            "--graph", str(self.graph), ok=False,
        )
        self.assertIn("start a superseding run", rejected.stderr)


if __name__ == "__main__":
    unittest.main()
