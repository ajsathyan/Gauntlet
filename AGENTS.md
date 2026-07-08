# Global Agent Coding Workflow

Gauntlet v2.0.2 is a product-thinking harness for AI coding agents. It chooses the lightest mode, depth, and proof scope that can responsibly turn rough asks into coherent product features, prove the requested change, and record only the decisions and exceptions future agents should not have to rediscover.

## Modes

Recommend one mode before non-trivial work. State the recommendation, why, depth, triggered gates, and escalation triggers. The user can override with "use Patch", "use Feature", or "use Release".

```text
Mode: Patch | Feature | Release
Depth: Standard | Deep
Proof scope: smoke | delta | full | not relevant
Triggered gates: Run Log, Panel Guard, Hygiene, TS Durability, Production Quality Bar
```

### Patch

Use Patch for small, clear, low-risk changes where product behavior and proof path are obvious.

Default loop: quick intake check -> implementer -> verify -> self-review -> concise summary.

When Patch uses Deep depth, keep the code surface narrow while comparing alternatives, strengthening proof, or running adversarial review.

### Feature

Use Feature for user-facing workflows, product concepts, high-fidelity features, onboarding, activation, retention, growth, information architecture, or design-heavy work.

Default full loop:

1. intake
2. product-architect
3. planner
4. implementer
5. black-box-tester
6. experience-reviewer
7. run-log-builder

Feature delta: for a small accepted UI or workflow change, scope product-architect, black-box-tester, and experience-reviewer to affected surfaces only. A combined black-box and experience pass is acceptable when the same evidence answers both behavior and UX questions.

Product features must look like the real product surface. Do not put draft labels, agent notes, process notes, or absence-of-metric rationale inside user-facing UI.

### Release

Use Release for production-bound, broad, risky, ambiguous, security/privacy-sensitive, billing, migration, auth, data-integrity, upload, concurrency, public API, or weak-test-coverage work.

Default full loop:

1. intake
2. planner
3. issue-triager
4. implementer
5. architecture hygiene pass
6. adversarial-reviewer
7. black-box-tester
8. issue-triager, only when reviews or tests produce findings, deferrals, or follow-ups
9. deep-code-reviewer
10. run-log-builder

Escalate Patch or Feature to Release when the work touches auth, permissions, billing, migrations, destructive writes, private data, uploads, concurrency, public API contracts, production deploys, large refactors, or any area where a regression could materially harm users.

## Depth

Mode describes the change shape and risk surface. Depth describes how hard Gauntlet should search before settling.

- Standard depth: use the simplest responsible path and prove it works.
- Deep depth: compare plausible approaches, measure before/after when relevant, run adversarial review, and document why the chosen approach is best within the appetite.

Choose Deep depth when the user asks for "best", "maximum", "fastest", "most secure", "audit", "harden", "optimize", "benchmark", "regression-proof", or when small code changes could have large performance, security, reliability, or data-integrity impact.

When depth is ambiguous for optimization or security work, ask whether the user wants an acceptable improvement or the best improvement worth searching for. If the cost appetite is unclear and the likely extra cost is meaningful, stop and ask.

## Proof Scope

Proof scope describes how wide the verification and review pass should be:

- `smoke`: prove the main changed path and confirm no risk triggers are present.
- `delta`: inspect changed surfaces, directly affected states, and changed invariants.
- `full`: run the broader mode loop because product behavior, blast radius, launch risk, weak tests, or durable systems justify it.
- `not relevant`: skip a role or gate with a short reason.

Full checks are trigger-based, not mode theater. Every non-default ceremony must declare its trigger, cap, artifact, and exit condition. Always prove the changed behavior when possible; audit the whole surface only when risk, ambiguity, repetition, or missing proof earns it.

## Workflow Etiquette

Use `docs/workflow-etiquette.md` for the full draft reference. Keep the active workflow lightweight:

```text
Execution Mode: review | autonomous
Decision Gate: none | before blocked archive | before unsafe side effect | before merge | before production change | custom
```

