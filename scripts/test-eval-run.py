#!/usr/bin/env python3
"""Behavioral tests for paired evaluation execution, replay, and reporting."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


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


class RunnerFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.adapter = root / "adapter.py"
        self.adapter.write_text(ADAPTER)
        self.native = [sys.executable, str(self.adapter)]
        self.wrapped = [sys.executable, str(self.adapter), "--wrapped"]
        self.core = json.loads((SCRIPT.parent.parent / "templates" / "evaluation" / "core-registry.json").read_text())
        self.conformance = eval_run.conformance(self.native, self.wrapped)
        assert self.conformance["status"] == "pass"
        self.adapters = self.adapter_registry(self.native, self.wrapped, self.conformance)
        self.plan = self.make_plan()

    def adapter_registry(self, native: list[str], wrapped: list[str], proof: dict) -> dict:
        return {
            "adapters": {
                "native": {"command": native, "kind": "native"},
                "wrapped": {"command": wrapped, "conformance": proof, "kind": "wrapped"},
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
        return eval_run.execute(plan or self.plan, self.core, adapters or self.adapters)


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
        proof = eval_run.conformance(self.fixture.native, wrapped)
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

    def test_conformance_detects_each_broken_adapter_dimension(self) -> None:
        for dimension in eval_run.DIMENSIONS:
            with self.subTest(dimension=dimension):
                broken = [sys.executable, str(self.fixture.adapter), "--wrapped", "--break-dimension", dimension]
                result = eval_run.conformance(self.fixture.native, broken)
                self.assertEqual(result["status"], "fail")
                self.assertIn(dimension, result["mismatches"])

    def test_optional_external_adapter_requires_matching_conformance(self) -> None:
        adapters = copy.deepcopy(self.fixture.adapters)
        adapters["adapters"]["wrapped"]["kind"] = "mastra"
        del adapters["adapters"]["wrapped"]["conformance"]
        with self.assertRaisesRegex(eval_run.EvalRunError, "requires passing A/A conformance"):
            self.fixture.execute(adapters=adapters)

    def test_external_adapter_rejects_self_attested_conformance(self) -> None:
        adapters = copy.deepcopy(self.fixture.adapters)
        proof = adapters["adapters"]["wrapped"]["conformance"]
        adapters["adapters"]["wrapped"]["conformance"] = {
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
        proof = eval_run.conformance(self.fixture.native, wrapped)
        adapters = self.fixture.adapter_registry(self.fixture.native, wrapped, proof)
        run = self.fixture.execute(adapters=adapters)
        treatment = [item for item in run["intention_to_run"] if item["condition_identity"] == "total-package"]
        self.assertTrue(all(item["outcome"] == "infrastructure_invalid" for item in treatment))
        self.assertTrue(all(item["invalidity"]["code"] == "canonical-state-override" for item in treatment))
        self.assertTrue(all(item["invalidity"]["retryable"] is False for item in treatment))
        self.assertEqual({item["task_id"] for item in treatment}, {"dev-one", "dev-two"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
