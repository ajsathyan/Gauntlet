# Workflow Etiquette

Status: authoritative Gauntlet collaboration reference.

Purpose: keep work legible and preserve user agency without turning metadata, planning, or closeout into ceremony.

## Normal Request Path

Use this path before Gauntlet lifecycle routing when all of these are true:

- the requested artifact is bounded, low-consequence, readily reversible, and directly checkable;
- the work uses existing or supplied content, data, or interfaces, or needs only a direct lookup; and
- it does not change a durable schema, contract, methodology, architecture, production system, or safety boundary.

Typical cases are presentation or formatting edits, copying existing results into an existing UI, simple lookups, routine administration, and comparable low-risk work. Deliver the artifact, run the direct outcome or smoke check, and stop. Do not create intake artifacts, plans, tickets, subagents, audits, review panels, run logs, coverage gaps, or follow-on improvements for these requests.

A user correction narrows or replaces the corrected premise; it does not authorize a schema, methodology, or workflow redesign. Existing data that is merely displayed or copied needs an outcome check, not exhaustive re-verification, unless the request or a concrete integrity risk requires it. Explicit narrow user scope outranks Gauntlet's preference for more process. Safety, permissions, destructive effects, and other consequential boundaries still apply; when one appears, route only that affected portion through the lightest responsible path or ask for the required authority.

## Planning

Carry forward user constraints, corrections, and dislikes. Report a plan delta only when their input changed the plan; do not restate the plan after a simple “go.”

Gauntlet uses one accepted spec and one canonical plan:

- Intake and product exploration refine the accepted spec in conversation.
- Planner turns the accepted spec into bounded implementation tasks and child tickets where delegation is useful.
- Implementation Memory, separate design documents, and duplicate child tickets are not active defaults.

For a PRD-backed build, one product task may keep several Epics in the canonical human source. Its explicit build-ready target is frozen into one launch set; each included Epic gets one visible implementation task, one Ticket Graph, and one Execution Run. See `docs/prd-execution.md`.

For Deep work, compare alternatives inside one pass. Use a second independent plan only when concrete Release-class harm or an explicit user request earns it.

## Classification And Titles

Classify path, depth, verification, execution posture, and priority internally. Surface them only when the classification changes cost, scope, authority, proof, or a decision.

Set or update the root thread title silently once the goal is clear. Do it as soon as practical and no later than the third substantive user-authored message. Count requests and corrections; ignore generated context, tool or skill payloads, and acknowledgements such as “okay” or “continue.” If the goal later changes materially, update the title again. Do not ask the user to approve priority or title metadata, and do not narrate the rename. Existing priority format remains:

```text
p#: four word goal
p#-auto: four word goal
```

The goal is exactly four whitespace-delimited words. Gauntlet-owned thread actions must validate this shape before emitting `set_thread_title` or `create_thread`; a raw host rename remains outside Gauntlet's interception boundary.

Use `-auto` when the agent can proceed through reversible local choices without the user watching. A Decision Gate may still name the next unsafe or unresolved boundary.

Priority remains consequence-based:

- `p0`: material Release-class harm.
- `p1`: substantial Feature or strategic direction.
- `p2`: consequential or Deep Patch.
- `p3`: normal Patch or bounded Research.
- `p4`: routine admin, low-durable exploration, or intentionally parked work.

If priority is unchanged, say nothing. If it changes, state the old and new values once with the material trigger.

The legacy five-field kickoff block is deprecated. `scripts/check-workflow-etiquette.py --require-kickoff` remains warning-only for migration and must not block execution.

## Minimum Useful Questions

Use an 80/20 question rule across every Gauntlet path and skill. Start from existing context. Make and label safe assumptions when missing detail would not materially change the result.

Ask only when the answer could materially change the result, product behavior, document purpose or audience, scope, acceptance, authority, data, money, privacy, security, cost, or an external effect. When clarification is necessary, ask at most three short questions in one message. Prefer one or two. Keep each question focused on one decision, do not send a generic questionnaire, and otherwise provide a provisional result.

