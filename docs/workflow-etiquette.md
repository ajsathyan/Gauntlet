# Workflow Etiquette

Status: authoritative Gauntlet collaboration reference.

Purpose: keep work legible and preserve user agency without turning metadata, planning, or closeout into ceremony.

## Planning

Carry forward user constraints, corrections, and dislikes. Report a plan delta only when their input changed the plan; do not restate the plan after a simple “go.”

Gauntlet uses one accepted spec and one canonical plan:

- Intake and product exploration refine the accepted spec in conversation.
- Planner turns the accepted spec into bounded task packets.
- `.gauntlet/subagent-plan.json` is the only additional planning artifact when real parallel lanes exist.
- Implementation Memory, separate design documents, and handwritten child packets are not active defaults.

For Deep work, compare alternatives inside one pass. Use a second independent plan only when concrete Release-class harm or an explicit user request earns it.

## Classification And Titles

Classify path, depth, verification, execution posture, and priority internally. Surface them only when the classification changes cost, scope, authority, proof, or a decision.

Set or update the thread title silently once the goal is stable. Do not ask the user to approve priority or title metadata. Existing priority format remains:

```text
p#: four word goal
p#-auto: four word goal
```

Use `-auto` when the agent can proceed through reversible local choices without the user watching. A Decision Gate may still name the next unsafe or unresolved boundary.

Priority remains consequence-based:

- `p0`: material Release-class harm.
- `p1`: substantial Feature or strategic direction.
- `p2`: consequential or Deep Patch.
- `p3`: normal Patch or bounded Research.
- `p4`: routine admin, low-durable exploration, or intentionally parked work.

If priority is unchanged, say nothing. If it changes, state the old and new values once with the material trigger.

The legacy five-field kickoff block is deprecated. `scripts/check-workflow-etiquette.py --require-kickoff` remains warning-only for migration and must not block execution.

## Decisions And Edge Cases

Ask only when an answer materially changes product behavior, data, money, privacy, security, acceptance, cost, or an external side effect.

Before consequential implementation, perform a bounded foresight check:

- identify 2–4 edge cases that change code or proof;
- surface only material findings or a user decision;
- do not print a no-op edge-case section;
- record a clean scope addition as `Scope delta checked: no material change.` in the canonical plan.

High-value surfaces include auth, billing, migrations, privacy, concurrency, data integrity, uploads, public APIs, control planes, automation, live operations, and product flows with ambiguous state.

## Research

Research is a first-class path, not a pre-Release ceremony.

- Bound the question, evidence, freshness, and downstream consequence.
- Separate observation, source claim, and inference.
- Deep Research performs exhaustive comparison inside one bounded pass.
- Delegated evidence lanes must be independent.
- The orchestrator spot-checks consequential claims and synthesizes; it does not redo complete child lanes.
- Transition to implementation by passing the accepted conclusion/spec to planner without repeating intake.

## Delegation

Use delegation only when parallelism beats context cost.

Use the canonical manifest for two or more parallel lanes or any write-heavy child implementation lane. It contains shared accepted source/constraints plus complete lane entries. Each lane names objective, skill, ownership, typed dependencies, consumes/produces, proof, and its context delta. Do not create a second Markdown packet. A single small read-only child does not need this gate.

Child behavior:

- receives a prompt generated from its canonical lane entry;
- works inside named files/state/worktree;
- returns a compact Role Report;
- reports `Needs decision` to the main task instead of asking the user;
- does not push or merge independently.

Main-task behavior:

- owns user decisions, synthesis, integration, PR, and merge;
- checks returned evidence and integration boundaries;
- does not duplicate full child assignments;
- waits 30–60 seconds or for meaningful state change instead of repeatedly polling unchanged state;
- archives a child task after its report is integrated when the product supports it.

Native Codex state owns child progress; do not require title or status churn. Use the stable lane id in the packet and report as the coordination handle.

## Execution

Communicate like a senior collaborator:

Surface:

- changed judgment, scope, risk, or verification;
- blockers, warnings, and material assumptions;
- user decisions;
- concise status during long work;
- final behavior, proof, and residual risk.

Keep routine reads, searches, formatting, command setup, generated packets, and unchanged polls in tools or artifacts.

In autonomous mode, continue through reversible local choices and expected verification fixes. Stop for the explicit Gauntlet stop conditions, not for metadata approval.

## Continuity And Debrief

When the user asks to pause or leave a landing pad, capture only:

```text
Current goal
State
Last useful context
Next best move
Open loops
Verification state
Reentry prompt
```

Debrief only when the plan was surprised, the user corrected a material assumption, or proof found a reusable failure pattern. Keep it to covered, missed, and destination. Routine clean completion gets no postmortem.

## Promotion

Promotion is not an automatic Release wrap-up.

- Ordinary work may include one compact candidate in the run log/final response.
- Run `promotion-scanner` when the user explicitly asks or repeated evidence supports a real durable destination decision.
- Produce a standalone `Promotion Brief` only when that durable artifact is itself requested or required across runs.
- Repo-specific lessons stay in repo code, tests, docs, or issues. Gauntlet-general gaps use the coverage-gap process.

## Archive

When the user asks to archive:

1. Reuse the existing valid title or set one silently.
2. Pass PR/closeout content to `scripts/gauntlet.py archive plan --content` so the Archive Summary is visible.
3. Resolve real git, proof, follow-up, or safety blockers.
4. Run `archive execute` only after the plan passes or warns within accepted authority.
5. Execute returned app actions in order: title, then archive.

Archive does not silently grant merge authority. Merge only from an accepted user request or explicit `--merge`, after objective checks pass.

Use `--confirm-git-risk` only when the user explicitly accepts dirty, unpushed, or unmerged preservation risk. Do not squash or rebase unless asked.

## Git Discipline

Use a branch for persisted work. Use a worktree for p0–p2, broad, dirty-worktree, or write-heavy delegated work. Preserve unrelated files. The main task owns integration and merge.

"Merge this," "land this," or "merge this to main" authorizes the contextual changelog → commit → push → PR → checks → merge-commit → remote cleanup → default-branch verification flow for the current scope. Use `scripts/gauntlet.py merge prepare`, `merge plan`, and `merge execute`; ask only for a new material choice or preservation risk.

See `docs/github-discipline.md` for the detailed beginner-friendly branch → coherent commits → PR → verification → merge-commit → cleanup path.

## Token Bounds

- Plan delta: at most three bullets.
- Material foresight: at most four edge cases.
- Status update: one decision or changed fact.
- Child prompt: generated from one manifest entry; no shared background duplication.
- Assumptions: at most three material items.
- Debrief: at most three bullets and only when triggered.
- Archive: quiet happy path; explain only blockers or warnings.
