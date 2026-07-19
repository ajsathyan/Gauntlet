#!/usr/bin/env python3
"""Black-box tests for the public adaptive-sensor CLI contracts."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from support import ROOT


GAUNTLET_CLI = ROOT / "scripts" / "gauntlet.py"
SENSOR_IDS = [
    "formatter",
    "type-checker",
    "linter",
    "focused-tests",
    "coverage",
    "complexity",
    "dead-code-dependency",
    "semgrep",
    "gitleaks",
    "browser",
    "accessibility",
    "dependency-cruiser",
    "jscpd",
    "mutation",
]


def run(args, *, cwd=None, check=True):
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        raise AssertionError(
            f"command failed ({result.returncode}): {args}\n{result.stdout}\n{result.stderr}"
        )
    return result


def git(repo, *args):
    return run(["git", *args], cwd=repo)


def init_repo(path):
    path.mkdir()
    git(path, "init", "-q")
    git(path, "config", "user.email", "gauntlet@example.test")
    git(path, "config", "user.name", "Gauntlet Test")


class SensorCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name) / "repo"
        init_repo(self.repo)

    def tearDown(self):
        self.temporary.cleanup()

    def cli(self, *args, check=True):
        return run(
            ["python3", str(GAUNTLET_CLI), "sensors", *args, "--json"],
            cwd=self.repo,
            check=check,
        )

    def plan(self, *args):
        result = self.cli(
            "plan",
            "--project-root",
            str(self.repo),
            *args,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(
            set(payload),
            {
                "schema",
                "status",
                "workflowMode",
                "projectRoot",
                "changedPaths",
                "facts",
                "sensors",
            },
        )
        self.assertEqual(payload["schema"], "gauntlet.sensor-plan/v1")
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["projectRoot"], str(self.repo.resolve()))
        self.assertEqual([entry["id"] for entry in payload["sensors"]], SENSOR_IDS)
        for entry in payload["sensors"]:
            self.assertIn(
                entry["disposition"],
                {"selected", "skipped", "not-configured", "unavailable"},
            )
            self.assertIsInstance(entry["reason"], str)
            self.assertTrue(entry["reason"].strip(), entry["id"])
            self.assertEqual(
                "command" in entry,
                entry["disposition"] == "selected",
                f"command exposure for {entry['id']}",
            )
        return payload

    @staticmethod
    def by_id(plan):
        return {entry["id"]: entry for entry in plan["sensors"]}

    def write_typescript_fixture(self, *, optional_dependencies=True):
        scripts = {
            f"check:{sensor}": f"fixture-tool {sensor}"
            for sensor in SENSOR_IDS
        }
        dev_dependencies = {
            "typescript": "0.0.0-fixture",
            "eslint": "0.0.0-fixture",
            "prettier": "0.0.0-fixture",
        }
        if optional_dependencies:
            dev_dependencies.update(
                {
                    "dependency-cruiser": "0.0.0-fixture",
                    "jscpd": "0.0.0-fixture",
                }
            )
        package = {
            "name": "sensor-fixture",
            "private": True,
            "scripts": scripts,
            "devDependencies": dev_dependencies,
        }
        (self.repo / "package.json").write_text(
            json.dumps(package, indent=2) + "\n",
            encoding="utf-8",
        )
        (self.repo / "package-lock.json").write_text(
            json.dumps(
                {
                    "name": "sensor-fixture",
                    "lockfileVersion": 3,
                    "packages": {"": {"devDependencies": dev_dependencies}},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        source = self.repo / "src"
        source.mkdir()
        (source / "app.ts").write_text("export const app = true;\n", encoding="utf-8")
        (source / "view.tsx").write_text(
            "export const View = () => <main>Ready</main>;\n",
            encoding="utf-8",
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "fixture")

    def configured_commands(self, *, include_optional=True):
        sensor_ids = SENSOR_IDS if include_optional else SENSOR_IDS[:-2]
        args = []
        for sensor in sensor_ids:
            args.extend(
                [
                    "--repo-command",
                    f"{sensor}=npm run check:{sensor}",
                ]
            )
        return args

    def test_plan_is_order_independent_and_scratch_requires_explicit_opt_in(self):
        self.write_typescript_fixture()
        common = [
            "--workflow-mode",
            "feature",
            "--app-surface",
            "--frontend-surface",
            "--architecture-change",
            "--durable-change",
            "--consequence",
            "authorization",
            *self.configured_commands(),
        ]
        forward = self.plan(
            *common,
            "--changed-path",
            "src/app.ts",
            "--changed-path",
            "src/view.tsx",
        )
        reverse = self.plan(
            *common,
            "--changed-path",
            "src/view.tsx",
            "--changed-path",
            "src/app.ts",
        )
        self.assertEqual(forward, reverse)
        self.assertEqual(forward["changedPaths"], ["src/app.ts", "src/view.tsx"])

        scratch = self.plan(
            "--workflow-mode",
            "scratch",
            "--changed-path",
            "src/app.ts",
            *self.configured_commands(),
        )
        self.assertFalse(
            [entry for entry in scratch["sensors"] if entry["disposition"] == "selected"]
        )
        requested = self.plan(
            "--workflow-mode",
            "scratch",
            "--changed-path",
            "src/app.ts",
            "--request-sensor",
            "linter",
            *self.configured_commands(),
        )
        self.assertEqual(self.by_id(requested)["linter"]["disposition"], "selected")
        self.assertTrue(
            all(
                entry["disposition"] != "selected" or entry["id"] == "linter"
                for entry in requested["sensors"]
            )
        )

    def test_typescript_app_routes_every_explained_sensor_branch(self):
        self.write_typescript_fixture()
        payload = self.plan(
            "--workflow-mode",
            "feature",
            "--changed-path",
            "src/app.ts",
            "--changed-path",
            "src/view.tsx",
            "--app-surface",
            "--frontend-surface",
            "--architecture-change",
            "--durable-change",
            "--consequence",
            "authentication",
            *self.configured_commands(),
        )
        sensors = self.by_id(payload)
        for sensor in [
            "formatter",
            "type-checker",
            "linter",
            "focused-tests",
            "coverage",
            "semgrep",
            "gitleaks",
            "browser",
            "accessibility",
            "mutation",
            "dependency-cruiser",
            "jscpd",
        ]:
            self.assertEqual(sensors[sensor]["disposition"], "selected", sensor)
        for sensor in ["complexity", "dead-code-dependency"]:
            self.assertIn(
                sensors[sensor]["disposition"],
                {"selected", "not-configured"},
                sensor,
            )

    def test_missing_optional_tools_are_explained_without_repository_mutation(self):
        self.write_typescript_fixture(optional_dependencies=False)
        package_before = (self.repo / "package.json").read_bytes()
        lock_before = (self.repo / "package-lock.json").read_bytes()
        status_before = git(self.repo, "status", "--porcelain=v1").stdout

        missing = self.plan(
            "--workflow-mode",
            "feature",
            "--changed-path",
            "src/app.ts",
            "--app-surface",
            "--architecture-change",
            "--durable-change",
            *self.configured_commands(include_optional=False),
        )
        sensors = self.by_id(missing)
        for sensor in ["dependency-cruiser", "jscpd"]:
            self.assertIn(
                sensors[sensor]["disposition"],
                {"not-configured", "unavailable"},
                sensor,
            )
            self.assertNotIn("command", sensors[sensor])

        self.assertEqual((self.repo / "package.json").read_bytes(), package_before)
        self.assertEqual((self.repo / "package-lock.json").read_bytes(), lock_before)
        self.assertEqual(git(self.repo, "status", "--porcelain=v1").stdout, status_before)

    def test_unsupported_repository_has_a_limitation_and_no_invented_command(self):
        (self.repo / "main.rb").write_text("puts 'ready'\n", encoding="utf-8")
        git(self.repo, "add", "main.rb")
        git(self.repo, "commit", "-qm", "unsupported fixture")
        payload = self.plan(
            "--workflow-mode",
            "patch",
            "--changed-path",
            "main.rb",
        )
        self.assertTrue(
            any(
                word in entry["reason"].lower()
                for entry in payload["sensors"]
                for word in ("unsupported", "limitation", "not configured")
            )
        )
        self.assertFalse(
            [entry for entry in payload["sensors"] if "command" in entry]
        )

    def test_normalize_keeps_raw_reference_without_copying_raw_output(self):
        raw_output = "SECRET_RAW_TOOL_OUTPUT"
        raw_path = self.repo / "artifacts" / "lint.txt"
        raw_path.parent.mkdir()
        raw_path.write_text(raw_output, encoding="utf-8")
        result = self.cli(
            "normalize",
            "--sensor",
            "linter",
            "--result",
            "fail",
            "--raw-evidence-ref",
            "artifacts/lint.txt",
            "--evidence-ref",
            "artifacts/lint-summary.json",
            "--command",
            "npm run lint",
            "--summary",
            "Two lint findings",
        )
        payload = json.loads(result.stdout)
        self.assertEqual(
            payload,
            {
                "schema": "gauntlet.sensor-result/v1",
                "status": "pass",
                "sensor": "linter",
                "result": "fail",
                "rawEvidenceRef": "artifacts/lint.txt",
                "evidenceRefs": ["artifacts/lint-summary.json"],
                "command": "npm run lint",
                "summary": "Two lint findings",
            },
        )
        self.assertNotIn(raw_output, result.stdout)

    def test_readability_requires_behavior_proof_not_metric_deltas(self):
        valid_receipt = {
            "schema": "gauntlet.readability-rewrite-evidence/v1",
            "finding": {"name": "split parser responsibilities"},
            "behaviorOracle": {
                "before": {
                    "identity": "parser-contract-v1",
                    "result": "pass",
                    "evidenceRefs": ["artifacts/before.json"],
                },
                "after": {
                    "identity": "parser-contract-v1",
                    "result": "pass",
                    "evidenceRefs": ["artifacts/after.json"],
                },
            },
            "structuralInspection": {
                "inspector": "reviewer@example.test",
                "summary": "Naming and ownership are clearer; effects are unchanged.",
                "evidenceRefs": ["artifacts/inspection.md"],
            },
            "metrics": {"complexity": {"before": 12, "after": 7}},
        }
        valid_path = self.repo / "valid-rewrite.json"
        valid_path.write_text(json.dumps(valid_receipt), encoding="utf-8")
        valid = json.loads(
            self.cli(
                "validate-rewrite",
                "--input",
                str(valid_path),
            ).stdout
        )
        self.assertEqual(set(valid), {"schema", "status", "valid", "findings"})
        self.assertEqual(valid["schema"], "gauntlet.readability-rewrite-evidence/v1")
        self.assertEqual(valid["status"], "pass")
        self.assertIs(valid["valid"], True)
        self.assertEqual(valid["findings"], [])

        metric_only = {
            "schema": "gauntlet.readability-rewrite-evidence/v1",
            "finding": {"name": "split parser responsibilities"},
            "metrics": {"complexity": {"before": 12, "after": 7}},
        }
        invalid_path = self.repo / "metric-only.json"
        invalid_path.write_text(json.dumps(metric_only), encoding="utf-8")
        invalid_result = self.cli(
            "validate-rewrite",
            "--input",
            str(invalid_path),
            check=False,
        )
        invalid = json.loads(invalid_result.stdout)
        self.assertNotEqual(invalid_result.returncode, 0)
        self.assertEqual(set(invalid), {"schema", "status", "valid", "findings"})
        self.assertEqual(invalid["schema"], "gauntlet.readability-rewrite-evidence/v1")
        self.assertEqual(invalid["status"], "fail")
        self.assertIs(invalid["valid"], False)
        self.assertTrue(invalid["findings"])

    def write_sensor_command(self):
        command = self.repo / "sensor-command.py"
        command.write_text(
            "\n".join(
                [
                    "import pathlib",
                    "import sys",
                    "sensor = sys.argv[1]",
                    "root = pathlib.Path.cwd()",
                    "output = root / '.gauntlet' / 'sensor-fixture'",
                    "output.mkdir(parents=True, exist_ok=True)",
                    "(output / f'{sensor}.executed').write_text('executed\\n')",
                    "cache = root / '__pycache__'",
                    "cache.mkdir(exist_ok=True)",
                    "(cache / 'sensor-fixture.pyc').write_bytes(b'generated')",
                    "failure = root / f'{sensor}.fail'",
                    "print(f'{sensor} concise output')",
                    "raise SystemExit(9 if failure.exists() else 0)",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return command

    def evidence_path(self, reference):
        prefix = "git:gauntlet-sensors/"
        if reference.startswith(prefix):
            git_path = git(
                self.repo,
                "rev-parse",
                "--git-path",
                "gauntlet-sensors",
            ).stdout.strip()
            root = Path(git_path)
            if not root.is_absolute():
                root = self.repo / root
            return root / reference[len(prefix) :]
        return Path(reference)

    def write_sensor_config(self, commands, *, required=None):
        required_ids = set(required or commands)
        rendered_commands = {}
        for sensor, command in commands.items():
            entry = dict(command) if isinstance(command, dict) else {"argv": command}
            entry.setdefault("required", sensor in required_ids)
            rendered_commands[sensor] = entry
        payload = {
            "schema": "gauntlet.sensor-config/v1",
            "commands": rendered_commands,
        }
        (self.repo / "gauntlet-sensors.json").write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )

    def run_sensors(self, *args, check=True):
        return self.cli(
            "run",
            "--project-root",
            str(self.repo),
            "--workflow-mode",
            "feature",
            *args,
            check=check,
        )

    def test_run_executes_selected_commands_and_returns_compact_handoff(self):
        command = self.write_sensor_command()
        self.write_sensor_config(
            {
                "linter": ["python3", str(command), "linter"],
                "focused-tests": ["python3", str(command), "tests"],
                "coverage": {
                    "argv": ["python3", str(command), "tests"],
                    "covers": ["focused-tests"],
                },
                "semgrep": ["python3", str(command), "semgrep"],
                "gitleaks": ["python3", str(command), "gitleaks"],
            }
        )
        source = self.repo / "app.py"
        source.write_text("print('ready')\n", encoding="utf-8")

        result = self.run_sensors()
        handoff = json.loads(result.stdout)

        self.assertEqual(handoff["schema"], "gauntlet.sensor-handoff/v1")
        self.assertEqual(handoff["status"], "pass")
        self.assertEqual(handoff["attention"], [])
        self.assertIn("linter", handoff["passed"])
        self.assertIn("coverage", handoff["passed"])
        self.assertIn("semgrep", handoff["passed"])
        self.assertIn("gitleaks", handoff["passed"])
        self.assertNotIn("focused-tests", handoff["passed"])
        self.assertNotIn("concise output", result.stdout)
        self.assertNotIn(str(self.repo), result.stdout)
        self.assertLess(len(result.stdout), 1600)
        fixture_output = self.repo / ".gauntlet" / "sensor-fixture"
        self.assertTrue((fixture_output / "linter.executed").is_file())
        self.assertTrue((fixture_output / "tests.executed").is_file())
        self.assertTrue((fixture_output / "semgrep.executed").is_file())
        self.assertTrue((fixture_output / "gitleaks.executed").is_file())

        evidence_path = self.evidence_path(handoff["evidenceRef"])
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.assertEqual(evidence["schema"], "gauntlet.sensor-evidence/v1")
        self.assertEqual(evidence["sourceFingerprint"], handoff["sourceFingerprint"])
        by_id = {item["sensor"]: item for item in evidence["results"]}
        self.assertEqual(by_id["linter"]["exitCode"], 0)
        self.assertEqual(by_id["linter"]["argv"][0], "python3")
        self.assertEqual(by_id["linter"]["cwd"], str(self.repo.resolve()))
        self.assertIn("rawOutputSha256", by_id["linter"])
        self.assertIn("rawLogRef", by_id["linter"])
        self.assertIn("durationMs", by_id["linter"])

    def test_failure_blocks_completion_then_repair_rerun_passes_and_stale_evidence_fails(self):
        command = self.write_sensor_command()
        self.write_sensor_config(
            {"linter": ["python3", str(command), "linter"]}
        )
        source = self.repo / "app.py"
        source.write_text("print('broken')\n", encoding="utf-8")
        (self.repo / "linter.fail").write_text("fail\n", encoding="utf-8")

        failed_result = self.run_sensors(check=False)
        failed = json.loads(failed_result.stdout)
        self.assertNotEqual(failed_result.returncode, 0)
        self.assertEqual(failed["status"], "fail")
        self.assertEqual([item["sensor"] for item in failed["attention"]], ["linter"])
        self.assertEqual(failed["attention"][0]["result"], "fail")
        self.assertLessEqual(
            len(failed["attention"][0]["summary"]),
            420,
        )

        old_evidence = self.evidence_path(failed["evidenceRef"])
        (self.repo / "linter.fail").unlink()
        source.write_text("print('repaired')\n", encoding="utf-8")

        stale = self.cli(
            "verify",
            "--project-root",
            str(self.repo),
            "--evidence",
            str(old_evidence),
            check=False,
        )
        stale_payload = json.loads(stale.stdout)
        self.assertNotEqual(stale.returncode, 0)
        self.assertEqual(stale_payload["status"], "fail")
        self.assertIn("stale", stale_payload["reason"].lower())

        passed_result = self.run_sensors()
        passed = json.loads(passed_result.stdout)
        self.assertEqual(passed["status"], "pass")
        self.assertNotEqual(
            passed["sourceFingerprint"],
            failed["sourceFingerprint"],
        )
        current = self.cli(
            "verify",
            "--project-root",
                str(self.repo),
                "--evidence",
                str(self.evidence_path(passed["evidenceRef"])),
        )
        self.assertEqual(json.loads(current.stdout)["status"], "pass")

    def test_verify_rejects_incomplete_private_evidence(self):
        command = self.write_sensor_command()
        self.write_sensor_config(
            {"linter": ["python3", str(command), "linter"]}
        )
        (self.repo / "app.py").write_text("print('ready')\n", encoding="utf-8")
        passed = json.loads(self.run_sensors().stdout)
        evidence_path = self.evidence_path(passed["evidenceRef"])
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["results"] = []
        evidence["verdict"] = "pass"
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

        result = self.cli(
            "verify",
            "--project-root",
            str(self.repo),
            "--evidence",
            str(evidence_path),
            check=False,
        )

        payload = json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(payload["status"], "fail")
        self.assertIn("incomplete", payload["reason"].lower())

    def test_deduplication_preserves_required_sensor_status(self):
        command = self.write_sensor_command()
        shared = ["python3", str(command), "shared"]
        self.write_sensor_config(
            {
                "formatter": shared,
                "linter": shared,
            },
            required=["linter"],
        )
        (self.repo / "app.py").write_text("print('broken')\n", encoding="utf-8")
        (self.repo / "shared.fail").write_text("fail\n", encoding="utf-8")

        result = self.run_sensors(check=False)
        handoff = json.loads(result.stdout)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(handoff["status"], "fail")
        self.assertEqual(
            handoff["attention"][0]["sensors"],
            ["formatter", "linter"],
        )
        evidence = json.loads(
            self.evidence_path(handoff["evidenceRef"]).read_text(encoding="utf-8")
        )
        self.assertEqual(len(evidence["results"]), 1)
        self.assertIs(evidence["results"][0]["required"], True)
        self.assertEqual(
            evidence["results"][0]["sensors"],
            ["formatter", "linter"],
        )

    def test_failure_handoff_excludes_output_and_caps_raw_log_while_running(self):
        command = self.repo / "noisy-sensor.py"
        command.write_text(
            "\n".join(
                [
                    "import sys",
                    "if '--version' in sys.argv:",
                    "    print('noisy fixture 1.0')",
                    "    raise SystemExit(0)",
                    "sys.stdout.write('x' * (3 * 1024 * 1024))",
                    "print('\\ntoken=TOPSECRET')",
                    "raise SystemExit(7)",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        self.write_sensor_config(
            {"linter": ["python3", str(command)]}
        )
        (self.repo / "app.py").write_text("print('broken')\n", encoding="utf-8")

        result = self.run_sensors(check=False)
        handoff = json.loads(result.stdout)

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("TOPSECRET", result.stdout)
        self.assertEqual(
            handoff["attention"][0]["summary"],
            "Exited with code 7; inspect the referenced raw log.",
        )
        evidence_path = self.evidence_path(handoff["evidenceRef"])
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        raw_path = evidence_path.parent / evidence["results"][0]["rawLogRef"]
        self.assertLessEqual(raw_path.stat().st_size, 2 * 1024 * 1024)
        self.assertIn(
            b"[Gauntlet truncated raw sensor output]",
            raw_path.read_bytes(),
        )

    def test_renamed_source_uses_current_destination_path(self):
        command = self.write_sensor_command()
        self.write_sensor_config(
            {"semgrep": ["python3", str(command), "semgrep"]}
        )
        old_path = self.repo / "old.py"
        old_path.write_text("print('old')\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "rename fixture")
        git(self.repo, "mv", "old.py", "new.py")

        handoff = json.loads(self.run_sensors().stdout)
        evidence = json.loads(
            self.evidence_path(handoff["evidenceRef"]).read_text(encoding="utf-8")
        )

        self.assertIn("new.py", evidence["changedPaths"])
        self.assertNotIn("old.py", evidence["changedPaths"])
        self.assertIn("semgrep", handoff["passed"])

    def test_run_derives_changed_paths_and_does_not_need_manual_sensor_flags(self):
        command = self.write_sensor_command()
        self.write_sensor_config(
            {
                "coverage": ["python3", str(command), "coverage"],
                "semgrep": ["python3", str(command), "semgrep"],
                "gitleaks": ["python3", str(command), "gitleaks"],
            }
        )
        source = self.repo / "service.py"
        source.write_text("def service():\n    return True\n", encoding="utf-8")

        payload = json.loads(self.run_sensors().stdout)

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(
            sorted(payload["passed"]),
            ["coverage", "gitleaks", "semgrep"],
        )
        evidence = json.loads(
            self.evidence_path(payload["evidenceRef"]).read_text(encoding="utf-8")
        )
        self.assertIn("service.py", evidence["changedPaths"])
        fixture_output = self.repo / ".gauntlet" / "sensor-fixture"
        self.assertTrue((fixture_output / "coverage.executed").is_file())
        self.assertTrue((fixture_output / "semgrep.executed").is_file())
        self.assertTrue((fixture_output / "gitleaks.executed").is_file())

    def test_completion_consumer_rejects_the_gauntlet_009_planner_only_wrong_case(self):
        router = (ROOT / "router" / "AGENTS.md").read_text(encoding="utf-8")
        implementer = (
            ROOT / "skills" / "implementer" / "SKILL.md"
        ).read_text(encoding="utf-8")
        documentation = (
            ROOT / "docs" / "code-quality-sensors.md"
        ).read_text(encoding="utf-8")
        repository_config = json.loads(
            (ROOT / "gauntlet-sensors.json").read_text(encoding="utf-8")
        )
        for value in (router, implementer):
            self.assertIn("sensors run", value)
            self.assertIn("completion", value)
            self.assertIn("block", value)
        self.assertIn("executes", documentation)
        self.assertIn("A sensor plan or normalized result without execution is not proof", router)
        self.assertNotIn("does not install tools, change dependencies, or run", documentation)
        self.assertIn(
            "--no-project",
            repository_config["commands"]["linter"]["argv"],
        )


if __name__ == "__main__":
    unittest.main()
