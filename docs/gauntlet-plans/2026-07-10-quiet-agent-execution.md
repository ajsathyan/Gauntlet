# Quiet Agent Execution Plan

Date: 2026-07-10  
Thread: `p0-auto: Quiet reliable agent execution`  
Accepted source: the completed Agent-Orchestra audit handoff and AJS's follow-up decisions in the current thread.

## Problem and target outcome

Gauntlet currently loads a large portable workflow from both global and repository `AGENTS.md`, installs Codex guidance by replacing most of the existing global file, requires a machine-readable subagent manifest plus a duplicative Markdown packet, and calls phrase-presence fixture scoring “behavioral” evaluation. Subagent work also produces more human-facing narration than AJS wants.

The target is a smaller always-loaded router, preservation-safe installation, one canonical subagent manifest, quiet autonomous execution with silent safe recovery, and outcome-oriented orchestration evaluation. Archive merging remains unchanged. Typed dependency, review-state, WIP, and full runtime-controller work are deferred.

## Appetite and change classification

- Path: Release
- Depth: Deep
- Verification scope: full for changed workflow/install/eval surfaces
- Execution mode: autonomous and quiet
- Decision gate: before merge or applying the installer to a real global agent home
- Production Quality Bar trigger: global instruction installation can overwrite durable user guidance. Cap the pass at temporary-home install preservation, idempotence, malformed-marker rejection, downstream path resolution, rollback-by-file-copy behavior, and no-mutation proof for the real global home.
- Panel Guard trigger: Release-class global-policy preservation. Use the decision table below; no role panel or subagent reviewer is needed unless implementation evidence creates a new concern.
- Hygiene trigger: broad multi-file workflow change.
- TypeScript Durability: not relevant because TypeScript is not in scope.

## Must-haves

1. Preserve every byte of unrelated global Codex guidance outside one bounded Gauntlet managed block.
2. Reject malformed or nested managed markers without changing the target file.
3. Keep repeated installs idempotent and preserve file permissions expected by current tests.
4. Split the installable global router from the repository contributor `AGENTS.md`.
5. Keep the installed router below the documented 32 KiB default and remove bare source-relative `docs/...` and `scripts/...` execution paths from downstream guidance.
6. Use one `.gauntlet/subagent-plan.json` as the lane source of truth. Remove the required Markdown packet and `taskPacketRef` contract.
7. Render a compact child prompt from a validated manifest lane and require only a compact machine receipt.
8. Keep routine autonomous work out of user-facing chat. Surface only a required decision, an unrecoverable failure, a host-required terse heartbeat, or the final outcome/proof.
9. Retry safe recovery silently while the next attempt is materially different. Stop when it would repeat the same failure fingerprint, require new authority, risk destructive external state, or exceed the accepted task appetite.
10. Rename the current phrase fixture tier to scorer smoke. Do not present it as behavioral proof.
11. Add outcome/trace evaluation that scores observable actions, artifacts, proof, authority, routing, and output budget. A phrase-echo canary that performs the wrong action must fail.
12. Preserve current archive merge behavior and regression coverage.
13. Open a pull request with coherent commits, changelog, proof, review context, and remaining deferrals.

## Non-goals and deferrals

- No opt-in archive merge change.
- No typed dependency graph, readiness engine, review state, WIP/reviewer capacity, reassignment controller, or runtime lane ledger in this cut.
- No live installation into `~/.codex`, `~/.claude`, or another real agent home.
- No paid or live model calls. This cut builds honest trace-pack evaluation and scorer proof; representative model response/trace collection is a later operational run.
- No daemon, scheduler, peer mesh, role-based model routing, or universal retry count.
- No wholesale import of the existing `codex/simplify-gauntlet-planning` branch. It is a read-only reference; only changes inside this accepted scope may be ported.
- No edits to unrelated `house-voice-plans.md` or other worktrees.

## Material assumptions and decisions

- AJS will not inspect subagent packets, reports, or progress narration. Human-readable coordination artifacts therefore have no product value by default.
- Machine-verifiable receipts remain necessary for integration and completion proof, but they should be compact and not duplicated into chat.
- The current installed `planner`/`implementer` skills and `codex/simplify-gauntlet-planning` worktree contain useful reference implementations. Typed dependency enforcement and unrelated planning changes in that branch are explicitly excluded.
- Backward compatibility should be kept only where it is cheap and does not preserve false assurance. Schema 1.1 manifests should fail with a clear migration message rather than silently accepting `taskPacketRef`.
- Any host-required progress update stays one sentence and contains only status or a blocker.
- Scope delta checked: no material change.

