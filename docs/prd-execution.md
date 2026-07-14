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
| Review Unit | Frozen group of tightly coupled Tickets that may receive an intermediate PR into the run integration branch. It is a parent review boundary, not a release boundary or child assignment. |
| Execution Run | Durable local instance of PRD implementation, including source lock, graph, state, receipts, and evidence. |
| Project PR | Complete, run-backed PR from the integration branch to the default branch. It covers every locked Epic and Scope Area regardless of intermediate review units. |
| Receipt | Compact machine result and evidence pointer returned for one ticket. It is not proof by itself. |
| Cohort Verification | Combined proof for tickets that share an interface, invariant, or release boundary. It is a selective barrier, not a global wait after every ticket. |

Use stable, searchable Markdown headings and identifiers in PRDs: `## Epic <ID>`, `### Scope Area <ID>`, and separate requirement sections. Tickets use stable generated IDs and reference their Epic and Scope Area IDs. Do not add delimiter tokens around sections; Markdown structure and stable IDs are the extraction interface.

## Build-Ready Target

Before compilation, identify the exact Epics and Scope Areas included in this run. They must be accepted, internally consistent, and free of unresolved questions that materially alter behavior, authority, safety, acceptance, rollout, rollback, or required proof. Proposed, deferred, and unresolved work remains in the PRD but is excluded from the build-ready target.

Choose and freeze the PR strategy when the run is initialized. Use `single-final-pr` for a small, reviewable multi-Epic target. Use `review-prs-plus-final` when a large target is tightly coupled enough to remain one release boundary but needs parent-owned intermediate review units. If outcomes can ship, roll back, and be accepted independently, create separate Execution Runs instead. Do not select the strategy from agent count, token count, or a late desire to make the diff look smaller.

The instruction **implement the PRD** authorizes the accepted build-ready target end to end:

1. create the branch or worktree and compile the Ticket Graph;
2. execute tickets, integrate changes incrementally, and run ticket, cohort, and PRD-level proof;
3. commit, open the pull request, satisfy repository merge policy, and merge;
4. deploy the exact merged default-branch revision when the PRD calls for deployment and existing project mechanisms make it safe;
5. perform documented production changes, production verification, rollback when required, durable documentation updates, and safe cleanup.

This default does not manufacture authority. Stop for missing credentials or permissions, a materially unresolved product decision, an unsafe or destructive effect absent from the accepted PRD, production reality that invalidates the accepted rollout or rollback, or required production proof that cannot be obtained. A PRD that does not require deployment or production mutation completes without inventing either.

## Compilation And Scheduling

Compile the PRD deterministically from stable IDs and source hashes. One implementation plan may span multiple Epics. For `review-prs-plus-final`, the graph's `review_units` map must assign every Ticket to exactly one review unit and record review-unit dependencies. Freeze that membership and dependency topology at compile; reconciliation may update affected Ticket revisions but must not silently regroup the review surface. Prefer one active ticket per implementation agent. When several ready Tickets declare the same affinity and share a cohort and dependency contract, the parent may claim them as one context lane for the same agent. A lane has no fixed Ticket ceiling, but each Ticket keeps its own lease, receipt, status, integration proof, and dependency release. Do not co-own one implementation ticket across agents. Independent verifier tickets may inspect the same integrated output.

The controller stores one normalized `ticket-graph.json` for validation and state transitions, then renders immutable prose Tickets for dispatch. The JSON is a machine artifact, not a giant child prompt; children receive only their individual Markdown bundle.

Schedule from a dynamic ready queue:

- prioritize the critical path and tickets that unlock the most downstream work;
- use agent affinity for related files, contracts, tools, or domain context;
- bundle only explicitly compatible ready Tickets into a lane, then integrate each Ticket as soon as its own proof passes;
- land interface-first tickets early so dependent tickets consume an explicit contract;
- integrate completed tickets continuously and run their targeted proof immediately;
- apply Cohort Verification only where tickets share a material interface or invariant;
- keep the parent-owned oracle independent of child-authored checks;
- require named output files, symbols, contracts, receipts, and evidence so consumers do not rediscover them.

Run full PRD verification after all required cohorts pass, followed by merge, deployment, and production verification when applicable.

## Integration Topology

Each Execution Run uses one parent-owned integration branch. Keep the default branch clean while child work proceeds in isolated branches or worktrees. The frozen strategy determines the parent review topology:

```text
single-final-pr
main (clean) <- complete Project PR <- run integration branch <- child checkpoints

review-prs-plus-final
main (clean) <- complete Project PR <- run integration branch <- Review Unit PRs <- child checkpoints
```

The parent integrates child commits as they arrive and runs targeted checks after each integration. Under `single-final-pr`, the checkpoints land directly on the integration branch. Under `review-prs-plus-final`, the parent groups completed checkpoints only by the compiled Review Units, opens each Review Unit PR against the integration branch, and merges it after its unit proof and dependencies pass. Review Unit PRs never target `main`, never replace full-PRD verification, and never count as independently shippable releases.

