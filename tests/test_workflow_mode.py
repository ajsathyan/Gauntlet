import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "workflow-mode.py"


class WorkflowModeRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name) / "repo"
        self.root.mkdir()
        subprocess.run(
            ["git", "init", "-q", str(self.root)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.nested = self.root / "one" / "two"
        self.nested.mkdir(parents=True)
        self.agents = self.root / "AGENTS.md"
        self.agents_bytes = b"# Existing instructions\n\nDo not replace me.\n"
        self.agents.write_bytes(self.agents_bytes)

    def run_hook(self, payload, *, cwd=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=json.dumps(payload).encode("utf-8"),
            cwd=cwd or self.nested,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def session_fixture(self, source, *, cwd=None):
        return {
            "session_id": "session-1",
            "transcript_path": None,
            "cwd": str(cwd or self.nested),
            "hook_event_name": "SessionStart",
            "model": "gpt-5",
            "permission_mode": "default",
            "source": source,
        }

    def pre_tool_fixture(self, tool_name, tool_input, *, cwd=None):
        return {
            "session_id": "session-1",
            "transcript_path": None,
            "cwd": str(cwd or self.nested),
            "hook_event_name": "PreToolUse",
            "model": "gpt-5",
            "permission_mode": "default",
            "turn_id": "turn-1",
            "tool_name": tool_name,
            "tool_use_id": "tool-1",
            "tool_input": tool_input,
        }

    def decode_json(self, completed):
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        return json.loads(completed.stdout)

    def run_guarded_bash(self, command):
        hook = self.run_hook(self.pre_tool_fixture("Bash", {"command": command}))
        if hook.stdout:
            decision = self.decode_json(hook).get("hookSpecificOutput", {})
            if decision.get("permissionDecision") == "deny":
                return hook, None
        command_result = subprocess.run(
            command,
            cwd=self.nested,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return hook, command_result

    def write_mode(self, content):
        declaration = self.root / ".gauntlet" / "workflow-mode"
        declaration.parent.mkdir(exist_ok=True)
        declaration.write_bytes(content)
        return declaration

    def assert_agents_unchanged(self):
        self.assertEqual(self.agents.read_bytes(), self.agents_bytes)

    def test_missing_mode_emits_choice_context_for_every_session_start_source(self):
        for source in ("startup", "resume", "clear", "compact"):
            with self.subTest(source=source):
                output = self.decode_json(self.run_hook(self.session_fixture(source)))
                self.assertEqual(
                    output["hookSpecificOutput"]["hookEventName"], "SessionStart"
                )
                context = output["hookSpecificOutput"]["additionalContext"]
                self.assertIn("No valid repository workflow mode is declared", context)
                self.assertIn(
                    "Which workflow should this repository use by default: "
                    "Gauntlet or Scratch?",
                    context,
                )
                self.assertIn("intended to be committed", context)
                self.assertIn("shared with collaborators", context)
                self.assertIn("supplements all applicable AGENTS.md", context)
                self.assertIn("continue to follow them", context)
                self.assertIn("do not replace or ignore them", context)
        self.assert_agents_unchanged()

    def test_exact_gauntlet_mode_emits_additive_context_from_nested_directory(self):
        self.write_mode(b"gauntlet\n")
        output = self.decode_json(self.run_hook(self.session_fixture("startup")))
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Workflow mode: Gauntlet", context)
        self.assertIn("Follow the applicable Gauntlet workflow", context)
        self.assertIn("supplements all applicable AGENTS.md", context)
        self.assert_agents_unchanged()

    def test_exact_scratch_mode_emits_complete_additive_context(self):
        declaration = self.write_mode(b"scratch\n")
        output = self.decode_json(self.run_hook(self.session_fixture("resume")))
        context = output["hookSpecificOutput"]["additionalContext"]
        for phrase in (
            "Workflow mode: Scratch",
            "Do not run tests",
            "linters",
            "builds",
            "smoke checks",
            "Gauntlet workflow steps",
            "explicitly disclose that they are unverified",
            "individual request",
            "do not modify .gauntlet/workflow-mode",
            "supplements all applicable AGENTS.md",
        ):
            self.assertIn(phrase, context)
        self.assertEqual(declaration.read_bytes(), b"scratch\n")
        self.assert_agents_unchanged()

    def test_invalid_bytes_never_select_a_mode_and_deny_bash(self):
        invalid_values = (
            b"",
            b"\n",
            b"GAUNTLET\n",
            b"gauntlet scratch\n",
            b" gauntlet\n",
            b"gauntlet",
            b"\xff\xfe\n",
        )
        for content in invalid_values:
            with self.subTest(content=content):
                self.write_mode(content)
                session = self.decode_json(
                    self.run_hook(self.session_fixture("compact"))
                )
                context = session["hookSpecificOutput"]["additionalContext"]
                self.assertIn("invalid", context)
                self.assertNotIn("Workflow mode: Gauntlet", context)
                self.assertNotIn("Workflow mode: Scratch", context)

                hook, command_result = self.run_guarded_bash(
                    "printf changed > arbitrary.txt"
                )
                decision = self.decode_json(hook)["hookSpecificOutput"]
                self.assertEqual(decision["hookEventName"], "PreToolUse")
                self.assertEqual(decision["permissionDecision"], "deny")
                self.assertIn(
                    "valid repository workflow mode",
                    decision["permissionDecisionReason"],
                )
                self.assertIsNone(command_result)
        self.assertFalse((self.root / "arbitrary.txt").exists())
        self.assert_agents_unchanged()

    def test_missing_or_invalid_mode_denies_write_tools_but_allows_read_tools(self):
        fixtures = (
            ("Bash", {"command": "touch changed"}),
            ("apply_patch", {"command": "*** Begin Patch\n*** End Patch\n"}),
            ("mcp__filesystem__write_file", {"path": "changed", "content": "x"}),
        )
        for tool_name, tool_input in fixtures:
            with self.subTest(tool_name=tool_name):
                output = self.decode_json(
                    self.run_hook(self.pre_tool_fixture(tool_name, tool_input))
                )
                self.assertEqual(
                    output["hookSpecificOutput"]["permissionDecision"], "deny"
                )

        read = self.run_hook(
            self.pre_tool_fixture(
                "mcp__filesystem__read_file", {"path": str(self.agents)}
            )
        )
        self.assertEqual(read.returncode, 0)
        self.assertEqual(read.stdout, b"")
        ask = self.run_hook(
            self.pre_tool_fixture(
                "request_user_input", {"questions": [{"question": "Choose a mode"}]}
            )
        )
        self.assertEqual(ask.returncode, 0)
        self.assertEqual(ask.stdout, b"")
        self.assert_agents_unchanged()

    def test_only_exact_bootstrap_command_is_allowed(self):
        valid_command = shlex.join(
            [sys.executable, str(SCRIPT), "bootstrap", "scratch"]
        )
        allowed = self.run_hook(
            self.pre_tool_fixture("Bash", {"command": valid_command})
        )
        self.assertEqual(allowed.returncode, 0)
        self.assertEqual(allowed.stdout, b"")

        self.write_mode(b"invalid\n")
        allowed_from_invalid = self.run_hook(
            self.pre_tool_fixture("Bash", {"command": valid_command})
        )
        self.assertEqual(allowed_from_invalid.returncode, 0)
        self.assertEqual(allowed_from_invalid.stdout, b"")

        wrong_commands = (
            shlex.join(
                [
                    sys.executable,
                    str(SCRIPT.with_name("other.py")),
                    "bootstrap",
                    "scratch",
                ]
            ),
            shlex.join([sys.executable, str(SCRIPT), "bootstrap", "SCRATCH"]),
            shlex.join([sys.executable, str(SCRIPT), "bootstrap", "scratch", "extra"]),
            "mkdir -p .gauntlet && printf 'scratch\\n' > .gauntlet/workflow-mode",
            "printf 'other\\n' > .gauntlet/workflow-mode",
            "printf 'scratch\\n' > workflow-mode",
        )
        for command in wrong_commands:
            with self.subTest(command=command):
                denied = self.decode_json(
                    self.run_hook(
                        self.pre_tool_fixture("Bash", {"command": command})
                    )
                )
                self.assertEqual(
                    denied["hookSpecificOutput"]["permissionDecision"], "deny"
                )
        self.assert_agents_unchanged()

    def test_bootstrap_creates_only_exact_declaration_and_validates_mode(self):
        invalid = subprocess.run(
            [sys.executable, str(SCRIPT), "bootstrap", "SCRATCH"],
            cwd=self.nested,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertNotEqual(invalid.returncode, 0)
        self.assertFalse((self.root / ".gauntlet").exists())

        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "bootstrap", "gauntlet"],
            cwd=self.nested,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        declaration = self.root / ".gauntlet" / "workflow-mode"
        self.assertEqual(declaration.read_bytes(), b"gauntlet\n")
        self.assertEqual(
            sorted(
                str(path.relative_to(self.root))
                for path in (self.root / ".gauntlet").rglob("*")
            ),
            [".gauntlet/workflow-mode"],
        )
        self.assert_agents_unchanged()

    def test_valid_modes_allow_local_calls_and_scratch_opt_in_preserves_bytes(self):
        for content in (b"gauntlet\n", b"scratch\n"):
            with self.subTest(content=content):
                declaration = self.write_mode(content)
                before = declaration.read_bytes()
                for payload in (
                    self.pre_tool_fixture(
                        "apply_patch", {"command": "*** Begin Patch\n*** End Patch\n"}
                    ),
                ):
                    result = self.run_hook(payload)
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, b"")
                hook, command_result = self.run_guarded_bash("touch allowed")
                self.assertEqual(hook.stdout, b"")
                self.assertEqual(command_result.returncode, 0)
                self.assertTrue((self.nested / "allowed").exists())
                (self.nested / "allowed").unlink()
                self.assertEqual(declaration.read_bytes(), before)
        self.assert_agents_unchanged()

    def test_non_git_working_directory_is_noop(self):
        outside = Path(self.temp_dir.name) / "outside"
        outside.mkdir()
        for payload in (
            self.session_fixture("startup", cwd=outside),
            self.pre_tool_fixture("Bash", {"command": "touch allowed"}, cwd=outside),
        ):
            with self.subTest(event=payload["hook_event_name"]):
                result = self.run_hook(payload, cwd=outside)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")
                self.assertEqual(result.stderr, b"")


if __name__ == "__main__":
    unittest.main()
