# Guarded Panel Plan Upgrade

Date: 2026-06-19

## Top-Level Goal

Create a prototyping system where the human spends roughly 20% of the time on intent, scope, review surfaces, and deterministic gates so the remaining 80% can be automated AI-driven coding with less supervision risk.

## Problem

Gauntlet's guarded panel planning is better than unconstrained role theater, but it still carries three risks:

1. Long panel output can sound authoritative without changing the plan.
2. Too many role concerns can inflate into launch blockers.
3. Proof can stay vague, leaving implementation agents with broad instructions instead of executable checks.

The panel needs a smaller, deterministic planning contract. It should improve Release planning quality without introducing a human-selected `Do It` queue or worktree execution flow. That downstream implementation-control layer belongs to `do-it-worktree-plan.md`.

## Target Outcome

Upgrade guarded-panel planning so every Release panel produces:

- A launch cut line.
- One compact decision table.
- A high blocker bar.
- Executable proof for blockers.
- Clear deferrals and rejections.
- A concrete panel delta, or a decision to collapse the panel into normal planner output.

The upgraded panel should generate better plans and better review brief cards while remaining lean enough that agents cannot hide behind checklist ceremony.

It should also protect prototype velocity by preventing heavyweight TypeScript durability standards from being applied unless the work has concrete durability triggers.

## Appetite

Mode: Patch.

Depth: Deep.

Why: This changes planning behavior rather than product runtime. The code/document surface should stay small, but the workflow affects high-risk Release planning, so it needs comparison-based proof.

Escalate to Feature only if the review brief UI/schema needs substantial changes to display the upgraded decision table.

## Simplified Mode Model

Keep Gauntlet's user-facing route small:

- `Patch`: small code, docs, config, or local behavior changes.
- `Feature`: user-facing product workflow changes that should feel real enough to evaluate.
- `Release`: risky, broad, production-bound, security/data/billing/API/migration work.

Depth stays separate:

- `Standard`: simplest responsible path.
- `Deep`: compare alternatives, strengthen proof, or run extra review when the upside/risk warrants it.

Do not add TypeScript durability as another mode/profile combination. Treat it as a triggered gate:

```text
Mode: Patch | Feature | Release
Depth: Standard | Deep
Triggered gates: Review Brief, Panel Guard, Hygiene, TS Durability
```

Example: `Feature, Standard depth, gates: Review Brief + Hygiene; TS durability not required because this is UI-only.`

## Naming Decision

Rename `Slice` to `Feature`.

Why:

- `Feature` is easier for humans to understand before they learn Gauntlet.
- It better signals user-facing product work, not just a vertical technical slice.
- It pairs naturally with review brief language such as feature workflow, first-value moment, states, proof, and PM/design acceptance.

Do not rename `Release` to `Version` in this upgrade.

Why:

- `Release` names the risk posture: production-bound, rollback-aware, support-aware, and proof-heavy.
- `Version` sounds like an artifact or milestone, not a mode that should trigger stronger gates.
- A future product UI can still show a version label for release candidates, but the agent workflow should keep `Release` as the operational mode.

Migration rule:

- Replace user-facing and skill-facing `Slice` mode references with `Feature`.
- Keep historical references only when describing old behavior or compatibility.
- Keep `Release` as the high-risk mode name.

## Core Rule

A panel is valid only if it produces:

1. A launch cut line.
2. A compact decision table.
3. Executable proof for every blocker.
4. At least one concrete plan delta.
5. Clear deferred and rejected work.

If it cannot do those things, collapse the output into the normal planner format and say the panel added no unique value.

## Decision Table Contract

Every guarded-panel plan must include exactly this table shape:

| Concern | Decision | Why Not Defer | Proof | Plan Delta |
| --- | --- | --- | --- | --- |

Allowed `Decision` values:

- `Ship blocker`
- `Conditional blocker`
- `Manual fallback`
- `Private beta gate`
- `Defer`
- `Reject`

No other decision labels should appear in the final decision table.

## Blocker Bar

A concern can be `Ship blocker` only when all four conditions are true:

1. It names concrete user, data, money, security, legal, or release-regression harm.
2. It explains why fallback, deferral, private beta, or support recovery is not acceptable.
3. It has executable proof or a concrete manual proof script.
4. It changes scope, order, proof, deferral, first task, or rejected alternatives.

If any condition is missing, downgrade the concern to `Conditional blocker`, `Manual fallback`, `Private beta gate`, `Defer`, or `Reject`.

## Panel Delta Rule

The panel must show what changed because the panel ran.

Valid deltas include:

- A different first ready task.
- A changed dependency order.
- A new executable proof requirement.
- A downgraded blocker.
- A rejected attractive alternative.
- A deferral that protects launch scope.
- A private-beta or manual-support fallback.

Invalid deltas:

- Restating the same plan in role language.
- Adding generic "must test" wording.
- Expanding a wishlist without changing the cut line.
- Adding cleanup work without evidence that it blocks proof or creates launch risk.

## Repeated Planning Run Rule

Default:

- Run one planning pass.

For Release, auth, billing, migrations, permissions, privacy, concurrency, data integrity, or ambiguous broad work:

