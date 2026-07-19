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

    def create_accepted_design(self, acceptance):
        created = self.cli(
            "docs",
            "design",
            "create",
            "--project-root",
            str(self.repo),
            "--title",
            "Workflow gate",
            "--json",
        )
        data = json.loads(created.stdout)
        design = Path(data["designPath"])
        design.write_text(
            "# Workflow gate\n\n## Acceptance\n\n" + acceptance,
            encoding="utf-8",
        )
        self.cli(
            "docs",
            "design",
            "accept",
            "--project-root",
            str(self.repo),
            "--design",
            data["designId"],
            "--json",
        )
        return data["designId"], design

    def write_json(self, name, value):
        path = Path(self.temporary.name) / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def revision(self):
        commit = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        tree = git(self.repo, "rev-parse", "HEAD^{tree}").stdout.strip()
        return commit, tree

    def reviews(self, design_binding, fourth_disposition="omitted"):
        lenses = (
            "product-completeness",
            "engineering-shape",
            "proof-and-consequence",
        )
        results = []
        for index, lens in enumerate(lenses):
            findings = []
            if index == 0:
                findings = [
                    {
                        "identity": f"finding-{number}",
                        "material": True,
                        "disposition": (
                            fourth_disposition if number == 4 else "rejected"
                        ),
                        "reason": "Resolved against accepted scope.",
                    }
                    for number in range(1, 5)
                ]
            results.append(
                {
                    "lens": lens,
                    "reviewer": f"reviewer-{index}",
                    "design": design_binding,
                    "materialFindingCount": len(findings),
                    "findings": findings,
                }
            )
        return results

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

    def test_build_entry_blocks_post_acceptance_source_edit(self):
        design_id, design = self.create_accepted_design(
            "1. External command runs.\n"
        )
        record = json.loads(design.with_suffix(".accepted.json").read_text())
        design.write_text(
            design.read_text(encoding="utf-8") + "\nUnaccepted behavior.\n",
            encoding="utf-8",
        )
        result = self.cli(
            "workflow",
            "build-entry",
            "--project-root",
            str(self.repo),
            "--design",
            design_id,
            "--reviews",
            str(self.write_json("reviews.json", self.reviews(record))),
            "--json",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stale", result.stdout.lower())

    def test_fourth_material_finding_beyond_display_cap_blocks_build(self):
        design_id, design = self.create_accepted_design(
            "1. External command runs.\n"
        )
        record = json.loads(design.with_suffix(".accepted.json").read_text())
        result = self.cli(
            "workflow",
            "build-entry",
            "--project-root",
            str(self.repo),
            "--design",
            design_id,
            "--reviews",
            str(
                self.write_json(
                    "reviews.json",
                    self.reviews(record, fourth_disposition=None),
                )
            ),
            "--json",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("finding-4", result.stdout)

    def test_verify_entry_revalidates_the_accepted_source_and_acceptance(self):
        design_id, design = self.create_accepted_design(
            "1. External command runs.\n"
        )
        record = json.loads(design.with_suffix(".accepted.json").read_text())
        commit, tree = self.revision()
        built = self.cli(
            "workflow",
            "build-entry",
            "--project-root",
            str(self.repo),
            "--design",
            design_id,
            "--reviews",
            str(self.write_json("reviews.json", self.reviews(record))),
            "--json",
        )
        bound = self.cli(
            "workflow",
            "bind-candidate",
            "--contract",
            str(
                self.write_json(
                    "contract.json",
                    json.loads(built.stdout)["contract"],
                )
            ),
            "--project-root",
            str(self.repo),
            "--design",
            design_id,
            "--reviews",
            str(self.write_json("bind-reviews.json", self.reviews(record))),
            "--commit",
            commit,
            "--tree",
            tree,
            "--json",
        )
        contract = json.loads(bound.stdout)["contract"]
        design.write_text(
            "# Workflow gate\n\n"
            "## Acceptance\n\n"
            "1. External command runs.\n"
            "2. A narrowed checklist is enough.\n",
            encoding="utf-8",
        )
        stale = self.cli(
            "workflow",
            "verify-entry",
            "--project-root",
            str(self.repo),
            "--design",
            design_id,
            "--contract",
            str(self.write_json("bound.json", contract)),
            "--json",
            check=False,
        )
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("stale", stale.stdout.lower())

    def test_completion_rejects_omitted_accepted_outcome_despite_green_sensors(self):
        design_id, design = self.create_accepted_design(
            "1. External command runs.\n"
            "2. Dashboard is published.\n"
        )
        record = json.loads(design.with_suffix(".accepted.json").read_text())
        commit, tree = self.revision()
        built = self.cli(
            "workflow",
            "build-entry",
            "--project-root",
            str(self.repo),
            "--design",
            design_id,
            "--reviews",
            str(self.write_json("reviews.json", self.reviews(record))),
            "--json",
        )
        contract = json.loads(built.stdout)["contract"]
        bound = self.cli(
            "workflow",
            "bind-candidate",
            "--contract",
            str(self.write_json("unbound-contract.json", contract)),
            "--project-root",
            str(self.repo),
            "--design",
            design_id,
            "--reviews",
            str(self.write_json("bind-reviews.json", self.reviews(record))),
            "--commit",
            commit,
            "--tree",
            tree,
            "--json",
        )
        contract = json.loads(bound.stdout)["contract"]
        outcomes = contract["acceptedDesign"]["outcomes"]

        verdict_inputs = [
            ("architecture", {"directEvidence": ["boundaries inspected"]}),
            ("sensor", {"directEvidence": ["configured sensors passed"]}),
            (
                "build",
                {
                    "directEvidence": ["external command observed"],
                    "outcomeEvidence": {
                        outcomes[0]["identity"]: [
                            f"revision:{commit}#path:README.md"
                        ]
                    },
                },
            ),
        ]
        for number, (area, evidence) in enumerate(verdict_inputs):
            contract_path = self.write_json(f"contract-{number}.json", contract)
            evidence_path = self.write_json(f"evidence-{number}.json", evidence)
            verdict = self.cli(
                "workflow",
                "record-verdict",
                "--contract",
                str(contract_path),
                "--project-root",
                str(self.repo),
                "--design",
                design_id,
                "--area",
                area,
                "--verdict",
                "pass",
                "--evidence",
                str(evidence_path),
                "--json",
                check=False,
            )
            if area == "build":
                self.assertNotEqual(verdict.returncode, 0)
                self.assertIn("every accepted outcome", verdict.stdout)
            else:
                contract = json.loads(verdict.stdout)["contract"]

        completion = self.cli(
            "workflow",
            "completion-check",
            "--project-root",
            str(self.repo),
            "--design",
            design_id,
            "--contract",
            str(self.write_json("completion-contract.json", contract)),
            "--json",
            check=False,
        )
        self.assertNotEqual(completion.returncode, 0)
        completion_data = json.loads(completion.stdout)["completion"]
        self.assertEqual(
            completion_data["verdicts"],
            {
                "build": "absent",
                "architecture": "pass",
                "sensor": "pass",
            },
        )

    def test_mixed_acceptance_prose_and_lists_all_bind_as_outcomes(self):
        design_id, design = self.create_accepted_design(
            "The existing command remains available.\n\n"
            "1. The command runs the configured check.\n"
            "2. The result reports the exact revision.\n\n"
            "No dashboard state is created.\n"
        )
        record = json.loads(design.with_suffix(".accepted.json").read_text())
        built = self.cli(
            "workflow",
            "build-entry",
            "--project-root",
            str(self.repo),
            "--design",
            design_id,
            "--reviews",
            str(self.write_json("mixed-reviews.json", self.reviews(record))),
            "--json",
        )
        outcomes = json.loads(built.stdout)["contract"]["acceptedDesign"]["outcomes"]
        self.assertEqual(
            [item["identity"] for item in outcomes],
            [
                "acceptance-001",
                "acceptance-002",
                "acceptance-003",
                "acceptance-004",
            ],
        )

    def test_bind_candidate_resolves_commit_and_derived_tree(self):
        design_id, design = self.create_accepted_design(
            "The external command remains available.\n"
        )
        record = json.loads(design.with_suffix(".accepted.json").read_text())
        reviews_path = self.write_json("git-reviews.json", self.reviews(record))
        built = self.cli(
            "workflow", "build-entry",
            "--project-root", str(self.repo),
            "--design", design_id,
            "--reviews", str(reviews_path),
            "--json",
        )
        contract_path = self.write_json(
            "git-contract.json",
            json.loads(built.stdout)["contract"],
        )
        commit, tree = self.revision()
        missing = self.cli(
            "workflow", "bind-candidate",
            "--project-root", str(self.repo),
            "--design", design_id,
            "--reviews", str(reviews_path),
            "--contract", str(contract_path),
            "--commit", "f" * 40,
            "--tree", tree,
            "--json",
            check=False,
        )
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("candidate commit", missing.stdout)

        mismatched = self.cli(
            "workflow", "bind-candidate",
            "--project-root", str(self.repo),
            "--design", design_id,
            "--reviews", str(reviews_path),
            "--contract", str(contract_path),
            "--commit", commit,
            "--tree", "a" * 40,
            "--json",
            check=False,
        )
        self.assertNotEqual(mismatched.returncode, 0)
        self.assertIn("does not match", mismatched.stdout)

        valid = self.cli(
            "workflow", "bind-candidate",
            "--project-root", str(self.repo),
            "--design", design_id,
            "--reviews", str(reviews_path),
            "--contract", str(contract_path),
            "--commit", commit,
            "--tree", tree,
            "--json",
        )
        self.assertEqual(
            json.loads(valid.stdout)["contract"]["candidateRevision"],
            {"commit": commit, "tree": tree},
        )

    def test_build_evidence_locator_must_resolve_in_candidate_revision(self):
        design_id, design = self.create_accepted_design(
            "The external command remains available.\n"
        )
        record = json.loads(design.with_suffix(".accepted.json").read_text())
        reviews_path = self.write_json("locator-reviews.json", self.reviews(record))
        built = self.cli(
            "workflow", "build-entry",
            "--project-root", str(self.repo),
            "--design", design_id,
            "--reviews", str(reviews_path),
            "--json",
        )
        commit, tree = self.revision()
        bound = self.cli(
            "workflow", "bind-candidate",
            "--project-root", str(self.repo),
            "--design", design_id,
            "--reviews", str(reviews_path),
            "--contract", str(
                self.write_json(
                    "locator-contract.json",
                    json.loads(built.stdout)["contract"],
                )
            ),
            "--commit", commit,
            "--tree", tree,
            "--json",
        )
        contract = json.loads(bound.stdout)["contract"]
        outcome = contract["acceptedDesign"]["outcomes"][0]["identity"]

        def verdict(locator, name):
            return self.cli(
                "workflow", "record-verdict",
                "--project-root", str(self.repo),
                "--design", design_id,
                "--contract", str(
                    self.write_json(f"{name}-contract.json", contract)
                ),
                "--area", "build",
                "--verdict", "pass",
                "--evidence", str(
                    self.write_json(
                        f"{name}-evidence.json",
                        {
                            "directEvidence": ["command observed"],
                            "outcomeEvidence": {
                                outcome: [f"revision:{commit}#{locator}"]
                            },
                        },
                    )
                ),
                "--json",
                check=False,
            )

        unresolved = verdict("path:missing-proof.txt", "unresolved")
        self.assertNotEqual(unresolved.returncode, 0)
        self.assertIn("could not be resolved by Git", unresolved.stdout)

        valid = verdict("path:README.md", "valid")
        self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)

    def test_legacy_accepted_epic_is_a_read_only_design_source(self):
        self.cli("docs", "ensure", "--project-root", str(self.repo), "--json")
        docs = self.repo / "local-docs"
        epic = docs / "epics" / "011" / "011_THIN_CONTRACT_WORKFLOW_PRD.md"
        epic.parent.mkdir(parents=True)
        source = (
            "# Thin Contract Workflow\n\n"
            "## Acceptance\n\n"
            "The old accepted Epic remains directly readable.\n\n"
            "## Architecture Contract\n\n"
            "Application services own workflow sequencing.\n\n"
            "## Sensor Contract\n\n"
            "Configured checks execute against the candidate revision.\n"
        )
        epic.write_text(source, encoding="utf-8")
        (docs / "INDEX.md").write_text(
            "# Local documents\n\n"
            "| ID | Title | Type | Status | Created | Dependencies | Supersedes | Implementation | Verification |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| `GAUNTLET-011` | [Thin Contract Workflow](epics/011/011_THIN_CONTRACT_WORKFLOW_PRD.md) | PRD | Accepted | 2026-07-19 | None | None | Not implemented | Not verified |\n",
            encoding="utf-8",
        )
        record = {
            "acceptedAt": "2026-07-19T04:51:11Z",
            "consequenceTriggers": [],
            "dependencies": [],
            "epicId": "GAUNTLET-011",
            "releaseStages": ["merge"],
            "schemaVersion": "gauntlet.accepted-epic.v1",
            "sourcePath": str(epic),
            "sourceSha256": hashlib.sha256(source.encode()).hexdigest(),
            "title": "Thin Contract Workflow",
        }
        sidecar = epic.with_suffix(".accepted.json")
        sidecar.write_text(json.dumps(record), encoding="utf-8")
        before = (epic.read_bytes(), sidecar.read_bytes(), (docs / "INDEX.md").read_bytes())

        built = self.cli(
            "workflow",
            "build-entry",
            "--project-root",
            str(self.repo),
            "--design",
            "GAUNTLET-011",
            "--reviews",
            str(self.write_json("legacy-reviews.json", self.reviews(record))),
            "--json",
        )
        accepted = json.loads(built.stdout)["contract"]["acceptedDesign"]
        self.assertEqual(accepted["identity"], "GAUNTLET-011")
        self.assertEqual(
            {
                area: binding["applicable"]
                for area, binding in accepted["contractApplicability"].items()
            },
            {"architecture": True, "sensor": True},
        )
        self.assertTrue(
            all(
                binding["sha256"].startswith("sha256:")
                for binding in accepted["contractApplicability"].values()
            )
        )
        self.assertEqual(before, (epic.read_bytes(), sidecar.read_bytes(), (docs / "INDEX.md").read_bytes()))

    def test_public_cli_rejects_one_evidence_reference_reused_for_two_outcomes(self):
        design_id, design = self.create_accepted_design(
            "1. External command runs.\n2. Dashboard is published.\n"
        )
        record = json.loads(design.with_suffix(".accepted.json").read_text())
        commit, tree = self.revision()
        reviews_path = self.write_json("duplicate-reviews.json", self.reviews(record))
        built = self.cli(
            "workflow", "build-entry",
            "--project-root", str(self.repo),
            "--design", design_id,
            "--reviews", str(reviews_path),
            "--json",
        )
        contract = json.loads(built.stdout)["contract"]
        bound = self.cli(
            "workflow", "bind-candidate",
            "--project-root", str(self.repo),
            "--design", design_id,
            "--reviews", str(reviews_path),
            "--contract", str(self.write_json("duplicate-contract.json", contract)),
            "--commit", commit,
            "--tree", tree,
            "--json",
        )
        contract = json.loads(bound.stdout)["contract"]
        reused = f"revision:{commit}#path:README.md"
        evidence = {
            "directEvidence": ["two outcomes claimed"],
            "outcomeEvidence": {
                item["identity"]: [reused]
                for item in contract["acceptedDesign"]["outcomes"]
            },
        }
        rejected = self.cli(
            "workflow", "record-verdict",
            "--project-root", str(self.repo),
            "--design", design_id,
            "--contract", str(self.write_json("duplicate-bound.json", contract)),
            "--area", "build",
            "--verdict", "pass",
            "--evidence", str(self.write_json("duplicate-evidence.json", evidence)),
            "--json",
            check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("unique evidence references", rejected.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
