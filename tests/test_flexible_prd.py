#!/usr/bin/env python3
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from support import ROOT


CLI = ROOT / "scripts" / "gauntlet.py"


def run(args, *, check=True):
    result = subprocess.run(
        ["python3", str(CLI), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        raise AssertionError(
            f"command failed ({result.returncode}): {args}\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return result


def git(repo, *args):
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def init_repo(path):
    path.mkdir()
    git(path, "init")
    git(path, "config", "user.email", "gauntlet@example.test")
    git(path, "config", "user.name", "Gauntlet Test")
    (path / "README.md").write_text("# App\n", encoding="utf-8")
    git(path, "add", "README.md")
    git(path, "commit", "-m", "initial")


class FlexibleDesignTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name) / "app"
        init_repo(self.repo)

    def tearDown(self):
        self.temporary.cleanup()

    def cli(self, *args, check=True):
        return run(args, check=check)

    def test_arbitrary_user_sections_and_bytes_survive_acceptance(self):
        created = self.cli(
            "docs",
            "design",
            "create",
            "--project-root",
            str(self.repo),
            "--title",
            "Machine labels",
            "--json",
        )
        data = json.loads(created.stdout)
        design = Path(data["designPath"])
        user_bytes = (
            b"# A title the user controls\r\n\r\n"
            b"## Bespoke heading\r\n\r\nUser bytes stay unchanged.\r\n"
            b"\r\n## Acceptance\r\n\r\n"
            b"- Each row shows its existing stable label.\r\n"
            b"- Provisioning behavior does not change.\r\n"
            b"\r\n## Another arbitrary section\r\n\r\n\xe2\x98\x83\r\n"
        )
        design.write_bytes(user_bytes)

        accepted = self.cli(
            "docs",
            "design",
            "accept",
            "--project-root",
            str(self.repo),
            "--design",
            data["designId"],
            "--json",
        )
        accepted_data = json.loads(accepted.stdout)
        self.assertEqual(user_bytes, design.read_bytes())
        record = json.loads(Path(accepted_data["acceptedRecord"]).read_text())
        self.assertEqual(hashlib.sha256(user_bytes).hexdigest(), record["sourceSha256"])
        self.assertEqual(
            {
                "schemaVersion",
                "designId",
                "sourcePath",
                "sourceSha256",
                "acceptanceSha256",
                "acceptedAt",
            },
            set(record),
        )

    def test_acceptance_record_exposes_later_semantic_edits(self):
        created = self.cli(
            "docs",
            "design",
            "create",
            "--project-root",
            str(self.repo),
            "--title",
            "Immutable meaning",
            "--json",
        )
        data = json.loads(created.stdout)
        design = Path(data["designPath"])
        design.write_text(
            "# Immutable meaning\n\n"
            "## Acceptance\n\nThe external command runs and reports its result.\n",
            encoding="utf-8",
        )
        accepted = self.cli(
            "docs",
            "design",
            "accept",
            "--project-root",
            str(self.repo),
            "--design",
            data["designId"],
            "--json",
        )
        record = json.loads(Path(json.loads(accepted.stdout)["acceptedRecord"]).read_text())
        design.write_text(
            design.read_text(encoding="utf-8")
            + "\n## Unaccepted expansion\n\nAlso publish a dashboard.\n",
            encoding="utf-8",
        )
        self.assertNotEqual(
            record["sourceSha256"],
            hashlib.sha256(design.read_bytes()).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
