#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_INTEGRITY = SCRIPT_DIR / "source_integrity.py"
MEASURE_LOC = SCRIPT_DIR / "measure_loc.py"
VALIDATE_LEDGER = SCRIPT_DIR / "validate_parity_ledger.py"


def run_script(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        check=False,
        capture_output=True,
        text=True,
    )


class SourceIntegrityTests(unittest.TestCase):
    def test_snapshot_and_compare_detect_tracked_content_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / "app.py").write_text("print('one')\n", encoding="utf-8")
            os.symlink("app.py", root / "current.py")
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "initial"], check=True)

            snapshot_path = Path(temporary) / "snapshot.json"
            snapshot = run_script(SOURCE_INTEGRITY, "snapshot", str(root), "--output", str(snapshot_path))
            self.assertEqual(snapshot.returncode, 0, snapshot.stderr)
            payload = json.loads(snapshot.stdout)
            self.assertEqual(payload["schemaVersion"], 1)
            self.assertEqual([entry["path"] for entry in payload["trackedFiles"]], ["app.py", "current.py"])

            matching = run_script(SOURCE_INTEGRITY, "compare", str(root), str(snapshot_path))
            self.assertEqual(matching.returncode, 0, matching.stdout)
            self.assertTrue(json.loads(matching.stdout)["match"])

            (root / "app.py").write_text("print('two')\n", encoding="utf-8")
            changed = run_script(SOURCE_INTEGRITY, "compare", str(root), str(snapshot_path))
            self.assertEqual(changed.returncode, 1)
            report = json.loads(changed.stdout)
            self.assertFalse(report["match"])
            self.assertIn("trackedFiles", report["changedFields"])

    def test_output_inside_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            result = run_script(SOURCE_INTEGRITY, "snapshot", str(root), "--output", str(root / "snapshot.json"))
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["error"]["code"], "output-inside-source")


class MeasureLocTests(unittest.TestCase):
    def test_categories_and_comparison_use_the_same_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            (root / "src").mkdir(parents=True)
            (root / "tests" / "fixtures").mkdir(parents=True)
            (root / "migrations").mkdir()
            (root / "generated").mkdir()
            (root / ".next" / "server").mkdir(parents=True)
            (root / ".gauntlet").mkdir()
            (root / "evals" / "results").mkdir(parents=True)
            (root / "src" / "app.py").write_text("x = 1\n\ny = 2\n", encoding="utf-8")
            (root / "tests" / "test_app.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
            (root / "tests" / "fixtures" / "case.json").write_text('{"x": 1}\n', encoding="utf-8")
            (root / "migrations" / "001.sql").write_text("select 1;\n", encoding="utf-8")
            (root / "generated" / "client.ts").write_text("export {};\n", encoding="utf-8")
            (root / ".next" / "server" / "bundle.js").write_text("generated();\n", encoding="utf-8")
            (root / ".gauntlet" / "state.json").write_text('{"state": true}\n', encoding="utf-8")
            (root / "evals" / "results" / "latest.json").write_text('{"pass": true}\n', encoding="utf-8")
            (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
            (root / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")

            first_path = Path(temporary) / "first.json"
            first = run_script(MEASURE_LOC, "measure", str(root), "--output", str(first_path))
            self.assertEqual(first.returncode, 0, first.stderr)
            payload = json.loads(first.stdout)
            self.assertEqual(payload["categories"]["production"]["nonblankLines"], 2)
            self.assertEqual(payload["categories"]["test"]["nonblankLines"], 2)
            self.assertEqual(payload["categories"]["fixture"]["files"], 1)
            self.assertEqual(payload["categories"]["migration"]["files"], 1)
            self.assertEqual(payload["categories"]["generated"]["files"], 4)
            self.assertEqual(payload["categories"]["config"]["files"], 2)

            second_path = Path(temporary) / "second.json"
            (root / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
            second = run_script(MEASURE_LOC, "measure", str(root), "--output", str(second_path))
            self.assertEqual(second.returncode, 0, second.stderr)
            compared = run_script(MEASURE_LOC, "compare", str(first_path), str(second_path))
            self.assertEqual(compared.returncode, 0, compared.stdout)
            self.assertAlmostEqual(json.loads(compared.stdout)["productionTestReductionPercent"], 25.0)

    def test_comparison_refuses_different_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            (root / "app.py").write_text("x = 1\n", encoding="utf-8")
            baseline = Path(temporary) / "baseline.json"
            current = Path(temporary) / "current.json"
            self.assertEqual(run_script(MEASURE_LOC, "measure", str(root), "--output", str(baseline)).returncode, 0)
            rules = Path(temporary) / "rules.json"
            default_payload = json.loads(baseline.read_text(encoding="utf-8"))
            custom_rules = default_payload["rules"]
            custom_rules["extensions"].append(".xyz")
            rules.write_text(json.dumps(custom_rules), encoding="utf-8")
            self.assertEqual(
                run_script(MEASURE_LOC, "measure", str(root), "--rules", str(rules), "--output", str(current)).returncode,
                0,
            )
            compared = run_script(MEASURE_LOC, "compare", str(baseline), str(current))
            self.assertEqual(compared.returncode, 1)
            self.assertFalse(json.loads(compared.stdout)["comparable"])


class ParityLedgerTests(unittest.TestCase):
    def complete_ledger(self) -> dict:
        return {
            "schemaVersion": 1,
            "inventoryAreas": [
                {"id": "routes", "title": "Routes", "status": "resolved", "evidence": ["router.ts"]}
            ],
            "rows": [
                {
                    "id": "route-home",
                    "inventoryArea": "routes",
                    "kind": "route",
                    "name": "Home",
                    "disposition": "preserve",
                    "baselineEvidence": ["GET /"],
                    "result": "pass",
                    "parityEvidence": ["route test"],
                }
            ],
        }

    def test_complete_ledger_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ledger.json"
            path.write_text(json.dumps(self.complete_ledger()), encoding="utf-8")
            result = run_script(VALIDATE_LEDGER, str(path))
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(json.loads(result.stdout)["valid"])

    def test_unresolved_area_and_pending_row_fail_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ledger = self.complete_ledger()
            ledger["inventoryAreas"][0]["status"] = "unresolved"
            ledger["rows"][0]["result"] = "pending"
            ledger["rows"][0]["parityEvidence"] = []
            path = Path(temporary) / "ledger.json"
            path.write_text(json.dumps(ledger), encoding="utf-8")
            result = run_script(VALIDATE_LEDGER, str(path))
            self.assertEqual(result.returncode, 1)
            codes = {issue["code"] for issue in json.loads(result.stdout)["issues"]}
            self.assertIn("unresolved-inventory-area", codes)
            self.assertIn("incomplete-row", codes)

            draft = run_script(VALIDATE_LEDGER, str(path), "--allow-incomplete")
            self.assertEqual(draft.returncode, 0, draft.stdout)

    def test_remove_feature_disposition_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ledger = self.complete_ledger()
            ledger["rows"][0]["disposition"] = "remove-feature"
            path = Path(temporary) / "ledger.json"
            path.write_text(json.dumps(ledger), encoding="utf-8")
            result = run_script(VALIDATE_LEDGER, str(path))
            self.assertEqual(result.returncode, 1)
            self.assertIn("invalid-disposition", {issue["code"] for issue in json.loads(result.stdout)["issues"]})


if __name__ == "__main__":
    unittest.main()
