# Do It Worktree Flow Plan

Date: 2026-06-18

## Upstream Dependency

This plan starts after `guarded-panel-plan-upgrade.md` is accepted and implemented.

The guarded-panel upgrade owns:

- The compact decision table.
- Valid decision values.
- The blocker bar.
- Repeated-run synthesis rules.
- Panel delta rules.
- Architecture hygiene blocker criteria.

This Do It/worktree plan consumes those upgraded planning outputs. It should not redefine the guarded-panel planning contract except where needed to explain how review cards become implementation scope.

## Problem

Gauntlet can generate strong plans and review briefs, but implementation scope is still too easy for an agent to expand. Long plans invite over-implementation, and long checklists invite skipped checks. The missing control surface is a human-owned `Do It` column: humans choose which cards enter implementation, and agents implement only those cards.

After the guarded-panel upgrade, Gauntlet will have deterministic planning outputs: decision rows, proof requirements, deltas, deferrals, and rejections. This plan turns those upgraded planning outputs into stable review cards, dependencies, proof requirements, and a human-selected implementation queue.

## Target Outcome

Add a Gauntlet flow where:

1. The upgraded guarded-panel plan generates release concerns, blockers, deferrals, proof, and plan deltas.
2. A review brief converts accepted decision rows into review cards.
3. Humans drag selected cards into `Do It`.
4. The agent implements only the human-selected `Do It` cards, ideally in a scoped worktree.
5. New findings go back to Review or Backlog, never directly into `Do It`.

The result should preserve planning breadth while making implementation scope explicit and human-controlled.

## Appetite

Mode: Slice, because this changes the review brief workflow and human interaction model.

Depth: Deep, because the workflow affects future agent scope control and Release safety. Use repeated prompt comparison as the proof method, but keep implementation slices small.

Escalate to Release if the implementation changes persisted data migration semantics, destructive file operations, external GitHub writes, or multi-agent worktree automation that can mutate user branches.

## Core Flow

```text
Intake
  -> Guarded-panel planning upgrade
  -> Compact decision table
  -> Review brief cards
  -> Human moves cards to Do It
  -> Agent implements only Do It cards in scoped worktree
  -> Proof updates review brief
  -> New findings return to Review/Backlog
```

## Deterministic Planning Rules

Use the deterministic planning rules from `guarded-panel-plan-upgrade.md` as the source of truth.

This plan only adds the downstream conversion from accepted decision rows to implementation cards. If the guarded-panel upgrade changes the decision vocabulary or blocker bar, update this plan to match instead of creating a competing set of rules.

## Repeated Plan Run Rule

Repeated planning belongs to `guarded-panel-plan-upgrade.md`.

The Do It/worktree flow receives the synthesized decision table and review cards after repeated-run synthesis is complete. It must not rerun planning or add additional planning variants during implementation.

## Card Generation Rules

Cards are generated mechanically from the decision table:

- `Ship blocker` -> review card.
- `Conditional blocker` -> review card, not automatically `Do It` ready.
- `Manual fallback` -> review card when a human decision is needed.
- `Private beta gate` -> review card with an explicit launch condition.
- `Defer` -> backlog note.
- `Reject` -> non-goal note.

Each card must include:

- `Concern`
- `Decision`
- `Depends On`
- `Why Not Defer`
- `Proof`
- `Do It Scope`
- `Out Of Scope`
- `Agent Next`
- `Human Decision Needed`

Do not let the model create a second, unrelated card universe after the decision table. Cards derive from table rows.

## Do It Rules

`Do It` is human-owned.

Rules:

- `Do It` starts empty.
- The plan may recommend first human selections, but must not pre-populate `Do It`.
- The agent implements only cards currently in `Do It`.
- The agent may not self-promote Review or Backlog cards into `Do It`.
- New findings become Review or Backlog cards.
- If selected cards conflict or dependencies are missing, the agent stops and reports the blocker instead of expanding scope.

Recommended `Do It` card states:

