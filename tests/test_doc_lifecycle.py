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
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {args}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
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
    (path / "README.md").write_text("# Test repository\n", encoding="utf-8")
    git(path, "add", "README.md")
    git(path, "commit", "-m", "initial")


class DocumentLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_ensure_is_lazy_idempotent_and_creates_no_controller_artifacts(self):
        repo = self.root / "new-product"
        init_repo(repo)

        dry = run(
            [
                "docs",
                "ensure",
                "--project-root",
                str(repo),
                "--dry-run",
                "--json",
            ]
        )
        self.assertEqual("pass", json.loads(dry.stdout)["status"])
        self.assertFalse((repo / "doc_org.md").exists())
        self.assertFalse((repo / "local-docs").exists())

        run(["docs", "ensure", "--project-root", str(repo), "--json"])
        expected = {
            "INDEX.md",
            "designs",
            "research",
            "decisions",
        }
        self.assertEqual(
            expected,
            {path.name for path in (repo / "local-docs").iterdir()},
        )
        for forbidden in [
            "drafts",
            "epics",
            "executions",
            "launch.json",
            "tickets",
            "runs",
            "journal",
            "dashboard",
        ]:
            self.assertFalse((repo / "local-docs" / forbidden).exists())

        policy = repo / "doc_org.md"
        index = repo / "local-docs" / "INDEX.md"
        policy.write_text(policy.read_text() + "\nUser policy note.\n", encoding="utf-8")
        index.write_text(index.read_text() + "\nUser index note.\n", encoding="utf-8")
        before = (policy.read_bytes(), index.read_bytes())
        run(["docs", "ensure", "--project-root", str(repo), "--json"])
        self.assertEqual(before, (policy.read_bytes(), index.read_bytes()))

    def test_linked_worktree_resolves_to_primary_and_preserves_user_edits(self):
        repo = self.root / "primary"
        init_repo(repo)
        linked = self.root / "linked"
        git(repo, "worktree", "add", "-b", "feature/docs", str(linked))

        created = run(
            [
                "docs",
                "design",
                "create",
                "--project-root",
                str(linked),
                "--title",
                "User owned flow",
                "--json",
            ]
        )
        data = json.loads(created.stdout)
        design = Path(data["designPath"])
        self.assertTrue(design.is_relative_to((repo / "local-docs").resolve()))
        self.assertFalse((linked / "local-docs").exists())
        self.assertFalse((linked / "doc_org.md").exists())

        user_bytes = (
            b"# User-owned title\r\n\r\n"
            b"## Bespoke section\r\n\r\nKeep this exact text.\r\n\r\n"
            b"## Acceptance\r\n\r\n- The whole flow completes.\r\n"
            b"- Existing records do not change.\r\n"
        )
        design.write_bytes(user_bytes)
        accepted = run(
            [
                "docs",
                "design",
                "accept",
                "--project-root",
                str(linked),
                "--design",
                data["designId"],
                "--json",
            ]
        )
        accepted_data = json.loads(accepted.stdout)
        self.assertEqual(user_bytes, design.read_bytes())
        record = json.loads(Path(accepted_data["acceptedRecord"]).read_text())
        self.assertEqual(hashlib.sha256(user_bytes).hexdigest(), record["sourceSha256"])
        self.assertNotIn("criteria", record)
        self.assertNotIn("acceptance", record.keys() - {"acceptanceSha256"})

    def test_create_allocates_once_and_template_prompts_do_not_count_as_acceptance(self):
        repo = self.root / "create"
        init_repo(repo)
        preview = run(
            [
                "docs",
                "design",
                "create",
                "--project-root",
                str(repo),
                "--title",
                "Sensor execution",
                "--dry-run",
                "--json",
            ]
        )
        preview_data = json.loads(preview.stdout)
        self.assertEqual("CREATE-001", preview_data["designId"])
        self.assertFalse(Path(preview_data["designPath"]).exists())

        created = run(
            [
                "docs",
                "design",
                "create",
                "--project-root",
                str(repo),
                "--title",
                "Sensor execution",
                "--json",
            ]
        )
        data = json.loads(created.stdout)
        design = Path(data["designPath"])
        self.assertEqual("CREATE-001", data["designId"])
        self.assertIn("## Acceptance", design.read_text())
        self.assertNotIn("implementation plan", design.read_text().lower())

        rejected = run(
            [
                "docs",
                "design",
                "accept",
                "--project-root",
                str(repo),
                "--design",
                str(design),
                "--json",
            ],
            check=False,
        )
        self.assertNotEqual(0, rejected.returncode)
        self.assertIn("missing_exact_acceptance", rejected.stdout)
        self.assertFalse(design.with_suffix(".accepted.json").exists())

        duplicate = run(
            [
                "docs",
                "design",
                "create",
                "--project-root",
                str(repo),
                "--title",
                "Duplicate",
                "--number",
                "1",
                "--json",
            ],
            check=False,
        )
        self.assertNotEqual(0, duplicate.returncode)
        self.assertIn("design_id_exists", duplicate.stdout)

    def test_accept_requires_exact_acceptance_heading_and_binds_whole_file(self):
        repo = self.root / "accept"
        init_repo(repo)
        created = run(
            [
                "docs",
                "design",
                "create",
                "--project-root",
                str(repo),
                "--title",
                "Outcome contract",
                "--json",
            ]
        )
        data = json.loads(created.stdout)
        design = Path(data["designPath"])
        design.write_text(
            "# Outcome contract\n\n"
            "## Done when\n\nPlanning is deterministic.\n",
            encoding="utf-8",
        )
        rejected = run(
            [
                "docs",
                "design",
                "accept",
                "--project-root",
                str(repo),
                "--design",
                data["designId"],
                "--json",
            ],
            check=False,
        )
        self.assertNotEqual(0, rejected.returncode)

        design.write_text(
            "# Outcome contract\n\n"
            "## Acceptance\n\n"
            "- The sensor command actually runs.\n"
            "- Planning does not run external commands.\n\n"
            "## Architecture Contract\n\nUse an explicit process adapter.\n",
            encoding="utf-8",
        )
        before = design.read_bytes()
        accepted = run(
            [
                "docs",
                "design",
                "accept",
                "--project-root",
                str(repo),
                "--design",
                str(design.relative_to((repo / "local-docs").resolve())),
                "--json",
            ]
        )
        record = json.loads(
            Path(json.loads(accepted.stdout)["acceptedRecord"]).read_text()
        )
        self.assertEqual(before, design.read_bytes())
        self.assertEqual(hashlib.sha256(before).hexdigest(), record["sourceSha256"])
        self.assertRegex(record["acceptanceSha256"], r"^[0-9a-f]{64}$")
        self.assertIn(
            "| Accepted |",
            (repo / "local-docs" / "INDEX.md").read_text(encoding="utf-8"),
        )

    def test_legacy_files_are_never_rewritten(self):
        repo = self.root / "legacy"
        init_repo(repo)
        run(
            [
                "docs",
                "init",
                "--project-root",
                str(repo),
                "--prefix",
                "LEGACY",
                "--json",
            ]
        )
        epic = repo / "local-docs" / "epics" / "009" / "009_OLD_PRD.md"
        execution = repo / "local-docs" / "executions" / "OLD-RUN" / "state.json"
        epic.parent.mkdir(parents=True)
        execution.parent.mkdir(parents=True)
        epic.write_bytes(b"# Legacy PRD\r\n\r\nDo not migrate me.\r\n")
        execution.write_bytes(b'{ "status": "historical" }\\n')
        before = (epic.read_bytes(), execution.read_bytes())

        run(["docs", "ensure", "--project-root", str(repo), "--json"])
        run(
            [
                "docs",
                "design",
                "create",
                "--project-root",
                str(repo),
                "--title",
                "New design",
                "--json",
            ]
        )
        self.assertEqual(before, (epic.read_bytes(), execution.read_bytes()))

    def test_collision_symlink_and_opt_out_fail_without_partial_writes(self):
        collision = self.root / "collision"
        init_repo(collision)
        (collision / "doc_org.md").write_text("# tracked\n")
        git(collision, "add", "doc_org.md")
        git(collision, "commit", "-m", "tracked collision")
        refused = run(
            [
                "docs",
                "ensure",
                "--project-root",
                str(collision),
                "--json",
            ],
            check=False,
        )
        self.assertNotEqual(0, refused.returncode)
        self.assertFalse((collision / "local-docs").exists())

        symlink_repo = self.root / "symlink"
        init_repo(symlink_repo)
        outside = self.root / "outside"
        outside.mkdir()
        (symlink_repo / "local-docs").symlink_to(outside, target_is_directory=True)
        symlink = run(
            [
                "docs",
                "ensure",
                "--project-root",
                str(symlink_repo),
                "--json",
            ],
            check=False,
        )
        self.assertNotEqual(0, symlink.returncode)
        self.assertEqual([], list(outside.iterdir()))

        opted_out = self.root / "optout"
        init_repo(opted_out)
        run(["docs", "disable", "--project-root", str(opted_out), "--json"])
        ensured = run(
            ["docs", "ensure", "--project-root", str(opted_out), "--json"]
        )
        self.assertEqual("opted-out", json.loads(ensured.stdout)["mode"])
        self.assertFalse((opted_out / "local-docs").exists())
        run(["docs", "enable", "--project-root", str(opted_out), "--json"])
        run(["docs", "ensure", "--project-root", str(opted_out), "--json"])
        self.assertTrue((opted_out / "local-docs" / "designs").is_dir())


if __name__ == "__main__":
    unittest.main(verbosity=2)