After every required Ticket, cohort, and Review Unit is integrated, the parent runs full-PRD verification and opens one complete Project PR from the integration branch to `main`. The Project PR projection must cover every locked Epic and Scope Area deterministically, including outcomes, proof references, material decisions, risks, and pending post-merge gates. If work has independent release boundaries, compile separate runs rather than using Review Units to imitate separate releases.

The run manifest records the integration branch, frozen PR strategy, Review Unit state, and merge authority. Initialization also records the repository identity and writes a branch-to-run binding under the repository's Git common directory, so a custom Execution Run root cannot be downgraded to a caller-authored handoff. The Ticket Graph records frozen Review Unit membership. This topology remains parent-owned and is absent from child bundles; a child receives no branch, PR strategy, Review Unit, or merge-owner metadata unless its Ticket must act on a named worktree. These fields do not grant authority.

## Run-Backed PR Projection And Merge

Initialize the run with the explicit strategy and compile its corresponding graph:

```text
prd-run.py init ... --pr-strategy single-final-pr|review-prs-plus-final
prd-run.py compile --run <run> --graph <ticket-graph.json>
prd-run.py project-pr --run <run>
```

The `project-pr` command emits the controller-owned schema v2 projection for the complete Project PR. Run-backed closeout must consume that projection through `gauntlet.py merge prepare|plan|execute --run <run>`; do not downgrade the run to a caller-authored schema v1 handoff. Non-run patches continue to use `--handoff <schema-v1.json>`.

When `review-prs-plus-final` is selected, use `scripts/gauntlet.py review-unit prepare|plan|execute --run <run> --unit <id>` to bind each unit PR to its frozen membership and target the run integration branch. The parent alone executes this surface. It accepts only an open PR whose base, head branch, and GitHub head object ID match the remote refs; serializes integration merges; binds passing checks to the current base, head, and synthetic merge tree; rechecks after base drift; verifies that the actual merge remains reachable from the remote integration branch; and deletes the review branch only with a lease on the reviewed head.

Full-PRD verification records the exact repository and integration-branch head. `project-pr` refuses a different repository or any clean post-verification commit. The merge adapter invokes the installed controller rather than a controller supplied by the candidate repository, requires separate `merge-to-default` authority at execution time, and uses GitHub's expected-head guard so a concurrently advanced Project PR cannot merge.

## Durable Execution State

An Execution Run lives below the canonical local-document root declared by `doc_org.md`, conventionally:

```text
executions/<run-id>/
  source-lock.json
  manifest.json
  ticket-graph.json
  ticket-graph.md
  shared-context/global-v1.md
  shared-context/<cohort>-v<N>.md
  resume.md
  events.jsonl
  tickets/
  receipts/
  handoffs/
  evidence/
  cohorts/
  release/
  outcomes/
```

`source-lock.json` pins the PRD revision, selected Epic and Scope Area sections, instruction version, release contract, and applicable release stages. `manifest.json` owns validated run and ticket state. `resume.md` is the minimal reentry view. Events are append-only diagnostics, not the normal context source. Tickets are immutable after dispatch; a changed requirement creates a new revision or selectively invalidates affected tickets through source-section hashes.

After the run starts, these artifacts are authoritative for execution state. Conversation remains the place for user decisions, but a compaction or restart must rehydrate from the source lock, manifest, and resume file rather than reconstructing progress from chat. The parent alone updates the manifest, resume, cohort results, lanes, and release records. A child owns its worktree plus its assigned receipt and evidence paths. Use atomic writes, an exclusive parent-process lock, an agent-and-attempt lease, hash-pinned proof artifacts, and validated state transitions so stale or concurrent agents cannot overwrite current state. The event journal is reconciled to the manifest's committed sequence on every restart, discarding an uncommitted or partial tail without replaying an event twice. Reconciliation keeps a recovery journal, restores the prior consistent source/graph generation after an interrupted update, and treats identical repeated input as a no-op.

The lifecycle is:

```text
discussing -> accepted -> compiled -> executing -> integrating
-> cohort_verified -> prd_verified -> merged -> deployed
-> production_verified -> complete
```

Skip inapplicable external stages explicitly; do not claim them from a status label alone.

## Bounded Child Context

Materialize each compact child bundle from deterministic state through the shared generated-context renderer. A lane may materialize several compatible Ticket bundles in one controller call; their common stable-prefix digest confirms context reuse, while the Ticket and receipt handoff remain volatile and last. The renderer also writes privacy-safe byte-digest metadata without source paths or authenticated-provenance claims. A child reads only:

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
- Keep the integration branch, PR strategy, and merge owner in parent-owned run state; include them in a child bundle only when a Ticket must act on a named worktree.
- Read `resume.md` only for restart or compaction recovery; read `events.jsonl` only for debugging.

Subagent model selection is defined separately in `docs/custom-agent-routing.md`. Execution Runs may record the resulting requested profile, but the routing contract and Codex native usage audit—not a self-reported Ticket field—establish which profile actually started.