- `Backlog`
- `Review`
- `Do It`
- `In Progress`
- `Proof Needed`
- `Done`
- `Blocked`

Only humans move cards into `Do It`. Agents may move a selected card from `Do It` to `In Progress`, `Proof Needed`, `Done`, or `Blocked` based on work state.

## Do It Eligibility

Eligibility is derived, not written by the model as a blanket yes/no.

A card is eligible for human selection when:

- Decision is `Ship blocker`, or an approved `Conditional blocker`.
- Dependencies are complete or selected together.
- Proof is executable or a concrete manual script.
- `Do It Scope` and `Out Of Scope` are present.
- The card is small enough to implement and verify in one focused worktree.

If a card fails eligibility, keep it in Review or Backlog until refined.

## Dependency Ordering

For Used Price-style paid releases, prefer this default dependency ladder:

1. Account/Auth/RLS boundary
2. Account-owned credit ledger
3. Stripe checkout/webhook idempotency
4. Credit consume, concurrency, and durable limits
5. Support recredit/refund recovery
6. Observability for paid paths
7. CI/staging release gate
8. Architecture hygiene

The planner may merge or split cards, but dependencies should preserve this order unless it records a concrete reason.

## Worktree Execution Contract

When worktree support is available, each `Do It` batch should run in a scoped worktree or branch:

- Worktree name should include the top selected card handle, for example `do-it-rb-002-stripe-webhook`.
- The agent reads only the selected `Do It` cards plus linked proof/context.
- The agent records changed files, proof, and reopened concerns back into the review brief.
- The agent must not implement unselected cards, even when nearby code makes them tempting.
- If implementation exposes a new blocker, the agent creates or updates a Review card and stops when it changes the selected scope.

Batch size guidance:

- Default: 1 card.
- Allow 2-3 cards only when dependencies are tight and proof can run together.
- Never select more than 3 cards into one worktree without an explicit human reason.

## Architecture Hygiene

Architecture hygiene remains a bounded pass, not a standing cleanup project.

Default:

- `Conditional blocker`
- Not `Do It` ready until implementation or proof exposes ambiguity

It becomes `Ship blocker` only when it finds:

- A bypass around the trusted account, credit, payment, or support path
- Dead/obsolete code that can run in production and contradicts the release path
- Duplicate mutation paths that make proof unreliable
- Generated or speculative abstractions that prevent a selected card from being verified

## Review Brief Product Changes

Add or evolve the review brief to support:

- A Review queue with decision/proof cards.
- A human-owned `Do It` column.
- Dependency indicators on cards.
- A selected-card details panel with `Do It Scope`, `Out Of Scope`, proof, and linked records.
- A clear warning when a card in `Do It` has unmet dependencies.
- Copy prompt actions scoped to selected `Do It` cards.
- A Changelog record when a human moves a card into `Do It`.

The review brief should not become a project-management board. It should remain a review and scope-control surface.

## Ordered Implementation Slices

### Prerequisite: Complete Guarded Panel Plan Upgrade

Finish `guarded-panel-plan-upgrade.md` before this plan begins.

Acceptance criteria:

- `AGENTS.md` and `planner` define the compact decision table.
- Valid decision values are stable.
- Blocker bar and panel delta rules are stable.
- Repeated-run synthesis is documented.
- Review brief builder preserves decision/proof/delta information.
- Used Price pressure test confirms the upgraded panel output is better than the prior guarded panel.

### Slice 1: Document The Do It Contract

Update Gauntlet instructions and relevant skills so the flow is explicit:

- Humans own `Do It`.
- Agents implement only selected `Do It` cards.
- New findings return to Review or Backlog.
- Guarded-panel planning output is the upstream source of implementation cards.

Acceptance criteria:

- `AGENTS.md` describes the `Do It` contract.
- `planner` skill points to the guarded-panel output as the source for review cards.
- `implementer` skill refuses unselected cards.
- `review-brief-builder` skill describes `Do It` cards and copy prompts.