## Edge Cases From This Ask

### Need user decision

None before repository implementation. Applying the finished installer to a real global home or merging the PR remains a separate durable action.

### Safe defaults

- Preserve archive merging exactly as tested today.
- Preserve all unrelated global content and abort before mutation on malformed markers.
- Use temporary agent homes for installation proof.
- Do not run live model evaluation.
- Keep retries silent and bounded by materially different recovery, authority, safety, and appetite rather than a fixed count.
- Keep child returns machine-compact; do not expose them to AJS unless they contain a decision or unrecoverable blocker.
- Preserve the dirty main checkout by implementing in isolated worktrees.

## Risks, invalidation triggers, and rollback

- Router compaction can silently delete an important rule. Invalidate the design if rule mapping cannot show keep/move/delete for every current top-level section or paired discovery tests lose a critical completion/safety rule.
- Managed-block migration can duplicate legacy Gauntlet text. Invalidate if an old unmarked install cannot be distinguished safely; preserve the full old file and append a managed block instead of deleting uncertain text.
- Prompt rendering can leak secrets or over-broad context. Reuse existing secret/context/path validation before rendering.
- Outcome evaluation can become another vanity gate. Invalidate any “behavioral pass” that has no actual trace observations or can be passed by phrase echo.
- Rollback is a normal git revert for repository changes. Installer tests must prove that pre-existing target content remains recoverable because it is preserved outside the managed block; the real global home is not mutated during this run.

## Release decision table

Launch cut line: the PR may open only when temporary-home install preservation/idempotence/malformed-marker tests pass, the global router stays below 32 KiB, manifest rendering works without packet files, the phrase-echo canary fails, archive merge regressions remain green, and full workflow checks pass.

| Concern | Decision | Why Not Defer | Proof | Plan Delta |
| --- | --- | --- | --- | --- |
| Installer deletes unrelated global guidance | Ship blocker | A later install can irreversibly remove user policy before they notice. | Temporary-home byte-preservation, malformed-marker no-mutation, and repeat-install tests. | Implement the managed block before any global-router rollout. |
| Router exceeds discovery budget or resolves downstream-relative paths | Conditional blocker | Truncation or path collision can silently skip safety rules or execute the wrong helper. | Byte-size assertion plus generic downstream repo with conflicting `scripts/` and `docs/` names. | Split portable router from repo guidance and render stable installed paths. |
| Manifest and packet diverge | Conditional blocker | A validated plan can dispatch a different human-authored packet. | Schema migration tests and render-from-manifest proof. | Remove packet references; manifest becomes canonical. |
| Phrase scorer reports behavioral confidence | Conditional blocker | A green release claim can rest on echoing expected words. | Wrong-action phrase-echo canary must fail outcome scoring. | Rename scorer tier and add trace outcome evaluation. |
| Typed dependency/runtime controller | Defer | The coordination model is intentionally unsettled and this cut does not require it. | Explicit schema/plan deferral and no dependency-state release claims. | Keep current descriptive dependency field only; no DAG enforcement. |

Panel delta: managed installer preservation is the first implementation lane; typed dependency enforcement is removed from this cut; the PR cut line requires outcome evidence rather than phrase presence.

## Verification plan

- `python3 scripts/check-gauntlet-workflow.py`
- `scripts/run-skill-change-checks.sh`
- Targeted temporary-home installer tests for clean install, legacy unmarked install, managed replacement, malformed/nested markers, unrelated byte preservation, permissions, and repeated-install idempotence.
- Targeted downstream discovery/path test from a generic repo containing conflicting `scripts/gauntlet.py` and `docs/workflow-etiquette.md`.
- `scripts/check-subagent-plan.py` regression fixtures for schema migration, missing fields, overlap/secret/context rules, and `--render-lane` output without packet files.
- Outcome scorer smoke pack with valid outcome, missing proof, authority violation, verbose output, and phrase-echo wrong-action canary.
- Router byte count and rule-mapping scan.
- `scripts/diff-intel.py`, `scripts/test-plan.py`, and `scripts/review-pack.py` after integration.
- Architecture hygiene delta review, adversarial review, black-box CLI/install proof, deep code review, and exceptions-first run log.
- Changelog generation, branch push, and PR checks.

## Parallel lanes

The lanes have separate write ownership and proof paths. The main integration lane owns shared router/repository docs, centralized workflow regression tests, integration, review, changelog, and PR.

### C1 — Installer and portable router

