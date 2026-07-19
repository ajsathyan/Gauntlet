from __future__ import annotations

import hashlib
import unittest

from tests import support as _support  # noqa: F401

from gauntletlib.workflow.application import (
    authorize_candidate,
    build_entry,
    record_verification_verdict,
)
from gauntletlib.workflow.contracts import (
    ContractError,
    accept_design,
    bind_candidate_revision,
    completion_status,
    record_verdict,
)


DESIGN = b"accepted design\n"
DESIGN_SHA256 = "sha256:" + hashlib.sha256(DESIGN).hexdigest()
COMMIT = "1" * 40
TREE = "2" * 40
DESIGN_IDENTITY = "design-accepted-v3"
DESIGN_REFERENCE = "docs/design.md"
ACCEPTANCE_SHA256 = "sha256:" + hashlib.sha256(
    b"## Acceptance\n\n1. External command runs.\n2. Dashboard is published.\n"
).hexdigest()
OUTCOMES = [
    {
        "identity": "acceptance-001",
        "sha256": "sha256:" + hashlib.sha256(b"1. External command runs.").hexdigest(),
    },
    {
        "identity": "acceptance-002",
        "sha256": "sha256:" + hashlib.sha256(b"2. Dashboard is published.").hexdigest(),
    },
]
CONTRACT_APPLICABILITY = {
    "architecture": {"applicable": False, "sha256": None},
    "sensor": {"applicable": False, "sha256": None},
}


