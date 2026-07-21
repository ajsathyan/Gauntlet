import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkflowPolicyTests(unittest.TestCase):
    def test_active_policy_has_no_retired_machinery(self):
        paths = [
            ROOT / "AGENTS.md",
            ROOT / "router" / "AGENTS.md",
            ROOT / "README.md",
            ROOT / "docs" / "workflow-etiquette.md",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in paths).lower()
        for retired in (
            "custom profile", "token audit", "durable workstream", "sensor verdict",
            "merge queue requirement", "generated context", "closeout command",
            "destructive, paid",
        ):
            with self.subTest(retired=retired):
                self.assertNotIn(retired, text)

    def test_removed_products_are_absent(self):
        for path in (
            ROOT / "scripts" / "gauntletlib" / "closeout",
            ROOT / "scripts" / "generated_context.py",
            ROOT / "scripts" / "workflow-mode.py",
            ROOT / "skills" / "implementer",
            ROOT / "skills" / "planner",
            ROOT / "skills" / "black-box-tester",
            ROOT / "skills" / "craft-product-terminology",
        ):
            with self.subTest(path=path):
                self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
