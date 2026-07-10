# Global Agent Coding Workflow

Gauntlet is the single workflow authority for coding, product, research, review, and release work in this environment. Version 2.0.2 chooses the lightest path and proof that can responsibly produce a useful result.

## One Workflow

- Use Gauntlet for intake, planning, implementation, delegation, review, verification, git completion, and continuity.
- Do not invoke overlapping workflow systems such as Superpowers brainstorming, writing-plans, executing-plans, subagent-driven-development, or finish-the-branch flows.
- A domain or tool skill is still welcome when it adds a concrete capability—frontend design, browser control, documents, PDFs, APIs, or a specialist review—without imposing a second lifecycle.
- Gauntlet contains adapted techniques from Superpowers with attribution and an upstream review map in `$AGENT_HOME/gauntlet/docs/upstream-superpowers.md`. Those techniques are Gauntlet behavior, not runtime dependencies on Superpowers skills.

## Work Paths

```text
Path: Research | Patch | Feature | Release
Depth: Standard | Deep
Verification scope: smoke | delta | full | not relevant
Execution mode: review | autonomous
Decision gate: none | before unsafe side effect | before merge | before production change | custom
```

Classify internally. Surface the classification only when it changes cost, scope, authority, verification, or a decision the user should make.

### Research

Use Research for investigation, comparison, audits, recommendations, and implementation discovery when no code change is requested yet.

Default loop: bound the question and evidence → investigate → distinguish observation from inference → spot-check consequential claims → answer with limitations and the next useful action.

Research does not inherit implementation gates merely because it is broad. Use Deep when the user asks for an audit, exhaustive comparison, best option, benchmark, or high-consequence answer. Create an implementation plan only when the user asks for one or accepts a change direction.

### Patch

Use Patch for small, clear, low-risk changes with an obvious proof path.

Default loop: quick intake → implement → verify changed behavior → self-review → concise summary.

### Feature

Use Feature for user-facing workflows, product concepts, onboarding, activation, information architecture, and design-heavy work.

Default loop: intake → product-architect when product behavior is not already settled → planner → implementer → bounded black-box and experience review → exceptions-first run log when material.

Feature delta may combine black-box and experience review when the same evidence answers both. Product features must look like the real product surface; keep draft/process notes out of user-facing UI.

### Release

Use Release for production-bound or materially risky work: auth, permissions, billing, migration, privacy, destructive writes, public contracts, durable data, concurrency, deploys, or broad refactors whose regression could harm users.

Default loop: intake → planner → issue triage when needed → implementer → architecture hygiene → adversarial review → black-box proof → deep code review → exceptions-first run log.

Second Release issue-triager only when review or tests create findings, deferrals, or follow-ups. Full checks are trigger-based, not automatic theater.

## Depth And Verification

- Standard: take the simplest responsible path and prove it works.
- Deep: compare plausible approaches, measure when relevant, run an adversarial pass, and record why the chosen path wins within the stated appetite.
- `smoke`: prove the main changed path.
- `delta`: prove changed surfaces, adjacent states, and changed invariants.
- `full`: run broader checks only when blast radius, launch risk, weak tests, or durable systems earn them.
- `not relevant`: skip with a short reason when proof truly does not apply.

Every non-default ceremony must declare its trigger, cap, artifact, and exit condition. Do not confuse breadth with risk.

## User Attention And Titles

- Ask only about decisions that materially change product behavior, data, money, privacy, security, acceptance, cost appetite, or external side effects.
- Set or update the thread title silently once the goal is stable. Do not ask the user to approve priority or title metadata.
- Priorities remain consequence-based: p0 material Release harm; p1 substantial Feature/strategy; p2 consequential or Deep Patch; p3 normal Patch or bounded Research; p4 routine admin, low-durable exploration, or deliberately parked work.
- If the priority is unchanged, say nothing about it. Explain a change only when scope or risk materially moved.
- Do not print a no-op edge-case section. Surface edge cases only when they alter the plan, proof, or require a decision.
- `review` means requirements or acceptable defaults still need the user. Self-review and QA are autonomous work.
- A Decision Gate exists only for a named unresolved decision or unsafe side effect; never re-ask for already accepted behavior.

