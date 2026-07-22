import subprocess
import unittest

try:
    from tests.support import ROOT
except ModuleNotFoundError:
    from support import ROOT
from gauntletlib.contracts.handoff import validate_merge_handoff


CLI = ROOT / "scripts" / "gauntlet.py"


def run_cli(*arguments):
    return subprocess.run(
        ["python3", str(CLI), *arguments],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def valid_handoff():
    return {
        "schemaVersion": "1.0",
        "title": "workflow: simplify Gauntlet Lite",
        "problem": {"context": "The workflow is costly.", "impact": "Routine work pays ceremony."},
        "solution": {
            "outcome": "Retain a compact behavior-first workflow.",
            "invariants": ["Personal skills remain available."],
            "preserved": ["Established PR format."],
            "nonGoals": ["Merge queues."],
        },
        "changelog": "Simplify Gauntlet Lite around behavior-first proof.",
        "testing": [{"command": "python3 scripts/check-gauntlet-workflow.py", "result": "pass", "proves": "Supported workflow checks pass."}],
        "securityRisk": None,
        "sourceBinding": {
            "repository": "/tmp/repo",
            "commit": "1" * 40,
            "tree": "2" * 40,
            "base": "3" * 40,
        },
    }


class ControllerFreeCliTests(unittest.TestCase):
    def test_help_exposes_only_supported_workflow_commands(self):
        result = run_cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in ("install", "merge", "land"):
            self.assertIn(command, result.stdout)
        for retired in (
            "archive", "closeout", "followup", "changelog", "diagram", "sensors",
        ):
            self.assertNotIn(retired, result.stdout)
        self.assertIn("{install,merge,land}", result.stdout)

        for removed_command in ("docs", "workflow"):
            removed = run_cli(removed_command)
            self.assertNotEqual(removed.returncode, 0)
            self.assertIn("invalid choice", removed.stderr)

    def test_source_binding_is_required_and_includes_base(self):
        value = valid_handoff()
        self.assertEqual(validate_merge_handoff(value), [])
        value["sourceBinding"].pop("base")
        codes = {item["code"] for item in validate_merge_handoff(value)}
        self.assertIn("invalid_source_binding", codes)

    def test_legacy_merge_argument_is_rejected(self):
        result = run_cli("merge", "plan", "--handoff", "x", "--run", "legacy")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unrecognized arguments", result.stderr)

    def test_land_does_not_expose_post_merge_monitoring(self):
        help_result = run_cli("land", "execute", "--help")
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertNotIn("monitor", help_result.stdout.lower())

        rejected = run_cli(
            "land",
            "execute",
            "--handoff",
            "handoff.json",
            "--monitor-timeout",
            "1",
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("unrecognized arguments", rejected.stderr)


if __name__ == "__main__":
    unittest.main()