- Use `review` only when goals, requirements, domain relationships, or acceptable defaults need human clarification before autonomous work would be responsible.
- Use `autonomous` when the agent can work without the user watching. Agent self-review, fixture review, code review, and QA do not require `review`.
- Use a `Decision Gate` only for a major unresolved decision, safety failure, or new material assumption. Do not re-ask for behavior the user already requested.
- For p0, p1, and p2 kickoff labels, ask the user to confirm or change the priority/title before implementation. If the user responds affirmatively or continues without objecting, treat the label as accepted and apply it.
- For p3 and p4 kickoff labels, do not block on naming; say `I'll use this.`
- After selecting a kickoff label, call `set_thread_title` immediately; the label is an app action, not just planning text.
- If the user supplies an alternate priority/title, call `set_thread_title` with the user's version and continue from that label.
- Before implementation, include `Edge Cases From This Ask` for p0-p2 work and p3 work with side effects, state changes, user-facing behavior, or a repeated prior miss. Split it into `Need user decision` and `Safe defaults I will apply`; ask only for edge cases that change product behavior, data/money/privacy/security risk, or acceptance criteria.

When the user asks to archive a Codex thread:

1. If the thread title already starts with `/^p[0-4](-auto)?:/`, skip naming.
2. Otherwise suggest a `p#:` or `p#-auto:` four-word-goal title and pass it as `--suggested-title`.
3. Run `scripts/gauntlet.py archive plan --title "$THREAD_TITLE" --git-root "$PROJECT_ROOT" --json`. Pass the PR changelog or closeout content to `scripts/gauntlet.py archive plan --content` so the Archive Summary is printed whether or not archive is currently allowed; use `--content -` when piping a PR body or generated closeout instead of saving another file.
4. If the plan returns pass or warn, run `scripts/gauntlet.py archive execute ... --json`. Execute any returned app actions in order: call `set_thread_title` for `set_thread_title`, then call `set_thread_archived` for `archive_thread`.
5. The CLI may push clean branches or merge an open GitHub PR with `--merge` when checks pass, the PR is mergeable, and no review blocker remains. Do not squash or rebase unless the user asks.
6. If the helper returns review or fail, pause only for a major unresolved decision, safety failure, new material assumption, or git preservation risk. `archive anyway` is acceptable for unresolved strong follow-ups only. For unmerged, unpushed, or dirty code, ask the user to confirm before continuing with `--confirm-git-risk`.
7. Do not pause merely because rename/archive/push/merge is durable when the user already requested that behavior and deterministic safety checks pass.

## Workflow Speedup Helpers

Use CLI helpers at the point where the manual loop would otherwise happen:

- Changed-surface, test, or review setup: `scripts/diff-intel.py "$PROJECT_ROOT"`, `scripts/test-plan.py "$PROJECT_ROOT"`, then `scripts/review-pack.py "$PROJECT_ROOT"`.
- Implementation Memory exists or will drive handoff/changelog work: `scripts/gauntlet.py memory lint --path "$MEMORY_PATH"` and pass it to `scripts/review-pack.py "$PROJECT_ROOT" --implementation-memory "$MEMORY_PATH"`.
- PR/changelog closeout: `scripts/gauntlet.py changelog pr --implementation-memory "$MEMORY_PATH" --git-root "$PROJECT_ROOT"`.
- Archive closeout: reuse the PR changelog or closeout content with `scripts/gauntlet.py archive plan --content "$CHANGELOG_OR_CLOSEOUT" ...`.
- Follow-up capture or thread handoff: `scripts/gauntlet.py followup note ...` or `scripts/gauntlet.py followup thread --content "$FOLLOWUP_FILE" --title "$THREAD_TITLE" --json`.

These helpers are advisory unless the command explicitly performs an accepted action, such as archive execution. Honor confidence and `Cannot verify`, preserve unrelated dirty worktree changes, and remember that thread helpers emit app-action packets; execute those with Codex app tools only after checking the packet.

## Promotion Scanner

Use `promotion-scanner` to produce a Promotion Brief when explicit artifacts show repeated manual or agent work that may deserve promotion into repo code, repo test, repo docs/run log, Gauntlet skill/tool, coverage gap, or Reject.

Trigger it on explicit user request, Release or live-ops wrap-up with repeated manual verification, repeated `Cannot verify`, or repeated run-log evidence. Do not run for ordinary Patch. No live operational actions: never recommend immediate destructive, billing, deploy, security, or production mutations.

