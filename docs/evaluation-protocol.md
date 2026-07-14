# Paired Evaluation Protocol

`scripts/eval-run.py` runs deterministic paired development evaluations, records every launch, replays only independently invalid infrastructure attempts against unchanged state, checks adapter A/A conformance, and reports total-package and matching-ablation estimands. It is Python-stdlib-only.

The protocol consumes the task and hidden-oracle contract in `docs/evaluation-tasks.md`: task identity and starting state are versioned, scoring is automatic, implementation failures remain implementation failures, and verifier infrastructure is separately admitted. The runner does not inspect hidden verifier content.

## Study plan

A version 1 plan declares:

- development tasks with `task_id`, `task_version`, and a full starting-state SHA-256;
- exactly one `baseline` and one `total-package` condition;
- optional `ablation` conditions, each naming the one removed component;
- a condition package and adapter reference;
- nested repetitions; and
- cache states in canonical `cold`, `steady` order.

The baseline package is rejected if it contains a Gauntlet artifact. It may declare native subagent use. Core tasks are rejected. `templates/evaluation/core-registry.json` contains exactly twelve `reserved-undefined` slots and no task identity or task content.

Condition IDs are reporting labels. They do not enter execution IDs, pairing, adapter requests, validity classification, replay selection, or estimands. Adapter requests receive an opaque package digest and the package itself, so swapping reporting labels leaves outcomes unchanged.

## Intention-to-run and execution

The runner creates a matched pair for every task, nested repetition, and cache state. It rotates condition order deterministically within each cache state. Before an adapter starts, the runner atomically records the execution as `launched`; it then records one of:

- `pass`;
- `implementation_failure`; or
- controller-observed `infrastructure_invalid` with a condition-blind retry record.

Adapters cannot self-declare infrastructure invalidity. Process timeout, nonzero exit, malformed response, or an attempt to add canonical fields produces infrastructure invalidity. The runner owns task, condition, pair, execution, order, state, and attempt fields. Adapter results are limited to automatic outcome, numeric metrics, artifact references, and telemetry.

The execution request intentionally omits condition ID and condition role. It contains task identity/version, state digest, repetition, cache state, opaque condition token, and package. Every original launch remains in `intention_to_run`, including infrastructure invalidities. Replays never replace originals.

```sh
python3 scripts/eval-run.py execute \
  --plan /trusted/development-plan.json \
  --adapters /trusted/adapter-registry.json \
  --core-registry templates/evaluation/core-registry.json \
  --output /trusted/run.json
```

An existing output path is rejected to prevent selective rerun-to-success.

## State-conditional replay

Only a retryable, controller-observed infrastructure invalidity is eligible. Replay locates the condition by semantic identity and package digest, not its reporting label. The task version and starting-state digest, plus the condition package digest, must match the original record. A mismatch creates a `not_run` replay record. A valid replay appends attempt 2 while preserving the original attempt and its intention-to-run effect.

```sh
python3 scripts/eval-run.py replay \
  --plan /trusted/development-plan.json \
  --adapters /trusted/adapter-registry.json \
  --core-registry templates/evaluation/core-registry.json \
  --run /trusted/run.json \
  --output /trusted/replayed-run.json
```

## Estimands and report

Task is the generalization unit. The report first averages matched repetition effects within task, then averages task effects and computes uncertainty across tasks. It does not treat repetitions as independent task samples.

The total-package estimand compares automatic correctness for `total-package` versus `baseline`. Infrastructure-invalid launches remain in intention-to-run correctness as non-passes and are also reported by condition-blind invalidity code. Replays are counted separately and never substituted. Correctness-conditional efficiency uses duration only when both members of the matched pair pass.

Cold and steady-state estimates are reported separately. There is no composite score. A component result exists only when a matching `ablation` condition is present; whole-package A/B alone produces `undecidable_without_matching_ablations`.

```sh
python3 scripts/eval-run.py report --plan /trusted/development-plan.json --run /trusted/run.json
```

Example report excerpt:

```json
{
  "cache_behavior": {
    "cold": {
      "correctness_conditional_efficiency_ms": {"estimate": 5.0, "task_count": 1},
      "correctness_itt": {"estimate": 0.5, "task_count": 2}
    },
    "steady": {
      "correctness_conditional_efficiency_ms": {"estimate": 2.0, "task_count": 1},
      "correctness_itt": {"estimate": 0.5, "task_count": 2}
    }
  },
  "component_policy": "undecidable_without_matching_ablations",
  "replay_records": {"count": 0, "substituted_for_originals": false},
  "total_package_estimand": {"estimate": 0.5, "task_count": 2}
}
```

## Adapter conformance

Native and wrapped adapters must produce identical observations for selector behavior, nested-agent behavior, permissions, timeout propagation, artifacts, and telemetry. The conformance command writes command digests and a suite digest. Any wrapped, Mastra, or Harbor adapter used by a plan must carry a passing record for every dimension, tied to its exact command and a registered native command.

```sh
python3 scripts/eval-run.py conformance \
  --native-command /trusted/native-command.json \
  --wrapped-command /trusted/wrapped-command.json \
  --output /trusted/conformance.json
```

Mastra and Harbor are registry kinds only; neither is bundled, installed, or treated as conformant by declaration. Remaining unknowns require real adapter implementations and isolated A/A runs: their selector equivalence, nested-agent semantics, sandbox/permission translation, timeout cancellation, artifact fidelity, telemetry completeness, and whether their runtimes leak condition labels or mutate canonical state.

## Proof

Run:

```sh
python3 scripts/test-eval-run.py
```

The development-only suite covers full intention-to-run retention, reporting-label swaps, opposing component results, absent-ablation undecidability, task-nested repetitions, invalidity and state-conditional relabeled replay, cache-order balance, cold/steady reports, sealed registry enforcement, all six deliberately broken adapter dimensions, optional-adapter gates, and canonical-state override attempts. It does not define or launch a core task or external trial.
