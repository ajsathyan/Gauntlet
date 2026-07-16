#!/usr/bin/env python3
"""Behavioral tests for the pure live Epic progress projection."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest


SCRIPT = Path(__file__).with_name("progress_projection.py")
SPEC = importlib.util.spec_from_file_location("progress_projection", SCRIPT)
projection = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(projection)


NOW = "2026-07-16T16:00:00Z"


def source_fixture() -> dict:
    units = [
        {"id": "prepare:source-lock", "kind": "prepare", "phase": "prepare", "status": "pass"},
        {"id": "prepare:ticket-graph", "kind": "prepare", "phase": "prepare", "status": "pass"},
        {"id": "build:ticket:T1", "kind": "ticket-build", "phase": "build", "status": "running"},
        {"id": "build:ticket:T2", "kind": "ticket-build", "phase": "build", "status": "pass"},
        {"id": "integrate:ticket:T1", "kind": "ticket-integration", "phase": "integrate", "status": "queued"},
        {"id": "integrate:ticket:T2", "kind": "ticket-integration", "phase": "integrate", "status": "running"},
        {"id": "verify:review:black-box", "kind": "consequence-review", "phase": "final-verify", "status": "running"},
        {"id": "verify:final-epic", "kind": "final-epic-verification", "phase": "final-verify", "status": "queued"},
        {"id": "ship:merge", "kind": "release-gate", "phase": "ship", "status": "queued"},
        {"id": "ship:deployment", "kind": "release-gate", "phase": "ship", "status": "queued"},
    ]
    operations = []
    for unit in units:
        if unit["kind"] in {"prepare", "ticket-build"}:
            continue
        operations.append({
            "attempt": 1 if unit["status"] == "running" else 0,
            "attempts": ([{
                "attempt": 1, "startedAt": "2026-07-16T15:55:00Z",
                "finishedAt": None, "status": "running",
            }] if unit["status"] == "running" else []),
            "finishedAt": None,
            "id": unit["id"], "kind": unit["kind"], "phase": unit["phase"],
            "queuedAt": "2026-07-16T15:40:00Z",
            "startedAt": "2026-07-16T15:55:00Z" if unit["status"] == "running" else None,
            "status": unit["status"],
        })
    return {
        "schemaVersion": "gauntlet/live-progress-source/v1",
        "launch": {
            "coverageSha256": "a" * 64,
            "targetEpicIds": ["E1"],
            "epics": {"E1": {"status": "in-progress", "blocker": None, "stopDisposition": None}},
        },
        "runs": {"E1": {
            "runId": "RUN1",
            "facts": {
                "schemaVersion": "gauntlet/epic-run-facts/v1",
                "epicId": "E1", "epicTitle": "Balance",
                "time": {
                    "protocolVersion": "gauntlet.rfc3339-utc.v1",
                    "elapsedCoverage": "complete", "createdAt": "2026-07-16T15:30:00Z",
                    "startedAt": "2026-07-16T15:40:00Z", "updatedAt": "2026-07-16T15:59:30Z",
                    "terminalAt": None,
                },
                "progress": {
                    "schemaVersion": "gauntlet.progress-units.v1",
                    "policyVersion": "gauntlet.progress-policy.v1",
                    "denominatorSha256": "b" * 64,
                    "units": units,
                },
                "operations": operations,
                "owners": [
                    {"ownerId": "root", "ownerKind": "parent", "ownerRef": "PRIVATE-ROOT",
                     "nativeChildId": "root-1", "requestedProfile": None,
                     "requestWindow": {"startedAt": "2026-07-16T15:30:00Z", "endedAt": None,
                                       "startOrdinal": 1, "endOrdinal": None}},
                    {"ownerId": "ticket:T1:r1:a1", "ownerKind": "delegated", "ownerRef": "PRIVATE-AGENT",
                     "nativeChildId": "child-1", "requestedProfile": "gauntlet_standard_worker",
                     "requestWindow": {"startedAt": "2026-07-16T15:50:00Z", "endedAt": None,
                                       "startOrdinal": 2, "endOrdinal": None}},
                ],
                "release": {"applicability": {"merge": True, "deployment": True, "production-verification": False}},
                "privatePath": "/Users/secret/PROMPT-CANARY",
                "verificationReceipts": [{"summary": "TRANSCRIPT-CANARY"}],
            },
        }},
        "telemetry": {"E1": {
            "schemaVersion": "gauntlet/run-telemetry-summary/v1",
            "coverage": {"status": "complete", "freshness": {"observedThrough": "2026-07-16T15:59:45Z"},
                         "limitations": [], "totalsScope": "all-declared-owners"},
            "tokens": {"input_tokens": 1200, "cached_input_tokens": 200, "output_tokens": 300,
                       "reasoning_output_tokens": 100, "total_tokens": 1500},
            "pricing": {"status": "complete", "registryVersion": "gauntlet.model-api-pricing.v1",
                        "effectiveAt": "2026-07-01", "estimatedUsd": 0.12, "lowerBoundUsd": 0.12,
                        "components": {"inputUsd": 0.04, "cachedInputUsd": 0.01, "outputUsd": 0.07},
                        "byModel": {"gpt-5.2": {"requests": 1, "inputUsd": 0.04,
                                                   "cachedInputUsd": 0.01, "outputUsd": 0.07,
                                                   "totalUsd": 0.12}},
                        "limitations": []},
        }},
    }


def epic(value: dict) -> dict:
    return projection.build_projection(value, now=NOW)["epics"][0]


class ProgressProjectionTests(unittest.TestCase):
    def test_overlapping_phases_use_fixed_policy_and_allowlisted_output(self) -> None:
        value = source_fixture()
        result = projection.build_projection(value, now=NOW)
        item = result["epics"][0]
        self.assertEqual("gauntlet/live-epic-progress/v1", result["schema"])
        self.assertEqual("parallel_work", item["presentation"]["state"])
        self.assertEqual(
            {"prepare": 0.05, "build": 0.35, "integrate": 0.25, "final_verify": 0.20, "ship": 0.15},
            {phase["key"]: phase["policyShare"] for phase in item["phases"]},
        )
        active = {phase["key"] for phase in item["phases"] if phase["status"] == "active"}
        self.assertEqual({"build", "integrate", "final_verify"}, active)
        serialized = json.dumps(result)
        for canary in ("PROMPT-CANARY", "TRANSCRIPT-CANARY", "PRIVATE-ROOT", "PRIVATE-AGENT", "/Users/secret"):
            self.assertNotIn(canary, serialized)
        self.assertEqual(1500, item["usage"]["totalTokens"])
        self.assertEqual("complete", item["usage"]["coverage"])
        self.assertEqual("complete", item["pricing"]["status"])

    def test_invalidation_moves_proved_progress_backward_without_denominator_change(self) -> None:
        value = source_fixture()
        operation = next(
            item for item in value["runs"]["E1"]["facts"]["operations"]
            if item["id"] == "integrate:ticket:T2"
        )
        operation.update({"status": "pass", "finishedAt": "2026-07-16T15:58:00Z"})
        operation["attempts"] = [{
            "attempt": 1, "startedAt": "2026-07-16T15:45:00Z",
            "finishedAt": "2026-07-16T15:58:00Z", "status": "pass",
        }]
        unit = next(item for item in value["runs"]["E1"]["facts"]["progress"]["units"] if item["id"] == operation["id"])
        unit["status"] = "pass"
        before = epic(value)
        operation.update({"status": "queued", "startedAt": None, "finishedAt": None})
        operation["attempts"] = [{
            "attempt": 1, "startedAt": "2026-07-16T15:45:00Z",
            "finishedAt": "2026-07-16T15:50:00Z", "status": "pass",
        }]
        unit["status"] = "queued"
        after = epic(value)
        invalidated = next(item for item in after["details"]["units"] if item["id"] == operation["id"])
        self.assertEqual("invalidated", invalidated["status"])
        self.assertEqual(before["details"]["denominatorDigest"], after["details"]["denominatorDigest"])
        self.assertLess(
            next(phase["provedShare"] for phase in after["phases"] if phase["key"] == "integrate"),
            next(phase["provedShare"] for phase in before["phases"] if phase["key"] == "integrate"),
        )

    def test_old_timestampless_run_is_elapsed_and_eta_unavailable(self) -> None:
        value = source_fixture()
        facts = value["runs"]["E1"]["facts"]
        facts["time"] = {"protocolVersion": None, "elapsedCoverage": "unavailable", "createdAt": None,
                         "startedAt": None, "updatedAt": "2026-07-16T15:59:30Z", "terminalAt": None}
        facts["progress"] = None
        facts["operations"] = []
        item = epic(value)
        self.assertEqual("Unavailable", item["time"]["elapsed"])
        self.assertEqual("unavailable", item["eta"]["status"])
        self.assertIsNone(item["time"]["startedAt"])

    def test_health_progress_freshness_and_eta_are_independent(self) -> None:
        value = source_fixture()
        item = epic(value)
        self.assertEqual("healthy", item["health"]["status"])
        self.assertFalse(item["freshness"]["stale"])
        self.assertIn(item["eta"]["status"], {"settling", "available"})

        needs_user = copy.deepcopy(value)
        needs_user["launch"]["epics"]["E1"]["status"] = "needs-decision"
        blocked = epic(needs_user)
        self.assertEqual("needs_user", blocked["health"]["status"])
        self.assertEqual("waiting_on_user", blocked["eta"]["status"])
        self.assertEqual(item["details"]["plannedProgress"], blocked["details"]["plannedProgress"])

        stale = projection.build_projection(value, now="2026-07-16T17:00:00Z")["epics"][0]
        self.assertTrue(stale["freshness"]["stale"])
        self.assertEqual("recovering", stale["health"]["status"])

    def test_canonical_presentation_states_cover_controller_outcomes(self) -> None:
        self.assertEqual({
            "starting", "healthy_build", "parallel_work", "return_update", "recovering",
            "needs_user", "ready_to_merge", "ready_to_deploy", "shipped",
        }, set(projection.PRESENTATION_STATES))
        value = source_fixture()
        self.assertEqual("parallel_work", epic(value)["presentation"]["state"])

        for unit in value["runs"]["E1"]["facts"]["progress"]["units"]:
            unit["status"] = "queued" if unit["phase"] != "prepare" else "pass"
        for operation in value["runs"]["E1"]["facts"]["operations"]:
            operation.update({"status": "queued", "attempts": [], "startedAt": None, "finishedAt": None})
        self.assertEqual("starting", epic(value)["presentation"]["state"])
        next(item for item in value["runs"]["E1"]["facts"]["progress"]["units"] if item["id"] == "build:ticket:T1")["status"] = "running"
        self.assertEqual("healthy_build", epic(value)["presentation"]["state"])

        failed = copy.deepcopy(value)
        op = next(item for item in failed["runs"]["E1"]["facts"]["operations"] if item["id"] == "integrate:ticket:T1")
        op["status"] = "fail"
        next(item for item in failed["runs"]["E1"]["facts"]["progress"]["units"] if item["id"] == op["id"])["status"] = "fail"
        self.assertEqual("recovering", epic(failed)["presentation"]["state"])

        final = copy.deepcopy(value)
        for unit in final["runs"]["E1"]["facts"]["progress"]["units"]:
            unit["status"] = "pass" if unit["phase"] != "ship" else "queued"
        for operation in final["runs"]["E1"]["facts"]["operations"]:
            operation["status"] = "pass" if operation["phase"] != "ship" else "queued"
        self.assertEqual("ready_to_merge", epic(final)["presentation"]["state"])
        next(item for item in final["runs"]["E1"]["facts"]["progress"]["units"] if item["id"] == "ship:merge")["status"] = "pass"
        next(item for item in final["runs"]["E1"]["facts"]["operations"] if item["id"] == "ship:merge")["status"] = "pass"
        self.assertEqual("ready_to_deploy", epic(final)["presentation"]["state"])
        for unit in final["runs"]["E1"]["facts"]["progress"]["units"]:
            unit["status"] = "pass"
        for operation in final["runs"]["E1"]["facts"]["operations"]:
            operation["status"] = "pass"
        final["runs"]["E1"]["facts"]["time"]["terminalAt"] = NOW
        self.assertEqual("shipped", epic(final)["presentation"]["state"])

    def test_projection_is_deterministic_and_rejects_malformed_sources(self) -> None:
        value = source_fixture()
        first = projection.build_projection(value, now=NOW)
        second = projection.build_projection(copy.deepcopy(value), now=NOW)
        self.assertEqual(first, second)
        with self.assertRaises(projection.ProjectionError):
            projection.build_projection({"schemaVersion": "wrong"}, now=NOW)

    def test_terminal_facts_do_not_age_back_into_recovery(self) -> None:
        value = source_fixture()
        facts = value["runs"]["E1"]["facts"]
        for unit in facts["progress"]["units"]:
            unit["status"] = "pass"
        for operation in facts["operations"]:
            operation["status"] = "pass"
        facts["time"]["terminalAt"] = NOW
        result = projection.build_projection(value, now="2026-07-17T16:00:00Z")["epics"][0]
        self.assertEqual("shipped", result["presentation"]["state"])
        self.assertEqual("healthy", result["health"]["status"])
        self.assertFalse(result["freshness"]["stale"])


if __name__ == "__main__":
    unittest.main()
