# PRD To Ticket Graph Execution

Status: authoritative Gauntlet reference for implementing an accepted PRD.

This contract lets one human-readable PRD describe multiple product outcomes while giving agents a compact, durable execution model. The PRD remains the source for product intent. An Execution Run compiles only its build-ready implementation target into a Ticket Graph and records live state on disk so conversation compaction does not become execution state.

## Terms And Boundaries

| Term | Responsibility |
| --- | --- |
| PRD | Human-readable product source of truth. It may contain multiple Epics and both build-ready and deferred work. |
| Epic | Stable product outcome inside a PRD. Epic identity survives replanning. |
| Scope Area | Stable responsibility or product surface within an Epic. It locates requirements without prescribing agent ownership. |
| Ticket Graph | Generated execution dependency graph for the current build-ready target. It is not a second product specification. |
| Ticket | One independently assignable unit with explicit ownership, inputs, outputs, dependencies, constraints, and proportional proof. |
| Execution Run | Durable local instance of PRD implementation, including source lock, graph, state, receipts, and evidence. |
| Receipt | Compact machine result and evidence pointer returned for one ticket. It is not proof by itself. |
| Cohort Verification | Combined proof for tickets that share an interface, invariant, or release boundary. It is a selective barrier, not a global wait after every ticket. |

Use stable, searchable Markdown headings and identifiers in PRDs: `## Epic <ID>`, `### Scope Area <ID>`, and separate requirement sections. Tickets use stable generated IDs and reference their Epic and Scope Area IDs. Do not add delimiter tokens around sections; Markdown structure and stable IDs are the extraction interface.

## Build-Ready Target

Before compilation, identify the exact Epics and Scope Areas included in this run. They must be accepted, internally consistent, and free of unresolved questions that materially alter behavior, authority, safety, acceptance, rollout, rollback, or required proof. Proposed, deferred, and unresolved work remains in the PRD but is excluded from the build-ready target.

The instruction **implement the PRD** authorizes the accepted build-ready target end to end:

1. create the branch or worktree and compile the Ticket Graph;
2. execute tickets, integrate changes incrementally, and run ticket, cohort, and PRD-level proof;
3. commit, open the pull request, satisfy repository merge policy, and merge;
4. deploy the exact merged default-branch revision when the PRD calls for deployment and existing project mechanisms make it safe;
5. perform documented production changes, production verification, rollback when required, durable documentation updates, and safe cleanup.

This default does not manufacture authority. Stop for missing credentials or permissions, a materially unresolved product decision, an unsafe or destructive effect absent from the accepted PRD, production reality that invalidates the accepted rollout or rollback, or required production proof that cannot be obtained. A PRD that does not require deployment or production mutation completes without inventing either.

## Compilation And Scheduling

Compile the PRD deterministically from stable IDs and source hashes. One implementation plan may span multiple Epics. Prefer one active ticket per implementation agent; an agent may receive sequential related tickets when affinity reduces context cost. Do not co-own one implementation ticket across agents. Independent verifier tickets may inspect the same integrated output.

Schedule from a dynamic ready queue:

- prioritize the critical path and tickets that unlock the most downstream work;
- use agent affinity for related files, contracts, tools, or domain context;
- land interface-first tickets early so dependent tickets consume an explicit contract;
- integrate completed tickets continuously and run their targeted proof immediately;
- apply Cohort Verification only where tickets share a material interface or invariant;
- keep the parent-owned oracle independent of child-authored checks;
- require named output files, symbols, contracts, receipts, and evidence so consumers do not rediscover them.

Run full PRD verification after all required cohorts pass, followed by merge, deployment, and production verification when applicable.

## Durable Execution State

An Execution Run lives below the canonical local-document root declared by `doc_org.md`, conventionally:

```text
executions/<run-id>/
  source-lock.json
  manifest.json
  shared-context.md
  resume.md
  events.jsonl
  tickets/
  receipts/
  evidence/
  cohorts/
  release/
```

`source-lock.json` pins the PRD revision and selected Scope Areas. `manifest.json` owns validated run and ticket state. `resume.md` is the minimal reentry view. Events are append-only diagnostics, not the normal context source. Tickets are immutable after dispatch; a changed requirement creates a new revision or selectively invalidates affected tickets through Scope Area source hashes.

After the run starts, these artifacts are authoritative for execution state. Conversation remains the place for user decisions, but a compaction or restart must rehydrate from the source lock, manifest, and resume file rather than reconstructing progress from chat. The parent alone updates the manifest, resume, cohort results, and release records. A child owns its worktree plus its assigned receipt and evidence paths. Use atomic writes, an agent-and-attempt lease, and validated state transitions so stale agents cannot overwrite current state.

The lifecycle is:

```text
discussing -> accepted -> compiled -> executing -> integrating
-> cohort_verified -> prd_verified -> merged -> deployed
-> production_verified -> complete
```

Skip inapplicable external stages explicitly; do not claim them from a status label alone.

## Bounded Child Context

Materialize one compact child bundle from deterministic state. A child reads only:

- its ticket and stable instruction contract;
- the relevant versioned shared context for its cohort;
- named dependency contracts and outputs;
- the source files needed for its ownership boundary.

Children do not read the entire PRD, manifest, event stream, unrelated receipts, or all repository context by default. They return a compact receipt with evidence pointers; raw test output belongs in evidence files. The parent independently resolves the pointers and verifies the oracle after integration.

## Prefix And Token Efficiency

Optimize for stable prefixes without claiming guaranteed cache hits. Cache behavior depends on the host, model, routing, and exact prompt bytes.

- Put stable instructions first and ticket-specific data last.
- Keep canonical field order, sorted IDs, stable whitespace, and versioned instruction text.
- Omit empty fields and avoid early timestamps, run IDs, absolute paths, mutable status, hashes, or agent nicknames.
- Version shared context by cohort and send only the version a ticket consumes.
- Dispatch similar tickets near each other when safe and retain agent affinity for sequential related tickets.
- Keep delegation depth at one unless a concrete dependency structure justifies more.
- Read `resume.md` only for restart or compaction recovery; read `events.jsonl` only for debugging.

Subagent model selection is intentionally outside this contract. Model routing must be designed and verified separately rather than encoded as an unenforced ticket field.
