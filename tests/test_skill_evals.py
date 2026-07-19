#!/usr/bin/env python3
"""Semantic contract checks for the Design -> Build -> Verify workflow."""

from __future__ import annotations

import json
import unittest

from support import ROOT


TERMINAL_DISPOSITIONS = {"accepted", "rejected", "deferred", "omitted"}


def verdicts(case):
    accepted = set(case["acceptedOutcomes"])
    claimed = set(case["claimedOutcomes"])
    build = "pass" if accepted <= claimed else "fail"
    overall = (
        "pass"
        if build == case["architectureVerdict"] == case["sensorVerdict"] == "pass"
        else "fail"
    )
    return build, overall


class DesignBuildVerifyContractTests(unittest.TestCase):
    def test_exact_revision_verdicts_reject_narrowed_build_evidence(self):
        fixtures = json.loads(
            (ROOT / "evals" / "design-build-verify-fixtures.json").read_text(
                encoding="utf-8"
            )
        )
        cases = {case["id"]: case for case in fixtures["cases"]}
        for case in cases.values():
            build, overall = verdicts(case)
            self.assertEqual(build, case["expectedBuildVerdict"], case["id"])
            self.assertEqual(overall, case["expectedOverallVerdict"], case["id"])

        wrong = cases["gauntlet-009-green-sensors-narrow-checklist"]
        self.assertEqual(wrong["sensorVerdict"], "pass")
        self.assertNotEqual(
            set(wrong["acceptedOutcomes"]),
            set(wrong["claimedOutcomes"]),
        )
        self.assertEqual(verdicts(wrong), ("fail", "fail"))

    def test_public_skills_preserve_one_build_contract_and_separate_verdicts(self):
        design = (ROOT / "skills" / "design" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        build = (ROOT / "skills" / "build" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        verify = (ROOT / "skills" / "verify" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Acceptance section is the canonical Build Contract", design)
        self.assertIn("ephemeral", build)
        self.assertIn("accepted design directly", verify)
        self.assertIn("Build Verdict", verify)
        self.assertIn("Architecture Verdict", verify)
        self.assertIn("Sensor Verdict", verify)
        self.assertIn("Build Verdict is authoritative", verify)

    def test_installed_agent_path_requires_the_stateless_semantic_gate_sequence(self):
        router = (ROOT / "router" / "AGENTS.md").read_text(encoding="utf-8")
        installed_root = "/tmp/agent-home/gauntlet"
        rendered = router.replace("{{GAUNTLET_ROOT}}", installed_root)
        self.assertIn(
            f"python3 {installed_root}/scripts/gauntlet.py workflow build-entry",
            rendered,
        )
        for command in (
            "workflow bind-candidate",
            "workflow verify-entry",
            "workflow record-verdict",
            "workflow completion-check",
        ):
            self.assertIn(command, rendered)
        self.assertIn("task-temporary", rendered)
        self.assertIn("first implementation edit", rendered)

        for skill_name, commands in {
            "design": ("workflow build-entry",),
            "build": ("workflow build-entry", "workflow bind-candidate"),
            "verify": (
                "workflow verify-entry",
                "workflow record-verdict",
                "workflow completion-check",
            ),
        }.items():
            text = (ROOT / "skills" / skill_name / "SKILL.md").read_text(
                encoding="utf-8"
            )
            for command in commands:
                self.assertIn(command, text)
            self.assertIn("task-temporary", text)

    def test_three_lens_review_caps_display_without_dropping_findings(self):
        reviewer = (
            ROOT / "skills" / "adversarial-reviewer" / "SKILL.md"
        ).read_text(encoding="utf-8")
        for lens in (
            "product completeness",
            "engineering shape",
            "proof and consequence",
        ):
            self.assertIn(lens, reviewer.lower())
        self.assertIn("at most three", reviewer.lower())
        self.assertIn("every material finding", reviewer.lower())
        for disposition in TERMINAL_DISPOSITIONS:
            self.assertIn(f"`{disposition}`", reviewer)

    def test_normal_requests_bypass_design_and_durable_plan_state(self):
        router = (ROOT / "router" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Normal Request", router)
        self.assertIn("do not create a durable design", router)
        self.assertIn("ephemeral", router)
        self.assertNotIn("one Execution Run per", router)


if __name__ == "__main__":
    unittest.main()
