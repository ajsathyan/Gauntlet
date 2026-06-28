# Global Agent Coding Workflow

Gauntlet v2.0.1 chooses the lightest mode and depth that can responsibly produce and prove the requested change, then records only the decisions and exceptions future agents should not have to rediscover.

## Modes

Recommend one mode before non-trivial work. State the recommendation, why, depth, triggered gates, and escalation triggers. The user can override with "use Patch", "use Feature", or "use Release".

```text
Mode: Patch | Feature | Release
Depth: Standard | Deep
Triggered gates: Run Log, Panel Guard, Hygiene, TS Durability
```

### Patch

Use Patch for small, clear, low-risk changes where product behavior and proof path are obvious.

Default loop: quick intake check -> implementer -> verify -> self-review -> concise summary.

When Patch uses Deep depth, keep the code surface narrow while comparing alternatives, strengthening proof, or running adversarial review.

### Feature

Use Feature for user-facing workflows, product concepts, high-fidelity features, onboarding, activation, retention, growth, information architecture, or design-heavy work.

Default loop:

1. intake
2. product-architect
3. planner
4. implementer
5. black-box-tester
6. experience-reviewer
7. run-log-builder

Product features must look like the real product surface. Do not put draft labels, agent notes, process notes, or absence-of-metric rationale inside user-facing UI.

### Release

Use Release for production-bound, broad, risky, ambiguous, security/privacy-sensitive, billing, migration, auth, data-integrity, upload, concurrency, public API, or weak-test-coverage work.

Default loop:

1. intake
2. planner
3. issue-triager
4. implementer
5. architecture hygiene pass
6. adversarial-reviewer
7. black-box-tester
8. issue-triager
9. deep-code-reviewer
10. run-log-builder

Escalate Patch or Feature to Release when the work touches auth, permissions, billing, migrations, destructive writes, private data, uploads, concurrency, public API contracts, production deploys, large refactors, or any area where a regression could materially harm users.

## Depth

Mode describes the change shape and risk surface. Depth describes how hard Gauntlet should search before settling.

- Standard depth: use the simplest responsible path and prove it works.
- Deep depth: compare plausible approaches, measure before/after when relevant, run adversarial review, and document why the chosen approach is best within the appetite.

Choose Deep depth when the user asks for "best", "maximum", "fastest", "most secure", "audit", "harden", "optimize", "benchmark", "regression-proof", or when small code changes could have large performance, security, reliability, or data-integrity impact.

When depth is ambiguous for optimization or security work, ask whether the user wants an acceptable improvement or the best improvement worth searching for. If the cost appetite is unclear and the likely extra cost is meaningful, stop and ask.

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

## Architecture Hygiene Pass

For Feature, Release, and Tier 2/3 or broad multi-file changes, run one architecture hygiene pass after implementation and before completion. Prefer `deep-code-reviewer`; route broad or follow-up findings through `issue-triager`. If later review fixes change code, refresh only the affected hygiene checks.

Do not run the pass by default for Patch unless the change touched shared architecture, replaced a path, introduced multiple abstractions, used generated code, used Deep depth for broad work, or the user asked for cleanup.

Check for current-change dead code, unreachable branches, unused exports/components/files/dependencies, stale sample code, obsolete TODOs, unnecessary abstractions, duplicated logic, mismatched tests/fixtures/docs, invisible scope creep, and compatibility shims with no consumer.

Use existing repo tooling first: typecheck, lint, tests, import/dependency scanners already present, and targeted `rg` searches. Fix only current-change cruft with low blast radius and passing proof. For Feature and Release work, record meaningful hygiene decisions or exceptions in the run log.

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

### Subagent Handoff Packet

- Project root and relevant files or surfaces
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

A coding task is complete only when acceptance criteria are met, relevant checks ran or limitations are stated, required run logs and coverage-gap candidates are updated, no blocking review/test/triage findings remain, and the final response includes what changed, what was verified, and remaining risks.

For Feature, Release, and applicable Tier 2/3 work, the architecture hygiene pass must be marked not applicable, completed with no blocking findings, or triaged into bounded follow-up work.

For Tier 2/3 work, add one short workflow lesson when useful: whether a recurring failure should update a skill, test, checklist, or this file.
