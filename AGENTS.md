# Gauntlet Contributor Guide

Gauntlet v2.0.2 is a product-thinking and proof harness for coding agents. This repository file governs work on Gauntlet itself. The portable workflow installed into agent homes lives in `router/AGENTS.md`; do not make the repository guide and global router byte-identical.

## Sources of truth

- `AGENTS.md`: repository contribution, implementation, proof, and release rules.
- `router/AGENTS.md`: compact always-loaded global router installed by `scripts/install.sh`.
- `skills/*/SKILL.md`: triggered role behavior and output contracts.
- `docs/workflow-etiquette.md`: detailed execution, delegation, continuity, and archive guidance.
- `docs/github-discipline.md`: branches, worktrees, commits, PRs, merge commits, and cleanup.
- `docs/meaningful-proof.md`: behavioral claims, observable oracles, evidence boundaries, and delegated proof.
- `docs/skill-quality-bar.md`: requirements for meaningful skill and workflow changes.
- `docs/production-quality-bar.md`: bounded launch/hardening checks when production risk triggers them.
- `docs/local-documentation.md`: default-on lazy local product-document organization, explicit project opt-out, tracked/private boundaries, and scaffolding behavior.
- `docs/prd-execution.md`: PRD terminology, Ticket Graph compilation, durable execution state, scheduling, and end-to-end implementation authority.
- `docs/custom-agent-routing.md`: deterministic Ticket classification, named Codex profile selection, bounded context, and audit requirements.
- `scripts/check-gauntlet-workflow.py`: end-to-end workflow regression suite.

Use repository-relative `docs/...` and `scripts/...` paths only for work inside this repository. Portable guidance must use the installed-path contract rendered by the installer.

## Normal requests and minimum scope

Before invoking Gauntlet's lifecycle, route bounded, low-consequence, readily reversible, directly checkable work through the Normal Request path when it uses existing inputs or only a direct lookup and does not alter durable schemas, contracts, methodology, architecture, production state, or safety boundaries. Direct presentation and formatting changes, copying existing results into an existing UI, simple lookups, and routine administration normally qualify.

Deliver the requested artifact first. Add no validation, refactoring, research, documentation, review panel, lifecycle ceremony, or methodological improvement unless the result needs it to work. A corrected assumption authorizes correcting that premise and its direct effects, not a redesign. Use a direct outcome or smoke check, keep small work in the main task, and stop when the artifact is delivered and checked. Ask before materially expanding scope. Explicit narrow user scope controls unless a real safety or authority boundary requires stopping or routing only the consequential part.

## Choose the lightest responsible path

```text
Path: Research | Patch | Feature | Release
Depth: Standard | Deep
Proof scope: smoke | delta | full | not relevant
Execution mode: review | autonomous
Decision gate: none | before unsafe side effect | before merge | before production change | custom
```

- Research: bounded investigation, comparison, audit, recommendation, or implementation discovery without requested code changes.
- Patch: small, clear, low-risk changes with an obvious proof path.
- Feature: user-facing workflow, product, IA, onboarding, activation, retention, growth, or design-heavy work.
- Release: broad, production-bound, weakly tested, destructive, security/privacy-sensitive, billing, auth, migration, concurrency, public API, or data-integrity work.
- Deep: the user asks for the best, fastest, most secure, hardened, audited, optimized, benchmarked, or regression-resistant result, or a small code delta has large consequences.

Classify internally. Surface the classification only when it changes scope, cost, authority, proof, or a decision AJS should make.

## Intake and planning

Before substantial implementation, establish one accepted source and one canonical plan with:

- goal, scope, non-goals, affected interfaces, and acceptance criteria;
- meaningful proof, constraints, assumptions, and material open questions;
- critical invariants and integration boundaries;
- ordered tasks, exact file/state ownership, and the first ready task;
- explicit deferrals and `Cannot verify` where proof is unavailable.

Use an 80/20 question rule across every Gauntlet skill. Start from existing context and make safe assumptions explicit. Ask only when the answer could materially change the result, scope, acceptance, authority, data/money/privacy/security risk, cost, or external effect. When clarification is necessary, ask at most three short questions in one message, preferably one or two, with each question focused on one decision. Do not send a generic questionnaire. Otherwise provide a provisional result.

