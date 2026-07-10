# Gauntlet Workflow Router

Gauntlet is the workflow authority for coding, product, research, review, and release work in this environment. Use the lightest path and proof that can responsibly produce the requested result.

Installed Gauntlet root: `{{GAUNTLET_ROOT}}`

Resolve Gauntlet references and commands from that absolute root. Never resolve a Gauntlet command against a downstream repository's similarly named files.

## Work Paths

Choose internally:

```text
Path: Research | Patch | Feature | Release
Depth: Standard | Deep
Proof scope: smoke | delta | full | not relevant
Execution: review | autonomous
Decision gate: none | before unsafe side effect | before merge | before production change | custom
```

- Research: bound the question and evidence, investigate, separate observation from inference, spot-check consequential claims, and report limits.
- Patch: use for a small, clear, low-risk change with an obvious proof path.
- Feature: use for a user-facing workflow, product concept, onboarding, activation, information architecture, or design-heavy change.
- Release: use for production-bound or materially risky work, including auth, permissions, billing, migrations, privacy, destructive writes, public contracts, durable data, concurrency, deploys, or broad refactors.
- Standard depth takes the simplest responsible path and proves it.
- Deep depth compares plausible approaches and strengthens evidence when the user asks for an audit, optimization, hardening, a benchmark, or the best option worth searching for.
- Smoke proves the main changed path. Delta covers changed surfaces and adjacent invariants. Full is earned by blast radius, launch risk, weak tests, or durable systems.

Keep classifications and no-op gate reports out of user-facing chat unless they change cost, scope, authority, proof, or a decision the user must make.

Priorities are consequence-based: p0 for material Release harm, p1 for substantial Feature or strategy work, p2 for consequential or Deep patches, p3 for normal patches or bounded research, and p4 for routine administration or deliberately parked exploration.

## Intake And Planning

Before substantial implementation, establish the goal, scope, non-goals, affected interfaces, acceptance criteria, proof, constraints, and material assumptions. Ask only questions whose answers change product behavior, data, money, privacy, security, cost appetite, external side effects, or acceptance.

Use the relevant installed Gauntlet skill from `{{AGENT_HOME}}/skills/<skill>/SKILL.md` when its trigger applies. The core roles are:

- `intake`: turn rough intent into an implementable spec.
- `product-architect`: shape user-facing workflow, information architecture, first value, trust, and meaningful metrics.
- `planner`: turn an accepted spec into bounded implementation tasks.
- `implementer`: execute accepted tasks with scoped changes and proof.
- `issue-triager`: classify and route plans, findings, failures, and follow-ups.
- `adversarial-reviewer`: stress-test assumptions, edge cases, authority, recovery, and regressions.
- `black-box-tester`: validate behavior through external outcomes.
- `experience-reviewer`: review workflow clarity, states, accessibility, trust, and next action.
- `deep-code-reviewer`: review correctness, maintainability, tests, integration, and regression risk.
- `run-log-builder`: capture material decisions, exceptions, and coverage gaps.
- `promotion-scanner`: evaluate repeated manual or agent work for promotion after Release or live-ops evidence, not ordinary Patch work.

Do not invoke a second overlapping lifecycle when Gauntlet already owns the workflow. Domain and tool skills remain welcome when they add a concrete capability without replacing the accepted Gauntlet path.

Stop planning when the first coherent build step and its proof path are clear. Do not create redundant specs, plans, packets, or reports.

## Implementation And Proof

- Read before editing, match repository patterns, keep interfaces narrow, and avoid unrelated cleanup.
- Preserve unrelated dirty work. Never overwrite, discard, archive over, or include it without authority.
- Use a branch for persisted changes. Use a separate worktree for p0-p2, broad, dirty-worktree, or write-heavy delegated work.
- Add or update tests when behavior changes. When a practical harness exists, observe the relevant failure, implement the smallest source fix, and refactor while green.
- Diagnose before fixing unexpected behavior: reproduce, trace the earliest divergence, state a falsifiable cause, and run the smallest discriminating check.
- Evidence precedes completion claims. State what proof establishes and what remains unverifiable.
- Treat review feedback as evidence to verify against the accepted spec, code, and tests.
- Use pull requests as decision and proof bundles. Preserve coherent checkpoint commits and follow repository merge policy.

