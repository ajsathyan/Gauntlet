#!/usr/bin/env python3

import json
import unittest

from support import ROOT


class LiteSkillContractTests(unittest.TestCase):
    def test_skill_eval_fixtures_target_retained_surface(self):
        cases = json.loads((ROOT / "evals" / "skill-evals.json").read_text())["cases"]
        retained = {
            "design", "adversarial-reviewer", "verify", "land", "refactor-codebase"
        }
        self.assertEqual({case["skill"] for case in cases}, retained)

    def test_six_lens_review_and_advisory_boundary(self):
        text = (ROOT / "skills" / "adversarial-reviewer" / "SKILL.md").read_text()
        for lens in ("Product", "Engineering", "Design", "Analytics", "QA", "Performance"):
            self.assertIn(f"**{lens}:**", text)
        self.assertIn("cannot accept its own recommendation", text.lower())
        self.assertIn("Not applicable", text)

    def test_verify_has_two_axis_outcomes(self):
        text = (ROOT / "skills" / "verify" / "SKILL.md").read_text()
        for marker in ("**Behavior:**", "**Proof availability:**", "Failed", "Blocked", "Passed"):
            self.assertIn(marker, text)
        self.assertIn("does not end", text)

    def test_only_nine_canonical_skills_remain(self):
        skills = sorted(path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md"))
        self.assertEqual(len(skills), 9)
        self.assertFalse(list((ROOT / "skills").glob("*/*/SKILL.md")))


if __name__ == "__main__":
    unittest.main()
