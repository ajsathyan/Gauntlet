# Evaluation Harness Adapters

`scripts/eval-harness.py` is the trusted boundary between Gauntlet's paired evaluation controller and a version-pinned Codex CLI process. It is Python-stdlib-only, keeps task prompts on standard input, materializes a fresh candidate workspace for every execution ID, runs the hidden scorer only after the coding process exits, and returns bounded metrics, artifact references, and telemetry without returning prompt or transcript content.

The adapter infrastructure is complete without defining a core task. `templates/evaluation/harnesses/trusted-tasks.json` therefore has an empty task map. The later task-selection decision fills that trusted registry with each task's starting tree, prompt path, scorer command, state digest, and artifact allowlist. The adapter recomputes the starting-tree digest before use. Core identities remain rejected until the sealed twelve-task set is approved.

`templates/evaluation/harnesses/adapter-registry.json.tmpl` connects one resolved harness manifest and trusted task registry to `scripts/eval-run.py`. Baseline and treatment normally reference the same `direct-reference` adapter; their profile package selects the isolated baseline or treatment configuration. The registry's `harness_cell` makes the runner enforce all non-treatment fields before launch.

## Harness manifests

Start from `templates/evaluation/harnesses/codex-cli.json.tmpl`.

A resolved manifest pins an absolute CLI executable, harness version, and model; records the provider-native reasoning and permission controls; declares every capability dimension; names environment variables to inherit without storing their values; and gives baseline and treatment separate `CODEX_HOME` paths. Other profile environment values must match. Prompt content is never placed in process arguments. Schema version 1 rejects untyped extra CLI arguments so they cannot silently override a matched field.

Codex CLI is launched through non-interactive `codex exec` JSON mode with ephemeral session persistence, an explicit model, sandbox, working directory, reasoning effort, and approval policy. This command surface is version-pinned because the CLI can change.

```sh
python3 scripts/eval-harness.py validate --manifest /trusted/codex.json
python3 scripts/eval-harness.py command --manifest /trusted/codex.json --workspace /isolated/candidate
python3 scripts/eval-harness.py probe --manifest /trusted/codex.json
```

`probe` runs only the CLI version command. It is a current liveness check and spends no model turn. A missing executable, broken shim, timeout, or version-pin mismatch reports unavailable.

## Paired study cells

One paired plan is one harness/model cell. Baseline, treatment, and any ablation must use the same harness and harness version, model, provider-native reasoning setting, permission mode, and resource profile. `scripts/eval-run.py` rejects a mixed cell.

Different Codex models run as separate blocks. Within each block, Gauntlet and no-Gauntlet remain the only intended difference. Comparing one model to another is not an A/A test of Gauntlet.

## Harness capability contract and A/A equivalence

Conformance is the established engineering term for checking whether an implementation satisfies a defined contract. Gauntlet uses **harness capability contract** for that per-harness check because it is clearer about what is being established.

A/A equivalence is narrower: two supposedly equivalent paths through the same version-pinned harness and model receive neutral fixtures. Gauntlet compares their observable control-plane behavior across single-agent execution, custom profiles, nested agents, concurrent lanes, resume/interrupt, permissions, PTY behavior, timeout handling, artifacts, telemetry, and failure behavior. It does not compare stochastic prose byte-for-byte.

```sh
python3 scripts/eval-harness.py aa-compare \
  --left /trusted/native-observations.json \
  --right /trusted/wrapped-observations.json
```

The comparator rejects cross-harness, cross-version, cross-model, or cross-resource inputs before producing an equivalence claim. A deliberate difference in any required dimension fails. The existing `eval-run.py adapter-equivalence` command performs the live command-boundary check across the same eleven neutral fixtures; `conformance` remains a compatibility alias.

Direct Codex CLI is the reference adapter. Harbor, Mastra, or another wrapper must pass A/A equivalence against it for the same cell before its results can be treated as the same execution path.

## Trusted task registry and execution

The trusted registry is evaluator-owned and unavailable to implementation agents. A development entry contains:

- an immutable starting tree and full starting-state digest;
- the visible prompt file;
- a hidden scorer command that accepts `{"op":"score","task_id":"...","candidate":"..."}` and returns `{"passed":true|false}`; and
- safe relative artifact paths.

The `adapter` subcommand reads the condition-blind execution request from standard input. It rejects a wrong starting digest, unknown task, core identity, symlinked starting tree, unsafe or reused execution ID, non-finite metrics, secret values embedded in a manifest, malformed or oversized event streams, or invalid scorer results. Its starting-tree digest is identical to the task-admission controller's canonical names, modes, and contents digest. Provider credentials pass by allowlisted environment-variable name to the coding CLI but are removed from the scorer environment. A timeout terminates the adapter process group. CLI nonzero completion remains an implementation failure; inability to start, timeout, or scorer infrastructure failure exits the adapter and is classified by the parent controller as infrastructure invalidity.

```sh
python3 scripts/eval-harness.py adapter \
  --manifest /trusted/codex.json \
  --tasks /trusted/tasks.json \
  --workspace-root /isolated/executions
```

## Current machine state

The adapter code and deterministic fake-CLI proof do not require provider credentials or model spend. A live harness/model cell still requires its CLI to be installed, authenticated, version-pinned, and available to `probe`. Live capability fixtures run only after the model and harness cells are selected; they do not depend on the twelve core tasks.

Official command reference: [Codex non-interactive mode](https://github.com/openai/codex/blob/main/codex-rs/README.md).

## Proof

Run:

```sh
python3 scripts/test-eval-harness.py
python3 scripts/test-eval-run.py
```

The tests use deterministic fake CLIs and a hidden scorer. They prove exact command construction, prompt-on-stdin behavior, version-pinned liveness, environment handling, fresh workspace materialization, automatic scoring, bounded telemetry, core-slot rejection, selective-rerun prevention, same-cell enforcement, and A/A rejection for a changed capability, harness, or model. They do not spend provider tokens or claim that an unavailable live CLI has passed.
