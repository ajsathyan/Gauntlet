# Durable Benchmark Receipt

Write receipts to the target repository's established Gauntlet or documentation area. If no convention exists, use a clearly named, repository-local performance evidence directory. Do not write into a protected source repository when another workflow owns an independent destination.

Prefer structured JSON for reproducibility and a short Markdown decision note only when material reasoning does not fit cleanly in fields. Keep raw measurement output in linked files when it is large. Do not rely on chat history.

Store baseline and candidate sample files in the schema accepted by [compare_benchmarks.py](../scripts/compare_benchmarks.py), then preserve its deterministic comparison output alongside this richer receipt.

Each comparator input must contain the same complete `metric`, `workload`, `environment`, and `protocol` objects, plus the same oracle identity and a passing oracle result. Evidence paths may differ between baseline and candidate. The comparator treats other differences as incomparable. `protocol` includes command, machine, dependency state, cache policy, concurrency, warm-up count, and the expensive-run declaration. Do not put comparison-critical identity only in surrounding Markdown.

## Required receipt fields

Record at minimum:

- receipt schema version, mode (`baseline-only` or `optimize`), timestamp, and artifact paths;
- source revision, working-tree state, and relevant changed files;
- performance surface, metric, unit, desired direction, and user-supplied target if present;
- workload purpose, exact commands, inputs, scale, setup, and correctness oracle;
- environment identity: hardware, OS, runtimes, dependencies, flags, variables with secrets redacted, services, and resource limits;
- cache policy, warm-up policy, concurrency, instrumentation, sample count, and outlier rule;
- complete raw baseline and candidate samples, failures, and summary statistic;
- absolute and relative change with enough precision to recompute it;
- profiler evidence, bottleneck diagnosis, hypothesis, prediction, and falsification condition;
- correctness, coverage, supported-environment, and adjacent-metric results;
- dependencies or complexity added, removed, generated, outsourced, or deferred;
- limitations, uncontrolled variables, unresolved regressions, and next measurement if any;
- gate result: `baseline-established`, `improvement-proved`, `no-material-improvement`, or `blocked`.

Use `candidate: null` and omit optimization-only evidence in `baseline-only` mode, but retain the complete protocol and raw baseline samples.

## Integrity and handoff

Hash or otherwise identify referenced raw artifacts so later work can detect invalidation. Record which changes invalidate the receipt, including source revision, workload, dependency, environment, profiler, benchmark protocol, or correctness-oracle changes.

A calling workflow should be able to reconstruct the conclusion from the receipt and linked artifacts alone. The receipt must distinguish observation from inference and must not claim unmeasured improvements.

## Compact example shape

```json
{
  "schema_version": 1,
  "mode": "optimize",
  "metric": {"name": "wall_time", "unit": "seconds", "direction": "lower-is-better"},
  "workload": {"id": "deterministic-tests", "inputDigest": "sha256:...", "scale": 842},
  "environment": {"os": "linux", "architecture": "x86_64", "runtime": "python-3.12", "flags": []},
  "oracle": {"id": "test-exit-and-count", "result": "pass", "evidence": ["842 passed"]},
  "protocol": {
    "command": "...", "machine": "ci-runner-1", "dependencyState": "lockfile-sha256:...",
    "cachePolicy": "warm", "concurrency": 1, "warmups": 1, "expensiveRunException": false
  },
  "samples": [12.4, 12.2, 12.5, 12.3, 12.4]
}
```

Baseline and candidate use separate files of this shape. The richer enclosing receipt may then record:

```json
{
  "schema_version": 1,
  "mode": "optimize",
  "source": {"revision": "...", "dirty": false},
  "surface": "deterministic-test-feedback",
  "target": null,
  "baseline_artifact": "baseline-samples.json",
  "candidate_artifact": "candidate-samples.json",
  "comparison_artifact": "comparison.json",
  "gate": "improvement-proved",
  "limitations": []
}
```

The shape is illustrative, not a substitute for the required fields above.