Detailed collaboration and archive behavior lives in `$AGENT_HOME/gauntlet/docs/workflow-etiquette.md`.

## Intake, Specs, And Plans

Before substantial implementation, establish goal, scope, non-goals, affected interfaces, acceptance criteria, proof, constraints, and material assumptions. Ask only questions whose answers change those.

Use one accepted spec and one canonical plan:

- Intake and product work refine the accepted spec; they do not create redundant permanent documents by default.
- Planner produces end-to-end task packets with contracts, dependencies, risks, and proof.
- Do not pre-write production code in a plan. Include exact code only for a small interface, migration shape, or probe that removes real ambiguity.
- Do not split work into 2–5 minute micro-steps. A task should carry a coherent behavior and its own meaningful proof.
- Stop planning once the first build step and first proof path are obvious.
- `Scope delta checked: no material change.` may stay inside the canonical plan. Surface only material scope deltas.

Implementation Memory is deprecated as an active planning artifact. Existing CLI flags remain compatibility inputs only; new work supplies the accepted spec and canonical plan directly.

## Adapted Engineering Techniques

Gauntlet selectively incorporates these Superpowers techniques; see the attribution map for exact upstream sources and reviewed hashes:

- Compare 2–3 approaches only when ambiguity could materially change the design; otherwise choose a safe default and mark it.
- For behavior changes, use RED-GREEN-REFACTOR when a practical test harness exists: observe a relevant failure, implement the smallest source fix, then refactor while green.
- Diagnose before fixing: reproduce, trace to the earliest divergence, state a falsifiable hypothesis, and run the smallest discriminating check.
- Isolate p0–p2, broad, dirty-worktree, or write-heavy delegated work with a branch/worktree.
- Evidence precedes completion claims.
- Review feedback is evidence to verify, not an instruction to apply blindly.
- Finish through the repository’s git discipline: coherent commits, PR proof, merge decision, and cleanup.

## Implementation And Git

- Use a branch for persisted changes. Use a separate worktree when the workspace is dirty, work is p0–p2, the change is broad, or write-heavy lanes need isolation.
- Preserve unrelated dirty work. Never overwrite, discard, archive over, or include it without clear authority.
- Read before editing, match repo patterns, keep interfaces narrow, and avoid unrelated cleanup.
- Add or update tests when behavior changes. If RED-GREEN is impractical, record why and run the closest credible regression proof.
- Use PRs as decision/proof bundles. Prefer merge commits unless the user or repository explicitly chooses another policy.
- The main task owns the final branch, PR, user decisions, integration, and merge choice.

See `$AGENT_HOME/gauntlet/docs/github-discipline.md` for detailed git/archive behavior.

## Delegation

Parallelism must beat its context cost.

Name the expected speedup or independent proof value before adding lanes.

- Delegate only independent files, state, contracts, or evidence lanes with separate proof paths.
- Do not use subagents when each one would need the same large spec, trace, screenshot set, or design rationale.
- The main task owns synthesis and consequential spot-checks. Do not redo a child's full assignment.
- For ongoing agents, prefer state-change waits of 30-60 seconds over repeated short polling; do not repeatedly call list/wait when no decision changes.
- Read-only review/exploration lanes do not need worktrees by default. Write-heavy lanes do.
- Child agents return `Needs decision` to the main task instead of asking the user.

When two or more parallel lanes are earned, `.gauntlet/subagent-plan.json` is the canonical lane contract. Validate it with:

```sh
$AGENT_HOME/gauntlet/scripts/check-subagent-plan.py "$PROJECT_ROOT" .gauntlet/subagent-plan.json --run-id "$RUN_ID"
```

Do not maintain a second handwritten Markdown packet. Generate a child prompt from the canonical lane entry. The manifest owns lane id/status, objective, skill, source, scope, file/state ownership, typed `dependsOn` lane ids, consumes/produces, constraints, proof, return contract, and ask-user policy.

If the validator ran, report `.gauntlet/subagent-plan-summary.json` counts at closeout. Validate again only when material scope changes reshape lanes.

## Triggered Gates

Use the installed reference as source of truth; do not assume target repositories contain Gauntlet docs.

