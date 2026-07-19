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

The runner does not edit code or contain an autonomous repair controller. Codex
uses the handoff's attention items, opens raw logs only when necessary, repairs
the source, and invokes `sensors run` again. Any required failed, unavailable,
not-run, or stale result blocks completion.

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

Missing optional configuration is reported rather than invented. The normal
Gauntlet install ships adapters and configuration but does not download external
tools. `scripts/install.sh --with-sensor-tools` installs pinned Semgrep,
coverage.py, and Gitleaks versions into an isolated
`~/.codex/gauntlet-tools/` generation. Its receipt owns only that directory;
tool failure does not invalidate the core Gauntlet install.

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

Evidence is bound to the current Git revision, changed-file content, and sensor
configuration. Editing relevant source or configuration invalidates earlier
evidence. A caller-supplied result cannot establish a pass.

## Readability rewrites

Readability is a behavioral claim. A
`gauntlet.readability-rewrite-evidence/v1` receipt is valid only when it includes
before/after behavior proof and shows that the rewrite preserved the intended
behavior.

Metric changes such as fewer lines, lower complexity, less duplication, or a
smaller bundle can support a review, but metric deltas alone cannot validate a
readability rewrite. They also do not authorize an automatic abstraction or
refactor. The behavior oracle remains the deciding evidence.