Separate stale vs latest evidence, redact secrets/redaction-sensitive details, and include Do not infer warnings. Add or update a `GAP-###` only for Gauntlet-general missing guidance; route repo-specific candidates to repo code, repo test, repo docs/run log, or issue follow-up.

## Task Tiers

- Tier 0 trivial: edit, verify, summarize.
- Tier 1 small: Patch.
- Tier 1 high-upside: Patch with Deep depth.
- Tier 2 medium: Feature or focused Release depending on risk.
- Tier 3 large or risky: Release with role subagents.

## Release Panel Guardrails

Use a role panel only for Release, Tier 3, or when the user explicitly asks for multi-role planning. The panel is a decision aid, not the final artifact.

Every guarded Release panel must produce a launch cut line and one compact decision table:

| Concern | Decision | Why Not Defer | Proof | Plan Delta |
| --- | --- | --- | --- | --- |

Allowed `Decision` values:

- `Ship blocker`
- `Conditional blocker`
- `Manual fallback`
- `Private beta gate`
- `Defer`
- `Reject`

A concern can be `Ship blocker` only when all four conditions are true:

1. It names concrete user, data, money, security, legal, or release-regression harm.
2. It explains why fallback, deferral, private beta, support recovery, or post-launch recovery is not acceptable.
3. It has executable proof or a concrete manual proof script.
4. It changes scope, order, proof, deferral, first task, or rejected alternatives.

If any condition is missing, downgrade the concern to `Conditional blocker`, `Manual fallback`, `Private beta gate`, `Defer`, or `Reject`.

The panel delta must name what changed because the panel ran: first ready task, dependency order, proof requirement, downgraded blocker, rejected alternative, deferral, fallback, or launch cut line. Invalid deltas include restating the same plan in role language, adding generic "must test" wording, expanding a wishlist, or adding cleanup without evidence that it blocks proof or creates launch risk.

For Release, auth, billing, migrations, permissions, privacy, concurrency, data integrity, or ambiguous broad work, run the same planning prompt twice when cost is reasonable. Compare only missing blockers, dependency order, proof requirements, first ready task, deferrals, and rejections. Merge only items that pass the decision table. Do not union every idea.

Use one release-risk reviewer or a compact role panel whose only job is to feed the decision table. If the decision table has no meaningful panel delta, collapse to the normal planner output and state that the panel added no unique value.

## Production Quality Bar

Run the Production Quality Bar only when an app or project is near-launch, launch-ready, in private beta, production-bound, deploy-sensitive, or explicitly being hardened or audited. Use the Gauntlet reference document as the source of truth: `docs/production-quality-bar.md` in the Gauntlet source repo, or `$AGENT_HOME/gauntlet/docs/production-quality-bar.md` in a global install. Do not assume that file exists in the target project unless the project ships Gauntlet docs locally.

Skip it for ordinary Patch work, early prototype work, local demo code, copy/config/docs-only tweaks, narrow visual polish, UI-only Feature work with no launch intent, tests/build-tool changes, and speculative refactors unless the user asks.

When active, keep the pass bounded: identify the trigger, cap, artifact, and exit condition; route automatable checks to existing CI/local commands; route product/engineering judgment to the relevant role; and record only material decisions, release proof, skipped proof, `Cannot verify`, launch cut lines, or gap candidates. Near-launch release proof may include automated GitHub release tags, generated artifacts, release notes, required checks, no-mutation or dry-run evidence, and rollback/support proof.

Use the bar to inspect control plane or core workflow ownership boundaries, invariants, launch-critical proof, durable state, state machines, operator/user feedback loops, threat model and redaction policy, and decision-oriented UI. Do not turn these into blockers unless there is concrete launch harm, proof, and a fix or deferral path.

## Architecture Hygiene Pass

For Feature, Release, and Tier 2/3 or broad multi-file changes, run one architecture hygiene pass after implementation and before completion. Scope it to smoke, delta, or full based on blast radius. Prefer `deep-code-reviewer`; route broad or follow-up findings through `issue-triager`. If later review fixes change code, refresh only the affected hygiene checks.

Do not run the pass by default for Patch unless the change touched shared architecture, replaced a path, introduced multiple abstractions, used generated code, used Deep depth for broad work, or the user asked for cleanup.

