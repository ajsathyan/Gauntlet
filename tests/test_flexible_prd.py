#!/usr/bin/env python3
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from support import ROOT


CLI = ROOT / "scripts" / "gauntlet.py"
LENSES = ("product", "engineering", "design", "analytics", "qa", "performance")


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


class FlexibleDesignTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name) / "app"
        self.repo.mkdir()
        git(self.repo, "init")
        git(self.repo, "config", "user.email", "gauntlet@example.test")
        git(self.repo, "config", "user.name", "Gauntlet Test")
        (self.repo / "README.md").write_text("# App\n", encoding="utf-8")
        git(self.repo, "add", "README.md")
        git(self.repo, "commit", "-m", "initial")

    def tearDown(self):
        self.temporary.cleanup()

    def cli(self, *args, check=True):
        return run(args, check=check)

    def write_json(self, name, value):
        path = Path(self.temporary.name) / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def create_accepted_design(self, acceptance="The external command runs.\n"):
        created = self.cli(
            "docs", "design", "create",
            "--project-root", str(self.repo),
            "--title", "Workflow gate",
            "--json",
        )
        data = json.loads(created.stdout)
        design = Path(data["designPath"])
        design.write_text(
            "# Workflow gate\n\n## Acceptance\n\n" + acceptance,
            encoding="utf-8",
        )
        accepted = self.cli(
            "docs", "design", "accept",
            "--project-root", str(self.repo),
            "--design", data["designId"],
            "--json",
        )
        record = json.loads(Path(json.loads(accepted.stdout)["acceptedRecord"]).read_text())
        return data["designId"], design, record

    def reviews(self, binding):
        return [
            {
                "lens": lens,
                "reviewer": "main-agent",
                "design": binding,
                "applicability": "not-applicable" if lens == "analytics" else "applicable",
                "applicabilityReason": (
                    "No instrumentation or metric behavior changes."
                    if lens == "analytics"
                    else None
                ),
                "materialFindingCount": 0,
                "findings": [],
            }
            for lens in LENSES
        ]

    def test_acceptance_preserves_arbitrary_user_bytes(self):
        created = self.cli(
            "docs", "design", "create",
            "--project-root", str(self.repo),
            "--title", "Machine labels",
            "--json",
        )
        data = json.loads(created.stdout)
        design = Path(data["designPath"])
        user_bytes = (
            b"# User title\r\n\r\n## Bespoke section\r\n\r\nKeep this.\r\n"
            b"\r\n## Acceptance\r\n\r\nThe stable label remains.\r\n"
        )
        design.write_bytes(user_bytes)
        accepted = self.cli(
            "docs", "design", "accept",
            "--project-root", str(self.repo),
            "--design", data["designId"],
            "--json",
        )
        record = json.loads(Path(json.loads(accepted.stdout)["acceptedRecord"]).read_text())
        self.assertEqual(user_bytes, design.read_bytes())
        self.assertEqual(hashlib.sha256(user_bytes).hexdigest(), record["sourceSha256"])

    def test_six_lenses_are_required_and_bind_the_accepted_snapshot(self):
        design_id, design, record = self.create_accepted_design()
        reviews = self.reviews(record)
        missing = self.cli(
            "workflow", "build-entry",
            "--project-root", str(self.repo),
            "--design", design_id,
            "--reviews", str(self.write_json("missing.json", reviews[:-1])),
            "--json",
            check=False,
        )
        self.assertNotEqual(0, missing.returncode)
        self.assertIn("exactly six", missing.stdout)

        design.write_text(design.read_text() + "\nUnaccepted expansion.\n", encoding="utf-8")
        stale = self.cli(
            "workflow", "build-entry",
            "--project-root", str(self.repo),
            "--design", design_id,
            "--reviews", str(self.write_json("stale.json", reviews)),
            "--json",
            check=False,
        )
        self.assertNotEqual(0, stale.returncode)
        self.assertIn("stale", stale.stdout.lower())

    def test_exact_candidate_base_and_two_axis_verdict_complete(self):
        design_id, _design, record = self.create_accepted_design()
        reviews_path = self.write_json("reviews.json", self.reviews(record))
        built = self.cli(
            "workflow", "build-entry",
            "--project-root", str(self.repo),
            "--design", design_id,
            "--reviews", str(reviews_path),
            "--json",
        )
        contract = json.loads(built.stdout)["contract"]
        commit = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        tree = git(self.repo, "rev-parse", "HEAD^{tree}").stdout.strip()
        bound = self.cli(
            "workflow", "bind-candidate",
            "--project-root", str(self.repo),
            "--design", design_id,
            "--reviews", str(reviews_path),
            "--contract", str(self.write_json("contract.json", contract)),
            "--commit", commit,
            "--tree", tree,
            "--base", commit,
            "--json",
        )
        contract = json.loads(bound.stdout)["contract"]
        outcome = contract["acceptedDesign"]["outcomes"][0]["identity"]
        build_evidence = {
            "outcomeResults": {
                outcome: {
                    "behavior": "passed",
                    "proofAvailability": "available",
                    "evidence": [f"revision:{commit}#path:README.md"],
                    "remainingCheck": None,
                }
            }
        }
        build = self.cli(
            "workflow", "record-verdict",
            "--project-root", str(self.repo),
            "--design", design_id,
            "--contract", str(self.write_json("bound.json", contract)),
            "--area", "build",
            "--verdict", "passed",
            "--evidence", str(self.write_json("build.json", build_evidence)),
            "--json",
        )
        contract = json.loads(build.stdout)["contract"]
        architecture = self.cli(
            "workflow", "record-verdict",
            "--project-root", str(self.repo),
            "--design", design_id,
            "--contract", str(self.write_json("built.json", contract)),
            "--area", "architecture",
            "--verdict", "not-applicable",
            "--evidence", str(
                self.write_json(
                    "architecture.json",
                    {"evidence": [], "remainingCheck": None},
                )
            ),
            "--json",
        )
        contract = json.loads(architecture.stdout)["contract"]
        completed = self.cli(
            "workflow", "completion-check",
            "--project-root", str(self.repo),
            "--design", design_id,
            "--contract", str(self.write_json("complete.json", contract)),
            "--json",
        )
        self.assertEqual(
            {"commit": commit, "tree": tree, "base": commit},
            contract["candidateRevision"],
        )
        self.assertTrue(json.loads(completed.stdout)["completion"]["complete"])

    def test_unsupported_legacy_record_fails_closed(self):
        design_id, design, record = self.create_accepted_design()
        record["schemaVersion"] = "gauntlet.accepted-epic.v1"
        design.with_suffix(".accepted.json").write_text(json.dumps(record), encoding="utf-8")
        result = self.cli(
            "workflow", "build-entry",
            "--project-root", str(self.repo),
            "--design", design_id,
            "--reviews", str(self.write_json("reviews.json", self.reviews(record))),
            "--json",
            check=False,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("unsupported", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