Questioning is complete when every question asked maps to a consequential decision whose outcome could change. This is a judgment rule, not a phrase-counting or questionnaire-format check.

## Decisions And Edge Cases

Before consequential implementation, perform a bounded foresight check:

- identify 2–4 edge cases that change code or proof;
- surface only material findings or a user decision;
- do not print a no-op edge-case section;
- update scope and proof when an addition is material; omit no-op scope phrases when it is clean.

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

Use delegation only when parallelism beats context cost. Normal Requests stay in the main task.

This is standing authorization to spawn subagents automatically when two or more useful lanes have independent ownership, state, and proof. Do not wait for the user to request delegation, and do not use Release classification as a prerequisite. Keep the work in the main task when the split would create dependency waits or repeated context without a real speed or evidence benefit.

A Gauntlet Ticket is a generated execution assignment within the current plan or Execution Run, not an issue-tracker record. Dispatch each child directly from one bounded ticket. Include only its material objective, skill, ownership, dependencies, consumes/produces contracts, constraints, proportional proof expectations, return contract, and ask-parent policy. Proof fields are optional. Native Codex state and main-task messages own live coordination.

Use one active implementation Ticket per child by default. The same child may take sequential related Tickets when affinity preserves useful context; do not co-own one implementation Ticket. The parent verifies ordinary work directly. Independent verification Tickets exist only for a named consequential boundary.

Schedule from the ready queue rather than document order. Integrate finished Tickets as they arrive and run targeted proof. Declare a Cohort only for a shared material invariant, then run one fresh final Epic verification against canonical acceptance on exact integration HEAD.

Child behavior:

- receives its bounded ticket directly from the main task;
- works inside named files/state/worktree;
- returns a compact Role Report;
- reports `Needs decision` to the main task instead of asking the user;
- does not push or merge independently.

Main-task behavior:

- owns user decisions, synthesis, integration, PR, and merge;
- treats receipts as evidence pointers, independently checks the oracle, reruns or resolves returned evidence, and checks integration boundaries;
- does not duplicate full child assignments;
- integrates child commits as results arrive and runs targeted checks, owns any frozen Review Unit PRs into the integration branch, then runs final Epic proof and opens that Epic's Project PR;
- waits 30–60 seconds or for meaningful state change instead of repeatedly polling unchanged state;
- archives a child task after its report is integrated when the product supports it.

Native Codex state owns child progress; do not require title or status churn. Use the stable lane id in the ticket and report as the coordination handle.

The Execution Run owns durable progress. After dispatch begins, its source lock, manifest, and resume file are authoritative; conversation is advisory except for new user decisions. A restart or compaction resumes from those files. Child context is materialized from the assigned ticket, relevant versioned shared context, named dependency contracts, and owned source paths—not the entire PRD, manifest, events, or unrelated receipts.

For an `implement the PRD` launch, execute the controller's secret-free `open_browser` action immediately after run binding by reading its private state file and invoking or reusing the Codex in-app Browser with the transient fragment. Do not claim the dashboard opened because a URL was printed. Missing Browser/server support is a quiet non-blocking fallback. Reconcile reuses the singleton supervisor, which refreshes run facts and telemetry automatically, discovers late siblings, and stops only after all Epics are complete, stopped, or failed. Archive cleanup may call `epic-tasks progress-stop` repeatedly.

Keep stable instruction text first and ticket-specific context last. Canonical field order, sorted IDs, stable formatting, omitted empty fields, and delayed volatile metadata improve prefix reuse and token efficiency. Do not promise cache hits: the host, model, routing, and exact prompt bytes still control caching.

Material Gauntlet workflows use deterministic controls for deterministic facts: the generated-context renderer owns prompt serialization, the router owns profile selection, the PRD controller owns Ticket and lane state, and the evaluation controllers own task admission and experiment records. Human-readable sources remain authoritative for meaning. External harnesses remain adapters, and model prose never becomes the canonical mechanism for state transitions, authority enforcement, or executable acceptance. Normal Requests bypass this machinery.