- Task and goal: implement preservation-safe managed installation, a compact portable router source, and stable installed path rendering.
- Files to inspect: `scripts/install.sh`, `scripts/gauntlet.py`, `AGENTS.md`, `README.md`, `codex/simplify-gauntlet-planning` reference diff.
- Files to write: `scripts/install.sh`, `router/**`, narrowly scoped installer test helpers if needed.
- Files to avoid: repository `AGENTS.md`, `README.md`, `scripts/check-gauntlet-workflow.py`, manifest/eval files, existing worktrees.
- Constraints: no real global install; archive behavior unchanged; preserve unrelated content byte-for-byte; use `apply_patch` for edits.
- Consumes: this plan and current installer behavior.
- Produces: managed-block installer, compact router source, stable path rendering contract, targeted proof report.
- Proof: temporary-home install probes and router byte/path assertions.
- Cannot verify: centralized workflow integration and actual Codex discovery, owned by the main lane.
- Done when: targeted proof passes and the child returns one compact machine receipt.
- Review target: adversarial installer/global-policy review.

### C2 — Canonical manifest and quiet execution

- Task and goal: remove packet duplication, render child prompts from validated lane entries, and encode compact receipt/silent-recovery guidance without adding typed dependency control.
- Files to inspect: `scripts/check-subagent-plan.py`, `docs/subagent-plan-validator.md`, `skills/planner/SKILL.md`, `skills/implementer/SKILL.md`, current manifest fixtures, the reference worktree.
- Files to write: `scripts/check-subagent-plan.py`, `docs/subagent-plan-validator.md`, `skills/planner/SKILL.md`, `skills/implementer/SKILL.md`.
- Files to avoid: `AGENTS.md`, `README.md`, `scripts/check-gauntlet-workflow.py`, installer and eval files.
- Constraints: schema migration must reject legacy packet claims clearly; retain descriptive dependencies without typed DAG/readiness enforcement; compact machine receipt only.
- Consumes: this plan and schema 1.1 behavior.
- Produces: canonical schema, lane renderer, quiet execution/receipt contract, targeted CLI proof.
- Proof: local temporary manifest fixtures exercising validation and rendering.
- Cannot verify: centralized regression integration, owned by the main lane.
- Done when: no packet file is required, legacy schema fails clearly, and rendered output is bounded.
- Review target: deep code review of validation, escaping, and compatibility behavior.

### C3 — Outcome-oriented evals

- Task and goal: demote phrase fixtures to scorer smoke and add trace/outcome evaluation that cannot be passed by phrase echo.
- Files to inspect: `scripts/run-skill-evals.py`, `scripts/run-skill-change-checks.sh`, `evals/behavior-fixtures.json`, `evals/skill-evals.json`, `docs/gauntlet-v2-skill-audit.md`, `docs/skill-quality-bar.md`.
- Files to write: `scripts/run-skill-evals.py`, `scripts/run-skill-change-checks.sh`, `scripts/run-orchestration-evals.py`, `evals/**` files owned by this lane, `docs/gauntlet-v2-skill-audit.md`, `docs/skill-quality-bar.md`.
- Files to avoid: `AGENTS.md`, `README.md`, `scripts/check-gauntlet-workflow.py`, installer and manifest files.
- Constraints: no network/model calls; deterministic scorer smoke must not claim behavior; subjective judgment remains `Cannot verify` until calibrated.
- Consumes: this plan and current eval artifacts.
- Produces: renamed scorer-smoke path, trace schema/scorer, paired-arm support, wrong-action canary, targeted proof.
- Proof: scorer self-tests in which correct traces pass and phrase-echo/authority/verbose traces fail.
- Cannot verify: representative live model behavior and calibrated judge quality.
- Done when: outputs clearly distinguish coverage, scorer smoke, deterministic outcomes, and unverified judgment.
- Review target: adversarial eval-validity review.

## Ordered main-lane tasks

1. Commit this canonical plan and validate the current-run subagent manifest.
2. Dispatch C1–C3 from isolated worktrees after their branches are based on the plan commit.
3. Integrate child commits into the final branch; do not import unrelated changes from reference worktrees.
4. Rewrite repository `AGENTS.md` as contributor guidance; map every old top-level rule to keep, move, or delete; update `README.md` and workflow references.
5. Add centralized regression tests in `scripts/check-gauntlet-workflow.py` for all lane outputs and archive non-regression.
6. Run full verification, architecture hygiene, adversarial/black-box/deep review, and triage any findings.
7. Write the exceptions-first run log and changelog, commit coherent checkpoints, push the final branch, and open the PR.

## First ready task

Commit the canonical plan, create the schema 1.1 current-run manifest referencing this plan as its accepted packet source, and validate it before any implementation lane begins.
