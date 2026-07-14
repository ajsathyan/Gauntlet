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


def benchmark(samples: list[float], *, command: str = "pytest") -> dict:
    return {
        "schemaVersion": 1,
        "metric": {"name": "deterministic-test-duration", "unit": "seconds", "direction": "lower-is-better"},
        "protocol": {
            "command": command,
            "machine": "ci-runner-1",
            "dependencyState": "lockfile-sha256:abc",
            "cachePolicy": "warm",
            "concurrency": 1,
            "warmups": 1,
        },
        "samples": samples,
    }


class CompareBenchmarksTests(unittest.TestCase):
    def test_uses_median_and_checks_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            baseline = Path(temporary) / "baseline.json"
            candidate = Path(temporary) / "candidate.json"
            baseline.write_text(json.dumps(benchmark([100, 101, 99, 100, 500])), encoding="utf-8")
            candidate.write_text(json.dumps(benchmark([20, 21, 19, 20, 200])), encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