### Slice 2: Extend Review Brief Data Model

Add fields that support deterministic cards:

- `decision`
- `whyNotDefer`
- `dependsOn`
- `doItScope`
- `outOfScope`
- `doItState`
- `humanSelectedAt`
- `selectedBy`
- `worktree`

Acceptance criteria:

- Schema validates the new fields.
- Existing review brief data either migrates cleanly or has a documented reset path.
- `Done` still requires passed or not-applicable proof.

### Slice 3: Add Do It UI

Add a human-owned `Do It` column or lane to the review brief.

Acceptance criteria:

- Review cards can be visually distinguished from `Do It` cards.
- `Do It` starts empty for new briefs.
- Dependency warnings appear before implementation.
- Card details show scope, out-of-scope, proof, and copy prompt.
- The UI avoids feeling like a heavy project board.

### Slice 4: Add Copy Prompts For Execution

Create copy actions that instruct an agent to implement selected `Do It` cards only.

Acceptance criteria:

- Copy prompt names selected handles.
- Prompt includes scope, out-of-scope, proof, dependencies, and artifact path.
- Prompt explicitly says not to self-promote new findings into `Do It`.
- Prompt stays compact enough for practical reuse.

### Slice 5: Consume Guarded-Panel Synthesis

Consume the upgraded guarded-panel synthesis without redefining it.

Acceptance criteria:

- Review brief can display whether one, two, or three planning runs were used upstream.
- Do It cards link back to the synthesized decision rows.
- The Do It flow does not union or alter upstream planning ideas by default.

### Slice 6: Add Worktree Handoff Guidance

Document and optionally script the worktree execution pattern.

Acceptance criteria:

- Worktree naming convention exists.
- Selected card batch size guidance exists.
- Agent handoff prompt references selected `Do It` cards only.
- New findings route back to Review or Backlog.

### Slice 7: Validate With Used Price

Use Used Price as the pressure test.

Acceptance criteria:

- Run the same planning prompt twice for Used Price.
- Synthesize deterministic cards.
- Human-selected `Do It` remains empty until selection.
- First recommended selection is clear but not auto-selected.
- Generated implementation prompt is scoped to selected cards only.

## Must-Haves

- Human ownership of `Do It`
- Guarded-panel upgrade completed first
- Cards derived from upgraded guarded-panel decision rows
- Dependency-aware `Do It` eligibility
- Executable proof for blockers
- No agent self-promotion into `Do It`
- Bounded architecture hygiene
- Review brief copy prompts scoped to selected cards

## Non-Goals

- Building a full project-management system
- Automatically choosing `Do It` cards
- One agent per checklist item
- Persisting every speculative planning idea
- Broad architecture cleanup
- Replacing human release judgment
- Creating GitHub issues by default

## Risks And Unknowns

- The review brief can become too board-like and lose its review focus.
- Human drag-and-drop state may need persistence and conflict handling.
- Existing review brief data may need migration.
- Multiple planning runs can inflate scope if synthesis rules are weak.
- Worktree automation can create branch/worktree clutter if not constrained.
- Agents may still try to implement nearby unselected code unless copy prompts are blunt.

## Verification Plan

- Schema validation for review brief data.
- Browser check for Review, Details, Changelog, and `Do It` interactions.
- Copy prompt inspection for scope containment.
- Used Price throwaway planning test with two identical prompt runs.
- Simulated implementation prompt test: confirm the agent can identify selected cards and refuses unselected work.
- Architecture hygiene test: confirm cleanup remains conditional unless proof exposes a bypass.

## First Ready Task

After `guarded-panel-plan-upgrade.md` is complete, update Gauntlet documentation and skills to define the `Do It` contract:

- `Do It` is human-owned.
- Agents implement only selected cards.
- New findings return to Review or Backlog.
- The upgraded guarded-panel decision table is the source of review cards.

Do not change the review brief UI until the written contract is accepted.
