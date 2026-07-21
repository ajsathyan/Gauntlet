from __future__ import annotations

import hashlib
import unittest

from tests import support as _support  # noqa: F401
from gauntletlib.workflow.application import validate_prebuild_reviews
from gauntletlib.workflow.contracts import (
    ContractError,
    accept_design,
    bind_candidate_revision,
    completion_status,
    record_verdict,
)

DESIGN_SHA = "sha256:" + hashlib.sha256(b"design").hexdigest()
ACCEPTANCE_SHA = "sha256:" + hashlib.sha256(b"acceptance").hexdigest()
COMMIT = "1" * 40
TREE = "2" * 40
BASE = "3" * 40
OUTCOMES = [
    {"identity": "outcome-1", "sha256": "sha256:" + hashlib.sha256(b"one").hexdigest()},
    {"identity": "outcome-2", "sha256": "sha256:" + hashlib.sha256(b"two").hexdigest()},
]


def contract(architecture=False):
    value = accept_design(
        identity="GAUNTLET-001",
        reference="designs/001.md",
        design_sha256=DESIGN_SHA,
        acceptance_sha256=ACCEPTANCE_SHA,
        outcomes=OUTCOMES,
        contract_applicability={
            "architecture": {
                "applicable": architecture,
                "sha256": DESIGN_SHA if architecture else None,
            }
        },
    )
    return bind_candidate_revision(value, commit=COMMIT, tree=TREE, base=BASE)


def result(behavior="passed", availability="available", index=1):
    unresolved = behavior == "unknown" or availability == "unavailable"
    return {
        "behavior": behavior,
        "proofAvailability": availability,
        "evidence": [f"revision:{COMMIT}#path:proof-{index}.txt"] if not unresolved else [],
        "remainingCheck": "Run the unavailable oracle." if unresolved else None,
    }


class WorkflowContractTests(unittest.TestCase):
    def test_pass_requires_every_outcome_and_exact_base(self):
        value = contract()
        value = record_verdict(
            value,
            area="build",
            verdict="passed",
            outcome_results={"outcome-1": result(index=1), "outcome-2": result(index=2)},
        )
        value = record_verdict(
            value,
            area="architecture",
            verdict="not-applicable",
        )
        self.assertEqual(
            value["candidateRevision"],
            {"commit": COMMIT, "tree": TREE, "base": BASE},
        )
        self.assertTrue(completion_status(value)["complete"])

    def test_known_failure_is_not_hidden_by_environment_block(self):
        value = contract()
        results = {
            "outcome-1": result("failed", "available", 1),
            "outcome-2": result("unknown", "unavailable", 2),
        }
        results["outcome-1"]["evidence"] = [f"revision:{COMMIT}#path:failure.txt"]
        value = record_verdict(
            value, area="build", verdict="failed", outcome_results=results
        )
        self.assertEqual(value["verdicts"]["build"]["verdict"], "failed")

    def test_unavailable_required_proof_is_blocked(self):
        value = contract()
        value = record_verdict(
            value,
            area="build",
            verdict="blocked",
            outcome_results={
                "outcome-1": result(index=1),
                "outcome-2": result("unknown", "unavailable", 2),
            },
        )
        self.assertEqual(completion_status(value)["verdicts"]["build"], "blocked")

    def test_false_pass_and_narrowed_outcomes_are_rejected(self):
        value = contract()
        with self.assertRaises(ContractError):
            record_verdict(
                value,
                area="build",
                verdict="passed",
                outcome_results={
                    "outcome-1": result(index=1),
                    "outcome-2": result("unknown", "unavailable", 2),
                },
            )
        with self.assertRaises(ContractError):
            record_verdict(
                value,
                area="build",
                verdict="passed",
                outcome_results={"outcome-1": result(index=1)},
            )

    def test_six_lenses_allow_one_main_agent_and_require_not_applicable_reason(self):
        accepted = contract()["acceptedDesign"]
        binding = {
            "identity": accepted["identity"],
            "reference": accepted["reference"],
            "sha256": accepted["sha256"],
            "acceptanceSha256": accepted["acceptanceSha256"],
        }
        reviews = []
        for lens in ("product", "engineering", "design", "analytics", "qa", "performance"):
            reviews.append(
                {
                    "lens": lens,
                    "reviewer": "main-agent",
                    "design": binding,
                    "applicability": "not-applicable" if lens == "analytics" else "applicable",
                    "applicabilityReason": "No instrumentation changes." if lens == "analytics" else None,
                    "findings": [],
                    "materialFindingCount": 0,
                }
            )
        summary = validate_prebuild_reviews(accepted, reviews)
        self.assertEqual(summary["reviewerMode"], "main-agent")
        self.assertEqual(len(summary["lenses"]), 6)

        reviews[-1]["applicability"] = "not-applicable"
        reviews[-1]["applicabilityReason"] = None
        with self.assertRaises(ContractError):
            validate_prebuild_reviews(accepted, reviews)


if __name__ == "__main__":
    unittest.main()
