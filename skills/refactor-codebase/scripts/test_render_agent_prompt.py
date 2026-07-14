#!/usr/bin/env python3
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parent / "render_agent_prompt.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], check=False, capture_output=True, text=True)


class RenderAgentPromptTests(unittest.TestCase):
    def test_render_is_deterministic_and_keeps_variable_assignment_last(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            packet = root / "packet.json"
            assignment = root / "assignment.json"
            packet.write_text('{"contract":"frozen"}\n', encoding="utf-8")
            assignment.write_text(json.dumps({"receipt_destination": "return-to-root", "allowed_root": "/repo"}), encoding="utf-8")
            outputs = []
            metadata = []
            for index in range(2):
                output = root / f"prompt-{index}.md"
                result = run(
                    "--template-kind", "breakthrough", "--packet", str(packet),
                    "--assignment", str(assignment), "--output", str(output),
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                outputs.append(output.read_text(encoding="utf-8"))
                metadata.append(json.loads(result.stdout))
            self.assertEqual(outputs[0], outputs[1])
            self.assertEqual(metadata[0], metadata[1])
            self.assertEqual(metadata[0]["contextMode"], "none")
            self.assertEqual(metadata[0]["assignmentPosition"], "last")
            self.assertTrue(outputs[0].rstrip().endswith("```"))
            self.assertLess(outputs[0].index("## Static contract"), outputs[0].index("## Populated variable assignment"))

    def test_dynamic_values_change_prompt_hash_not_static_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            packet = root / "packet.json"
            packet.write_text('{"contract":"frozen"}\n', encoding="utf-8")
            receipts = []
            for index in range(2):
                assignment = root / f"assignment-{index}.json"
                assignment.write_text(json.dumps({"assigned_rows": [f"row-{index}"]}), encoding="utf-8")
                result = run(
                    "--template-kind", "observable-review", "--packet", str(packet),
                    "--assignment", str(assignment), "--output", str(root / f"prompt-{index}.md"),
                )
                self.assertEqual(result.returncode, 0, result.stdout)
                receipts.append(json.loads(result.stdout))
            self.assertEqual(receipts[0]["staticPrefixSha256"], receipts[1]["staticPrefixSha256"])
            self.assertEqual(receipts[0]["packetSha256"], receipts[1]["packetSha256"])
            self.assertNotEqual(receipts[0]["promptSha256"], receipts[1]["promptSha256"])

    def test_metadata_output_and_invalid_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            packet = root / "packet.json"
            assignment = root / "assignment.json"
            packet.write_text("{}\n", encoding="utf-8")
            assignment.write_text("{}\n", encoding="utf-8")
            invalid = run(
                "--template-kind", "breakthrough", "--packet", str(packet),
                "--assignment", str(assignment), "--output", str(root / "prompt.md"),
            )
            self.assertEqual(invalid.returncode, 2)
            self.assertEqual(json.loads(invalid.stdout)["error"]["code"], "invalid-assignment")

            assignment.write_text('{"receipt_destination":"return-to-root"}\n', encoding="utf-8")
            metadata_path = root / "metadata.json"
            valid = run(
                "--template-kind", "breakthrough", "--packet", str(packet),
                "--assignment", str(assignment), "--output", str(root / "prompt.md"),
                "--metadata-output", str(metadata_path),
            )
            self.assertEqual(valid.returncode, 0, valid.stdout)
            self.assertEqual(json.loads(metadata_path.read_text(encoding="utf-8")), json.loads(valid.stdout))

            assignment.write_text('{"packet_sha256":"forged"}\n', encoding="utf-8")
            forged = run(
                "--template-kind", "breakthrough", "--packet", str(packet),
                "--assignment", str(assignment), "--output", str(root / "forged.md"),
            )
            self.assertEqual(forged.returncode, 2)
            self.assertEqual(json.loads(forged.stdout)["error"]["code"], "invalid-assignment")


if __name__ == "__main__":
    unittest.main()
