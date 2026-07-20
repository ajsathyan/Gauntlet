# Gauntlet

A product-thinking and verification workflow for Codex.

Gauntlet helps an agent turn an idea into a complete feature without making a
permanent project-management system out of the implementation process or
pausing for routine acceptance gates. Product meaning stays in the request and,
when explicitly requested, one durable Design. Implementation planning stays
temporary. Verification checks the exact integrated revision against the
original outcome, intended architecture, and repository's executed quality
checks.

## The workflow

```text
Design -> Build -> Verify -> Ship
```

### Design

For non-trivial implementation, Gauntlet explores materially different
approaches, assumptions, feature-level edge cases, user-visible states, and
observable outcomes. It resolves routine product and engineering decisions
independently and records material decisions. A permanent Design is optional and
is created or edited only with explicit user authority.

When accepted, the Design's exact `## Acceptance` section is the **Build
Contract** for optional exact-design proof. Build and Verify also read the user
request directly. A plan, workstream assignment, sensor result, or PR summary
cannot narrow requested or accepted outcomes.

Before Build, three bounded lenses review the same Design:

- **Product completeness:** missing outcomes, states, assumptions, and edge cases.
- **Engineering shape:** boundaries, dependencies, compatibility, and ownership.
- **Proof and consequence:** observable oracles, false-green paths, required
  non-effects, and concrete risk triggers.

Only material findings are shown. Every material finding receives an
implementation disposition and reason. Design acceptance and advisory findings
do not block code, commits, publication, or non-production landing.

### Build

Build creates an internal, ephemeral plan from the request, repository context,
and any accepted Design, and stops planning once the first coherent step and
proof path are clear. One parent task keeps shared contracts, integration, and
external authority.

Parallel work uses compact native workstreams only when ownership or independent
evidence makes it worthwhile. Children receive an outcome slice, owned files or
state, dependency contracts, constraints, proof, and a compact return contract.
Coherent changes land as atomic commits. When parallel candidates share a Git
base, the generic FIFO workstream queue serializes integration and rejects stale
candidates after the base changes. See
[Parallel Workstreams](docs/parallel-workstreams.md).

### Verify

Independent Verify reads the request, any accepted Design, and exact integrated revision. It
returns three separate verdicts:

- **Build:** every requested and accepted outcome and required non-effect is observably true.
- **Architecture:** required boundaries, dependencies, compatibility, and code
  shape hold.
- **Sensor:** configured checks executed at the required cadence against the
  exact source.

All applicable verdicts must pass. A clean architecture or green sensor run
cannot compensate for an absent product outcome. This explicitly prevents the
GAUNTLET-009 failure, where planning passed but the requested sensor execution
never existed.

### Ship

An implementation request authorizes the ordinary code lifecycle:

- local commits;
- implementation branch push;
- pull-request creation;
- non-production merge to the default branch.

Before landing, Gauntlet inspects repository automation because merge itself may
deploy, publish, migrate, or otherwise change production. Every production
change requires separate explicit acceptance. The request includes bullets for
met criteria and evidence, independent implementation decisions, unmet criteria
or remaining risk, exact revision, and rollback. Installation, destructive or
paid actions, credential use, rollback, and task archival remain separately
scoped. PR checks do not prove production health. See
[GitHub Discipline](docs/github-discipline.md).

## Normal requests

Bounded, low-consequence, reversible work uses the light path: make the requested
change in the parent task and run its smoke check. It does not create a durable
Design, review panel, workstream queue, or other process state.

## Durable local Designs

Private product documents are created only for explicit covered document work:

```sh
python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs ensure \
  --project-root "$PROJECT_ROOT"

python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs design create \
  --project-root "$PROJECT_ROOT" --title "Message surfaces"

python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs design accept \
  --project-root "$PROJECT_ROOT" --design PROJECT-001
```

The profile uses ignored `doc_org.md` and `local-docs/` paths in the primary
worktree. Legacy PRDs and historical execution files remain readable and are not
rewritten. See [Local Design Documentation](docs/local-documentation.md).

## Adaptive code-quality sensors

Sensors discover changed code, select repository-owned checks, execute them
without a shell, and return a compact handoff containing only counts and
non-passing attention items. Full commands and raw output stay in referenced
Git-private evidence instead of recurring model context.

Two phases keep the loop proportional:

- `fast` for cheap edit-loop checks;
- `integrated` for final, source-bound proof.

```sh
python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" sensors run \
  --project-root "$PROJECT_ROOT" --workflow-mode feature --phase fast --json

python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" sensors run \
  --project-root "$PROJECT_ROOT" --workflow-mode feature --phase integrated --json
```

The Codex installer installs pinned machine-local Semgrep, coverage.py, and
Gitleaks by default in an isolated owned tool generation. Use
`--without-sensor-tools` when the core workflow should be installed without
those tools. Repository configuration decides which checks actually apply.
See [Adaptive Code-Quality Sensors](docs/code-quality-sensors.md).

## Generic workstream queue

The queue is a small Git-bound integration primitive, not a project tracker:

```sh
python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" workstreams enqueue \
  --repo "$PROJECT_ROOT" --state "$QUEUE_FILE" \
  --workstream "$ID" --source-commit "$SHA"

python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" workstreams claim \
  --repo "$PROJECT_ROOT" --state "$QUEUE_FILE"
```

It keeps FIFO order, allows one active attempt, binds candidate commit and tree
identity, and reconciles only observable Git state. Native Codex task state
remains sufficient for normal coordination.

## Install, upgrade, and uninstall

Gauntlet installs only for Codex:

```sh
./scripts/install.sh --target codex --instructions-reviewed
```

The installer preserves unrelated instructions and config, records ownership,
removes only byte-identical stale managed files during upgrades, and preserves
modified or unowned files with a finding. A controller-era upgrade refuses to
proceed while supplied project roots contain live legacy work:

```sh
./scripts/install.sh --target codex --instructions-reviewed \
  --cutover-project-root "$PROJECT_ROOT"
```

After checking every relevant project yourself, the explicit alternative is
`--confirm-no-live-controller-work`. To omit the default sensor tools, add
`--without-sensor-tools`.

Uninstall removes receipt-owned Gauntlet files and its managed instruction block
while preserving user-owned and modified files:

```sh
./scripts/install.sh --target codex --uninstall
```

Restart Codex after installing or upgrading so the new global instructions and
skills are loaded.

## Current public surfaces

- [Design, Build, Verify, Ship](docs/design-build-verify.md)
- [Workflow Etiquette](docs/workflow-etiquette.md)
- [Meaningful Proof](docs/meaningful-proof.md)
- [Parallel Workstreams](docs/parallel-workstreams.md)
- [Thin Contract Assessment](docs/thin-contract-assessment.md)
- [Optional Agent Profiles](docs/optional-agent-profiles.md)
- [GitHub Discipline](docs/github-discipline.md)
- [Skills](skills)
- [Workflow helper CLI](scripts/gauntlet.py)
- [Deterministic evals](evals)

Gauntlet is released under the [MIT License](LICENSE).