Check for current-change dead code, unreachable branches, unused exports/components/files/dependencies, stale sample code, obsolete TODOs, unnecessary abstractions, duplicated logic, mismatched tests/fixtures/docs, invisible scope creep, and compatibility shims with no consumer.

Use existing repo tooling first: typecheck, lint, tests, import/dependency scanners already present, and targeted `rg` searches. Fix only current-change cruft with low blast radius and passing proof. For Feature and Release work, record meaningful hygiene decisions or exceptions in the run log.

For ordinary narrow Feature changes, use a bounded delta scan. Full hygiene is earned by shared modules, new abstractions, replacement paths, generated code, broad diffs, weak tests, or Release risk.

## TypeScript Durability Gate

Do not make TypeScript durability standards a global default. Treat them as a triggered gate, not a mode or profile combination. Before applying heavyweight TypeScript standards, run:

```sh
scripts/classify-ts-durability.sh "$PROJECT_ROOT"
```

The classifier writes `.gauntlet-ts-durability.json` with `durabilityRequired: true|false`, concrete `reason`, `triggers`, `filesScanned`, and `generatedAt`. If TypeScript is not in scope, the gate may be skipped or recorded as `durabilityRequired: false` with reason `TypeScript not in scope`.

Turn TS durability on only for concrete triggers: auth, permissions, billing, payments, credits, entitlements, migrations, schema changes, persistence adapters, data integrity, public API contracts, SDK surfaces, cross-service protocols, idempotency, retries, durable workflows, queues, concurrency, compensation, security/privacy-sensitive data, shared domain modules, Release mode, production-bound risk, existing durable TS patterns in a broad or non-UI durable surface, or explicit user requests to harden, productionize, audit, secure, or refactor architecture.

Non-triggers include UI-only Feature work, visual polish, copy, simple config, local demo code, tests/docs/build-tool changes, and clearly UI-only changed files even when durable patterns exist elsewhere in the repo.

If the classifier cannot name a concrete trigger, set `durabilityRequired: false`. Agents may not apply TypeScript durability rules unless the artifact says `durabilityRequired: true` or the user explicitly asks.

## Decision Log Gate

For Feature and Release work, or any Tier 2/3 task with material decisions or exceptions, maintain a small exceptions-first run log:

```text
docs/gauntlet-runs/YYYY-MM-DD-<slug>.md
```

For narrow Patch work, skip the run log unless the user asks, the work escalates, Deep depth makes the work decision-heavy, or future agents would lose material context.

The run log is not a diary and not a proof dump. It captures only:

- Material assumptions.
- Non-obvious decisions and tradeoffs.
- Exceptions: checks skipped, things that went wrong, `Cannot verify`, user decisions needed, and follow-ups.
- For Release only, a compact proof summary or launch cut line when it materially affects risk.

Do not list successful routine checks in the run log. Put routine passing verification in the final chat summary. Use `run-log-builder` to create or update the file.

## Occasional And Systemic Checks

Some checks are valuable but should not run for every task:

- Skill eval full suite: run before Gauntlet releases, after eval infrastructure changes, or during periodic calibration. For ordinary skill edits, run targeted changed-skill evals plus the skill linter.
- Global install verification: run after installer changes, global workflow changes, or explicit global install requests. Skip it for local-only docs unless the installed copy is the target.
- Full responsive, accessibility, visual-regression, motion, and dead-component sweeps: run for major frontend work, demos, releases, or repeated UI findings.
- Full product-architect and experience reviews: run for new or ambiguous workflows; use delta review for accepted small changes.
- Second Release issue-triager only when reviews or tests create findings, deferrals, or follow-ups.

## Coverage Gaps

Autonomously capture candidate gaps when a run exposes missing reusable guidance, but never promote a gap into a standard without human approval.

Write candidates to:

```text
docs/coverage-gaps.md
```

Good candidate signals:

- The agent made a material assumption because no rule/reference existed.
- A reviewer says the same issue keeps coming up.
- A finding is `Cannot verify` because the expected standard is missing.
- The same class of issue appears across multiple run logs.
- A lint/check cannot decide safely without product context.
- The agent asks a human question that repo guidance should eventually answer.
- A rule has too many exceptions and should move back to guidance.

Human review chooses: rule, reference, exemplar, lint, eval, coverage gap, or no change. Accepted changes go into the narrowest relevant file and pass checks before merging.

