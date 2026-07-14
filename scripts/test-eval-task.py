#!/usr/bin/env python3
"""Behavioral tests for isolated evaluation task admission and scoring."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("eval-task.py")
SPEC = importlib.util.spec_from_file_location("eval_task", SCRIPT)
eval_task = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(eval_task)


ADAPTER = r'''#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

request = json.loads(sys.stdin.read())
counter_dir = Path(os.environ["GAUNTLET_EVAL_COUNTER_DIR"])
counter_dir.mkdir(parents=True, exist_ok=True)

if request["op"] == "liveness":
    counter = counter_dir / "liveness-count"
    counter.write_text(str(int(counter.read_text()) + 1) if counter.exists() else "1")
    gate = Path(os.environ["GAUNTLET_EVAL_LIVENESS_FILE"])
    print(json.dumps({"passed": gate.read_text().strip() == "up"}))
    raise SystemExit(0)

counter = counter_dir / "score-count"
counter.write_text(str(int(counter.read_text()) + 1) if counter.exists() else "1")
candidate = Path(request["candidate"])
behavior = json.loads((candidate / "behavior.json").read_text())
print(json.dumps({"passed": behavior.get("succeeds") is True and behavior.get("invariant") == 7}))
'''


class EvaluationFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.task = root / "visible-task"
        self.verifier = root / "hidden-verifier"
        self.runtime = root / "trusted-runtime"
        self.state = self.runtime / "admission.json"
        self.cache = self.runtime / "immutable-cache.json"
        self.counter = self.runtime / "counters"
        self.liveness = self.runtime / "liveness"
        self.task.mkdir()
        self.verifier.mkdir()
        self.runtime.mkdir()
        self.liveness.write_text("up")
        self.wrong_candidate = root / "wrong-candidate"
        self.wrong_candidate.mkdir()
        (self.wrong_candidate / "behavior.json").write_text(json.dumps({"invariant": 7, "succeeds": False}))
        (self.wrong_candidate / "README.md").write_text("expected output success complete")

        (self.verifier / "adapter.py").write_text(ADAPTER)
        fixtures = self.verifier / "fixtures"
        for name, succeeds, phrase in (
            ("starting", False, "clean starting state"),
            ("reference", True, "reference implementation"),
            ("regression", False, "reference implementation"),
            ("wrong", False, "expected output success complete"),
        ):
            candidate = fixtures / name
            candidate.mkdir(parents=True)
            (candidate / "behavior.json").write_text(json.dumps({"invariant": 7, "succeeds": succeeds}))
            (candidate / "README.md").write_text(phrase)
        self.verifier_manifest = {
            "adapter": {"command": [sys.executable, "adapter.py"], "kind": "command-v1"},
            "cases": {
                "reference_solution": {"expected": True, "path": "fixtures/reference"},
                "regressions": [{"expected": False, "path": "fixtures/regression"}],
                "starting_state": {"expected": False, "path": "fixtures/starting"},
                "wrong_solutions": [{"expected": False, "path": "fixtures/wrong"}],
            },
            "image_digest": "sha256:" + "1" * 64,
            "liveness": {"probe": "adapter-ready"},
            "mode": "isolated",
            "mutable": False,
            "schema_version": 1,
            "task_id": "development-oracle",
            "verifier_id": "hidden-development-oracle-v1",
        }
        self.write_verifier()
        self.task_manifest = {
            "schema_version": 1,
            "slot": "development",
            "task_id": "development-oracle",
            "task_version": 1,
            "verifier": {
                "bundle_sha256": "sha256:" + eval_task.tree_digest(self.verifier),
                "id": "hidden-development-oracle-v1",
                "image_digest": "sha256:" + "1" * 64,
            },
        }
        self.write_task()

    @property
    def environment(self) -> dict[str, str]:
        return {
            "GAUNTLET_EVAL_COUNTER_DIR": str(self.counter),
            "GAUNTLET_EVAL_LIVENESS_FILE": str(self.liveness),
        }

    def write_verifier(self) -> None:
        (self.verifier / "verifier.json").write_text(json.dumps(self.verifier_manifest, sort_keys=True, indent=2) + "\n")

    def write_task(self) -> None:
        (self.task / "task.json").write_text(json.dumps(self.task_manifest, sort_keys=True, indent=2) + "\n")

    def repin(self) -> None:
        self.write_verifier()
        self.task_manifest["verifier"]["bundle_sha256"] = "sha256:" + eval_task.tree_digest(self.verifier)
        self.task_manifest["verifier"]["image_digest"] = self.verifier_manifest["image_digest"]
        self.write_task()

    def admit(self) -> dict:
        return eval_task.admit(self.task, self.verifier, self.state, self.cache, self.environment)

    def score_count(self) -> int:
        path = self.counter / "score-count"
        return int(path.read_text()) if path.exists() else 0

    def liveness_count(self) -> int:
        path = self.counter / "liveness-count"
        return int(path.read_text()) if path.exists() else 0


class EvalTaskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.fixture = EvaluationFixture(Path(self.temporary.name))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_admission_discriminates_start_reference_regression_and_wrong_solution(self) -> None:
        result = self.fixture.admit()
        observations = result["immutable"]["observations"]
        self.assertEqual(
            [(item["case"], item["observed"]) for item in observations],
            [
                ("starting_state", False),
                ("reference_solution", True),
                ("regressions[0]", False),
                ("wrong_solutions[0]", False),
            ],
        )
        self.assertEqual(result["status"], "admitted")
        self.assertEqual(self.fixture.score_count(), 4)

    def test_words_and_files_do_not_make_a_wrong_solution_pass(self) -> None:
        self.fixture.admit()
        result = eval_task.score(
            self.fixture.task,
            self.fixture.verifier,
            self.fixture.wrong_candidate,
            self.fixture.state,
            self.fixture.cache,
            self.fixture.environment,
        )
        self.assertEqual(result["outcome"], "implementation_failure")

    def test_shared_verifier_mode_is_quarantined(self) -> None:
        self.fixture.verifier_manifest["mode"] = "shared"
        self.fixture.repin()
        with self.assertRaisesRegex(eval_task.EvalTaskError, "shared verifier mode is forbidden"):
            self.fixture.admit()
        state = json.loads(self.fixture.state.read_text())
        self.assertEqual(state["status"], "quarantined")
        self.assertEqual(state["reason_kind"], "isolation")

    def test_mutable_verifier_image_is_quarantined(self) -> None:
        self.fixture.verifier_manifest["mutable"] = True
        self.fixture.repin()
        with self.assertRaisesRegex(eval_task.EvalTaskError, "mutable=false"):
            self.fixture.admit()
        self.assertEqual(json.loads(self.fixture.state.read_text())["status"], "quarantined")

    def test_hidden_verifier_tampering_fails_preflight(self) -> None:
        self.fixture.admit()
        with (self.fixture.verifier / "adapter.py").open("a") as handle:
            handle.write("\n# tampered\n")
        with self.assertRaisesRegex(eval_task.EvalTaskError, "pinned digest"):
            eval_task.preflight(
                self.fixture.task,
                self.fixture.verifier,
                self.fixture.state,
                self.fixture.cache,
                self.fixture.environment,
            )
        state = json.loads(self.fixture.state.read_text())
        self.assertEqual(state["reason_kind"], "integrity")

    def test_stale_cache_is_ignored_and_immutable_checks_rerun(self) -> None:
        self.fixture.admit()
        baseline = self.fixture.score_count()
        self.fixture.cache.write_text(json.dumps({
            "immutable_checks": {"stale-key": {"passed": True}},
            "schema_version": 1,
        }))
        result = eval_task.preflight(
            self.fixture.task,
            self.fixture.verifier,
            self.fixture.state,
            self.fixture.cache,
            self.fixture.environment,
        )
        self.assertFalse(result["immutable"]["immutable_cache_hit"])
        self.assertEqual(self.fixture.score_count(), baseline + 4)

    def test_repeated_preflight_reuses_immutable_checks_but_rechecks_liveness(self) -> None:
        self.fixture.admit()
        immutable_count = self.fixture.score_count()
        first = eval_task.preflight(
            self.fixture.task,
            self.fixture.verifier,
            self.fixture.state,
            self.fixture.cache,
            self.fixture.environment,
        )
        self.assertTrue(first["immutable"]["immutable_cache_hit"])
        self.assertEqual(self.fixture.score_count(), immutable_count)
        liveness_before_failure = self.fixture.liveness_count()

        self.fixture.liveness.write_text("down")
        with self.assertRaisesRegex(eval_task.EvalTaskError, "liveness probe failed"):
            eval_task.preflight(
                self.fixture.task,
                self.fixture.verifier,
                self.fixture.state,
                self.fixture.cache,
                self.fixture.environment,
            )
        self.assertEqual(self.fixture.score_count(), immutable_count)
        self.assertEqual(self.fixture.liveness_count(), liveness_before_failure + 1)
        state = json.loads(self.fixture.state.read_text())
        self.assertEqual(state["reason_kind"], "liveness")

    def test_failure_only_triage_cannot_relabel_implementation_failure(self) -> None:
        result = eval_task.classify_retry([{
            "failure_only_triage": {"requested_outcome": "infrastructure_invalid"},
            "outcome": "implementation_failure",
        }])
        self.assertEqual(result["classification"], "implementation_failure")
        self.assertFalse(result["retry"])
        self.assertEqual(result["ignored_failure_only_triage"], [0])

    def test_visible_task_does_not_expose_hidden_cases_or_adapter(self) -> None:
        visible = json.loads((self.fixture.task / "task.json").read_text())
        self.assertNotIn("cases", visible)
        self.assertNotIn("adapter", visible)
        self.assertFalse(str(self.fixture.verifier) in json.dumps(visible))
        with self.assertRaisesRegex(eval_task.EvalTaskError, "separate directory trees"):
            eval_task.load_contract(self.fixture.root, self.fixture.verifier)

    def test_core_slots_template_reserves_twelve_undefined_slots(self) -> None:
        template = SCRIPT.parent.parent / "templates" / "evaluation" / "core-slots.json"
        slots = json.loads(template.read_text())["slots"]
        self.assertEqual([item["slot"] for item in slots], [f"CORE-{index:02d}" for index in range(1, 13)])
        self.assertTrue(all(item == {"slot": item["slot"], "status": "reserved-undefined"} for item in slots))

    def test_cli_reports_implementation_failure_without_human_review(self) -> None:
        self.fixture.admit()
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "score",
                "--task", str(self.fixture.task),
                "--verifier", str(self.fixture.verifier),
                "--candidate", str(self.fixture.wrong_candidate),
                "--state", str(self.fixture.state),
                "--cache", str(self.fixture.cache),
                "--runtime-env", f"GAUNTLET_EVAL_COUNTER_DIR={self.fixture.counter}",
                "--runtime-env", f"GAUNTLET_EVAL_LIVENESS_FILE={self.fixture.liveness}",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["outcome"], "implementation_failure")


if __name__ == "__main__":
    unittest.main(verbosity=2)
