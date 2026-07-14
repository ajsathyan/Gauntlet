# Local Product Documentation

Gauntlet projects may keep private working context outside Git without displacing the repository's tracked documentation. This is an opt-in profile for product documents, research, decisions, implementation plans, and run history that should remain local to one primary checkout.

The profile scaffolds:

```text
doc_org.md
local-docs/
  INDEX.md
  epics/
  research/
  executions/
```

Both `doc_org.md` and `local-docs/` are ignored through the repository's local Git exclude file. Gauntlet does not add them to a tracked `.gitignore`, overwrite an existing document, or repurpose a tracked `docs/` directory.

## Visibility Boundary

`local-docs/` is for local working history. It is not a security boundary and must not contain credentials, secret values, private destinations, or sensitive resource identifiers.

Documents required by another checkout, contributor, CI process, operator, auditor, or future maintainer belong in the repository's tracked documentation location. This includes public contracts, contributor guidance, durable architectural decisions, operational runbooks, release notes, compliance evidence, and other material required to understand or operate the repository.

When an accepted requirement is necessary to maintain the product, make it durable through tracked code, tests, a pull request, or tracked documentation. The ignored product history cannot be its only home.

## Canonical Location

Canonical local documents live only in the primary worktree. Linked implementation worktrees read those documents and return durable decisions, exceptions, unresolved gaps, and proof to the main task. The main task updates the primary copies before removing a linked worktree.

Private-document changes are local filesystem changes. They are not committed, merged, or deployed.

## One Gauntlet Lifecycle

The profile organizes artifacts; it does not create another intake, planning, implementation, or release lifecycle. Existing Gauntlet roles continue to own research, product architecture, planning, implementation, review, and run logs.

The always-loaded Gauntlet question discipline applies to every document role. For documentation work, a question is consequential when its answer could change the document's purpose, audience, scope, authority, organization, or acceptance.

## PRD Organization

One PRD may cover multiple Epics and may be developed in one conversation. Keep it human-readable and searchable with stable identifiers:

```text
# <Product or initiative>
## Epic <EPIC-ID>: <Outcome>
### Objectives
### Principles
### Non-goals
### Scope Area <SCOPE-ID>: <Responsibility>
```

An Epic is a stable product outcome. A Scope Area is a stable responsibility or surface inside that outcome; it is not an agent assignment. Separate objectives, principles, and non-goals rather than combining them under one heading. Likewise, keep user/job/first-value, states/recovery, trust/privacy/security/authority, acceptance/test expectations, dependencies/assumptions/open questions, and rollout/rollback distinct when each contains material information.

Acceptance criteria state what must be true. Test expectations identify the behavior claim, observable oracle, plausible wrong case, and required non-effects. Verification strategy describes plan-level proof layers. Tickets and Cohort Verification are generated only after a build-ready implementation target is accepted; they do not belong in the PRD as a second hand-written plan.

## Release Contract

The generated `doc_org.md` contains one implementation and release contract. PRDs record product-level release constraints. Build-ready plans resolve the worktree, branch, authority gates, integration order, proof, rollout, rollback, and release source for that implementation and reference the current contract.

Do not copy the full release procedure into every PRD and plan. A material contract change invalidates an active plan until its resolved release section is reviewed.

The phrase **implement the PRD** applies only to the explicit build-ready target. It carries the end-to-end authority described in `docs/prd-execution.md`; proposed, deferred, or materially unresolved Epics and Scope Areas stay out of the Execution Run.

## Execution Runs

Generated Ticket Graphs and live execution state belong below `local-docs/executions/<run-id>/`, not beside the PRD as another human-authored source. After a run starts, its source lock, manifest, and resume file are authoritative for execution progress. Conversation continues to own user decisions, while compaction recovery reads the durable artifacts.

Children receive one materialized ticket context plus relevant shared context, named dependency outputs, and owned source paths. They do not need the full PRD or execution history. The parent owns state transitions, integration, oracle verification, cohort results, and release records. See `docs/prd-execution.md` for the artifact and scheduling contract.

## Configuration Boundary

PRDs describe which behavior must be configurable, who controls it, and which secret or private-data classes are involved. Implementation plans classify likely external values and give each one an approved destination.

Never hardcode secrets, credentials, private resource identifiers, environment-specific endpoints, deployment identifiers, or values that legitimately vary by environment or operator. Stable product rules, protocol constants, enum values, state transitions, and safe code defaults may remain in code when they are typed, reviewed, and tested.

Use the project's approved secret-management system for production secrets. An ignored local environment file may support development but is not a production secret store.

## Commands

Initialize from either the primary checkout or a linked worktree:

```sh
python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs init \
  --project-root "$PROJECT_ROOT" \
  --epic-prefix PROJECT
```

Inspect the profile without changing it:

```sh
python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs check \
  --project-root "$PROJECT_ROOT"
```

Create the next stable epic:

```sh
python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs epic create \
  --project-root "$PROJECT_ROOT" \
  --title "Message surfaces"
```

Initialization and epic creation refuse tracked-path collisions and preserve existing local documents.
