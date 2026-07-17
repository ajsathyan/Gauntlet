#!/usr/bin/env python3
"""Behavioral tests for Codex CLI and Claude Code evaluation adapters."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import SCRIPTS


SCRIPT = SCRIPTS / "eval-harness.py"
SPEC = importlib.util.spec_from_file_location("eval_harness", SCRIPT)
eval_harness = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(eval_harness)
TASK_SCRIPT = SCRIPTS / "eval-task.py"
TASK_SPEC = importlib.util.spec_from_file_location("eval_task_for_digest", TASK_SCRIPT)
eval_task = importlib.util.module_from_spec(TASK_SPEC)
assert TASK_SPEC.loader is not None
TASK_SPEC.loader.exec_module(eval_task)


FAKE_CLI = r'''#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

if "--version" in sys.argv:
    print("fake-cli 9.9.0")
    raise SystemExit(0)

prompt = sys.stdin.read()
if "exec" in sys.argv:
    workspace = Path(sys.argv[sys.argv.index("--cd") + 1])
    (workspace / "result.txt").write_text(os.environ["GAUNTLET_EVAL_PROFILE"] + ":" + prompt.strip())
    print(json.dumps({"type": "thread.started", "thread_id": "volatile"}))
    print(json.dumps({"type": "turn.completed", "model": sys.argv[sys.argv.index("--model") + 1], "permission_mode": sys.argv[sys.argv.index("--sandbox") + 1], "tools": ["shell", "apply_patch"], "usage": {"input_tokens": 12, "output_tokens": 4}}))
else:
    workspace = Path.cwd()
    (workspace / "result.txt").write_text(os.environ["GAUNTLET_EVAL_PROFILE"] + ":" + prompt.strip())
    print(json.dumps({"type": "system", "subtype": "init", "session_id": "volatile", "model": sys.argv[sys.argv.index("--model") + 1], "permissionMode": sys.argv[sys.argv.index("--permission-mode") + 1], "tools": ["Bash", "Read"]}))
    print(json.dumps({"type": "result", "subtype": "success", "duration_ms": 12, "is_error": False, "num_turns": 2, "total_cost_usd": 0.01, "usage": {"input_tokens": 10, "output_tokens": 3}}))
'''


SCORER = r'''#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
request = json.loads(sys.stdin.read())
candidate = Path(request["candidate"])
value = (candidate / "result.txt").read_text()
print(json.dumps({"passed": value.endswith(":implement the development fixture") and "OPENAI_API_KEY" not in os.environ}))
'''


def observations(**overrides):
    base = {name: {"status": "same", "supported": True} for name in eval_harness.EQUIVALENCE_DIMENSIONS}
    base.update(overrides)
    return {
        "harness": "codex-cli",
        "harness_version": "9.9.0",
        "model": "gpt-test",
        "observations": base,
        "permission_mode": "workspace-write",
        "reasoning_effort": "medium",
        "resource_profile": "standard",
    }


class HarnessFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.cli = root / "fake-cli.py"
        self.scorer = root / "score.py"
        self.cli.write_text(FAKE_CLI)
        self.cli.chmod(0o755)
        self.scorer.write_text(SCORER)
        self.scorer.chmod(0o755)
        self.start = root / "start"
        self.start.mkdir()
        (self.start / "README.md").write_text("fixture")
        self.state_digest = eval_harness.tree_digest(self.start)
        self.prompt = root / "prompt.md"
        self.prompt.write_text("implement the development fixture")
        self.workspaces = root / "workspaces"

    def manifest(self, kind: str = "codex-cli") -> dict:
        permission = "workspace-write" if kind == "codex-cli" else "acceptEdits"
        return {
            "capabilities": {name: "required" for name in eval_harness.EQUIVALENCE_DIMENSIONS},
            "executable": [sys.executable, str(self.cli)],
            "extra_args": [],
            "harness_id": f"{kind}-fake",
            "inherit_env": [],
            "kind": kind,
            "max_turns": None,
            "model": "gpt-test" if kind == "codex-cli" else "claude-test",
            "permission_mode": permission,
            "profiles": {
                "baseline": {"environment": {
                    "CODEX_HOME" if kind == "codex-cli" else "CLAUDE_CONFIG_DIR": str(self.root / f"{kind}-baseline"),
                    "GAUNTLET_EVAL_PROFILE": "baseline",
                }},
                "treatment": {"environment": {
                    "CODEX_HOME" if kind == "codex-cli" else "CLAUDE_CONFIG_DIR": str(self.root / f"{kind}-treatment"),
                    "GAUNTLET_EVAL_PROFILE": "treatment",
                }},
            },
            "reasoning_effort": "medium" if kind == "codex-cli" else None,
            "schema_version": 1,
            "version_pin": "9.9.0",
        }

    def tasks(self) -> dict:
        return {"schema_version": 1, "tasks": {"dev-harness": {
            "artifact_allowlist": ["result.txt"],
            "prompt_file": str(self.prompt),
            "score_command": [sys.executable, str(self.scorer)],
            "starting_tree": str(self.start),
            "state_digest": self.state_digest,
        }}}

    def request(self, execution_id: str = "execution-one", profile: str = "baseline") -> dict:
        return {
            "cache_state": "cold", "condition_token": "opaque", "execution_id": execution_id,
            "op": "execute", "package": {"profile": profile}, "repetition": 1,
            "schema_version": 1, "state_digest": self.state_digest, "task_id": "dev-harness", "task_version": 1,
        }


class EvalHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.fixture = HarnessFixture(Path(self.temporary.name))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_manifests_build_native_noninteractive_commands_without_prompt_argv(self) -> None:
        codex = eval_harness.validate_manifest(self.fixture.manifest("codex-cli"))
        command = eval_harness.build_command(codex, self.fixture.start)
        self.assertIn("exec", command)
        self.assertIn("--json", command)
        self.assertIn("--ephemeral", command)
        self.assertIn('model_reasoning_effort="medium"', command)
        self.assertNotIn("implement the development fixture", command)

        claude = eval_harness.validate_manifest(self.fixture.manifest("claude-code"))
        command = eval_harness.build_command(claude, self.fixture.start)
        self.assertIn("-p", command)
        self.assertIn("stream-json", command)
        self.assertNotIn("--max-turns", command)
        self.assertNotIn("implement the development fixture", command)

    def test_manifest_rejects_inline_secrets_and_unresolved_models(self) -> None:
        manifest = self.fixture.manifest()
        manifest["profiles"]["baseline"]["environment"]["OPENAI_API_KEY"] = "secret"
        with self.assertRaisesRegex(eval_harness.HarnessError, "cannot store secret-like"):
            eval_harness.validate_manifest(manifest)
        manifest = self.fixture.manifest()
        manifest["model"] = "SET_ME"
        with self.assertRaisesRegex(eval_harness.HarnessError, "model must be resolved"):
            eval_harness.validate_manifest(manifest)
        manifest = self.fixture.manifest()
        manifest["profiles"]["treatment"]["environment"]["EXPERIMENT_FLAG"] = "treatment-only"
        with self.assertRaisesRegex(eval_harness.HarnessError, "environment keys must match"):
            eval_harness.validate_manifest(manifest)
        manifest = self.fixture.manifest("claude-code")
        manifest["reasoning_effort"] = "high"
        with self.assertRaisesRegex(eval_harness.HarnessError, "reasoning_effort must be null"):
            eval_harness.validate_manifest(manifest)

    def test_liveness_is_version_pinned_and_spends_no_model_turn(self) -> None:
        manifest = eval_harness.validate_manifest(self.fixture.manifest())
        result = eval_harness.probe(manifest, 2)
        self.assertTrue(result["available"])
        manifest["version_pin"] = "8.8.0"
        self.assertFalse(eval_harness.probe(manifest, 2)["available"])

    def test_starting_tree_digest_matches_task_admission_controller(self) -> None:
        self.assertEqual(self.fixture.state_digest, "sha256:" + eval_task.tree_digest(self.fixture.start))

    def test_nonfinite_provider_metric_is_rejected(self) -> None:
        with self.assertRaisesRegex(eval_harness.HarnessError, "must be finite"):
            eval_harness.numeric_metrics({"input_tokens": float("nan")})

    def test_codex_and_claude_adapters_launch_score_and_return_bounded_telemetry(self) -> None:
        tasks = eval_harness.validate_task_registry(self.fixture.tasks())
        for kind, execution in (("codex-cli", "codex-one"), ("claude-code", "claude-one")):
            with self.subTest(kind=kind):
                raw_manifest = self.fixture.manifest(kind)
                raw_manifest["inherit_env"] = ["OPENAI_API_KEY"]
                manifest = eval_harness.validate_manifest(raw_manifest)
                with patch.dict(os.environ, {"OPENAI_API_KEY": "provider-secret"}):
                    result = eval_harness.execute_adapter(
                        manifest, tasks, self.fixture.workspaces, self.fixture.request(execution), 5
                    )
                self.assertEqual(result["outcome"], "pass")
                self.assertEqual(result["artifacts"], ["result.txt"])
                self.assertEqual(result["telemetry"]["harness"], kind)
                self.assertNotIn("prompt", eval_harness.canonical_json(result).lower())
                self.assertGreater(result["metrics"]["duration_ms"], 0)

        manifest = eval_harness.validate_manifest(self.fixture.manifest())
        events = '\n'.join((
            json.dumps({"type": "thread.started", "thread_id": "volatile"}),
            json.dumps({"type": "turn.completed", "model": "wrong-model", "usage": {}}),
        ))
        with self.assertRaisesRegex(eval_harness.HarnessError, "expected the pinned model"):
            eval_harness.normalize_events(manifest, events)

    def test_adapter_rejects_selective_rerun_and_wrong_starting_state(self) -> None:
        manifest = eval_harness.validate_manifest(self.fixture.manifest())
        tasks = eval_harness.validate_task_registry(self.fixture.tasks())
        request = self.fixture.request()
        eval_harness.execute_adapter(manifest, tasks, self.fixture.workspaces, request, 5)
        with self.assertRaisesRegex(eval_harness.HarnessError, "selective rerun"):
            eval_harness.execute_adapter(manifest, tasks, self.fixture.workspaces, request, 5)
        changed = self.fixture.request("execution-two")
        changed["state_digest"] = "sha256:" + "2" * 64
        with self.assertRaisesRegex(eval_harness.HarnessError, "starting state"):
            eval_harness.execute_adapter(manifest, tasks, self.fixture.workspaces, changed, 5)
        escaped = self.fixture.request("../escape")
        with self.assertRaisesRegex(eval_harness.HarnessError, "safe stable identifier"):
            eval_harness.execute_adapter(manifest, tasks, self.fixture.workspaces, escaped, 5)

    def test_empty_registry_is_ready_but_core_identity_is_rejected(self) -> None:
        self.assertEqual(eval_harness.validate_task_registry({"schema_version": 1, "tasks": {}}), {})
        registry = self.fixture.tasks()
        registry["tasks"]["CORE-01"] = registry["tasks"].pop("dev-harness")
        with self.assertRaisesRegex(eval_harness.HarnessError, "core tasks remain sealed"):
            eval_harness.validate_task_registry(registry)

    def test_direct_adapter_answers_all_neutral_equivalence_fixtures_without_a_task(self) -> None:
        for dimension in eval_harness.EQUIVALENCE_DIMENSIONS:
            request = {"dimension": dimension, "fixture": {"marker": dimension}, "op": "conformance"}
            self.assertEqual(
                eval_harness.protocol_observation(request),
                {"dimension": dimension, "observation": {"marker": dimension}},
            )

    def test_allowlisted_artifact_symlink_is_not_accepted_as_evidence(self) -> None:
        candidate = self.fixture.root / "candidate"
        candidate.mkdir()
        target = self.fixture.root / "outside.txt"
        target.write_text("outside")
        (candidate / "result.txt").symlink_to(target)
        self.assertEqual(eval_harness.collect_safe_artifacts(candidate, ["result.txt"]), [])

    def test_aa_equivalence_is_same_harness_same_model_only(self) -> None:
        left = observations()
        right = copy.deepcopy(left)
        self.assertEqual(eval_harness.aa_compare(left, right)["status"], "pass")
        right["observations"]["permission"] = {"status": "different", "supported": True}
        result = eval_harness.aa_compare(left, right)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["mismatches"], ["permission"])
        cross_model = observations()
        cross_model["model"] = "other-model"
        with self.assertRaisesRegex(eval_harness.HarnessError, "separate study blocks"):
            eval_harness.aa_compare(left, cross_model)
        cross_harness = observations()
        cross_harness["harness"] = "claude-code"
        with self.assertRaisesRegex(eval_harness.HarnessError, "separate study blocks"):
            eval_harness.aa_compare(left, cross_harness)
        cross_version = observations()
        cross_version["harness_version"] = "9.9.1"
        with self.assertRaisesRegex(eval_harness.HarnessError, "same harness_version"):
            eval_harness.aa_compare(left, cross_version)
        cross_resources = observations()
        cross_resources["resource_profile"] = "large"
        with self.assertRaisesRegex(eval_harness.HarnessError, "same resource_profile"):
            eval_harness.aa_compare(left, cross_resources)


if __name__ == "__main__":
    unittest.main(verbosity=2)