Use the promotion rule when deciding what to record: if a failure is reliably detectable and has a concrete fix, add or update a `GAP-###` candidate with a suggested destination such as lint, eval, guidance, or no change. If the check depends on product judgment, record the judgment gap instead of pretending it is a linter. At the end of the final response, name only gaps added or updated in this run using `Added GAP-###: Short name - why it matters`; do not list routine passes.

## Frontend Quality Gate

Run this gate only for substantial frontend work: new or materially changed components, user-facing Feature work, design-heavy prototypes, frontend Release work, broad responsive/state changes, or repeated UI findings. Skip it for narrow Patch work, copy-only changes, local config, and non-frontend work unless the user asks.

Use the Gauntlet reference document as the source of truth: `docs/ui-constitution.md` in the Gauntlet source repo, or `$AGENT_HOME/gauntlet/docs/ui-constitution.md` in a global install. Do not assume that file exists in the target project unless the project ships Gauntlet docs locally. Keep the pass bounded:

- Use existing project lint, typecheck, test, browser, and accessibility tooling first.
- Apply general UI lint candidates from the Gauntlet reference document `docs/design-lint-candidates.md` or `$AGENT_HOME/gauntlet/docs/design-lint-candidates.md` when code can detect the failure.
- Route browser-visible behavior through `black-box-tester`.
- Route workflow, state, accessibility, and product feel through `experience-reviewer`.
- Fix in-scope blockers. For reliable repeated issues without guidance, add a pending coverage gap instead of expanding the checklist.
- Do not create a design system or speculative local UI convention layer for an early prototype. Use the tiny UI constitution and existing repo conventions only.

## Intake Gate

Before substantial implementation, ensure the task has: goal, scope, non-goals, affected interfaces, acceptance criteria, verification/proof, constraints, and assumptions/open questions.

Ask only questions that materially affect implementation, product behavior, risk, UX, data, API behavior, verification, or scope. Otherwise make a reasonable assumption, record it, and proceed.

Treat `/intake` or "use intake" as an explicit request to run the intake skill before planning or implementation. For follow-ups, run delta intake: identify what changed, which assumptions are invalid, which acceptance criteria are new, and what new proof is required.

## Role Skills

Use these skills on demand:

- intake: turns rough intent into an implementable spec.
- product-architect: turns user-facing intent into a coherent product feature with workflow, IA, meaningful metrics, assumptions, and PM/design acceptance criteria.
- planner: turns accepted specs into ordered implementation steps.
- issue-triager: converts plans/findings into prioritized ready tasks.
- implementer: executes scoped code changes.
- adversarial-reviewer: stress-tests assumptions, edge cases, trust boundaries, and regressions.
- black-box-tester: validates behavior externally.
- experience-reviewer: reviews user-facing features for workflow clarity, IA, progress feedback, states, accessibility, trust, activation, retention, and growth.
- deep-code-reviewer: reviews correctness, maintainability, tests, and regression risk.
- run-log-builder: creates or updates exceptions-first Markdown run logs and pending coverage gaps.
- ian-xiaohei-illustrations: creates English-only Xiaohei explanation illustrations when a visual explanation would help reviewers understand architecture, code paths, workflows, process boundaries, trust boundaries, or operational flow.

When spawning subagents, explicitly point each subagent at the relevant skill and give it a bounded packet. Prefer parallel subagents only for independent files, state, surfaces, charters, risk lenses, or review lanes with separate proof paths. Do not create one agent per failure mode or split one tightly coupled decision tree across workers.

Parallelism must beat its context cost. Do not use subagents when each one would need the same large spec, trace, codebase context, screenshot set, or design rationale and the work is not truly independent. Use one agent with a shared context window when repeated handoff packets would cost more than the expected speedup.

For child Codex chats or long-running delegated lanes, keep the main chat as orchestrator. The main chat owns the user-facing ledger, user questions, merge decisions, and final synthesis. A child chat does bounded work from a task packet, returns a compact report, and does not ask the user directly; it reports `Needs decision` to the main chat instead.

Title child chats with the normal priority prefix plus lane/status tags:

```text
p#-auto: [C1][In Progress] Backend policy layer
p#-auto: [C2][Blocked] Dashboard Policy UI
p#-auto: [C3][To Do] Proof regression tests
```

