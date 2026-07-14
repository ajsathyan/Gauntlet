# Evaluation Task Infrastructure

`scripts/eval-task.py` admits and scores development evaluation tasks against hidden, digest-pinned verifiers. It is deterministic and Python-stdlib-only. Routine scoring is automatic; human review is not part of the score.

The twelve study slots in `templates/evaluation/core-slots.json` are reserved and undefined. The controller rejects every `CORE-01` through `CORE-12` identity. This infrastructure must be proven with development fixtures before any separate decision defines or runs a core task.

## Visible and hidden packages

The implementation agent receives only the visible task directory. Its `task.json` uses schema version 1 and contains:

- a development task ID and version;
- `slot: development`;
- a verifier ID;
- the SHA-256 digest of the entire hidden verifier bundle; and
- the immutable verifier image digest.

The trusted evaluator separately mounts the hidden verifier directory. Its `verifier.json` contains the adapter command, reference solution, starting state, regressions, plausible wrong solutions, and one cheap liveness probe. The task and verifier directories must be disjoint. Symlinks are rejected, and every hidden fixture path must resolve inside the verifier directory.

The hidden verifier contract is:

```json
{"op":"score","task_id":"development-example","candidate":"/isolated/path"}
```

or:

```json
{"op":"liveness","task_id":"development-example","probe":"adapter-ready"}
```

The adapter reads one request from standard input and writes one JSON object containing a boolean `passed`. A nonzero exit, timeout, malformed response, or missing boolean is an infrastructure failure. A healthy score with `passed: false` is an implementation failure.

## Admission and preflight

Admission validates isolation metadata, exact task/verifier identity, a full image digest, `mutable: false`, and the pinned verifier-bundle digest. It then proves the automatic oracle against four required classes:

- the untouched starting state fails;
- the reference solution passes;
- at least one regression fails; and
- at least one plausible wrong solution fails.

Those expensive immutable checks are cached by the visible task digest, hidden bundle digest, image digest, and schema version. Cache entries are reused only when every field matches. Admission and each preflight run one current liveness probe after the immutable checks. There is no background or continuous healthy-path verifier loop.

Admission state and the cache are trusted evaluator state. Keep both outside the implementation workspace and unavailable to implementation agents. Any shared-mode declaration, mutable image, digest mismatch, hidden-bundle mutation, invalid oracle case, or liveness failure writes quarantine state. A quarantined task must be admitted again after its cause is resolved.

Example commands:

```sh
python3 scripts/eval-task.py admit \
  --task /visible/task \
  --verifier /trusted/hidden-verifier \
  --state /trusted/state/admission.json \
  --cache /trusted/state/immutable-cache.json

python3 scripts/eval-task.py preflight \
  --task /visible/task \
  --verifier /trusted/hidden-verifier \
  --state /trusted/state/admission.json \
  --cache /trusted/state/immutable-cache.json

python3 scripts/eval-task.py score \
  --task /visible/task \
  --verifier /trusted/hidden-verifier \
  --candidate /isolated/submission \
  --state /trusted/state/admission.json \
  --cache /trusted/state/immutable-cache.json
```

The optional `--runtime-env GAUNTLET_EVAL_NAME=value` flag passes evaluator-owned runtime state to an adapter. Do not accept these values from an implementation agent.

## Retry classification

`classify-retry` consumes recorded outcomes. A failure-only triage opinion cannot relabel an automatic `implementation_failure` as `infrastructure_invalid`. A retry is automatic only when every recorded outcome is already an independently observed infrastructure invalidity. Any pass finishes the execution; any implementation failure remains an implementation failure.

```sh
python3 scripts/eval-task.py classify-retry --attempts /trusted/state/attempts.json
```

## Isolation boundary

The controller verifies digest pins, directory separation, contained paths, immutable execution, sanitized adapter environment, and state transitions. A command adapter is replaceable so a trusted runner can launch a local sandbox, container, VM, or remote grading service.

The controller cannot make a filesystem path secret from a process that already has host-level read access, nor can metadata prove that a named image actually ran. Production use therefore requires the orchestrator to withhold the verifier mount, admission state, cache, adapter command, and runtime environment from implementation agents, and the adapter must enforce the declared image digest and network/process isolation. These are host responsibilities and are the remaining isolation limit of the local scaffold.

## Proof

Run:

```sh
python3 scripts/test-eval-task.py
```

The suite covers clean starting state, reference solution, regressions, phrase-bearing wrong solutions, shared mode, mutable images, hidden verifier tampering, stale cache, repeated cached preflight, current liveness failure, automatic scoring, failure-only retry triage, path separation, and sealed core slots. It defines and runs only a development fixture.
