import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkflowPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.titles = load_module("thread_titles", ROOT / "scripts" / "thread_titles.py")

    def test_plain_titles_accept_one_to_four_words(self):
        for title in ("Sensors", "Build sensors", "Build reliable sensors", "Build reliable sensor execution"):
            with self.subTest(title=title):
                parsed = self.titles.parse_thread_title(title)
                self.assertEqual(parsed["format"], "current")
                self.assertEqual(parsed["goal"], title)
                self.assertNotIn("priority", parsed)
                self.assertNotIn("executionMode", parsed)

    def test_priority_and_autonomy_metadata_are_rejected(self):
        for title in ("p1: Build reliable sensor execution", "p1-auto: Build reliable sensors", "Build reliable sensor execution now"):
            with self.subTest(title=title):
                self.assertEqual(self.titles.parse_thread_title(title)["format"], "malformed")

    def test_checker_reports_at_most_four_words(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "check-workflow-etiquette.py"),
                "--title",
                "Build reliable sensor execution now",
                "--json",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 1)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["findings"][0]["code"], "title_word_limit")
        self.assertEqual(payload["findings"][0]["maximumWordCount"], 4)
        self.assertNotIn("effectiveExecutionMode", payload)
        self.assertNotIn("kickoffFields", payload)

    def test_active_policy_has_no_obsolete_default_machinery(self):
        paths = [
            ROOT / "AGENTS.md",
            ROOT / "router" / "AGENTS.md",
            ROOT / "docs" / "workflow-etiquette.md",
            ROOT / "docs" / "design-build-verify.md",
            ROOT / "docs" / "parallel-workstreams.md",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in paths).lower()
        for obsolete in (
            "route-codex-agent.py",
            "subagent-audit.py",
            "ticket graph",
            "execution run",
            "project pr",
            "p#-auto",
            "p#:",
        ):
            with self.subTest(obsolete=obsolete):
                self.assertNotIn(obsolete, text)

    def test_obsolete_workflow_products_are_removed(self):
        paths = [
            ROOT / "scripts" / "route-codex-agent.py",
            ROOT / "scripts" / "subagent-audit.py",
            ROOT / "scripts" / "run-orchestration-evals.py",
            ROOT / "scripts" / "test-subagent-orchestration.py",
            ROOT / "tests" / "test_subagent_orchestration.py",
            ROOT / "evals" / "orchestration-trace-fixtures.json",
            ROOT / "evals" / "orchestration-trace-schema.json",
            ROOT / "skills" / "implement-prd",
            ROOT / "skills" / "maintain-prd",
            ROOT / "skills" / "to-prd",
            ROOT / "skills" / "run-log-builder",
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
