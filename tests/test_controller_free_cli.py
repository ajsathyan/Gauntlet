import copy
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

try:
    from tests.support import ROOT
except ModuleNotFoundError:
    from support import ROOT
from gauntletlib.contracts.handoff import validate_merge_handoff


CLI = ROOT / "scripts" / "gauntlet.py"


def run_cli(*arguments, cwd=ROOT, env=None):
    return subprocess.run(
        ["python3", str(CLI), *arguments],
        cwd=cwd,
        env={**os.environ, **(env or {})},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def valid_handoff():
    binding = {
        "repository": "/tmp/repo",
        "commit": "1" * 40,
        "tree": "2" * 40,
        "base": "3" * 40,
    }
    return {
        "schemaVersion": "1.0",
        "title": "workflow: simplify Gauntlet",
        "problem": {"context": "The workflow is costly.", "impact": "Routine work pays ceremony."},
        "solution": {
            "outcome": "Retain a compact behavior-first workflow.",
            "invariants": ["Personal skills remain available."],
            "preserved": ["Established PR format."],
            "nonGoals": ["Merge queues."],
        },
        "changelog": "Simplify Gauntlet around behavior-first proof.",
        "testing": [{"command": "python3 scripts/check-gauntlet-workflow.py", "result": "pass", "proves": "Supported workflow checks pass."}],
        "securityRisk": None,
        "sourceBinding": binding,
        "verification": {
            "build": "Passed",
            "architecture": "Not applicable",
            "sourceBinding": dict(binding),
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

    def test_landing_verdicts_are_required_and_must_pass(self):
        missing = valid_handoff()
        missing.pop("verification")
        missing_codes = {item["code"] for item in validate_merge_handoff(missing)}
        self.assertIn("missing_handoff_field", missing_codes)
        self.assertIn("invalid_verification", missing_codes)

        for field, verdict in (("build", "Failed"), ("architecture", "Blocked")):
            with self.subTest(field=field, verdict=verdict):
                value = valid_handoff()
                value["verification"][field] = verdict
                codes = {item["code"] for item in validate_merge_handoff(value)}
                self.assertIn("unacceptable_verification_verdict", codes)

        malformed = valid_handoff()
        malformed["verification"]["build"] = []
        codes = {item["code"] for item in validate_merge_handoff(malformed)}
        self.assertIn("invalid_verification_verdict", codes)

    def test_prepare_does_not_require_verdicts_or_create_a_changelog(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._repository_fixture(Path(directory))
            handoff = valid_handoff()
            handoff["sourceBinding"] = fixture["binding"]
            handoff.pop("verification")
            fixture["handoff"].write_text(json.dumps(handoff), encoding="utf-8")

            result = run_cli(
                "merge",
                "prepare",
                "--git-root",
                str(fixture["repo"]),
                "--handoff",
                str(fixture["handoff"]),
                "--body-output",
                str(fixture["body"]),
                "--json",
                env=fixture["env"],
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(fixture["body"].is_file())
            self.assertFalse((fixture["repo"] / "CHANGELOG.md").exists())
            payload = json.loads(result.stdout)
            self.assertNotIn("changelogPath", payload)
            self.assertNotIn("changelogChanged", payload)

    def test_public_execute_rejects_stale_verification_before_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._repository_fixture(Path(directory))
            base_handoff = valid_handoff()
            base_handoff["sourceBinding"] = fixture["binding"]
            base_handoff["verification"]["sourceBinding"] = dict(
                fixture["binding"]
            )
            fixture["handoff"].write_text(
                json.dumps(base_handoff), encoding="utf-8"
            )
            prepared = run_cli(
                "merge",
                "prepare",
                "--git-root",
                str(fixture["repo"]),
                "--handoff",
                str(fixture["handoff"]),
                "--body-output",
                str(fixture["body"]),
                "--json",
                env=fixture["env"],
            )
            self.assertEqual(prepared.returncode, 0, prepared.stderr)

            for field in ("commit", "tree", "base"):
                with self.subTest(field=field):
                    stale = copy.deepcopy(base_handoff)
                    stale["verification"]["sourceBinding"][field] = "f" * 40
                    fixture["handoff"].write_text(
                        json.dumps(stale), encoding="utf-8"
                    )
                    result = run_cli(
                        "merge",
                        "execute",
                        "--git-root",
                        str(fixture["repo"]),
                        "--handoff",
                        str(fixture["handoff"]),
                        "--body",
                        str(fixture["body"]),
                        "--json",
                        env=fixture["env"],
                    )
                    self.assertNotEqual(result.returncode, 0)
                    codes = {
                        finding["code"]
                        for finding in json.loads(result.stdout)["findings"]
                    }
                    self.assertIn("verification_binding_drift", codes)

            logged = [
                json.loads(line)
                for line in fixture["gh_log"].read_text(encoding="utf-8").splitlines()
            ]
            self.assertFalse(any(args and args[0] == "pr" for args in logged))
            remote_task = subprocess.run(
                ["git", "ls-remote", "--heads", str(fixture["remote"]), "task"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(remote_task.returncode, 0, remote_task.stderr)
            self.assertEqual(remote_task.stdout, "")

    def _repository_fixture(self, directory):
        remote = directory / "github.com" / "owner" / "repo"
        repo = directory / "repo"
        remote.parent.mkdir(parents=True)
        subprocess.run(
            ["git", "init", "--bare", "--initial-branch=main", str(remote)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "init", "-b", "main", str(repo)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"], cwd=repo, check=True
        )
        (repo / "file.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "base"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "remote", "add", "origin", str(remote)],
            cwd=repo,
            check=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "main"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        base = self._git_output(repo, "rev-parse", "HEAD")
        subprocess.run(
            ["git", "switch", "-c", "task"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        (repo / "file.txt").write_text("candidate\n", encoding="utf-8")
        subprocess.run(
            ["git", "commit", "-am", "candidate"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git",
                "remote",
                "set-url",
                "origin",
                f"file://{remote}",
            ],
            cwd=repo,
            check=True,
        )
        gh_log = directory / "gh.log"
        fake_gh = directory / "fake-gh"
        fake_gh.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            f"log = {str(gh_log)!r}\n"
            "args = sys.argv[1:]\n"
            "with open(log, 'a', encoding='utf-8') as stream:\n"
            "    stream.write(json.dumps(args) + '\\n')\n"
            "if 'viewerPermission' in args:\n"
            "    print(json.dumps({'viewerPermission': 'WRITE'}))\n"
            "else:\n"
            "    print(json.dumps({'nameWithOwner': 'owner/repo', "
            "'defaultBranchRef': {'name': 'main'}}))\n",
            encoding="utf-8",
        )
        fake_gh.chmod(0o755)
        binding = {
            "repository": str(repo.resolve()),
            "commit": self._git_output(repo, "rev-parse", "HEAD"),
            "tree": self._git_output(repo, "rev-parse", "HEAD^{tree}"),
            "base": base,
        }
        return {
            "repo": repo,
            "remote": remote,
            "handoff": directory / "handoff.json",
            "body": directory / "pr-body.md",
            "gh_log": gh_log,
            "binding": binding,
            "env": {
                "GAUNTLET_GH": str(fake_gh),
                "GIT_ALLOW_PROTOCOL": "file",
            },
        }

    @staticmethod
    def _git_output(repo, *arguments):
        return subprocess.run(
            ["git", *arguments],
            cwd=repo,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()

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
