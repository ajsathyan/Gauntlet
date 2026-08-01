import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkflowPolicyTests(unittest.TestCase):
    def test_ci_runs_only_for_pull_requests(self):
        workflow = (ROOT / ".github" / "workflows" / "gauntlet.yml").read_text()
        trigger = workflow[workflow.index("on:\n"):workflow.index("\npermissions:")]
        self.assertEqual(trigger, "on:\n  pull_request:\n")

    def test_ci_has_one_sequential_verification_job(self):
        workflow = (ROOT / ".github" / "workflows" / "gauntlet.yml").read_text()
        jobs = workflow[workflow.index("jobs:\n") + len("jobs:\n"):]
        job_names = [
            line.removeprefix("  ").removesuffix(":")
            for line in jobs.splitlines()
            if line.startswith("  ")
            and not line.startswith("    ")
            and line.endswith(":")
        ]
        self.assertEqual(job_names, ["checks"])
        self.assertNotIn("matrix:", workflow)
        self.assertNotIn("if: always()", workflow)

        group_commands = [
            f"python3 scripts/check-gauntlet-workflow.py --group {group}"
            for group in ("policy", "install", "contracts", "evals")
        ]
        positions = [workflow.index(command) for command in group_commands]
        self.assertEqual(positions, sorted(positions))
        for command in group_commands:
            self.assertEqual(workflow.count(command), 1)

        self.assertIn("python3 scripts/generate-install-manifest.py --check", workflow)
        self.assertIn("python3 -m ruff check .", workflow)
        self.assertIn("python3 -m pyright", workflow)

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
            ROOT / "scripts" / "gauntletlib" / "docs",
            ROOT / "scripts" / "gauntletlib" / "workflow",
            ROOT / "scripts" / "test-doc-lifecycle.py",
            ROOT / "scripts" / "test-flexible-prd.py",
            ROOT / "docs" / "local-documentation.md",
            ROOT / "tests" / "test_doc_lifecycle.py",
            ROOT / "tests" / "test_flexible_prd.py",
            ROOT / "tests" / "test_workflow_contracts.py",
            ROOT / "skills" / "implementer",
            ROOT / "skills" / "planner",
            ROOT / "skills" / "black-box-tester",
            ROOT / "skills" / "craft-product-terminology",
        ):
            with self.subTest(path=path):
                self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