For changed-surface, test, review, and archive helpers, invoke the installed scripts by absolute path, for example:

```sh
python3 {{GAUNTLET_ROOT}}/scripts/diff-intel.py "$PROJECT_ROOT"
python3 {{GAUNTLET_ROOT}}/scripts/test-plan.py "$PROJECT_ROOT"
python3 {{GAUNTLET_ROOT}}/scripts/review-pack.py "$PROJECT_ROOT"
python3 {{GAUNTLET_ROOT}}/scripts/gauntlet.py archive plan --title "$THREAD_TITLE" --git-root "$PROJECT_ROOT" --json
```

Detailed Git and archive guidance: `{{GAUNTLET_ROOT}}/docs/github-discipline.md` and `{{GAUNTLET_ROOT}}/docs/workflow-etiquette.md`.

Archive behavior is authority-sensitive: use the installed archive planner and execute only the actions it returns. Preserve the user's requested merge behavior and do not invent an additional confirmation after merge authority has already been granted.

## Delegation And Quiet Execution

Parallelism must beat its context cost. Delegate only independent files, state, contracts, or evidence lanes with separate proof paths. The main task owns user decisions, integration, synthesis, the final branch, and the pull request.

For two or more implementation lanes, keep one canonical `.gauntlet/subagent-plan.json` and validate it with `python3 {{GAUNTLET_ROOT}}/scripts/check-subagent-plan.py "$PROJECT_ROOT" .gauntlet/subagent-plan.json --run-id "$RUN_ID"`. Do not require a second prose packet. Write-heavy lanes use isolated worktrees unless a tiny disjoint change makes that unnecessary.

Child agents return compact machine receipts. Keep routine coordination, packets, status narration, and internal reports out of user-facing chat. Surface only:

- a decision requiring new user authority;
- an unrecoverable failure or safety stop;
- a host-required terse heartbeat; or
- the brief final outcome and proof.

Retry safe recovery silently while the next attempt is materially different. Stop when recovery would repeat the same failure fingerprint, require new authority, risk destructive external state, or exceed the accepted appetite.

## Triggered Gates

Run gates only when their trigger applies:

- Feature, Release, or material multi-file work: bounded architecture hygiene after implementation.
- Substantial frontend work: use `{{GAUNTLET_ROOT}}/docs/ui-constitution.md` and `{{GAUNTLET_ROOT}}/docs/design-lint-candidates.md`.
- Near-launch, private-beta, production-bound, hardened, or audited work: use `{{GAUNTLET_ROOT}}/docs/production-quality-bar.md` with a named cap and exit condition.
- Durable TypeScript surfaces: run `{{GAUNTLET_ROOT}}/scripts/classify-ts-durability.sh "$PROJECT_ROOT"`; apply heavyweight durability rules only when the classifier identifies a concrete trigger.
- Meaningful skill or workflow changes: use `{{GAUNTLET_ROOT}}/docs/skill-quality-bar.md` and run targeted changed-skill checks.
- Feature, Release, or material decision-heavy work: keep an exceptions-first run log in the target repository's Gauntlet run-log directory only when future agents would otherwise lose important context.
- Missing reusable guidance: record a pending coverage-gap candidate; do not promote it into a standard without human approval.

Skip full UI, production, TypeScript durability, role-panel, and systemic eval sweeps for ordinary narrow patches unless the user explicitly asks or repeated evidence earns them.

## Authority And Completion

Stop for a material unresolved decision, ambiguous data-loss/migration/billing/security/privacy risk, missing required credentials or permission, conflict with accepted architecture or policy, or likely cost beyond the accepted appetite.

A coding task is complete only when:

- acceptance criteria are met;
- changed behavior is proved or the precise limitation is stated;
- required review findings are resolved or explicitly deferred within authority;
- required run-log or coverage-gap updates are made;
- unrelated user work is preserved; and
- the final response briefly names changed files, proof, and unresolved risks.

Do not claim a behavior from prose compliance alone. Prefer observable actions, artifacts, tests, side effects, routing choices, and proof.
