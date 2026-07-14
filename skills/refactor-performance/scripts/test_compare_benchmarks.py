#!/usr/bin/env python3
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parent / "compare_benchmarks.py"


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], check=False, capture_output=True, text=True)


def benchmark(samples: list[float], *, command: str = "pytest", direction: str = "lower-is-better") -> dict:
    return {
        "schemaVersion": 1,
        "metric": {"name": "deterministic-test-duration", "unit": "seconds", "direction": direction},
        "workload": {"id": "unit-tests", "inputDigest": "sha256:work", "scale": 100},
        "environment": {"os": "linux", "architecture": "x86_64", "runtime": "python-3.12", "flags": []},
        "oracle": {"id": "pytest-exit-and-count", "result": "pass", "evidence": ["100 passed"]},
        "protocol": {
            "command": command,
            "machine": "ci-runner-1",
            "dependencyState": "lockfile-sha256:abc",
            "cachePolicy": "warm",
            "concurrency": 1,
            "warmups": 1,
            "expensiveRunException": False,
        },
        "samples": samples,
    }


class CompareBenchmarksTests(unittest.TestCase):
    def test_uses_median_and_checks_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            baseline = Path(temporary) / "baseline.json"
            candidate = Path(temporary) / "candidate.json"
            baseline.write_text(json.dumps(benchmark([100, 101, 99, 100, 500])), encoding="utf-8")
            candidate.write_text(json.dumps(benchmark([20, 21, 19, 20, 22])), encoding="utf-8")
            result = run_script(str(baseline), str(candidate), "--minimum-improvement", "75")
            self.assertEqual(result.returncode, 0, result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["statistic"], "median")
            self.assertEqual(payload["baselineMedian"], 100.0)
            self.assertEqual(payload["candidateMedian"], 20.0)
            self.assertEqual(payload["improvementPercent"], 80.0)
            self.assertTrue(payload["targetMet"])

    def test_refuses_incomparable_protocols(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            baseline = Path(temporary) / "baseline.json"
            candidate = Path(temporary) / "candidate.json"
            baseline.write_text(json.dumps(benchmark([10, 10, 10, 10, 10])), encoding="utf-8")
            candidate.write_text(json.dumps(benchmark([5, 5, 5, 5, 5], command="pytest -n auto")), encoding="utf-8")
            result = run_script(str(baseline), str(candidate))
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["comparable"])
            self.assertEqual(payload["protocolDifferences"][0]["field"], "command")

    def test_requires_five_samples_and_a_warmup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            baseline = Path(temporary) / "baseline.json"
            candidate = Path(temporary) / "candidate.json"
            invalid = benchmark([10, 10, 10, 10])
            invalid["protocol"]["warmups"] = 0
            baseline.write_text(json.dumps(invalid), encoding="utf-8")
            candidate.write_text(json.dumps(benchmark([5, 5, 5, 5, 5])), encoding="utf-8")
            result = run_script(str(baseline), str(candidate))
            self.assertEqual(result.returncode, 2)
            errors = json.loads(result.stdout)["error"]["details"]
            self.assertTrue(any("at least 5" in item for item in errors))
            self.assertTrue(any("warmups" in item for item in errors))

    def test_regression_and_equal_result_do_not_succeed_without_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            baseline = Path(temporary) / "baseline.json"
            candidate = Path(temporary) / "candidate.json"
            baseline.write_text(json.dumps(benchmark([99, 100, 100, 101, 100])), encoding="utf-8")
            for samples in ([100, 101, 101, 102, 101], [99, 100, 100, 101, 100]):
                candidate.write_text(json.dumps(benchmark(samples)), encoding="utf-8")
                result = run_script(str(baseline), str(candidate))
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertFalse(json.loads(result.stdout)["targetMet"])

    def test_noisy_overlap_does_not_prove_improvement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            baseline = Path(temporary) / "baseline.json"
            candidate = Path(temporary) / "candidate.json"
            baseline.write_text(json.dumps(benchmark([90, 100, 110, 100, 100])), encoding="utf-8")
            candidate.write_text(json.dumps(benchmark([85, 95, 105, 95, 95])), encoding="utf-8")
            result = run_script(str(baseline), str(candidate))
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertFalse(json.loads(result.stdout)["improvementProved"])

    def test_rejects_changed_workload_environment_or_oracle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            baseline = Path(temporary) / "baseline.json"
            candidate = Path(temporary) / "candidate.json"
            original = benchmark([10, 10, 10, 10, 10])
            baseline.write_text(json.dumps(original), encoding="utf-8")
            for field, replacement in (
                ("workload", {"id": "smaller", "inputDigest": "sha256:x", "scale": 10}),
                ("environment", {"os": "other", "architecture": "x86_64", "runtime": "python-3.12", "flags": []}),
                ("oracle", {"id": "other", "result": "pass", "evidence": ["ok"]}),
            ):
                changed = benchmark([5, 5, 5, 5, 5])
                changed[field] = replacement
                candidate.write_text(json.dumps(changed), encoding="utf-8")
                result = run_script(str(baseline), str(candidate))
                self.assertEqual(result.returncode, 1, result.stdout)
                expected_field = "oracle.id" if field == "oracle" else field
                self.assertIn(expected_field, {item["field"] for item in json.loads(result.stdout)["protocolDifferences"]})

    def test_cold_and_expensive_protocols_are_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            baseline = Path(temporary) / "baseline.json"
            candidate = Path(temporary) / "candidate.json"
            before = benchmark([10, 11, 10])
            after = benchmark([5, 6, 5])
            for payload in (before, after):
                payload["protocol"].update({
                    "cachePolicy": "cold", "warmups": 0,
                    "expensiveRunException": True, "expensiveRunReason": "each run costs one hour",
                })
            baseline.write_text(json.dumps(before), encoding="utf-8")
            candidate.write_text(json.dumps(after), encoding="utf-8")
            self.assertEqual(run_script(str(baseline), str(candidate)).returncode, 0)

    def test_zero_target_allows_only_positive_proved_gain_and_negative_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            baseline = Path(temporary) / "baseline.json"
            candidate = Path(temporary) / "candidate.json"
            baseline.write_text(json.dumps(benchmark([10, 10, 10, 10, 10])), encoding="utf-8")
            candidate.write_text(json.dumps(benchmark([5, 5, 5, 5, 5])), encoding="utf-8")
            self.assertEqual(run_script(str(baseline), str(candidate), "--minimum-improvement", "0").returncode, 0)
            self.assertEqual(run_script(str(baseline), str(candidate), "--minimum-improvement", "-1").returncode, 2)

    def test_higher_is_better_direction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            baseline = Path(temporary) / "baseline.json"
            candidate = Path(temporary) / "candidate.json"
            baseline.write_text(json.dumps(benchmark([10, 11, 10, 11, 10], direction="higher-is-better")), encoding="utf-8")
            candidate.write_text(json.dumps(benchmark([20, 21, 20, 21, 20], direction="higher-is-better")), encoding="utf-8")
            result = run_script(str(baseline), str(candidate))
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(json.loads(result.stdout)["improvementProved"])

    def test_rejects_empty_protocol_identity_and_exception_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            baseline = Path(temporary) / "baseline.json"
            candidate = Path(temporary) / "candidate.json"
            for field, invalid in (("command", None), ("machine", ""), ("dependencyState", "  "), ("cachePolicy", None)):
                payload = benchmark([10, 10, 10, 10, 10])
                payload["protocol"][field] = invalid
                baseline.write_text(json.dumps(payload), encoding="utf-8")
                candidate.write_text(json.dumps(benchmark([5, 5, 5, 5, 5])), encoding="utf-8")
                self.assertEqual(run_script(str(baseline), str(candidate)).returncode, 2)
            for reason in (None, "", "   ", "short"):
                before = benchmark([10, 10, 10])
                after = benchmark([5, 5, 5])
                for payload in (before, after):
                    payload["protocol"].update({"expensiveRunException": True, "expensiveRunReason": reason})
                baseline.write_text(json.dumps(before), encoding="utf-8")
                candidate.write_text(json.dumps(after), encoding="utf-8")
                self.assertEqual(run_script(str(baseline), str(candidate)).returncode, 2)

    def test_rejects_missing_workload_and_environment_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            baseline = Path(temporary) / "baseline.json"
            candidate = Path(temporary) / "candidate.json"
            candidate.write_text(json.dumps(benchmark([5, 5, 5, 5, 5])), encoding="utf-8")
            mutations = []
            for field in ("id", "inputDigest", "scale"):
                payload = benchmark([10, 10, 10, 10, 10])
                payload["workload"].pop(field)
                mutations.append(payload)
            for field in ("os", "architecture", "runtime", "flags"):
                payload = benchmark([10, 10, 10, 10, 10])
                payload["environment"].pop(field)
                mutations.append(payload)
            for payload in mutations:
                baseline.write_text(json.dumps(payload), encoding="utf-8")
                self.assertEqual(run_script(str(baseline), str(candidate)).returncode, 2)


if __name__ == "__main__":
    unittest.main()
