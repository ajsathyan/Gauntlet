#!/usr/bin/env python3
"""Behavioral tests for paired evaluation execution, replay, and reporting."""

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


SCRIPT = Path(__file__).with_name("eval-run.py")
SPEC = importlib.util.spec_from_file_location("eval_run", SCRIPT)
eval_run = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(eval_run)


ADAPTER = r'''#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--break-dimension")
parser.add_argument("--gate")
parser.add_argument("--override-state", action="store_true")
parser.add_argument("--wrapped", action="store_true")
args = parser.parse_args()
request = json.loads(sys.stdin.read())

if request["op"] == "conformance":
    observation = request["fixture"]
    if args.break_dimension == request["dimension"]:
        observation = {"broken": request["dimension"]}
    print(json.dumps({"dimension": request["dimension"], "observation": observation}, sort_keys=True))
    raise SystemExit(0)

if args.gate:
    gate = Path(args.gate)
    marker = gate.with_suffix(".used")
    if gate.read_text().strip() == "fail-once" and not marker.exists():
        marker.write_text("used")
        print("injected infrastructure failure", file=sys.stderr)
        raise SystemExit(9)

package = request["package"]
passed = bool(package["outcome_by_task"].get(request["task_id"], False))
response = {
    "artifacts": package.get("artifacts", []),
    "metrics": {"duration_ms": package.get("duration_by_cache", {}).get(request["cache_state"], 10)},
    "outcome": "pass" if passed else "implementation_failure",
    "telemetry": {"request_keys": sorted(request), "wrapped": args.wrapped},
}
if args.override_state:
    response["task_id"] = "adapter-redefined-task"
print(json.dumps(response, sort_keys=True))
'''


def state_digest(character: str) -> str:
    return "sha256:" + character * 64


def equivalence_record(native: list[str], wrapped: list[str]) -> dict:
    comparisons = []
    for dimension in eval_run.DIMENSIONS:
        request = eval_run.equivalence_request(dimension)
        observation = {"dimension": dimension, "observation": request["fixture"]}
        comparisons.append({"dimension": dimension, "native": observation, "passed": True, "wrapped": observation})
    return {
        "comparisons": comparisons,
        "dimensions": list(eval_run.DIMENSIONS),
        "mismatches": [],
        "native_command_digest": eval_run.command_digest(native),
        "schema_version": 1,
        "status": "pass",
        "suite_digest": "sha256:" + eval_run.digest(comparisons),
        "wrapped_command_digest": eval_run.command_digest(wrapped),
    }


class RunnerFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.adapter = root / "adapter.py"
        self.adapter.write_text(ADAPTER)
        self.native = [sys.executable, str(self.adapter)]
        self.wrapped = [sys.executable, str(self.adapter), "--wrapped"]
        self.core = json.loads((SCRIPT.parent.parent / "templates" / "evaluation" / "core-registry.json").read_text())
        self.equivalence = equivalence_record(self.native, self.wrapped)
        self.adapters = self.adapter_registry(self.native, self.wrapped, self.equivalence)
        self.plan = self.make_plan()

    def adapter_registry(self, native: list[str], wrapped: list[str], proof: dict) -> dict:
        return {
            "adapters": {
                "native": {"command": native, "kind": "native"},
                "wrapped": {"command": wrapped, "equivalence": proof, "kind": "wrapped"},
            },
            "schema_version": 1,
        }

    def make_plan(self, *, ablation: bool = False) -> dict:
        conditions = [
            {
                "adapter": "native", "condition_id": "control-label", "package": {
                    "duration_by_cache": {"cold": 30, "steady": 10},
                    "native_subagents": True,
                    "outcome_by_task": {"dev-one": False, "dev-two": False},
                }, "role": "baseline",
            },
            {
                "adapter": "wrapped", "condition_id": "treatment-label", "package": {
                    "artifacts": ["workflow-receipt"], "duration_by_cache": {"cold": 35, "steady": 12},
                    "gauntlet_enabled": True,
                    "outcome_by_task": {"dev-one": True, "dev-two": False},
                }, "role": "total-package",
            },
        ]
        if ablation:
            conditions.append({
                "adapter": "wrapped", "component": "planner", "condition_id": "without-planner", "package": {
                    "artifacts": ["workflow-receipt"], "duration_by_cache": {"cold": 33, "steady": 11},
                    "gauntlet_enabled": True,
                    "outcome_by_task": {"dev-one": True, "dev-two": True},
                }, "role": "ablation",
            })
        return {
            "cache_states": ["cold", "steady"], "conditions": conditions, "repetitions": 2,
            "schema_version": 1, "study_id": "development-paired-study",
            "tasks": [
                {"slot": "development", "state_digest": state_digest("1"), "task_id": "dev-one", "task_version": 1},
                {"slot": "development", "state_digest": state_digest("2"), "task_id": "dev-two", "task_version": 1},
            ],
        }

    def execute(self, plan: dict | None = None, adapters: dict | None = None) -> dict:
        registry = adapters or self.adapters
        proof = next((
            item.get("equivalence", item.get("conformance"))
            for item in registry["adapters"].values()
            if item.get("kind") != "native" and isinstance(item.get("equivalence", item.get("conformance")), dict)
        ), None)
        if proof is None:
            return eval_run.execute(plan or self.plan, self.core, registry)
        with patch.object(eval_run, "adapter_equivalence", return_value=proof):
            return eval_run.execute(plan or self.plan, self.core, registry)


class EvalRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.fixture = RunnerFixture(Path(self.temporary.name))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_matched_pairs_retain_every_launched_execution(self) -> None:
        run = self.fixture.execute()
        self.assertEqual(len(run["intention_to_run"]), 2 * 2 * 2 * 2)
        pairs = {}
        for record in run["intention_to_run"]:
            pairs.setdefault(record["pair_id"], set()).add(record["condition_identity"])
        self.assertTrue(all(identities == {"baseline", "total-package"} for identities in pairs.values()))
        self.assertNotIn("launched", {item["outcome"] for item in run["intention_to_run"]})

    def test_label_swap_does_not_change_outcomes_or_estimands(self) -> None:
        first_run = self.fixture.execute()
        swapped = copy.deepcopy(self.fixture.plan)
        swapped["conditions"][0]["condition_id"] = "renamed-z"
        swapped["conditions"][1]["condition_id"] = "renamed-a"
        second_run = self.fixture.execute(swapped)
        first_outcomes = [(item["execution_id"], item["outcome"]) for item in first_run["intention_to_run"]]
        second_outcomes = [(item["execution_id"], item["outcome"]) for item in second_run["intention_to_run"]]
        self.assertEqual(first_outcomes, second_outcomes)
        self.assertEqual(
            eval_run.report(self.fixture.plan, first_run)["total_package_estimand"],
            eval_run.report(swapped, second_run)["total_package_estimand"],
        )

    def test_total_package_and_opposing_component_estimands_stay_separate(self) -> None:
        plan = self.fixture.make_plan(ablation=True)
        report = eval_run.report(plan, self.fixture.execute(plan))
        self.assertEqual(report["total_package_estimand"]["estimate"], 0.5)
        self.assertEqual(report["component_estimands"]["planner"]["correctness_contribution"]["estimate"], -0.5)
        self.assertEqual(report["component_estimands"]["planner"]["decision_scope"], "matching-ablation-only")

    def test_component_policy_is_undecidable_without_matching_ablation(self) -> None:
        report = eval_run.report(self.fixture.plan, self.fixture.execute())
        self.assertEqual(report["component_policy"], "undecidable_without_matching_ablations")
        self.assertEqual(report["component_estimands"], {})

    def test_repetitions_are_nested_under_task_generalization_units(self) -> None:
        report = eval_run.report(self.fixture.plan, self.fixture.execute())
        estimate = report["total_package_estimand"]
        self.assertEqual(estimate["task_count"], 2)
        self.assertEqual(estimate["repetition_count"], 8)
        self.assertEqual(report["nested_repetitions"]["task_generalization_count"], 2)
        self.assertEqual(report["nested_repetitions"]["launched_execution_count"], 16)

    def test_invalid_execution_is_retained_and_replay_is_state_conditional_and_blind(self) -> None:
        gate = self.fixture.root / "gate"
        gate.write_text("fail-once")
        wrapped = [sys.executable, str(self.fixture.adapter), "--wrapped", "--gate", str(gate)]
        proof = eval_run.adapter_equivalence(self.fixture.native, wrapped)
        adapters = self.fixture.adapter_registry(self.fixture.native, wrapped, proof)
        run = self.fixture.execute(adapters=adapters)
        invalid = [item for item in run["intention_to_run"] if item["outcome"] == "infrastructure_invalid"]
        self.assertEqual(len(invalid), 1)
        self.assertTrue(invalid[0]["invalidity"]["condition_blind"])

        gate.write_text("up")
        relabeled = copy.deepcopy(self.fixture.plan)
        relabeled["conditions"][0]["condition_id"] = "opaque-a"
        relabeled["conditions"][1]["condition_id"] = "opaque-b"
        replayed = eval_run.replay(relabeled, self.fixture.core, adapters, run)
        self.assertEqual(len(replayed["intention_to_run"]), len(run["intention_to_run"]))
        self.assertEqual(replayed["replays"][0]["outcome"], "pass")
        self.assertFalse(eval_run.report(self.fixture.plan, replayed)["replay_records"]["substituted_for_originals"])
        keys = replayed["replays"][0]["telemetry"]["request_keys"]
        self.assertNotIn("condition_id", keys)
        self.assertNotIn("condition_identity", keys)

        changed = copy.deepcopy(self.fixture.plan)
        changed["tasks"][0]["state_digest"] = state_digest("3")
        denied = eval_run.replay(changed, self.fixture.core, adapters, run)
        self.assertEqual(denied["replays"][0]["outcome"], "not_run")
        self.assertEqual(denied["replays"][0]["reason"], "state_or_package_mismatch")

    def test_cache_order_is_balanced_and_reports_are_separate(self) -> None:
        run = self.fixture.execute()
        by_cache = {cache: [] for cache in eval_run.CACHE_STATES}
        for record in run["intention_to_run"]:
            if record["condition_identity"] == "baseline":
                by_cache[record["cache_state"]].append(record["order_index"])
        self.assertEqual(set(by_cache["cold"]), {0, 1})
        self.assertEqual(set(by_cache["steady"]), {0, 1})
        report = eval_run.report(self.fixture.plan, run)
        self.assertEqual(set(report["cache_behavior"]), {"cold", "steady"})
        self.assertIn("correctness_conditional_efficiency_ms", report["cache_behavior"]["cold"])
        self.assertNotIn("composite_score", report)

    def test_core_registry_is_sealed_and_core_task_execution_is_rejected(self) -> None:
        expected = [{"slot": f"CORE-{index:02d}", "status": "reserved-undefined"} for index in range(1, 13)]
        self.assertEqual(self.fixture.core["slots"], expected)
        plan = copy.deepcopy(self.fixture.plan)
        plan["tasks"][0]["slot"] = "CORE-01"
        with self.assertRaisesRegex(eval_run.EvalRunError, "core slots are sealed"):
            self.fixture.execute(plan)

    def test_equivalence_detects_each_broken_adapter_dimension(self) -> None:
        broken = [sys.executable, str(self.fixture.adapter), "--wrapped", "--break-dimension", "permission"]
        live = eval_run.adapter_equivalence(self.fixture.native, broken)
        self.assertEqual(live["status"], "fail")
        self.assertIn("permission", live["mismatches"])

        for dimension in eval_run.DIMENSIONS:
            with self.subTest(dimension=dimension):
                proof = copy.deepcopy(self.fixture.equivalence)
                index = list(eval_run.DIMENSIONS).index(dimension)
                proof["comparisons"][index]["wrapped"] = {"dimension": dimension, "observation": {"broken": True}}
                proof["suite_digest"] = "sha256:" + eval_run.digest(proof["comparisons"])
                with self.assertRaisesRegex(eval_run.EvalRunError, f"comparison {dimension} did not pass"):
                    eval_run.validate_equivalence_record(proof, "wrapped")

    def test_plan_admission_rechecks_live_equivalence(self) -> None:
        mismatch = copy.deepcopy(self.fixture.equivalence)
        mismatch["suite_digest"] = "sha256:" + "0" * 64
        with patch.object(eval_run, "adapter_equivalence", return_value=mismatch):
            with self.assertRaisesRegex(eval_run.EvalRunError, "failed live A/A equivalence"):
                eval_run.execute(self.fixture.plan, self.fixture.core, self.fixture.adapters)

    def test_optional_external_adapter_requires_matching_equivalence(self) -> None:
        adapters = copy.deepcopy(self.fixture.adapters)
        adapters["adapters"]["wrapped"]["kind"] = "mastra"
        del adapters["adapters"]["wrapped"]["equivalence"]
        with self.assertRaisesRegex(eval_run.EvalRunError, "requires passing A/A equivalence"):
            self.fixture.execute(adapters=adapters)

    def test_adapter_environment_passes_provider_auth_names_only(self) -> None:
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "openai-secret", "ANTHROPIC_API_KEY": "anthropic-secret",
            "UNRELATED_SECRET": "must-not-pass",
        }, clear=False):
            environment = eval_run.adapter_environment()
        self.assertEqual(environment["OPENAI_API_KEY"], "openai-secret")
        self.assertEqual(environment["ANTHROPIC_API_KEY"], "anthropic-secret")
        self.assertNotIn("UNRELATED_SECRET", environment)

    def test_adapter_result_rejects_nonfinite_metrics_and_unsafe_artifact_references(self) -> None:
        adapter = {"command": ["unused"], "timeout_seconds": 1}
        result = {"artifacts": [], "metrics": {"duration_ms": float("nan")}, "outcome": "pass", "telemetry": {}}
        with patch.object(eval_run, "run_process", return_value=result):
            with self.assertRaisesRegex(eval_run.AdapterFailure, "metrics must be numeric"):
                eval_run.invoke_execution(adapter, {})
        result = {"artifacts": ["../private"], "metrics": {}, "outcome": "pass", "telemetry": {}}
        with patch.object(eval_run, "run_process", return_value=result):
            with self.assertRaisesRegex(eval_run.AdapterFailure, "safe bounded relative"):
                eval_run.invoke_execution(adapter, {})

    def test_paired_plan_requires_one_matched_harness_model_cell(self) -> None:
        adapters = copy.deepcopy(self.fixture.adapters)
        cell = {
            "harness": "codex-cli", "model": "gpt-test", "permission_mode": "workspace-write",
            "harness_version": "9.9.0", "reasoning_effort": "medium", "resource_profile": "standard",
        }
        adapters["adapters"]["native"]["harness_cell"] = copy.deepcopy(cell)
        adapters["adapters"]["wrapped"]["harness_cell"] = copy.deepcopy(cell)
        self.fixture.execute(adapters=adapters)
        adapters["adapters"]["wrapped"]["harness_cell"]["model"] = "different-model"
        with self.assertRaisesRegex(eval_run.EvalRunError, "same harness version, model, effort"):
            self.fixture.execute(adapters=adapters)

    def test_external_adapter_rejects_self_attested_equivalence(self) -> None:
        adapters = copy.deepcopy(self.fixture.adapters)
        proof = adapters["adapters"]["wrapped"]["equivalence"]
        adapters["adapters"]["wrapped"]["equivalence"] = {
            "dimensions": list(eval_run.DIMENSIONS),
            "mismatches": [],
            "native_command_digest": proof["native_command_digest"],
            "schema_version": 1,
            "status": "pass",
            "wrapped_command_digest": proof["wrapped_command_digest"],
        }
        with self.assertRaisesRegex(eval_run.EvalRunError, "complete comparison evidence"):
            self.fixture.execute(adapters=adapters)

    def test_report_is_bound_to_exact_study_plan(self) -> None:
        run = self.fixture.execute()
        unrelated = copy.deepcopy(self.fixture.plan)
        unrelated["study_id"] = "unrelated-study"
        with self.assertRaisesRegex(eval_run.EvalRunError, "does not match the supplied study plan"):
            eval_run.report(unrelated, run)
        with self.assertRaisesRegex(eval_run.EvalRunError, "schema_version must be 1"):
            eval_run.report({}, run)

    def test_adapter_cannot_redefine_canonical_state(self) -> None:
        wrapped = [sys.executable, str(self.fixture.adapter), "--wrapped", "--override-state"]
        proof = eval_run.adapter_equivalence(self.fixture.native, wrapped)
        adapters = self.fixture.adapter_registry(self.fixture.native, wrapped, proof)
        run = self.fixture.execute(adapters=adapters)
        treatment = [item for item in run["intention_to_run"] if item["condition_identity"] == "total-package"]
        self.assertTrue(all(item["outcome"] == "infrastructure_invalid" for item in treatment))
        self.assertTrue(all(item["invalidity"]["code"] == "canonical-state-override" for item in treatment))
        self.assertTrue(all(item["invalidity"]["retryable"] is False for item in treatment))
        self.assertEqual({item["task_id"] for item in treatment}, {"dev-one", "dev-two"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