- Run the same planning prompt twice when the cost is reasonable.
- Compare only:
  - Missing blockers
  - Dependency order
  - Proof requirements
  - First ready task
  - Deferrals and rejections
- Merge only items that pass the decision table.
- Do not union every idea.

For very high-risk work:

- Run three planning outputs, or one planning output plus one release-risk reviewer.
- Synthesize through the same decision table.

## Role Panel Simplification

Do not create one agent or checklist item per failure mode.

Use either:

- One release-risk reviewer who checks blockers, fallbacks, proof, and panel theater.
- A compact role panel whose only job is to feed the decision table.

Panel lenses may still include Auth/Data, Payments, Support/Observability, and Release Quality, but their output should be compressed into the final decision table. Role essays are supporting notes, not the artifact.

## Architecture Hygiene Rule

Architecture hygiene is not a default launch blocker.

Default decision: `Conditional blocker` or `Defer`.

It becomes `Ship blocker` only when it finds:

- A bypass around the trusted account, credit, payment, or support path.
- Dead or obsolete code that can run in production and contradicts the release path.
- Duplicate mutation paths that make proof unreliable.
- Generated or speculative abstractions that prevent a selected release concern from being verified.

Broad cleanup, style preferences, naming cleanup, and speculative simplification stay deferred.

## TypeScript Durability Gate

Do not make TypeScript durability standards a global default. Treat them as a triggered boolean gate selected by an executable classifier.

Before applying heavy TypeScript standards, run a deterministic classifier such as:

```sh
scripts/classify-ts-durability.sh "$PROJECT_ROOT"
```

The classifier writes `.gauntlet-ts-durability.json`:

```json
{
  "schemaVersion": "1.0",
  "durabilityRequired": false,
  "reason": "UI-only Feature; no auth, billing, persistence, API, or shared domain changes.",
  "filesScanned": ["package.json", "tsconfig.json"],
  "triggers": [],
  "generatedAt": "2026-06-19T00:00:00Z"
}
```

If `durabilityRequired` is `false`, use Gauntlet's lightweight baseline and local repo conventions. If it is `true`, apply TypeScript durability standards for the relevant changed surface. Non-TypeScript work can skip the gate or record `durabilityRequired: false` with reason `TypeScript not in scope`.

Durability triggers:

- Auth, permissions, billing, payments, credits, or entitlements.
- Migrations, schema changes, persistence adapters, or data integrity work.
- Public API contracts, SDK surfaces, or cross-service protocol changes.
- Idempotency, retries, durable workflows, queues, concurrency, or compensation.
- Security/privacy-sensitive data or secrets handling.
- Shared domain modules used by multiple flows.
- Release mode or production-bound risk.
- Existing repo already uses durability patterns such as Effect, typed results, branded/refined types, domain modules, or strict schema parsing, and the work is broad, unclear, or touches a non-UI durable surface.
- User explicitly asks to harden, productionize, audit, secure, or perform architecture refactoring.

Non-triggers:

- UI-only Feature work.
- Visual polish, copy, simple config, or local demo code.
- One-screen prototypes without durable data paths.
- Tests, docs, or build-tool changes unless they touch a durability trigger.
- Clearly UI-only changed files, even when the repo has durable patterns elsewhere.
- Repos with no existing durability patterns when the task does not introduce durable domain behavior.

If the classifier cannot name a concrete trigger from task scope, file paths, package/config signals, or existing repo patterns, set `durabilityRequired: false`. Agents may not apply TypeScript durability rules unless the artifact sets `durabilityRequired: true` or the user explicitly asks for them.

The classifier should preserve the useful baseline from the TypeScript standards gist without importing the whole standard globally:

- Inspect existing conventions before adding patterns, libraries, adapters, or abstractions.
- Parse untrusted inputs at boundaries.
- Keep secrets out of errors, traces, logs, snapshots, review briefs, and assets.
- Avoid shallow pass-through abstractions.
- Test important behavior through real seams.

## Review Brief Impact

The review brief should surface:

- Launch cut line.
- Compact decision table.
- Panel delta.
- Deferrals and rejections.
- Proof gaps.
- TypeScript durability gate decision and reasons when TypeScript work is in scope.
- Follow-up prompts based on handles.

This plan does not add a `Do It` column. It only improves the planning and review-card source material. A future Do It/worktree flow can consume these upgraded planning outputs after this upgrade is accepted.

## Ordered Implementation Steps

### Step 1: Update Global Guarded-Panel Instructions

Update `AGENTS.md` so Release panel guidance uses the compact decision table and high blocker bar.

Acceptance criteria:

- `AGENTS.md` names the decision table contract.
- `AGENTS.md` defines valid decision values.
- `AGENTS.md` says panels collapse when they do not change the plan.
- `AGENTS.md` explicitly avoids one-agent-per-failure-mode checklist sprawl.

### Step 2: Update Planner Skill

Update `skills/planner/SKILL.md` so Release planning produces the upgraded panel shape.

Acceptance criteria:

- Planner output includes launch cut line when Release/high-risk work needs it.
- Planner uses the compact decision table.
- Planner downgrades concerns that fail the blocker bar.
- Planner stops once the first ready task and proof path are obvious.