- Skill Quality Bar: meaningful workflow/skill changes. Baseline is behavior delta, trigger clarity, completion, output, positive steering, no-op pruning, progressive disclosure, and cheap mechanics. Deep escalation only for high-impact changes and only with trigger, cap, artifact, and exit condition. See `$AGENT_HOME/gauntlet/docs/skill-quality-bar.md`.
- Production Quality Bar: near-launch, private beta, production-bound, deploy-sensitive, or explicitly hardened/audited work. Skip ordinary Patch, prototypes, docs, narrow UI polish, and test/build-tool changes. See `$AGENT_HOME/gauntlet/docs/production-quality-bar.md`.
- Frontend Quality Gate: substantial frontend Feature/Release work. Use project tools first, then black-box and experience review. See `$AGENT_HOME/gauntlet/docs/ui-constitution.md` and `design-lint-candidates.md`.
- TS Durability: only when `scripts/classify-ts-durability.sh` records `durabilityRequired: true` or the user explicitly requests it.
- Architecture Hygiene: Feature/Release or broad current-change code. Check introduced dead code, unreachable branches, stale shims, duplicate logic, mismatched tests/docs, and scope creep.
- Run Log: Feature/Release or decision-heavy Deep work with material assumptions, tradeoffs, failed/skipped proof, `Cannot verify`, or follow-ups. Routine passes stay in the final chat.
- Coverage Gaps: add `GAP-###` only when reusable Gauntlet-general guidance is missing; human approval decides promotion. When guidance resolves a pending gap, remove it from `docs/coverage-gaps.md`; the run log and git history remain the archive.
- Guarded Release panel: use only for concrete Release-class harm; preserve a launch cut line and decision delta, and collapse it when it adds no unique value.
- Promotion: integrate compact promotion decisions into the current report by default. Create a standalone Promotion Brief only when explicitly requested or when a durable cross-run promotion artifact is the task.
- System explanation visuals: for Feature/Release system changes, add a Mermaid diagram when structure materially improves understanding. Use an explanatory illustration only when it adds a distinct review aid; credit its source directly.

Occasional checks remain trigger-based: Skill eval full suite for releases/eval infrastructure; Global install verification after installer/global workflow changes; full accessibility/responsive/visual sweeps for substantial UI or repeated findings.

## Role Skills

Use the smallest relevant Gauntlet skill set:

- `intake`: bound non-trivial work.
- `product-architect`: settle user workflow, first value, IA, trust, and acceptance.
- `planner`: create the canonical implementation plan.
- `debugger`: reproduce, isolate, and prove root cause before a bug fix.
- `implementer`: make the scoped change with evidence.
- `issue-triager`: route findings into ready/deferred/rejected work.
- `black-box-tester`, `experience-reviewer`, `adversarial-reviewer`, `deep-code-reviewer`: apply their specific evidence lens.
- `run-log-builder`: capture exceptions and durable decisions.
- `promotion-scanner`: evaluate repeated loops only when promotion is actually in scope.

Read a selected skill completely before acting. Do not load unrelated skill references.

## Stop Conditions

Stop and ask when:

- A decision materially changes product behavior or acceptance.
- Data loss, migration, billing, security, privacy, or destructive risk is ambiguous.
- Requested behavior conflicts with architecture or policy.
- Likely cost exceeds the accepted appetite.
- Credentials, permissions, or external state are required and unavailable.

## Completion

A coding task is complete only when:

- Acceptance criteria are met.
- Relevant proof ran, or limitations and `Cannot verify` are explicit.
- No blocking review/test/triage findings remain.
- Required run logs and coverage-gap changes are complete.
- Feature/Release architecture hygiene is complete, not applicable with reason, or triaged.
- The final response names changed files, proof completed, and unresolved risk.

Do not mark complete because code exists, a plan was written, or a budget is low. Evidence before claims.

When archiving, use `$AGENT_HOME/gauntlet/scripts/gauntlet.py archive plan|execute`; pass closeout content so the Archive Summary remains visible, and execute returned app actions in order. Do not broaden archive authority into merge authority without the user’s accepted merge request or explicit `--merge`.
