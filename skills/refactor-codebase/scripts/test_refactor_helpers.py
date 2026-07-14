#!/usr/bin/env python3
import json
import os
from pathlib import Path
import shutil
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
            self.assertEqual(payload["schemaVersion"], 2)
            self.assertEqual(len(payload["trackedFiles"]), 2)
            self.assertTrue(all("pathToken" in entry and "path" not in entry for entry in payload["trackedFiles"]))

            matching = run_script(SOURCE_INTEGRITY, "compare", str(root), str(snapshot_path))
            self.assertEqual(matching.returncode, 0, matching.stdout)
            self.assertTrue(json.loads(matching.stdout)["match"])

            (root / "app.py").write_text("print('two')\n", encoding="utf-8")
            changed = run_script(SOURCE_INTEGRITY, "compare", str(root), str(snapshot_path))
            self.assertEqual(changed.returncode, 1)
            report = json.loads(changed.stdout)
            self.assertFalse(report["match"])
            self.assertIn("trackedFiles", report["changedFields"])

    def test_snapshot_detects_untracked_content_addition_and_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            untracked = root / "runtime.json"
            untracked.write_text("one\n", encoding="utf-8")
            snapshot_path = Path(temporary) / "snapshot.json"
            self.assertEqual(
                run_script(SOURCE_INTEGRITY, "snapshot", str(root), "--output", str(snapshot_path)).returncode,
                0,
            )

            untracked.write_text("two\n", encoding="utf-8")
            changed = run_script(SOURCE_INTEGRITY, "compare", str(root), str(snapshot_path))
            self.assertEqual(changed.returncode, 1, changed.stdout)
            self.assertIn("untrackedFiles", json.loads(changed.stdout)["changedFields"])

            untracked.write_text("one\n", encoding="utf-8")
            (root / "added.txt").write_text("added\n", encoding="utf-8")
            added = run_script(SOURCE_INTEGRITY, "compare", str(root), str(snapshot_path))
            self.assertEqual(added.returncode, 1, added.stdout)

            (root / "added.txt").unlink()
            untracked.unlink()
            deleted = run_script(SOURCE_INTEGRITY, "compare", str(root), str(snapshot_path))
            self.assertEqual(deleted.returncode, 1, deleted.stdout)

    def test_snapshot_detects_untracked_symlink_target_and_file_type_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            entry = root / "current"
            os.symlink("first-target", entry)
            snapshot_path = Path(temporary) / "snapshot.json"
            self.assertEqual(
                run_script(SOURCE_INTEGRITY, "snapshot", str(root), "--output", str(snapshot_path)).returncode,
                0,
            )

            entry.unlink()
            os.symlink("second-target", entry)
            changed_target = run_script(SOURCE_INTEGRITY, "compare", str(root), str(snapshot_path))
            self.assertEqual(changed_target.returncode, 1, changed_target.stdout)

            entry.unlink()
            entry.write_text("first-target", encoding="utf-8")
            changed_type = run_script(SOURCE_INTEGRITY, "compare", str(root), str(snapshot_path))
            self.assertEqual(changed_type.returncode, 1, changed_type.stdout)

    def test_publishable_snapshot_omits_raw_local_paths_and_symlink_targets(self) -> None:
        with tempfile.TemporaryDirectory(prefix="private-home-segment-") as temporary:
            root = Path(temporary) / "sensitive-source-name"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "secret-filename.env").write_text("value\n", encoding="utf-8")
            os.symlink("/Users/private-user/private-target", root / "private-link-name")

            result = run_script(SOURCE_INTEGRITY, "snapshot", str(root))
            self.assertEqual(result.returncode, 0, result.stdout)
            serialized = result.stdout
            for sensitive_value in (
                str(root),
                "private-home-segment-",
                "sensitive-source-name",
                "secret-filename.env",
                "private-link-name",
                "/Users/private-user/private-target",
            ):
                self.assertNotIn(sensitive_value, serialized)

    def test_dirty_submodule_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            child = Path(temporary) / "child"
            child.mkdir()
            subprocess.run(["git", "init", "-q", str(child)], check=True)
            subprocess.run(["git", "-C", str(child), "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", str(child), "config", "user.name", "Test"], check=True)
            (child / "child.txt").write_text("one\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(child), "add", "."], check=True)
            subprocess.run(["git", "-C", str(child), "commit", "-qm", "initial"], check=True)

            root = Path(temporary) / "source"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            subprocess.run(
                ["git", "-c", "protocol.file.allow=always", "-C", str(root), "submodule", "add", "-q", str(child), "module"],
                check=True,
            )
            subprocess.run(["git", "-C", str(root), "commit", "-qam", "submodule"], check=True)
            (root / "module" / "child.txt").write_text("two\n", encoding="utf-8")

            result = run_script(SOURCE_INTEGRITY, "snapshot", str(root))
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertEqual(json.loads(result.stdout)["error"]["code"], "dirty-submodule-unsupported")

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
            self.assertEqual(payload["categories"]["generated"]["files"], 3)
            self.assertEqual(payload["categories"]["config"]["files"], 2)

            current_root = Path(temporary) / "current"
            shutil.copytree(root, current_root)
            second_path = Path(temporary) / "second.json"
            (current_root / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
            second = run_script(MEASURE_LOC, "measure", str(current_root), "--output", str(second_path))
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

    def test_comparison_blocks_category_transfer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            baseline_root = Path(temporary) / "baseline-root"
            current_root = Path(temporary) / "current-root"
            (baseline_root / "src").mkdir(parents=True)
            (current_root / "generated").mkdir(parents=True)
            (baseline_root / "src" / "core.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
            (current_root / "generated" / "core.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
            baseline = Path(temporary) / "baseline.json"
            current = Path(temporary) / "current.json"
            self.assertEqual(run_script(MEASURE_LOC, "measure", str(baseline_root), "--output", str(baseline)).returncode, 0)
            self.assertEqual(run_script(MEASURE_LOC, "measure", str(current_root), "--output", str(current)).returncode, 0)
            result = run_script(MEASURE_LOC, "compare", str(baseline), str(current))
            self.assertEqual(result.returncode, 1, result.stdout)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["displacedComplexity"])
            self.assertEqual(payload["categoryNonblankLineDeltas"]["generated"], 2)

    def test_comparison_rejects_fabricated_or_stale_measurements(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            root.mkdir()
            (root / "app.py").write_text("x = 1\n", encoding="utf-8")
            good = Path(temporary) / "good.json"
            self.assertEqual(run_script(MEASURE_LOC, "measure", str(root), "--output", str(good)).returncode, 0)
            original = json.loads(good.read_text(encoding="utf-8"))
            mutations = []
            fabricated = json.loads(json.dumps(original))
            fabricated["productionTestNonblankLines"] = 0
            mutations.append(fabricated)
            retained_hash = json.loads(json.dumps(original))
            retained_hash["rules"]["extensions"].append(".madeup")
            mutations.append(retained_hash)
            negative = json.loads(json.dumps(original))
            negative["categories"]["production"]["nonblankLines"] = -1
            mutations.append(negative)
            boolean = json.loads(json.dumps(original))
            boolean["allMeasuredNonblankLines"] = True
            mutations.append(boolean)
            for index, mutation in enumerate(mutations):
                bad = Path(temporary) / f"bad-{index}.json"
                bad.write_text(json.dumps(mutation), encoding="utf-8")
                self.assertEqual(run_script(MEASURE_LOC, "compare", str(bad), str(good)).returncode, 2)
            (root / "app.py").write_text("x = 2\n", encoding="utf-8")
            stale = run_script(MEASURE_LOC, "compare", str(good), str(good), "--verify-live")
            self.assertEqual(stale.returncode, 2)
            self.assertEqual(json.loads(stale.stdout)["error"]["code"], "stale-measurement")

    def test_offline_receipts_and_repository_local_output_remain_comparable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            root.mkdir()
            (root / "app.py").write_text("x = 1\n", encoding="utf-8")
            receipt = root / ".gauntlet" / "loc.json"
            measured = run_script(MEASURE_LOC, "measure", str(root), "--output", str(receipt))
            self.assertEqual(measured.returncode, 0, measured.stdout)
            self.assertEqual(run_script(MEASURE_LOC, "compare", str(receipt), str(receipt), "--verify-live").returncode, 0)
            saved = Path(temporary) / "saved.json"
            shutil.copy2(receipt, saved)
            shutil.rmtree(root)
            self.assertEqual(run_script(MEASURE_LOC, "compare", str(saved), str(saved)).returncode, 0)
            self.assertEqual(run_script(MEASURE_LOC, "compare", str(saved), str(saved), "--verify-live").returncode, 2)

    def test_comparison_blocks_vendor_and_unmeasured_extension_transfer(self) -> None:
        for destination in (Path("vendor/core.py"), Path("assets/core.txt")):
            with self.subTest(destination=str(destination)), tempfile.TemporaryDirectory() as temporary:
                baseline_root = Path(temporary) / "baseline-root"
                current_root = Path(temporary) / "current-root"
                (baseline_root / "src").mkdir(parents=True)
                (current_root / destination.parent).mkdir(parents=True)
                content = "x = 1\ny = 2\n"
                (baseline_root / "src" / "core.py").write_text(content, encoding="utf-8")
                (current_root / destination).write_text(content, encoding="utf-8")
                baseline = Path(temporary) / "baseline.json"
                current = Path(temporary) / "current.json"
                self.assertEqual(run_script(MEASURE_LOC, "measure", str(baseline_root), "--output", str(baseline)).returncode, 0)
                self.assertEqual(run_script(MEASURE_LOC, "measure", str(current_root), "--output", str(current)).returncode, 0)
                result = run_script(MEASURE_LOC, "compare", str(baseline), str(current))
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertTrue(json.loads(result.stdout)["excludedInventoryChanged"])


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

    def test_complete_ledger_rejects_each_empty_evidence_array(self) -> None:
        cases = (
            ("area", lambda ledger: ledger["inventoryAreas"][0].update(evidence=[]), "invalid-area-evidence"),
            ("baseline", lambda ledger: ledger["rows"][0].update(baselineEvidence=[]), "invalid-baseline-evidence"),
            ("parity", lambda ledger: ledger["rows"][0].update(parityEvidence=[]), "invalid-parity-evidence"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            for name, mutate, expected_code in cases:
                with self.subTest(name=name):
                    ledger = self.complete_ledger()
                    mutate(ledger)
                    path = Path(temporary) / f"{name}.json"
                    path.write_text(json.dumps(ledger), encoding="utf-8")
                    result = run_script(VALIDATE_LEDGER, str(path))
                    self.assertEqual(result.returncode, 1, result.stdout)
                    self.assertIn(expected_code, {item["code"] for item in json.loads(result.stdout)["issues"]})


if __name__ == "__main__":
    unittest.main()
