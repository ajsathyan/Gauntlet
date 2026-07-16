# Local Product Documentation

Gauntlet keeps private product working documents and execution state in the primary checkout. The profile is default-on but materializes only for an explicit covered document action.

```text
doc_org.md
local-docs/
  INDEX.md
  drafts/
  epics/
  research/
  executions/
```

These paths are added to the repository's local Git exclude file. They are not a security boundary and must not contain credentials, secret values, personal data, or sensitive resource identifiers. Documentation required by another checkout, contributor, CI process, or operator remains tracked in the repository's normal documentation location.

## User-owned workflow

Discussion does not write a document. On an explicit create request:

- a new repository receives the guided Founding Hypothesis;
- a follow-up feature receives the guided Peter Yang PRD without Meeting Notes.

Both templates keep useful source guidance but no product-specific answer. Users may add, remove, or rename sections. Agents write only stated or explicitly requested product content and keep suggestions outside the document until accepted. Non-goals, security boundaries, rollout, quality gates, and other product limits are never inferred from empty fields.

Drafts live in `local-docs/drafts/`. Explicit promotion allocates the stable Epic ID, chooses the final filename, moves the exact draft bytes under `local-docs/epics/`, and updates the index atomically. Promotion does not imply acceptance.

Explicit acceptance requires an answered `Acceptance`, `Done when`, or legacy `Product Acceptance` section. The controller binds the document digest and compact mechanical launch facts in a sidecar without modifying product content. A later edit invalidates that acceptance until the user accepts the revised version.

Legacy accepted PRDs with machine-readable Epic fields remain launchable. They are not rewritten merely to adopt the new templates.

## Artifact ownership

- Product documents own user-authorized intent and observable done behavior.
- Research owns evidence and uncertainty; it does not authorize implementation.
- The index is navigational, not proof.
- Accepted-Epic records own the exact source digest and compact launch facts.
- Launch sets and Execution Runs own task IDs, dependencies, review dispositions, proof, resume state, and dashboard projections.

Canonical local documents exist only in the primary worktree. Linked implementation worktrees read them and return durable results to the parent task. Private-document changes are not committed or deployed.

## Implementation

An explicit `implement the PRD` request freezes the accepted target and creates one visible task and one Execution Run per independently shippable Epic. The visible task receives a compact launch envelope. Its bootstrap command verifies the immutable source and returns the complete relevant Epic once before run creation; the task prompt does not contain a second copy.

Children receive bounded Tickets, accepted source slices, and dependency contracts. The complete product document, manifest, event history, unrelated receipts, and parent-owned pull-request state stay out of child context.

Proof uses focused changed-behavior checks and one final Epic verification on the exact integrated revision. A bounded Epic gap review may run before build and after integration, with at most three findings per pass and three passes. Every finding ends as `fixed`, `ask-user`, `deferred`, or `omitted`. Consequence-specific specialists run only for explicit accepted triggers.

See `docs/prd-execution.md` for controller commands and release behavior.

## Commands

Check without writing:

```sh
python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs check --project-root "$PROJECT_ROOT"
```

Materialize the profile. A repository with no product document also receives the founding draft:

```sh
python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs ensure --project-root "$PROJECT_ROOT"
```

Create a follow-up draft:

```sh
python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs draft create \
  --project-root "$PROJECT_ROOT" --template peter-yang
```

Promote exact draft bytes after the title is clear:

```sh
python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs draft promote \
  --project-root "$PROJECT_ROOT" --draft PETER_YANG_PRD.md --title "Message surfaces"
```

Accept the exact promoted version after the user reviews its semantics:

```sh
python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs epic accept \
  --project-root "$PROJECT_ROOT" --epic PROJECT-001 \
  --prd "epics/001/001_MESSAGE_SURFACES_PRD.md"
```

`docs draft create`, `docs draft promote`, and `docs epic accept` support `--dry-run`. Acceptance defaults mechanical release applicability to merge and consequence triggers to none; pass explicit command options when the user accepted different facts.

Explicit initialization, project opt-out, and re-enable remain available through `docs init`, `docs disable`, and `docs enable`. The legacy `docs epic create` command remains available for existing comprehensive PRD workflows.
