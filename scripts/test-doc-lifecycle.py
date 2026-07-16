#!/usr/bin/env python3
import argparse
import contextlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "gauntlet.py"
SPEC = importlib.util.spec_from_file_location("gauntlet_cli", CLI)
GAUNTLET = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GAUNTLET)


def run(args, *, check=True):
    result = subprocess.run(
        ["python3", str(CLI), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {args}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def git(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=repo, text=True, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
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

    def test_ensure_creates_only_an_unanswered_founding_draft_for_a_new_profile(self):
        repo = self.root / "new-product"
        init_repo(repo)

        dry_run = run(["docs", "ensure", "--project-root", str(repo), "--dry-run", "--json"])
        dry_data = json.loads(dry_run.stdout)
        self.assertEqual("pass", dry_data["status"])
        self.assertFalse((repo / "local-docs").exists())
        self.assertFalse((repo / "doc_org.md").exists())

        ensured = run(["docs", "ensure", "--project-root", str(repo), "--json"])
        data = json.loads(ensured.stdout)
        draft = repo / "local-docs" / "drafts" / "FOUNDING_HYPOTHESIS.md"
        self.assertEqual(draft.resolve(), Path(data["foundingDraftPath"]).resolve())
        self.assertTrue(draft.is_file())
        text = draft.read_text(encoding="utf-8")
        self.assertIn("*Guidance:", text)
        self.assertIn("## Founding hypothesis", text)
        self.assertNotIn("## Meeting Notes", text)
        self.assertNotIn("Customer answer:", text)

        before = draft.read_bytes()
        repeated = run(["docs", "ensure", "--project-root", str(repo), "--json"])
        self.assertEqual("pass", json.loads(repeated.stdout)["status"])
        self.assertEqual(before, draft.read_bytes())

    def test_ensure_does_not_add_a_founding_draft_to_an_existing_product_profile(self):
        repo = self.root / "existing-product"
        init_repo(repo)
        run(["docs", "init", "--project-root", str(repo), "--epic-prefix", "EXISTING", "--json"])
        legacy = run([
            "docs", "epic", "create", "--project-root", str(repo),
            "--title", "Existing feature", "--json",
        ])
        legacy_path = Path(json.loads(legacy.stdout)["prdPath"])
        legacy_before = legacy_path.read_bytes()

        ensured = run(["docs", "ensure", "--project-root", str(repo), "--json"])
        self.assertEqual("pass", json.loads(ensured.stdout)["status"])
        self.assertFalse((repo / "local-docs" / "drafts" / "FOUNDING_HYPOTHESIS.md").exists())
        self.assertEqual(legacy_before, legacy_path.read_bytes())

    def test_followup_draft_explicitly_selects_the_peter_yang_template(self):
        repo = self.root / "followup"
        init_repo(repo)
        run(["docs", "init", "--project-root", str(repo), "--epic-prefix", "FOLLOWUP", "--json"])

        created = run([
            "docs", "draft", "create", "--project-root", str(repo),
            "--template", "peter-yang", "--json",
        ])
        data = json.loads(created.stdout)
        draft = Path(data["draftPath"])
        self.assertEqual("peter-yang", data["template"])
        self.assertEqual((repo / "local-docs" / "drafts" / "PETER_YANG_PRD.md").resolve(), draft.resolve())
        text = draft.read_text(encoding="utf-8")
        self.assertIn("# Feature PRD", text)
        self.assertIn("*Guidance:", text)
        self.assertNotIn("## Meeting Notes", text)

    def test_promotion_preserves_exact_bytes_and_updates_the_index_once(self):
        repo = self.root / "promotion"
        init_repo(repo)
        run(["docs", "init", "--project-root", str(repo), "--epic-prefix", "PROMOTE", "--json"])
        created = run([
            "docs", "draft", "create", "--project-root", str(repo),
            "--template", "peter-yang", "--json",
        ])
        draft = Path(json.loads(created.stdout)["draftPath"])
        user_bytes = (
            b"# A title the user controls\r\n\r\n"
            b"## Bespoke heading\r\n\r\nUser bytes stay unchanged.\r\n"
            b"\r\n## Another arbitrary section\r\n\r\n\xe2\x98\x83\r\n"
        )
        draft.write_bytes(user_bytes)

        preview = run([
            "docs", "draft", "promote", "--project-root", str(repo),
            "--draft", draft.name, "--title", "User-owned launch", "--dry-run", "--json",
        ])
        preview_data = json.loads(preview.stdout)
        self.assertEqual("PROMOTE-001", preview_data["epicId"])
        self.assertTrue(draft.is_file())
        self.assertFalse(Path(preview_data["prdPath"]).exists())

        promoted = run([
            "docs", "draft", "promote", "--project-root", str(repo),
            "--draft", draft.name, "--title", "User-owned launch", "--json",
        ])
        data = json.loads(promoted.stdout)
        prd = Path(data["prdPath"])
        self.assertFalse(draft.exists())
        self.assertEqual(user_bytes, prd.read_bytes())
        index = (repo / "local-docs" / "INDEX.md").read_text(encoding="utf-8")
        self.assertEqual(1, index.count("PROMOTE-001"))
        self.assertEqual(1, index.count("User-owned launch"))

    def test_collision_and_index_failure_leave_the_draft_and_index_unchanged(self):
        repo = self.root / "rollback"
        init_repo(repo)
        run(["docs", "init", "--project-root", str(repo), "--epic-prefix", "ROLLBACK", "--json"])
        run([
            "docs", "epic", "create", "--project-root", str(repo),
            "--title", "Allocated", "--number", "1", "--json",
        ])
        created = run([
            "docs", "draft", "create", "--project-root", str(repo),
            "--template", "peter-yang", "--json",
        ])
        draft = Path(json.loads(created.stdout)["draftPath"])
        draft_bytes = draft.read_bytes()
        index = repo / "local-docs" / "INDEX.md"
        index_before = index.read_bytes()

        collision = run([
            "docs", "draft", "promote", "--project-root", str(repo),
            "--draft", draft.name, "--title", "Collision", "--number", "1", "--json",
        ], check=False)
        self.assertNotEqual(0, collision.returncode)
        self.assertEqual(draft_bytes, draft.read_bytes())
        self.assertEqual(index_before, index.read_bytes())

        args = argparse.Namespace(
            project_root=repo,
            draft=draft.name,
            title="Rollback proof",
            number=2,
            dry_run=False,
            json=True,
        )
        original_atomic_write = GAUNTLET.atomic_write_text

        def fail_index_write(path, content, mode=0o600):
            if Path(path).resolve() == index.resolve():
                raise OSError("injected index failure")
            return original_atomic_write(path, content, mode=mode)

        with mock.patch.object(GAUNTLET, "atomic_write_text", side_effect=fail_index_write):
            with self.assertRaisesRegex(OSError, "injected index failure"):
                with contextlib.redirect_stdout(io.StringIO()):
                    GAUNTLET.command_docs_draft_promote(args)

        self.assertEqual(draft_bytes, draft.read_bytes())
        self.assertEqual(index_before, index.read_bytes())
        self.assertFalse((repo / "local-docs" / "epics" / "002").exists())

    def test_read_only_and_non_command_paths_do_not_create_documents(self):
        repo = self.root / "discussion"
        init_repo(repo)
        before = sorted(path.relative_to(repo) for path in repo.rglob("*") if path.is_file())

        checked = run(["docs", "check", "--project-root", str(repo), "--json"])
        self.assertEqual("pass", json.loads(checked.stdout)["status"])
        no_command = run(["docs", "--help"], check=False)
        self.assertEqual(0, no_command.returncode)

        after = sorted(path.relative_to(repo) for path in repo.rglob("*") if path.is_file())
        self.assertEqual(before, after)
        self.assertFalse((repo / "local-docs").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
