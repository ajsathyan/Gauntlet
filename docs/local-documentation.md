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

## Multi-Epic Product Source

A canonical PRD may contain several Epics from one product conversation. Each Epic receives a stable ID and index row; each stable product responsibility within it receives a Scope Area ID. A numbered `epics/` directory is a document home and does not force a one-file/one-Epic split.

Keep the PRD readable by separating user, objective, workflow, state, trust, acceptance, interface, proof, dependency, uncertainty, rollout, and rollback concerns under distinct headings. `Implementation target` names only accepted, build-ready Epics. Proposed, deferred, and unresolved Epics may remain in the document without entering execution.

Use the `maintain-prd` skill to create or revise this source. It never implements.

## One Gauntlet Lifecycle

The profile organizes artifacts; it does not create another intake, planning, implementation, or release lifecycle. Existing Gauntlet roles continue to own research, product architecture, planning, implementation, review, and run logs. `implement-prd` coordinates those roles for an explicit end-to-end PRD request.

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

## Compilation And Durable Execution

An explicit `implement the PRD` request validates and freezes the accepted Implementation Target, then compiles it into a deterministic Ticket Graph. The graph uses stable H2 Epic, H3 Ticket, and H4 field headings. Tickets are current execution units and reference stable Scope Areas; no JSON packet or delimiter sentinels are required.

Runs live under `local-docs/executions/<run-id>/`. Source locks, manifests, compact resume state, materialized Tickets, receipts, evidence, cohort results, and release evidence make execution resilient to conversation compaction. Disk state is authoritative after a run starts. Children receive only bounded Ticket bundles and relevant versioned context; the whole PRD, manifest, event history, unrelated receipts, and raw logs stay out of child prompts.

One active implementation Ticket per child is the default. Related sequential Tickets may reuse a child for context affinity. One implementation Ticket is never co-owned; independent checking uses a verifier Ticket. The parent integrates continuously and verifies Ticket, cohort, full-PRD, and release/production layers.

## Release Contract

The generated `doc_org.md` contains one implementation and release contract. PRDs record product-level release constraints. Compiled Ticket Graphs resolve the worktree, branch, integration order, proof, rollout, rollback, and release source for that implementation and reference the current contract.

An explicit request to `implement the PRD` authorizes the accepted build-ready target's normal branch-through-production lifecycle, including a pull request, required-check merge, deployment of the exact verified `main` revision, and documented production changes named in the PRD. A narrower request controls. Missing credentials or permissions, a material unresolved decision, an unaccepted destructive effect, invalid rollout or rollback assumptions, preservation risk, or unavailable required production proof stops the affected transition.

Do not copy the full release procedure into every PRD and graph. A material source or contract change selectively invalidates affected Tickets until their source locks and resolved release fields are refreshed.

The phrase **implement the PRD** applies only to the explicit build-ready target. It carries the end-to-end authority described in `docs/prd-execution.md`; proposed, deferred, or materially unresolved Epics and Scope Areas stay out of the Execution Run.

## Execution Runs

Generated Ticket Graphs and live execution state belong below `local-docs/executions/<run-id>/`, not beside the PRD as another human-authored source. After a run starts, its source lock, manifest, and resume file are authoritative for execution progress. Conversation continues to own user decisions, while compaction recovery reads the durable artifacts.

Children receive one materialized ticket context plus relevant shared context, named dependency outputs, and owned source paths. They do not need the full PRD or execution history. The parent owns state transitions, integration, oracle verification, cohort results, and release records. See `docs/prd-execution.md` for the artifact and scheduling contract.

## Configuration Boundary

PRDs describe which behavior must be configurable, who controls it, and which secret or private-data classes are involved. Compiled Ticket Graphs classify likely external values and give each one an approved destination.

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

Append the next stable Epic to an existing multi-Epic PRD:

```sh
python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs epic create \
  --project-root "$PROJECT_ROOT" \
  --title "Delivery controls" \
  --prd "epics/001/001_MESSAGE_SURFACES_PRD.md"
```

Epic allocation scans both the index and canonical PRDs, so manually appended indexed Epics cannot silently reuse an ID. Initialization and epic creation refuse tracked-path collisions and preserve existing local documents.