For genuine scope additions, check the added scope and its boundary with accepted work. Update the plan and proof when the addition is material; do not emit a no-op scope phrase when it is clean.

Unless the primary worktree contains `.gauntlet/doc-org.disabled`, the global router's default local-document profile applies before creating or changing covered documents; read `doc_org.md` and `local-docs/INDEX.md` after the router materializes it. Canonical local documents stay in the primary worktree; tracked documentation stays in the repository's established documentation location.

An accepted multi-Epic PRD is the human product source. At implementation time, compile only its explicit build-ready target into a Ticket Graph; do not turn proposed, deferred, or materially unresolved work into tickets. Follow `docs/prd-execution.md` for terminology, durable artifacts, resumption, scheduling, and release authority.

## Quiet autonomous execution

- Routine execution stays in tools and machine artifacts, not user-facing narration.
- User-facing chat is reserved for a required decision, an unrecoverable failure, a host-required terse heartbeat, or a concise final outcome and proof.
- Implementation children return a compact machine receipt: `status`, `changedFiles`, evidence pointers, and `blocker`. Research and review children return the requested artifact or findings compactly. Neither form is proof by itself.
- Retry silently only when the next attempt is safe and materially different.
- Stop when recovery would repeat the same failure fingerprint, require new authority, risk destructive external state, or exceed the accepted appetite.
- Do not ask AJS to inspect tickets, reports, ledgers, traces, or progress prose.

After an Execution Run starts, its source lock, manifest, and resume artifact own execution state. Recover from those local artifacts after compaction or restart instead of reconstructing progress from chat.

## Subagents and bounded dispatch

Standing authorization: automatically use subagents when two or more useful lanes have independent file or evidence ownership, mutable state, and proof, and the speed or independent-evidence gain clearly beats the context cost. Do not wait for the user to request delegation, and do not require Release classification. Keep execution in the main task when the split would serialize on shared state, duplicate substantial context, or weaken proof.

- The main chat owns the accepted plan, user decisions, final branch, integration, PR, merge decision, and final synthesis.
- Write-heavy lanes use isolated worktrees unless a tiny disjoint patch clearly does not need one.
- A Gauntlet Ticket is a generated execution assignment within the current plan or Execution Run, not an issue-tracker record.
- The Ticket Graph uses a dynamic ready queue: prioritize critical-path and interface-first work, preserve useful agent affinity, integrate completed tickets continuously, and wait at selective Cohort Verification barriers only where tickets share an invariant or interface.
- Dispatch each child directly from one bounded ticket. Include only the material objective, ownership, dependencies, constraints, proof expectations, return contract, and ask-parent policy; proof fields are optional and proportional.
- Native Codex state and main-chat messages own live coordination.
- Codex children must be started by calling native `spawn_agent` with `agent_name` equal to the explicit `gauntlet_*` profile returned by `scripts/route-codex-agent.py` under `docs/custom-agent-routing.md`. Do not wait before spawn returns a child ID, and do not perform a rejected child Ticket in the parent. A profile mismatch is a routing failure, not permission to substitute silently.
- After a Gauntlet child reaches a terminal state, sync the privacy-bounded local audit with `scripts/subagent-audit.py`; Codex native state remains the immediate source of truth.
- Keep files, mutable state, and proof targets disjoint. Avoid splitting one tightly coupled decision tree across lanes.
- Children report `Needs decision` to the orchestrator instead of asking AJS directly.
- The main chat owns the oracle, independently reruns or resolves child evidence, integrates commits into one branch as results arrive, runs targeted integration checks, and runs combined proof after all required tickets finish. It opens one final PR.
- Materialize one bounded child context with named dependency contracts and outputs. Children do not load the whole PRD, manifest, event stream, or unrelated receipts by default.
- Keep delegation, child progress, completion, and receipts out of user-facing narration. All applicable etiquette and gates still run internally; surface only the user-facing action or material exception they require.

## Implementation

