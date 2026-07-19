# Adaptive code-quality sensors

`gauntlet sensors` discovers changed repository content, selects configured
quality checks, executes them without a shell, and returns a compact completion
verdict. Raw output and full command evidence stay in Git-private evidence
storage rather than recurring model context.

The command family has five public operations:

- `sensors plan` returns a deterministic `gauntlet.sensor-plan/v1` document.
- `sensors run` discovers changes, executes applicable configured commands once,
  writes `gauntlet.sensor-evidence/v1`, and returns a compact
  `gauntlet.sensor-handoff/v1`.
- `sensors verify` rejects failing or stale evidence for the current source.
- `sensors normalize` converts a tool result into
  `gauntlet.sensor-result/v1` evidence.
- `sensors validate-rewrite` checks a
  `gauntlet.readability-rewrite-evidence/v1` receipt.

The runner does not edit or repair code. Codex
uses the handoff's attention items, opens raw logs only when necessary, repairs
the source, and invokes `sensors run` again. Any required failed, unavailable,
not-run, incomplete, or stale result blocks completion.

## Proof phases

`sensors plan`, `sensors run`, and `sensors verify` accept
`--phase fast|integrated`. Omitting the option retains the existing
`integrated` behavior.

- `fast` is the edit-loop phase. It runs only commands whose repository
  configuration opts into `fast`; the bundled configuration runs the workflow
  smoke suite directly as a focused-test sensor, plus applicable lint, Semgrep,
  and Gitleaks checks. It never selects coverage.
- `integrated` is the final sensor phase. It runs the full workflow suite under
  coverage plus every other applicable configured command. A command with no
  `phases` field defaults to integrated-only, so adding phases cannot silently
  weaken an existing repository's final proof.

The phase appears in plan facts, the compact handoff, and private evidence. It
also participates in both source and plan fingerprints. Verification defaults
to integrated, so fast evidence is rejected unless the verifier explicitly
requests `--phase fast`; integrated verification never accepts smoke evidence.
Required failures, unavailable commands, not-run results, incomplete evidence,
and stale evidence block in either phase.

## Proportional planning

Every plan lists the known sensor entries in a fixed order. Each entry has an
outcome and a reason, including entries that do not apply:

- `selected` means the repository already exposes an applicable command and the
  changed surface earns that evidence.
- `skipped` means the sensor is known but is unnecessary for this request or
  changed surface.
- `not-configured` means the sensor would be relevant, but the repository does
  not configure the corresponding tool.
- `unavailable` means the repository declares a command that cannot be used in
  the current environment.

Scratch work selects no sensors unless the caller explicitly opts in for that
request. An opt-in affects only the returned plan; it does not become repository
configuration.

For configured application logic, the baseline covers formatting, type
checking, linting, focused tests, and coverage. The planner can add evidence when the
changed surface and existing configuration support it:

- app logic can select complexity and dead-code/dependency evidence;
- durable source changes can select explicit Semgrep rules;
- durable repository changes can select Gitleaks;
- browser-facing behavior can select a browser sensor;
- accessible UI behavior can select an accessibility sensor;
- high-consequence logic can select a mutation sensor;
- duplication evidence can select a duplication sensor.

Each selected, skipped, or limited branch includes its reason. Reversing the
order of changed paths does not change the plan.

## Configuration and unsupported repositories

Repository commands are declared in `gauntlet-sensors.json` as argument arrays,
never shell strings. A coverage command may declare that it also covers focused
tests, which prevents duplicate execution. Identical command arrays are
deduplicated. Mutation remains consequence-triggered and runs after cheaper
checks in repository configuration.

Each command may declare `phases` as a non-empty array containing `fast`,
`integrated`, or both. The optional `{phase}` and `{suite}` argv placeholders
expand without a shell; `{suite}` becomes `smoke` for fast proof and `full` for
integrated proof. The bundled fast focused-test command invokes
`scripts/check-gauntlet-workflow.py --smoke` directly. Coverage is
integrated-only, and `scripts/run-coverage-sensor.py` accepts only the full
suite.

Missing optional configuration is reported rather than invented. The normal
Codex install includes pinned Semgrep, coverage.py, and Gitleaks versions in an
isolated `~/.codex/gauntlet-tools/` generation. Add
`--without-sensor-tools` to install only the core workflow. The tool receipt owns
only its isolated generation; an unavailable repository command is reported
explicitly and cannot be represented as executed proof.

An unsupported repository still receives a valid plan with an explicit
limitation. The planner does not guess an ecosystem or invent a command. Add the
tool and command through the repository's normal configuration process, then
plan again.

## Normalized evidence

The handoff contains pass IDs, counts, and only non-passing attention items with
bounded summaries and evidence references. It deliberately omits repeated
commands, working directories, tool versions, and raw pass output. Full evidence
retains the argument array, working directory, exit status, duration, tool
identity, source and plan fingerprints, raw-output digest, and raw-log reference.

Evidence is bound to the current Git revision, changed-file content, sensor
configuration, and proof phase. Editing relevant source or configuration, or
requesting a different proof phase, invalidates earlier evidence. A
caller-supplied result cannot establish a pass.

## Readability rewrites

Readability is a behavioral claim. A
`gauntlet.readability-rewrite-evidence/v1` receipt is valid only when it includes
before/after behavior proof and shows that the rewrite preserved the intended
behavior.

Metric changes such as fewer lines, lower complexity, less duplication, or a
smaller bundle can support a review, but metric deltas alone cannot validate a
readability rewrite. They also do not authorize an automatic abstraction or
refactor. The behavior oracle remains the deciding evidence.