### Step 3: Update Review And Triage Skills

Update `issue-triager`, `deep-code-reviewer`, and related review guidance so findings preserve the decision taxonomy.

Acceptance criteria:

- Triage uses `Ship blocker`, `Conditional blocker`, `Manual fallback`, `Private beta gate`, `Defer`, and `Reject`.
- Hygiene findings require evidence and proof impact.
- Reviewers do not turn taste or general cleanup into blockers.

### Step 4: Add TypeScript Durability Gate Classifier

Add or specify `scripts/classify-ts-durability.sh` and the `.gauntlet-ts-durability.json` artifact.

Acceptance criteria:

- TypeScript durability standards are applied only when the classifier sets `durabilityRequired: true` or the user explicitly requests them.
- The classifier records concrete triggers and files/configs scanned.
- The default for unclear work is `durabilityRequired: false`.
- Release/high-risk TS work with auth, billing, migrations, public API, data integrity, security/privacy, concurrency, or existing durable patterns in a broad or non-UI durable surface sets `durabilityRequired: true`.
- UI-only/prototype TS work sets `durabilityRequired: false`.

### Step 5: Update Review Brief Builder

Update `review-brief-builder` so review briefs can represent the upgraded plan without inventing a second planning model.

Acceptance criteria:

- Review cards can link back to decision table rows.
- Proof gaps are explicit.
- Deferrals and rejections become notes/backlog records, not hidden prose.
- Panel delta is visible in the review brief.
- TypeScript durability gate decisions are visible as notes or review cards when relevant.

### Step 6: Validate With Used Price

Use Used Price as the pressure test.

Acceptance criteria:

- Generate the current guarded-panel output.
- Generate the upgraded guarded-panel output.
- Run the same upgraded planning prompt twice.
- Compare blocker count, proof specificity, dependency order, deferrals, rejected alternatives, and first ready task.
- Confirm the upgraded output is smaller, clearer, and less prone to blocker inflation.
- Run the TypeScript durability classifier on at least one prototype/UI task and one high-risk/backend-style task, and confirm the gate decision changes for concrete reasons.

## Must-Haves

- Compact decision table
- Strict decision vocabulary
- High blocker bar
- Executable proof for blockers
- Panel delta or panel collapse
- Optional repeated-run synthesis for high-risk Release work
- Bounded architecture hygiene
- Deterministic TypeScript durability gate classifier
- Clear deferrals and rejections
- Used Price pressure test

## Non-Goals

- Adding a human-owned `Do It` column
- Worktree execution
- Drag/drop board behavior
- One agent per checklist item
- Full project-management workflow
- Automatic implementation scope selection
- Broad cleanup tooling
- Applying the full TypeScript standards gist globally
- Rewriting prototype code into durable domain architecture by default
- Expanding Gauntlet into a matrix of mode/profile combinations

## Risks And Unknowns

- The compact table may lose useful rationale if supporting notes are too sparse.
- Two planning runs can inflate scope if synthesis unions every idea.
- The decision vocabulary may need mapping to existing review brief enums.
- Existing review brief data may need light migration if the schema changes.
- Agents may still produce role essays unless the final artifact shape is strongly enforced.
- The TypeScript durability classifier may miss subtle durable-domain work if it relies only on file paths or package names.
- The classifier may slow prototyping if its triggers are too broad.
- Some repos may intentionally use durable patterns everywhere; the classifier must respect existing local convention without forcing broad migrations.

## Verification Plan

- Run `git diff --check` after doc/skill edits.
- Compare old and upgraded Used Price plan outputs.
- Run two identical upgraded planning prompts and inspect variation.
- Verify no concern becomes a `Ship blocker` without harm, why-not-defer, proof, and plan delta.
- Verify architecture hygiene remains conditional unless it exposes a bypass or proof blocker.
- Verify TypeScript durability sets `durabilityRequired: false` when no concrete trigger is present.
- Verify TypeScript durability sets `durabilityRequired: true` for auth, billing, migrations, public API, data integrity, security/privacy, concurrency, Release mode, or existing durable TS patterns.
- If review brief schema/template changes, validate sample data and inspect the UI in a browser.

## First Ready Task

Update `AGENTS.md` and `skills/planner/SKILL.md` with the compact decision table, valid decision vocabulary, high blocker bar, panel delta rule, repeated-run synthesis rule, simplified mode/depth/gate model, and TypeScript durability gate classifier contract.

Do not start the Do It/worktree implementation plan until this guarded-panel upgrade is accepted and its output contract is stable.

## Handoff To Do It Worktree Plan

This plan is upstream of `do-it-worktree-plan.md`.

Completion criteria before starting the Do It/worktree plan:

- Guarded-panel planning has a stable compact decision table.
- Valid decision values are documented.
- The blocker bar is documented.
- Repeated-run synthesis is documented.
- TypeScript durability gate selection is deterministic and defaults off unless concrete triggers exist.
- Review brief builder can preserve decision/proof/delta information.
- Used Price pressure test confirms the upgraded panel produces better planning output.