class WorkflowContractTests(unittest.TestCase):
    def contract(self):
        contract = accept_design(
            identity=DESIGN_IDENTITY,
            reference=DESIGN_REFERENCE,
            design_sha256=DESIGN_SHA256,
            acceptance_sha256=ACCEPTANCE_SHA256,
            outcomes=OUTCOMES,
            contract_applicability=CONTRACT_APPLICABILITY,
        )
        return bind_candidate_revision(
            contract,
            commit=COMMIT,
            tree=TREE,
        )

    def verdict(self, contract, area, verdict="pass", **overrides):
        values = {
            "area": area,
            "verdict": verdict,
            "design_identity": DESIGN_IDENTITY,
            "design_reference": DESIGN_REFERENCE,
            "design_sha256": DESIGN_SHA256,
            "commit": COMMIT,
            "tree": TREE,
            "read_design_directly": True,
            "direct_evidence": [f"{area} oracle observed"],
        }
        if area == "build" and verdict == "pass":
            values["outcome_evidence"] = {
                outcome["identity"]: [
                    f"revision:{COMMIT}#proof/{outcome['identity']}"
                ]
                for outcome in OUTCOMES
            }
        values.update(overrides)
        return record_verdict(contract, **values)

    def test_exact_source_and_revision_with_independent_verdicts_complete(self):
        contract = self.contract()
        for area in ("build", "architecture", "sensor"):
            contract = self.verdict(contract, area)

        result = completion_status(contract)

        self.assertTrue(result["complete"])
        self.assertEqual(
            set(contract["verdicts"]),
            {"build", "architecture", "sensor"},
        )
        self.assertTrue(
            contract["verdicts"]["build"]["acceptedDesignReadDirectly"]
        )

    def test_contract_points_to_design_without_copying_acceptance(self):
        contract = self.contract()

        self.assertEqual(
            contract["acceptedDesign"],
            {
                "identity": DESIGN_IDENTITY,
                "reference": DESIGN_REFERENCE,
                "sha256": DESIGN_SHA256,
                "acceptanceSha256": ACCEPTANCE_SHA256,
                "outcomes": OUTCOMES,
                "contractApplicability": CONTRACT_APPLICABILITY,
            },
        )
        keys = set()

        def collect_keys(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    keys.add(key.casefold())
                    collect_keys(child)
            elif isinstance(value, list):
                for child in value:
                    collect_keys(child)

        collect_keys(contract)
        self.assertFalse(
            {"acceptance", "checklist", "criteria"} & keys,
        )

    def test_design_and_candidate_revision_are_separate_bindings(self):
        accepted = accept_design(
            identity=DESIGN_IDENTITY,
            reference=DESIGN_REFERENCE,
            design_sha256=DESIGN_SHA256,
            acceptance_sha256=ACCEPTANCE_SHA256,
            outcomes=OUTCOMES,
            contract_applicability=CONTRACT_APPLICABILITY,
        )
        self.assertIsNone(accepted["candidateRevision"])
        self.assertNotIn("commit", accepted["acceptedDesign"])
        self.assertNotIn("tree", accepted["acceptedDesign"])

        bound = bind_candidate_revision(
            accepted,
            commit=COMMIT,
            tree=TREE,
        )

        self.assertEqual(
            bound["candidateRevision"],
            {"commit": COMMIT, "tree": TREE},
        )

    def test_sensor_pass_cannot_replace_missing_or_failed_build_proof(self):
        contract = self.verdict(self.contract(), "sensor")
        contract = self.verdict(contract, "architecture")
        missing = completion_status(contract)
        self.assertFalse(missing["complete"])
        self.assertIn("build verdict is absent", missing["reasons"])

        failed = self.verdict(contract, "build", verdict="fail")
        result = completion_status(failed)
        self.assertFalse(result["complete"])
        self.assertIn("build verdict did not pass", result["reasons"])

    def test_non_applicable_architecture_and_sensor_can_complete(self):
        contract = self.verdict(self.contract(), "build")
        contract = self.verdict(
            contract,
            "architecture",
            verdict="not-applicable",
        )
        contract = self.verdict(
            contract,
            "sensor",
            verdict="not-applicable",
        )

        result = completion_status(contract)

        self.assertTrue(result["complete"])
        self.assertEqual(result["verdicts"]["architecture"], "not-applicable")
        self.assertEqual(result["verdicts"]["sensor"], "not-applicable")

    def test_build_rejects_not_applicable(self):
        with self.assertRaisesRegex(ContractError, "build verdict"):
            self.verdict(
                self.contract(),
                "build",
                verdict="not-applicable",
            )

    def test_present_architecture_or_sensor_contract_rejects_not_applicable(self):
        for area in ("architecture", "sensor"):
            with self.subTest(area=area):
                contract = self.contract()
                contract["acceptedDesign"]["contractApplicability"][area] = {
                    "applicable": True,
                    "sha256": "sha256:" + "a" * 64,
                }
                with self.assertRaisesRegex(ContractError, "cannot be not-applicable"):
                    self.verdict(contract, area, verdict="not-applicable")

    def test_cannot_verify_blocks_each_area(self):
        for area in ("build", "architecture", "sensor"):
            with self.subTest(area=area):
                contract = self.contract()
                for current in ("build", "architecture", "sensor"):
                    contract = self.verdict(
                        contract,
                        current,
                        verdict="cannot-verify" if current == area else "pass",
                    )

                result = completion_status(contract)

                self.assertFalse(result["complete"])
                self.assertEqual(result["verdicts"][area], "cannot-verify")
                self.assertIn(f"{area} could not be verified", result["reasons"])

    def test_failed_architecture_or_sensor_blocks_completion(self):
        for area in ("architecture", "sensor"):
            with self.subTest(area=area):
                contract = self.contract()
                for current in ("build", "architecture", "sensor"):
                    contract = self.verdict(
                        contract,
                        current,
                        verdict="fail" if current == area else "pass",
                    )

                result = completion_status(contract)

                self.assertFalse(result["complete"])
                self.assertEqual(result["verdicts"][area], "fail")

    def test_unproved_build_verdict_cannot_complete(self):
        contract = self.contract()
        for area in ("build", "architecture", "sensor"):
            contract = self.verdict(contract, area)
        contract["verdicts"]["build"]["directEvidence"] = []

        result = completion_status(contract)

        self.assertFalse(result["complete"])
        self.assertIn("build verdict is unproved", result["reasons"])

    def test_mismatched_design_or_exact_revision_is_rejected(self):
        for override in (
            {"design_sha256": "sha256:" + "9" * 64},
            {"design_identity": "another-design"},
            {"design_reference": "docs/other.md"},
            {"commit": "3" * 40},
            {"tree": "4" * 40},
        ):
            with self.subTest(override=override):
                with self.assertRaises(ContractError):
                    self.verdict(self.contract(), "build", **override)

    def test_build_must_attest_that_it_read_the_design_directly(self):
        with self.assertRaisesRegex(ContractError, "read the accepted design directly"):
            self.verdict(
                self.contract(),
                "build",
                read_design_directly=False,
            )

    def test_derivative_only_evidence_is_rejected(self):
        with self.assertRaisesRegex(ContractError, "direct evidence"):
            self.verdict(
                self.contract(),
                "build",
                direct_evidence=[],
                derivative_evidence=["generated summary"],
            )

    def test_verdict_areas_do_not_overwrite_each_other(self):
        contract = self.verdict(self.contract(), "build")
        contract = self.verdict(contract, "sensor", verdict="fail")
        self.assertEqual(contract["verdicts"]["build"]["verdict"], "pass")
        self.assertEqual(contract["verdicts"]["sensor"]["verdict"], "fail")

    def test_build_pass_requires_direct_evidence_for_every_accepted_outcome(self):
        with self.assertRaisesRegex(ContractError, "every accepted outcome"):
            self.verdict(
                self.contract(),
                "build",
                outcome_evidence={
                    OUTCOMES[0]["identity"]: [
                        f"revision:{COMMIT}#proof/command"
                    ],
                },
            )

    def test_build_pass_rejects_reused_or_non_revision_evidence(self):
        duplicate = f"revision:{COMMIT}#proof/reused"
        with self.assertRaisesRegex(ContractError, "unique evidence references"):
            self.verdict(
                self.contract(),
                "build",
                outcome_evidence={
                    outcome["identity"]: [duplicate] for outcome in OUTCOMES
                },
            )
        with self.assertRaisesRegex(ContractError, "exact-revision"):
            self.verdict(
                self.contract(),
                "build",
                outcome_evidence={
                    outcome["identity"]: [f"self-attested:{outcome['identity']}"]
                    for outcome in OUTCOMES
                },
            )

    def test_application_accepts_an_explicit_alternate_design_reader(self):
        accepted = {
            "identity": DESIGN_IDENTITY,
            "reference": DESIGN_REFERENCE,
            "sha256": DESIGN_SHA256,
            "acceptanceSha256": ACCEPTANCE_SHA256,
            "outcomes": OUTCOMES,
            "contractApplicability": CONTRACT_APPLICABILITY,
        }
        calls = []

        class Repository:
            def resolve_candidate(self, project_root, commit, tree):
                return {"commit": commit, "tree": tree}

            def resolve_evidence(self, project_root, commit, locator):
                return f"revision:{commit}#{locator}"

        repository = Repository()

        def reader(project_root, design):
            calls.append((project_root, design))
            return accepted

        reviews = [
            {
                "lens": lens,
                "reviewer": f"reviewer-{index}",
                "design": accepted,
                "materialFindingCount": 0,
                "findings": [],
            }
            for index, lens in enumerate(
                (
                    "product-completeness",
                    "engineering-shape",
                    "proof-and-consequence",
                )
            )
        ]
        entered = build_entry(
            project_root="adapter-root",
            design="adapter-design",
            review_results=reviews,
            accepted_design_reader=reader,
        )
        candidate = authorize_candidate(
            project_root="adapter-root",
            design="adapter-design",
            review_results=reviews,
            contract=entered["contract"],
            commit=COMMIT,
            tree=TREE,
            accepted_design_reader=reader,
            git_repository=repository,
        )
        recorded = record_verification_verdict(
            project_root="adapter-root",
            design="adapter-design",
            contract=candidate,
            area="sensor",
            verdict="pass",
            evidence={"directEvidence": ["sensor evidence"]},
            accepted_design_reader=reader,
            git_repository=repository,
        )
        self.assertEqual(recorded["verdicts"]["sensor"]["verdict"], "pass")
        self.assertEqual(calls, [("adapter-root", "adapter-design")] * 3)


if __name__ == "__main__":
    unittest.main()