- Read before editing and match local patterns.
- Use `apply_patch` for hand-edited files; bulk mechanical formatting may use the relevant formatter.
- Preserve unrelated dirty work. Use a separate worktree for p0-p2, broad, risky, or dirty-workspace changes.
- Add or update tests when behavior changes. Use red-green-refactor when a credible harness exists.
- Keep interfaces narrow, behavior explicit, and scope bounded.
- Do not add speculative abstractions, compatibility shims without consumers, generated boilerplate, or unrelated cleanup.
- Do not make durable external changes, live installs, pushes, merges, releases, or production mutations beyond the user's accepted scope.

## Proof and review

Prove changed behavior proportionally. For Normal Requests, the direct outcome or smoke check is sufficient. Expand proof only when risk, blast radius, weak tests, or release intent earns it.

Use `docs/meaningful-proof.md` for every material behavior claim. Define the claim or invariant and observable oracle before choosing checks. When proportionate, include a plausible wrong case or negative control, required non-effects, independent parent verification, and `Cannot verify` limits. Phrase presence, populated fields, schema validity, status labels, receipts, and self-reported results are structural evidence or evidence pointers, not behavioral proof. A child may write regression tests, but must not weaken or tailor the oracle; the parent independently reviews and reruns or resolves the evidence after integration.

- Run targeted tests first, then the smallest relevant broader suite.
- Use `scripts/diff-intel.py`, `scripts/test-plan.py`, and `scripts/review-pack.py` for changed-surface and review setup.
- Run `python3 scripts/check-gauntlet-workflow.py` for broad workflow, installer, router, orchestration, or release changes.
- Run `scripts/run-skill-change-checks.sh` when skills, skill evals, or skill-quality guidance changes.
- Use temporary agent homes for install verification; do not mutate a real global home during tests.
- Preserve archive merge behavior unless AJS explicitly requests a change.

Feature, Release, Tier 2/3, or broad multi-file work requires an architecture hygiene delta pass. Check current-change dead code, unused exports/files/dependencies, stale samples/TODOs, duplicated logic, mismatched docs/tests, unnecessary abstractions, invisible scope creep, and compatibility code without a consumer.

Use the Production Quality Bar only for near-launch, private-beta, production-bound, deploy-sensitive, hardened, or audited work. State its trigger, cap, artifact, and exit condition. Do not turn speculative concerns into blockers.

## Skills and workflow guidance

Use the narrowest Gauntlet role skill that adds value:

- `intake`, `product-architect`, `maintain-prd`, `planner`, `issue-triager`, `implementer`, `implement-prd`;
- `researcher`, `debugger`;
- `adversarial-reviewer`, `black-box-tester`, `experience-reviewer`, `deep-code-reviewer`;
- `run-log-builder`, `promotion-scanner`, and `ian-xiaohei-illustrations` when their triggers apply.

Domain/tool skills may add concrete capability without imposing a second planning or execution lifecycle.

Create every Gauntlet-owned skill under this repository's `skills/` directory with the installed `skill-creator`. The Codex and Claude Code plugin manifests bundle that directory automatically; do not maintain a separate installed copy as source. Use family prefixes such as `craft-` and `eval-` only when they make a coherent capability family easier to discover.

Before finalizing a skill with `skill-creator`, ask: **Is this cache-hit friendly in every step? Are there ways to improve token efficiency? Is this being assigned to the right custom agent? How should this skill be structured to avoid response drift from its instructions?** Apply the detailed, trigger-bounded review in `docs/skill-quality-bar.md`; do not add delegation fields when the skill never delegates.

Selected techniques adapted from Jesse Vincent's Superpowers are tracked in `docs/upstream-superpowers.md`; Gauntlet owns the runtime behavior and Superpowers remains disabled as a lifecycle.

For meaningful skill, router, eval, or workflow changes, apply `docs/skill-quality-bar.md`: behavior delta, trigger clarity, completion criterion, output contract, positive steering, no-op pruning, progressive disclosure, practical explanation, cheap harness mechanics, negative cases, authority/completion checks, and baseline provenance.

Keep deterministic coverage, scorer plumbing, and behavioral outcome evidence distinct. A fixture that echoes required phrases is scorer smoke, not behavioral proof.

## Installer and router safety

