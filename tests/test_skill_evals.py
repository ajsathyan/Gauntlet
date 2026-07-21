#!/usr/bin/env python3
"""Semantic contract checks for the Gauntlet Lite workflow."""

from __future__ import annotations

import json
import unittest

from support import ROOT


TERMINAL_DISPOSITIONS = {"accepted", "rejected", "deferred", "omitted"}


def verdicts(case):
    accepted = set(case["acceptedOutcomes"])
    claimed = set(case["claimedOutcomes"])
    build = "pass" if accepted <= claimed else "fail"
    overall = "pass" if build == case["architectureVerdict"] == "pass" else "fail"
    return build, overall


class LiteWorkflowContractTests(unittest.TestCase):
    def test_two_verdicts_reject_narrowed_build_evidence(self):
        fixtures = json.loads(
            (ROOT / "evals" / "design-build-verify-fixtures.json").read_text()
        )
        cases = {case["id"]: case for case in fixtures["cases"]}
        for case in cases.values():
            build, overall = verdicts(case)
            self.assertEqual(build, case["expectedBuildVerdict"], case["id"])
            self.assertEqual(overall, case["expectedOverallVerdict"], case["id"])

        wrong = cases["narrow-happy-path-proof"]
        self.assertNotEqual(
            set(wrong["acceptedOutcomes"]), set(wrong["claimedOutcomes"])
        )
        self.assertEqual(verdicts(wrong), ("fail", "fail"))

    def test_design_acceptance_blocks_nontrivial_implementation(self):
        design = (ROOT / "skills" / "design" / "SKILL.md").read_text()
        router = (ROOT / "router" / "AGENTS.md").read_text()
        self.assertIn("stop before implementation", design)
        self.assertIn("accept its exact `Acceptance` section", router)
        self.assertIn("canonical Build Contract", design)

    def test_verify_reports_build_and_architecture_only(self):
        verify = (ROOT / "skills" / "verify" / "SKILL.md").read_text()
        self.assertIn("Build Verdict", verify)
        self.assertIn("Architecture Verdict", verify)
        self.assertNotIn("third verdict", verify.lower())
        self.assertIn("required non-effect", verify)

    def test_shipping_has_no_second_production_acceptance(self):
        router = (ROOT / "router" / "AGENTS.md").read_text()
        ship = (ROOT / "skills" / "ship" / "SKILL.md").read_text()
        land = (ROOT / "skills" / "land" / "SKILL.md").read_text()
        self.assertIn("Do not request a second production acceptance", router)
        self.assertIn("Do not request another acceptance", ship)
        self.assertIn("No second acceptance is required", land)
        self.assertIn("merge-triggered deployment proceeds automatically", ship.lower())

    def test_three_lens_review_covers_stateful_failure_modes(self):
        reviewer = (ROOT / "skills" / "adversarial-reviewer" / "SKILL.md").read_text()
        for lens in ("product completeness", "engineering shape", "proof and consequence"):
            self.assertIn(lens, reviewer.lower())
        for mode in ("state transitions", "retries", "idempotency", "recovery", "concurrency"):
            self.assertIn(mode, reviewer.lower())
        for disposition in TERMINAL_DISPOSITIONS:
            self.assertIn(f"`{disposition}`", reviewer)

    def test_only_one_canonical_copy_of_each_retained_skill(self):
        canonical = sorted(path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md"))
        duplicates = list((ROOT / "evals").glob("**/skills/*/SKILL.md"))
        self.assertEqual(len(canonical), 20)
        self.assertFalse(duplicates)
        for retired in ("archive", "build", "eval-audit", "eval-rag"):
            self.assertNotIn(retired, canonical)


if __name__ == "__main__":
    unittest.main()
