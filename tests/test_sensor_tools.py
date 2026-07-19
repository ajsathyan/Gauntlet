#!/usr/bin/env python3
"""Black-box tests for isolated optional sensor tool installation."""

import hashlib
import importlib.util
import io
import json
import os
import platform
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

from support import ROOT


INSTALLER = ROOT / "scripts" / "install-sensor-tools.py"
COVERAGE_SENSOR = ROOT / "scripts" / "run-coverage-sensor.py"


def load_installer_module():
    spec = importlib.util.spec_from_file_location(
        "gauntlet_sensor_tool_installer",
        INSTALLER,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SensorToolInstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.agent_home = self.root / "agent-home"
        self.fake_uv = self.root / "fake-uv"
        self.fake_uv.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import os",
                    "import pathlib",
                    "import sys",
                    "spec = sys.argv[-1]",
                    "name, version = spec.split('==', 1)",
                    "target = pathlib.Path(os.environ['UV_TOOL_BIN_DIR']) / name",
                    "target.parent.mkdir(parents=True, exist_ok=True)",
                    "target.write_text(",
                    "    '#!/bin/sh\\n'",
                    "    + (f\"echo 'Coverage.py, version {version}'\\n\" if name == 'coverage' else f\"echo '{version}'\\n\")",
                    ")",
                    "target.chmod(0o755)",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        self.fake_uv.chmod(0o755)

        self.asset_dir = self.root / "assets"
        self.asset_dir.mkdir()
        system = platform.system().lower()
        machine = platform.machine().lower()
        machine = {"aarch64": "arm64", "amd64": "x86_64"}.get(machine, machine)
        self.platform_key = f"{system}-{machine}"
        self.asset_name = "gitleaks-fixture.tar.gz"
        archive = self.asset_dir / self.asset_name
        content = b"#!/bin/sh\necho '8.30.1'\n"
        with tarfile.open(archive, "w:gz") as bundle:
            info = tarfile.TarInfo("gitleaks")
            info.mode = 0o755
            info.size = len(content)
            bundle.addfile(info, io.BytesIO(content))
        self.asset_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.manifest = self.root / "sensor-tools.json"
        self.manifest.write_text(
            json.dumps(
                {
                    "schema": "gauntlet.sensor-tools/v1",
                    "python": "3.12",
                    "tools": {
                        "coverage": {"kind": "uv-tool", "version": "7.15.2"},
                        "semgrep": {"kind": "uv-tool", "version": "1.170.0"},
                        "gitleaks": {
                            "kind": "release-archive",
                            "version": "8.30.1",
                            "assets": {
                                self.platform_key: {
                                    "name": self.asset_name,
                                    "sha256": self.asset_sha,
                                }
                            },
                        },
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temporary.cleanup()

    def cli(self, command, *, check=True):
        arguments = [
            "python3",
            str(INSTALLER),
            command,
            "--agent-home",
            str(self.agent_home),
            "--manifest",
            str(self.manifest),
            "--json",
        ]
        if command == "install":
            arguments.extend(
                [
                    "--uv",
                    str(self.fake_uv),
                    "--gitleaks-base-url",
                    self.asset_dir.as_uri(),
                ]
            )
        result = subprocess.run(
            arguments,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if check and result.returncode:
            raise AssertionError(f"{result.stdout}\n{result.stderr}")
        return result

    def test_install_verify_idempotence_checksum_and_owned_removal(self):
        first = json.loads(self.cli("install").stdout)
        self.assertEqual(first["status"], "pass")
        current = self.agent_home / "gauntlet-tools" / "current"
        self.assertTrue(current.is_symlink())
        for tool in ("coverage", "gitleaks", "semgrep"):
            self.assertTrue((current / "bin" / tool).is_file())
        receipt_before = (
            self.agent_home / "gauntlet-tools" / "receipt.json"
        ).read_bytes()

        self.assertEqual(json.loads(self.cli("verify").stdout)["status"], "pass")
        self.assertEqual(json.loads(self.cli("install").stdout)["status"], "pass")
        self.assertEqual(
            (self.agent_home / "gauntlet-tools" / "receipt.json").read_bytes(),
            receipt_before,
        )

        removed = json.loads(self.cli("remove").stdout)
        self.assertEqual(removed["status"], "pass")
        self.assertEqual(removed["action"], "removed")
        self.assertFalse(current.exists())

    def test_bad_archive_checksum_preserves_previous_active_generation(self):
        self.cli("install")
        current = self.agent_home / "gauntlet-tools" / "current"
        active_before = current.resolve()
        manifest = json.loads(self.manifest.read_text())
        manifest["tools"]["gitleaks"]["assets"][self.platform_key]["sha256"] = "0" * 64
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")

        failed = self.cli("install", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("checksum", failed.stdout)
        self.assertEqual(current.resolve(), active_before)

    def test_repeat_install_rejects_a_missing_owned_binary(self):
        self.cli("install")
        current = self.agent_home / "gauntlet-tools" / "current"
        (current / "bin" / "coverage").unlink()

        failed = self.cli("install", check=False)

        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("content drift", failed.stdout)
        self.assertIn("bin/coverage", failed.stdout)

    def test_repeat_install_and_remove_report_and_preserve_a_modified_binary(self):
        self.cli("install")
        current = self.agent_home / "gauntlet-tools" / "current"
        coverage = current / "bin" / "coverage"
        coverage.write_text("#!/bin/sh\necho user-modified\n", encoding="utf-8")

        failed = self.cli("install", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("content drift", failed.stdout)
        self.assertIn("bin/coverage", failed.stdout)

        generation = current.resolve()
        generation_name = generation.name
        removed = json.loads(self.cli("remove").stdout)
        preserved_coverage = (
            self.agent_home
            / "gauntlet-tools"
            / "preserved-generations"
            / generation_name
            / "bin"
            / "coverage"
        )
        self.assertEqual(removed["action"], "removed")
        self.assertTrue(preserved_coverage.exists())
        self.assertTrue(
            any("bin/coverage" in finding for finding in removed["findings"])
        )
        self.cli("install")
        self.assertNotIn(
            "user-modified",
            (current / "bin" / "coverage").read_text(encoding="utf-8"),
        )

    def test_remove_preserves_and_reports_an_unknown_generation_file(self):
        self.cli("install")
        current = self.agent_home / "gauntlet-tools" / "current"
        generation = current.resolve()
        unknown = generation / "user-owned.txt"
        unknown.write_text("preserve me\n", encoding="utf-8")

        removed = json.loads(self.cli("remove").stdout)
        preserved_unknown = (
            self.agent_home
            / "gauntlet-tools"
            / "preserved-generations"
            / generation.name
            / "user-owned.txt"
        )

        self.assertEqual(removed["action"], "removed")
        self.assertEqual(
            preserved_unknown.read_text(encoding="utf-8"),
            "preserve me\n",
        )
        self.assertTrue(
            any("user-owned.txt" in finding for finding in removed["findings"])
        )

    def test_direct_install_migrates_a_predecessor_receipt(self):
        installed = json.loads(self.cli("install").stdout)
        root = self.agent_home / "gauntlet-tools"
        receipt_path = root / "receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt.pop("contents")
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

        upgraded = json.loads(self.cli("install").stdout)

        preserved = (
            root
            / "preserved-generations"
            / installed["currentGeneration"]
        )
        self.assertTrue((preserved / "bin" / "coverage").is_file())
        self.assertIn("contents", upgraded)
        self.assertTrue(upgraded["findings"])
        self.assertTrue((root / "current" / "bin" / "coverage").is_file())

    def test_predecessor_receipt_uninstall_preserves_then_reinstalls(self):
        installed = json.loads(self.cli("install").stdout)
        root = self.agent_home / "gauntlet-tools"
        receipt_path = root / "receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt.pop("contents")
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        generation_name = installed["currentGeneration"]

        removed = json.loads(self.cli("remove").stdout)

        preserved = root / "preserved-generations" / generation_name
        self.assertTrue((preserved / "bin" / "coverage").is_file())
        self.assertTrue(
            any("predecessor receipt generation" in item for item in removed["findings"])
        )
        reinstalled = json.loads(self.cli("install").stdout)
        self.assertIn("contents", reinstalled)
        self.assertTrue((root / "current" / "bin" / "coverage").is_file())

    def test_drifted_predecessor_receipt_uninstall_preserves_then_reinstalls(self):
        installed = json.loads(self.cli("install").stdout)
        root = self.agent_home / "gauntlet-tools"
        receipt_path = root / "receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt.pop("contents")
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        current = root / "current"
        (current / "bin" / "coverage").write_text(
            "#!/bin/sh\necho drifted predecessor\n",
            encoding="utf-8",
        )

        removed = json.loads(self.cli("remove").stdout)

        preserved = (
            root
            / "preserved-generations"
            / installed["currentGeneration"]
            / "bin"
            / "coverage"
        )
        self.assertIn("drifted predecessor", preserved.read_text(encoding="utf-8"))
        self.assertTrue(removed["findings"])
        self.cli("install")
        self.assertNotIn(
            "drifted predecessor",
            (root / "current" / "bin" / "coverage").read_text(encoding="utf-8"),
        )

    def test_activation_receipt_failure_restores_previous_generation(self):
        self.cli("install")
        current = self.agent_home / "gauntlet-tools" / "current"
        active_before = current.resolve()
        receipt_path = self.agent_home / "gauntlet-tools" / "receipt.json"
        receipt_before = receipt_path.read_bytes()
        next_generation = (
            self.agent_home
            / "gauntlet-tools"
            / "generations"
            / "next-generation"
        )
        next_generation.mkdir()
        installer = load_installer_module()

        def fail_receipt(_path, _receipt):
            raise OSError("simulated receipt write failure")

        with self.assertRaises(OSError):
            installer._activate(
                self.agent_home / "gauntlet-tools",
                next_generation,
                {"schema": "fixture"},
                receipt_writer=fail_receipt,
            )

        self.assertEqual(current.resolve(), active_before)
        self.assertEqual(receipt_path.read_bytes(), receipt_before)

    def test_coverage_sensor_preserves_repo_import_path(self):
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        fake_coverage = fake_bin / "coverage"
        expected = str(ROOT / "scripts")
        fake_coverage.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import os",
                    "import sys",
                    f"expected = {expected!r}",
                    "if sys.argv[1] == 'run' and expected not in os.environ.get('PYTHONPATH', '').split(os.pathsep):",
                    "    print('missing repository scripts path', file=sys.stderr)",
                    "    raise SystemExit(1)",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        fake_coverage.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"

        result = subprocess.run(
            ["python3", str(COVERAGE_SENSOR)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