Use only these child-lane statuses: `To Do`, `In Progress`, `Blocked`, `In Review`, `Done`, and `Canceled`. Use `Blocked` only for a concrete blocker such as a missing interface, user decision, credential, merge conflict, failed proof, or external state. Otherwise keep future work as `To Do` with a dependency note.

For write-heavy child chats, create a separate git worktree by default unless the lane is a tiny clearly disjoint patch. Read-only review, exploration, and log-analysis lanes do not need worktrees by default. Name the worktree in the ledger and packet, preserve unrelated dirty work, and keep file ownership explicit.

Archive a child chat after its report is integrated into the main-chat ledger. If the same lane is needed later, unarchive it or create a focused follow-up thread with the prior lane id and a fresh packet.

When parallel lanes are proposed, write `.gauntlet/subagent-plan.json` and run `scripts/check-subagent-plan.py "$PROJECT_ROOT" .gauntlet/subagent-plan.json --run-id "$RUN_ID"` before dispatch. Do not dispatch rejected lanes. If the validator ran, include `.gauntlet/subagent-plan-summary.json` counts in the final response.

### Subagent Handoff Packet

- Project root and relevant files or surfaces
- Child lane id, title, status, dependency note, and worktree path when write-heavy
- Skill to use and role objective
- Accepted spec, task packet, or review source
- In scope and out of scope
- Files/areas to inspect
- Files/areas to avoid
- Constraints and non-goals
- Proof already available
- Expected return format

### Role Report Contract

Role reports should use shared slots so the orchestrator can update the run log only when needed:

- Verdict: `Approved`, `Needs fixes`, `Needs proof`, `Needs decision`, `Blocked`, or `Cannot verify`
- Evidence reviewed
- Findings by P0/P1/P2/P3 with file/line, surface, command, or repro evidence when possible
- Cannot verify: missing proof, why it matters, and the next check
- Residual risk
- Agent next: one concrete action
- Coverage gap candidate: only when reusable guidance is missing

## System-Level Explanation Visuals

For Feature or Release work with system-level changes or system-level scope, create a Mermaid diagram whenever formal structure would make the system, code, workflow, or process easier to understand. Use `ian-xiaohei-illustrations` whenever an explanatory image would make the same scope easier to understand. Treat them as complementary; omit either only when redundant or impossible, and state the rationale in the run log or final summary.

When a Xiaohei image is generated, credit the author directly under the image with this Markdown line:

```markdown
Credit: [helloianneo](https://github.com/helloianneo/ian-xiaohei-illustrations)
```

## Product Features

For Feature mode, the product-architect owns the product workflow and defines what progress means. The experience-reviewer validates whether the implemented experience communicates that progress well.

Product-architect priorities:

- Define the user's first-value moment.
- Shape the workflow and information architecture.
- Identify onboarding, activation, retention, growth, trust, and completion moments.
- Include metrics only when they are meaningful to the user's task.
- Prefer behavior-based metrics over vanity metrics.
- Record metric rationale in the run log when it is non-obvious, not inside product UI.
- Make the next best action obvious.

Experience-reviewer priorities:

- Check whether the feature feels like the real product, not a draft explanation.
- Verify loading, empty, error, success, disabled, and partial-data states when relevant.
- Check whether progress, completion, and next action are clear.
- Surface PM/design questions separately from engineering defects.

## Stop Conditions

Stop and ask before proceeding when:

- A decision materially changes product behavior
- Data loss, migration, billing, security, or privacy risk is ambiguous
- The requested behavior conflicts with existing architecture or policy
- The likely cost exceeds the stated appetite
- Required credentials, permissions, or external state are unavailable

## Completion Rule

A coding task is complete only when acceptance criteria are met, relevant checks ran or limitations are stated, required run logs and coverage-gap candidates are updated, new or updated `GAP-###` items are named at the end of the final response, no blocking review/test/triage findings remain, and the final response includes what changed, what was verified, and remaining risks. Every Gauntlet implementation closeout should print the Archive Summary when archiving or preparing to archive.

For Feature, Release, and applicable Tier 2/3 work, the architecture hygiene pass must be marked not applicable, completed with no blocking findings, or triaged into bounded follow-up work.

For Tier 2/3 work, add one short workflow lesson when useful: whether a recurring failure should update a skill, test, checklist, or this file.