Reconcile native start metadata asynchronously. A profile/version mismatch opens the non-blocking dispatch circuit for new affected work without killing already-running ordinary children. Keep analytics ingestion outside scheduler locks. A multi-Ticket lane persists and integrates each Ticket independently so a blocked sibling cannot hold completed work.

Do not narrate the delegation lifecycle to the user unless a higher-priority host instruction explicitly requires disclosure. All applicable workflow etiquette remains active during quiet execution: perform classification, foresight, proof, state, and archive checks internally, then surface only a required user-facing action or material exception such as a title change, suggestion, decision, blocker, or safety stop.

## Execution

Communicate like a senior collaborator:

Surface:

- changed judgment, scope, risk, or verification;
- blockers, warnings, and material assumptions;
- user decisions;
- concise status during long work;
- final behavior, proof, and residual risk.

Keep routine reads, searches, formatting, command setup, generated tickets, and unchanged polls in tools or artifacts.

For material proof, follow `docs/meaningful-proof.md`. A test or receipt is useful only when its observable oracle distinguishes the intended result from a plausible wrong one. Structural checks and self-reports must not be presented as behavior.

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
2. Pass PR/closeout changelog content to `scripts/gauntlet.py archive plan --content`; missing or malformed Archive Summary content blocks archive actions.
3. Resolve real git, proof, follow-up, or safety blockers.
4. Run `archive execute` only after the plan passes or warns within accepted authority.
5. Execute returned app actions in order: set the title if needed, present the Archive Summary to the user, then archive the thread.

Gauntlet-owned archive plans always place `present_archive_summary` immediately before `archive_thread`. A direct host archive call remains outside Gauntlet's interception boundary and must not be used for Gauntlet workflow closeout.

Archive does not silently grant merge authority. Merge only from an accepted user request or explicit `--merge`, after objective checks pass.

Use `--confirm-git-risk` only when the user explicitly accepts dirty, unpushed, or unmerged preservation risk. Do not squash or rebase unless asked.

## Git Discipline

Use a branch for persisted work. Use a worktree for p0–p2, broad, dirty-worktree, or write-heavy delegated work. Preserve unrelated files. The main task owns integration and merge.

"Merge this," "land this," or "merge this to main" authorizes the contextual changelog → commit → push → ready PR → required checks → merge-commit → landed-revision verification → established revision-attributable post-merge monitoring → local default-branch fast-forward → remote branch deletion → safe isolated-worktree and local-branch removal flow for the current scope. Skip monitoring only when the repository provides none; never infer production health from PR CI. Preserve cleanup state when unique or dirty work, branch drift, another worktree, or failed monitoring makes deletion unsafe. Generic merge authority does not archive the task or install locally. For an Epic Run, use `scripts/gauntlet.py merge prepare|plan|execute --run <run>` and its controller-owned schema 3.0 Project PR facts; use schema v1 `--handoff` only for non-run Patches. Ask only for a new material choice or preservation risk.

Use the `land` skill for this flow. Default to local `git` and authenticated `gh`; use a GitHub connector only when explicitly requested or the CLI cannot perform a required operation.

"Implement the PRD" authorizes freezing its complete accepted target, creating one visible task and one Execution Run per independently shippable Epic, and carrying dependency-ready Epics through branch/worktree setup, Ticket execution, exact-revision proof, PR, merge, specified deployment/production stages, required rollback, durable updates, and safe cleanup. Proposed, deferred, and materially unresolved work stays out.

See `docs/github-discipline.md` for the detailed beginner-friendly branch → coherent commits → PR → verification → merge-commit → cleanup path.

## Token Bounds

- Plan delta: at most three bullets.
- Material foresight: at most four edge cases.
- Status update: one decision or changed fact.
- Child prompt: one bounded ticket; no shared background duplication.
- Assumptions: at most three material items.
- Debrief: at most three bullets and only when triggered.
- Archive: quiet happy path; explain only blockers or warnings.
