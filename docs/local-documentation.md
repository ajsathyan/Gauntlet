# Local Design Documentation

Gauntlet keeps private product designs in the primary checkout. The profile is
default-on, but it materializes only for an explicit covered document action.

```text
doc_org.md
local-docs/
  INDEX.md
  designs/
  research/
  decisions/
  epics/        # optional legacy files, preserved as-is
  executions/   # optional legacy files, preserved as-is
```

These paths are added to the repository's local Git exclude file. They are not a
security boundary and must not contain credentials, secret values, personal data,
or sensitive resource identifiers. Documentation needed by another checkout,
contributor, CI process, or operator remains tracked in the repository's normal
documentation location.

## What the lifecycle keeps

A bounded Normal Request does not create a durable design. For non-trivial product
or implementation work, one permanent Design preserves the accepted product
meaning. Before acceptance, the conversation explicitly considers material
alternatives, assumptions, completeness, edge cases, observable outcomes, and
required non-effects.

The template contains prompts, not decisions. Users may add, remove, or rename
sections. Agents write only stated or explicitly requested content and keep
unaccepted suggestions outside the document. Empty prompts never create non-goals,
security boundaries, rollout constraints, quality gates, or other product limits.

`docs design create` creates the durable Design directly. There is no separate
draft promotion, implementation-plan document, Epic compilation, or controller
run. Direct user edits and arbitrary sections remain untouched.

Explicit acceptance requires one answered exact `## Acceptance` section. Gauntlet
stores the whole-file digest and the Acceptance-section digest in an adjacent
acceptance record, updates only the navigational index, and does not edit the
Design. The exact section is the Build Contract. A later semantic edit requires a
new explicit acceptance.

Legacy PRD, Epic, and execution files remain readable at their existing paths.
Profile initialization and Design commands do not rewrite them.

## Artifact ownership

- The accepted Design owns user-authorized intent and observable outcomes.
- Its exact `## Acceptance` section owns the Build Contract.
- Research owns evidence and uncertainty; it does not authorize implementation.
- Decisions preserve reasoning that would otherwise be lost.
- Architecture and Sensor Contracts remain separate from product acceptance.
- The index is navigational, not proof.
- Build plans and workstream assignments are ephemeral implementation aids.

Before Build, product-completeness, engineering-shape, and proof/consequence lenses
inspect the same Design. Material findings receive terminal dispositions. Independent
Verify reads the accepted Design and exact integrated revision and returns separate
Build, Architecture, and Sensor verdicts. Green sensors cannot compensate for a
missing accepted outcome.

## Commands

Check without writing:

```sh
python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs check \
  --project-root "$PROJECT_ROOT"
```

Materialize the default profile:

```sh
python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs ensure \
  --project-root "$PROJECT_ROOT"
```

Create one durable Design:

```sh
python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs design create \
  --project-root "$PROJECT_ROOT" --title "Message surfaces"
```

After editing and explicit user review, accept its exact bytes:

```sh
python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs design accept \
  --project-root "$PROJECT_ROOT" --design PROJECT-001
```

Opt out or return to the default:

```sh
python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs disable \
  --project-root "$PROJECT_ROOT"
python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs enable \
  --project-root "$PROJECT_ROOT"
```

Canonical documents exist only in the primary worktree. Linked worktrees resolve
there and must not create alternate copies.
