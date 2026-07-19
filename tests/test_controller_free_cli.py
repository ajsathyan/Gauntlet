import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "gauntlet.py"


def run_cli(*arguments, cwd=None):
    return subprocess.run(
        ["python3", str(CLI), *arguments],
        cwd=cwd or ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git(repo, *arguments):
    return subprocess.run(
        ["git", *arguments],
        cwd=repo,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def handoff(repo):
    return {
        "schemaVersion": "1.0",
        "title": "workflow: preserve generic merge",
        "problem": {
            "context": "A completed change needs a contextual PR.",
            "impact": "Publishing without exact source identity can use stale work.",
        },
        "solution": {
            "outcome": "Prepare a PR from a validated generic handoff.",
            "invariants": ["The current commit remains exact."],
            "preserved": ["Normal Git and GitHub behavior."],
            "nonGoals": ["Owning implementation state."],
        },
        "changelog": "Preserve generic source-bound merge handoffs.",
        "testing": [
            {
                "command": "python3 -m unittest tests.test_controller_free_cli",
                "result": "pass",
                "proves": "The controller-free merge surface is available.",
            }
        ],
        "securityRisk": None,
        "sourceBinding": {
            "repository": str(repo.resolve()),
            "commit": git(repo, "rev-parse", "HEAD"),
            "tree": git(repo, "rev-parse", "HEAD^{tree}"),
        },
    }


class ControllerFreeCliTests(unittest.TestCase):
    def test_help_exposes_generic_commands_without_controller_commands(self):
        root = run_cli("--help")
        self.assertEqual(root.returncode, 0, root.stderr)
        for command in (
            "merge",
            "land",
            "closeout",
            "sensors",
            "workstreams",
        ):
            self.assertIn(command, root.stdout)
        for removed in (
            "epic-tasks",
            "progress",
            "analytics",
            "review-unit",
        ):
            self.assertNotIn(removed, root.stdout)

        for command in ("merge", "land", "closeout", "archive"):
            help_result = run_cli(command, "--help")
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            self.assertNotIn("--run", help_result.stdout)
        self.assertNotIn("reconcile", run_cli("merge", "--help").stdout)

    def test_merge_prepare_accepts_exact_source_and_rejects_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            git(repo.parent, "init", "-b", "main", str(repo))
            git(repo, "config", "user.name", "Gauntlet Test")
            git(repo, "config", "user.email", "gauntlet@example.test")
            (repo / "README.md").write_text("base\n", encoding="utf-8")
            git(repo, "add", "README.md")
            git(repo, "commit", "-m", "base")
            value = handoff(repo)
            handoff_path = repo / "handoff.json"
            handoff_path.write_text(
                json.dumps(value, indent=2) + "\n",
                encoding="utf-8",
            )

            prepared = run_cli(
                "merge",
                "prepare",
                "--git-root",
                str(repo),
                "--handoff",
                str(handoff_path),
                "--json",
                cwd=repo,
            )
            self.assertEqual(prepared.returncode, 0, prepared.stdout + prepared.stderr)
            payload = json.loads(prepared.stdout)
            self.assertEqual(payload["status"], "pass")
            self.assertTrue((repo / ".gauntlet" / "pr-body.md").is_file())
            self.assertIn(
                value["changelog"],
                (repo / "CHANGELOG.md").read_text(encoding="utf-8"),
            )

            (repo / "README.md").write_text("changed\n", encoding="utf-8")
            git(repo, "add", "README.md")
            git(repo, "commit", "-m", "drift")
            stale = run_cli(
                "merge",
                "prepare",
                "--git-root",
                str(repo),
                "--handoff",
                str(handoff_path),
                "--json",
                cwd=repo,
            )
            self.assertEqual(stale.returncode, 1)
            stale_payload = json.loads(stale.stdout)
            self.assertIn(
                "source_binding_drift",
                [item["code"] for item in stale_payload["findings"]],
            )

    def test_removed_run_argument_is_rejected(self):
        result = run_cli(
            "merge",
            "plan",
            "--handoff",
            "handoff.json",
            "--run",
            "legacy-run",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unrecognized arguments: --run", result.stderr)

    def test_closeout_keeps_explicit_generic_scope_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            git(repo.parent, "init", "-b", "main", str(repo))
            git(repo, "config", "user.name", "Gauntlet Test")
            git(repo, "config", "user.email", "gauntlet@example.test")
            (repo / "README.md").write_text("base\n", encoding="utf-8")
            git(repo, "add", "README.md")
            git(repo, "commit", "-m", "base")
            handoff_path = repo / "handoff.json"
            handoff_path.write_text(
                json.dumps(handoff(repo), indent=2) + "\n",
                encoding="utf-8",
            )

            result = run_cli(
                "closeout",
                "execute",
                "--git-root",
                str(repo),
                "--handoff",
                str(handoff_path),
                "--title",
                "Preserve generic closeout boundary",
                "--json",
                cwd=repo,
            )
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertIn(
                "missing_stage_scope",
                [item["code"] for item in payload["findings"]],
            )


if __name__ == "__main__":
    unittest.main()
