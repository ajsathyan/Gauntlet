#!/usr/bin/env python3
"""Focused proof for fast and integrated sensor phases."""

import argparse
import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from support import ROOT

from gauntletlib.sensors import register as register_sensors



def run(arguments, *, cwd, check=True):
    result = subprocess.run(
        arguments,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        raise AssertionError(
            f"command failed ({result.returncode}): {arguments}\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return result


class SensorCadenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name) / "repo"
        self.repo.mkdir()
        run(["git", "init", "-q"], cwd=self.repo)
        run(
            ["git", "config", "user.email", "gauntlet@example.test"],
            cwd=self.repo,
        )
        run(["git", "config", "user.name", "Gauntlet Test"], cwd=self.repo)
        self.command = self.repo / "sensor.py"
        self.command.write_text(
            "\n".join(
                [
                    "import pathlib",
                    "import sys",
                    "name = sys.argv[1]",
                    "suite = sys.argv[2] if len(sys.argv) > 2 else 'none'",
                    "root = pathlib.Path.cwd()",
                    "output = root / '.gauntlet' / 'sensor-cadence'",
                    "output.mkdir(parents=True, exist_ok=True)",
                    "(output / f'{name}-{suite}.ran').write_text('ran\\n')",
                    "raise SystemExit(7 if (root / f'{name}.fail').exists() else 0)",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (self.repo / "app.py").write_text("print('ready')\n", encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def cli(self, command, *arguments, check=True):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="family", required=True)
        register_sensors(subparsers)
        args = parser.parse_args(
            [
                "sensors",
                command,
                "--project-root",
                str(self.repo),
                *arguments,
                "--json",
            ]
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            returncode = args.func(args)
        result = SimpleNamespace(
            returncode=returncode,
            stdout=stdout.getvalue(),
            stderr=stderr.getvalue(),
        )
        if check and returncode:
            raise AssertionError(
                f"sensor command failed ({returncode})\n"
                f"{result.stdout}\n{result.stderr}"
            )
        return result

    def write_config(self):
        config = {
            "schema": "gauntlet.sensor-config/v1",
            "commands": {
                "linter": {
                    "argv": ["python3", str(self.command), "linter"],
                    "phases": ["fast", "integrated"],
                    "required": True,
                },
                "coverage": {
                    "argv": [
                        "python3",
                        str(self.command),
                        "coverage",
                        "{suite}",
                    ],
                    "phases": ["fast", "integrated"],
                    "required": True,
                },
                "semgrep": {
                    "argv": ["python3", str(self.command), "semgrep"],
                    "required": True,
                },
            },
        }
        (self.repo / "gauntlet-sensors.json").write_text(
            json.dumps(config, indent=2) + "\n",
            encoding="utf-8",
        )

    def evidence_path(self, reference):
        prefix = "git:gauntlet-sensors/"
        self.assertTrue(reference.startswith(prefix))
        git_path = run(
            ["git", "rev-parse", "--git-path", "gauntlet-sensors"],
            cwd=self.repo,
        ).stdout.strip()
        root = Path(git_path)
        if not root.is_absolute():
            root = self.repo / root
        return root / reference.removeprefix(prefix)

    def test_default_is_integrated_and_fast_uses_only_fast_commands(self):
        self.write_config()

        default = json.loads(
            self.cli("run", "--workflow-mode", "feature").stdout
        )
        default_evidence = json.loads(
            self.evidence_path(default["evidenceRef"]).read_text(encoding="utf-8")
        )
        self.assertEqual(default["proofPhase"], "integrated")
        self.assertEqual(default_evidence["proofPhase"], "integrated")
        integrated_argv = {
            result["sensor"]: result["argv"]
            for result in default_evidence["results"]
        }
        self.assertEqual(integrated_argv["coverage"][-1], "full")
        self.assertIn("semgrep", integrated_argv)

        fast = json.loads(
            self.cli(
                "run",
                "--workflow-mode",
                "feature",
                "--phase",
                "fast",
            ).stdout
        )
        fast_evidence_path = self.evidence_path(fast["evidenceRef"])
        fast_evidence = json.loads(fast_evidence_path.read_text(encoding="utf-8"))
        fast_argv = {
            result["sensor"]: result["argv"]
            for result in fast_evidence["results"]
        }
        self.assertEqual(fast["proofPhase"], "fast")
        self.assertEqual(fast_evidence["proofPhase"], "fast")
        self.assertNotEqual(
            fast["sourceFingerprint"],
            default["sourceFingerprint"],
        )
        self.assertNotEqual(
            fast_evidence["planFingerprint"],
            default_evidence["planFingerprint"],
        )
        self.assertEqual(fast_argv["coverage"][-1], "smoke")
        self.assertEqual(set(fast_argv), {"coverage", "linter"})
        self.assertNotIn("argv", fast)
        self.assertNotIn("raw output", json.dumps(fast).lower())

        mismatch = self.cli(
            "verify",
            "--evidence",
            str(fast_evidence_path),
            check=False,
        )
        mismatch_payload = json.loads(mismatch.stdout)
        self.assertNotEqual(mismatch.returncode, 0)
        self.assertEqual(mismatch_payload["status"], "fail")
        self.assertIn("phase", mismatch_payload["reason"].lower())

        matching = json.loads(
            self.cli(
                "verify",
                "--phase",
                "fast",
                "--evidence",
                str(fast_evidence_path),
            ).stdout
        )
        self.assertEqual(matching["status"], "pass")

    def test_phase_is_in_plan_and_required_fast_failure_blocks(self):
        self.write_config()
        plan = json.loads(
            self.cli(
                "plan",
                "--workflow-mode",
                "patch",
                "--phase",
                "fast",
                "--changed-path",
                "app.py",
                "--repo-command",
                "linter=python3 lint.py",
                "--app-surface",
                "--durable-change",
            ).stdout
        )
        self.assertEqual(plan["facts"]["proofPhase"], "fast")

        (self.repo / "linter.fail").write_text("fail\n", encoding="utf-8")
        failed = self.cli(
            "run",
            "--workflow-mode",
            "feature",
            "--phase",
            "fast",
            check=False,
        )
        handoff = json.loads(failed.stdout)
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(handoff["status"], "fail")
        self.assertEqual(handoff["attention"][0]["sensor"], "linter")

        config_path = self.repo / "gauntlet-sensors.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["commands"]["linter"]["argv"] = ["missing-sensor-executable"]
        config_path.write_text(json.dumps(config), encoding="utf-8")
        (self.repo / "linter.fail").unlink()
        unavailable = self.cli(
            "run",
            "--workflow-mode",
            "feature",
            "--phase",
            "fast",
            check=False,
        )
        unavailable_handoff = json.loads(unavailable.stdout)
        self.assertNotEqual(unavailable.returncode, 0)
        self.assertEqual(unavailable_handoff["status"], "fail")
        self.assertEqual(
            unavailable_handoff["attention"][0]["result"],
            "unavailable",
        )

    def test_required_not_run_and_incomplete_evidence_are_rejected(self):
        self.write_config()
        passed = json.loads(
            self.cli(
                "run",
                "--workflow-mode",
                "feature",
                "--phase",
                "fast",
            ).stdout
        )
        evidence_path = self.evidence_path(passed["evidenceRef"])
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["results"][0]["result"] = "not-run"
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
        not_run = self.cli(
            "verify",
            "--phase",
            "fast",
            "--evidence",
            str(evidence_path),
            check=False,
        )
        self.assertNotEqual(not_run.returncode, 0)

        evidence["results"] = []
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
        incomplete = self.cli(
            "verify",
            "--phase",
            "fast",
            "--evidence",
            str(evidence_path),
            check=False,
        )
        self.assertNotEqual(incomplete.returncode, 0)
        self.assertIn("incomplete", json.loads(incomplete.stdout)["reason"].lower())

    def test_coverage_wrapper_routes_smoke_and_defaults_to_full(self):
        bin_dir = self.repo / "bin"
        bin_dir.mkdir()
        capture = self.repo / "coverage-arguments.jsonl"
        coverage = bin_dir / "coverage"
        coverage.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json",
                    "import os",
                    "import sys",
                    "with open(os.environ['COVERAGE_CAPTURE'], 'a') as output:",
                    "    output.write(json.dumps(sys.argv[1:]) + '\\n')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        coverage.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
        env["COVERAGE_CAPTURE"] = str(capture)

        for arguments in ([], ["--suite", "full"], ["--suite", "smoke"]):
            result = subprocess.run(
                [
                    "python3",
                    str(ROOT / "scripts" / "run-coverage-sensor.py"),
                    *arguments,
                ],
                cwd=self.repo,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

        calls = [
            json.loads(line)
            for line in capture.read_text(encoding="utf-8").splitlines()
        ]
        measured = [call for call in calls if call and call[0] == "run"]
        self.assertEqual(len(measured), 3)
        self.assertNotIn("--smoke", measured[0])
        self.assertNotIn("--smoke", measured[1])
        self.assertEqual(measured[2][-1], "--smoke")


if __name__ == "__main__":
    unittest.main()
