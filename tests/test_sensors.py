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
    "complexity",
    "dead-code-dependency",
    "semantic-data-flow",
    "browser",
    "accessibility",
    "mutation",
    "dependency-cruiser",
    "jscpd",
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
            "semantic-data-flow",
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


if __name__ == "__main__":
    unittest.main()