- `router/AGENTS.md` must stay below Codex's documented default `project_doc_max_bytes` budget.
- The Codex installer owns only one marked Gauntlet block and preserves every byte outside it.
- Reject partial, reversed, duplicated, or nested managed markers before changing the target; an unmarked file is a valid first install.
- Repeated installs must be idempotent.
- Installed guidance must not execute downstream-relative `scripts/...` or read downstream-relative `docs/...` as Gauntlet sources.
- Test clean, legacy, managed, malformed, conflicting-downstream-path, and repeat-install cases in temporary homes.

## Git, contextual merge, and PR discipline

- Branch from `main`; use isolated worktrees when the workspace is dirty, the work is p0-p2, the change is broad, or child lanes write files.
- For a multi-Ticket run, keep `main` clean and use one parent integration branch; integrate child checkpoints there and open one final PR per run. Split independent release boundaries into separate runs.
- Commit coherent checkpoints. Preserve useful commits; do not squash or rebase unless AJS or the repository asks.
- Treat the PR as the proof and decision bundle: changed files, execution-backed checks, review context, run log, changelog, and residual risk.
- Automated merges use merge commits. Direct push to `main` is an explicit tiny-change shortcut, not the default.
- Child lanes commit to their branches and return receipts; the main chat integrates and owns the PR.

“Merge this,” “land this,” or “merge this to main” authorizes the complete safe closeout for the accepted scope: prepare the contextual handoff, update `CHANGELOG.md`, commit and push the task branch, create or update one PR, wait for required checks and blocking review state, merge, delete the remote task branch, verify the default branch, and clean local task state only when no unique work remains. Ask only for a new material decision or preservation risk.

“Implement the PRD” authorizes the accepted build-ready target through branch/worktree creation, Ticket Graph execution, incremental integration, proof, PR, merge, exact-default-branch deployment when specified, documented production changes, production verification, required rollback, durable updates, and safe cleanup. It excludes proposed, deferred, and materially unresolved work. Stop for missing authority or credentials, an unsafe or destructive effect absent from the PRD, production reality that invalidates rollout or rollback, or required production proof that cannot be obtained.

When cutting a version, move the shipped entries from `Unreleased` under a heading for that version and release date. Keep the `Unreleased` heading for future work, and never delete released changelog history.

“Push to git” means push the current branch; it does not authorize direct-pushing or merging `main`. Use `scripts/gauntlet.py merge prepare` before the handoff commit, `scripts/gauntlet.py merge plan` for read-only preflight, and `scripts/gauntlet.py merge execute` only when the user requested merge. A request to open a PR does not authorize merging it.

When AJS asks to apply Gauntlet locally, merge it through a new PR, and then archive the task, use one `scripts/gauntlet.py closeout execute` invocation with explicit `--stage` paths. The command preflights archive inputs, commits only the named scope plus `CHANGELOG.md`, merges through the existing PR gates, updates and installs the merged default branch, and returns the Codex app actions. The main task must execute those returned app actions in order because the local CLI cannot mutate Codex task state.

## Run logs and coverage gaps

For Feature, Release, or Tier 2/3 work with material decisions or exceptions, maintain the default profile's canonical run log unless the project has explicitly opted out. Opted-out projects use:

```text
docs/gauntlet-runs/YYYY-MM-DD-<slug>.md
```

Keep it exceptions-first: material assumptions, non-obvious decisions, deviations, skipped/failed/unavailable proof, `Cannot verify`, and follow-ups. Routine passing checks belong in the final summary and PR.

Add or update `docs/coverage-gaps.md` only when reusable Gauntlet guidance is genuinely missing. Remove a pending gap when the same run resolves it.

## Stop conditions

Stop and ask only when:

- a decision materially changes product behavior or acceptance criteria;
- data loss, migration, billing, security, privacy, or destructive external risk is ambiguous;
- the request conflicts with architecture, policy, or authority;
- the likely cost exceeds the accepted appetite;
- credentials, permissions, external state, or required proof are unavailable;
- safe recovery is exhausted and continuing would repeat the same failure.

## Completion

Work is complete only when acceptance criteria are met, relevant checks pass or limitations are explicit, blocking findings are resolved or rejected with evidence, required run logs/gaps are updated, architecture hygiene is complete or not applicable, and the final handoff names changed files, proof, and residual risk concisely.
