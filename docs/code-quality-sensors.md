# Adaptive code-quality sensors

`gauntlet sensors` turns repository facts and the changed surface into a small,
explained evidence plan. It does not install tools, change dependencies, or run
the planned commands.

The V1 command family has three public operations:

- `sensors plan` returns a deterministic `gauntlet.sensor-plan/v1` document.
- `sensors normalize` converts a tool result into
  `gauntlet.sensor-result/v1` evidence.
- `sensors validate-rewrite` checks a
  `gauntlet.readability-rewrite-evidence/v1` receipt.

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

For configured TypeScript application logic, the baseline covers formatting,
type checking, linting, and focused tests. The planner can add evidence when the
changed surface and existing configuration support it:

- app logic can select complexity and dead-code/dependency evidence;
- semantic or data-flow changes can select an architecture/dependency sensor;
- browser-facing behavior can select a browser sensor;
- accessible UI behavior can select an accessibility sensor;
- high-consequence logic can select a mutation sensor;
- duplication evidence can select a duplication sensor.

Each selected, skipped, or limited branch includes its reason. Reversing the
order of changed paths does not change the plan.

## Configuration and unsupported repositories

Optional tools are discovery-only. Missing `dependency-cruiser` or `jscpd`
configuration is reported as `not-configured`; a configured command that is not
usable is reported as `unavailable`. Planning never adds either package, rewrites
`package.json` or a lockfile, or changes Git state.

An unsupported repository still receives a valid plan with an explicit
limitation. The planner does not guess an ecosystem or invent a command. Add the
tool and command through the repository's normal configuration process, then
plan again.

## Normalized evidence

Normalization keeps the stable facts needed by later workflow steps and a
reference to the raw output. It does not copy the full raw output into the
normalized result. Keep the referenced artifact for debugging and detailed
review.

The `gauntlet.sensor-result/v1` schema is tool-neutral: consumers should use its
sensor ID, result, evidence references, and optional command and summary rather
than parse a tool's console format.

## Readability rewrites

Readability is a behavioral claim. A
`gauntlet.readability-rewrite-evidence/v1` receipt is valid only when it includes
before/after behavior proof and shows that the rewrite preserved the intended
behavior.

Metric changes such as fewer lines, lower complexity, less duplication, or a
smaller bundle can support a review, but metric deltas alone cannot validate a
readability rewrite. They also do not authorize an automatic abstraction or
refactor. The behavior oracle remains the deciding evidence.
