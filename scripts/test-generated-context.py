#!/usr/bin/env python3
"""Behavioral tests for the generated context renderer."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import generated_context


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = REPOSITORY_ROOT / "templates" / "generated-context"


class GeneratedContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.write("global.md", "Keep the human source authoritative.\n")
        self.write("cohort.md", "Use deterministic generated context.\n")
        self.write("dependency.md", "Contract ALPHA is version 1.\n")
        self.write("ticket.md", "Implement ticket T01.\n")
        self.write("handoff.md", "Return evidence to receipt T01-A1.\n")
        self.manifest = {
            "schema_version": 1,
            "family": "implementation",
            "template_version": 1,
            "stable_sources": [
                {"role": "global", "id": "global-v1", "path": "global.md"},
                {"role": "cohort", "id": "context-v1", "path": "cohort.md"},
                {"role": "dependency", "id": "alpha-v1", "path": "dependency.md"},
            ],
            "volatile_sources": [
                {"role": "ticket", "id": "ticket", "path": "ticket.md"},
                {"role": "handoff", "id": "handoff", "path": "handoff.md"},
            ],
        }

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write(self, relative_path: str, content: str) -> Path:
        path = self.root / relative_path
        path.write_text(content, encoding="utf-8")
        return path

    def render(self, manifest=None):
        return generated_context.render_manifest(
            self.manifest if manifest is None else manifest,
            source_root=self.root,
            template_root=TEMPLATE_ROOT,
        )

    def assert_error(self, code: str, manifest) -> None:
        with self.assertRaises(generated_context.ContextError) as caught:
            self.render(manifest)
        self.assertEqual(code, caught.exception.code)

    def test_volatile_assignments_share_exact_stable_prefix(self) -> None:
        first = self.render()
        self.write("ticket-two.md", "Implement ticket T99.\n")
        self.write("handoff-two.md", "Return evidence to receipt T99-A3.\n")
        second_manifest = copy.deepcopy(self.manifest)
        second_manifest["volatile_sources"] = [
            {"role": "ticket", "id": "ticket", "path": "ticket-two.md"},
            {"role": "handoff", "id": "handoff", "path": "handoff-two.md"},
        ]
        second = self.render(second_manifest)

        self.assertEqual(first.stable_prefix, second.stable_prefix)
        self.assertNotEqual(first.prompt, second.prompt)
        self.assertTrue(first.prompt.startswith(first.stable_prefix))
        self.assertEqual(
            first.metadata["stable_prefix_sha256"],
            second.metadata["stable_prefix_sha256"],
        )

    def test_rendering_is_byte_deterministic_and_metadata_is_privacy_safe(self) -> None:
        first = self.render()
        second = self.render(copy.deepcopy(self.manifest))

        self.assertEqual(first.prompt, second.prompt)
        self.assertEqual(first.metadata_bytes, second.metadata_bytes)
        metadata_text = first.metadata_bytes.decode("utf-8")
        self.assertNotIn(str(self.root), metadata_text)
        self.assertNotIn("Implement ticket T01", metadata_text)
        self.assertEqual("local-byte-digest", first.metadata["provenance"]["method"])
        self.assertFalse(first.metadata["provenance"]["authenticated"])
        self.assertEqual("last", first.metadata["volatile_position"])

    def test_human_source_bytes_are_preserved(self) -> None:
        source = "Heading\n\n  Deliberate indentation.  \n"
        self.write("cohort.md", source)
        result = self.render()
        self.assertIn(source.encode("utf-8"), result.prompt)

    def test_early_volatile_source_is_rejected(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        manifest["stable_sources"].append(
            {"role": "ticket", "id": "too-early", "path": "ticket.md"}
        )
        self.assert_error("invalid-source-phase", manifest)

    def test_duplicate_source_is_rejected(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        manifest["stable_sources"].append(
            {"role": "dependency", "id": "global-v1", "path": "global.md"}
        )
        self.assert_error("duplicate-source", manifest)

    def test_padding_field_is_rejected(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        manifest["padding"] = " " * 4096
        self.assert_error("padding-forbidden", manifest)

    def test_missing_critical_context_is_rejected(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        manifest["stable_sources"] = [
            source for source in manifest["stable_sources"] if source["role"] != "cohort"
        ]
        self.assert_error("missing-critical-context", manifest)

    def test_untrusted_authenticated_provenance_claim_is_rejected(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        manifest["provenance"] = {
            "method": "sha256",
            "digest": "0" * 64,
            "authenticated": True,
        }
        self.assert_error("untrusted-provenance-claim", manifest)

    def test_templates_are_small_versioned_literal_prefixes(self) -> None:
        for family in generated_context.FAMILIES:
            template = generated_context.load_template(TEMPLATE_ROOT, family, 1)
            self.assertLess(len(template), 2048)
            self.assertIn(b"Template version: 1\n", template)
            self.assertNotIn(b"{{", template)
            self.assertNotIn(b"${", template)
            self.assertNotIn(b"\n\n\n\n", template)

    def test_cli_writes_exact_prompt_and_canonical_metadata(self) -> None:
        manifest_path = self.root / "manifest.json"
        output_path = self.root / "prompt.md"
        metadata_path = self.root / "metadata.json"
        manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")

        completed = subprocess.run(
            [
                sys.executable,
                str(REPOSITORY_ROOT / "scripts" / "generated_context.py"),
                "--manifest", str(manifest_path),
                "--source-root", str(self.root),
                "--template-root", str(TEMPLATE_ROOT),
                "--output", str(output_path),
                "--metadata-output", str(metadata_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        direct = self.render()
        self.assertEqual(direct.prompt, output_path.read_bytes())
        self.assertEqual(direct.metadata_bytes, metadata_path.read_bytes())
        self.assertEqual(direct.metadata_bytes.decode("utf-8"), completed.stdout)


if __name__ == "__main__":
    unittest.main()
