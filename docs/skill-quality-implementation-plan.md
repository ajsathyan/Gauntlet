# Skill Quality, Harness, And Analytics Implementation Plan

> **For agentic workers:** Use this as the index plan for the approved Gauntlet skill-quality, harness, and local analytics direction. Analytics capture, bounded attempt memory, useful closeout facts, and release-candidate summaries are planned work; do not auto-commit, auto-push, auto-generate changelogs, or auto-archive threads as part of Gauntlet closeout.

**Goal:** Make Gauntlet's future skill, harness, and analytics changes practical, explainable, checkable, lean, and private by default.

**Architecture:** Add one Gauntlet-owned skill-quality reference, wire it into the global workflow only for meaningful skill/workflow edits, and add local-only analytics as append-only events under `.gauntlet/analytics/`. Use Matt Pocock's `writing-great-skills` as attributed source material, not as hidden copied policy.

**Tech Stack:** Markdown workflow docs, existing Gauntlet skills, existing verifier scripts, Git-native stats, optional `scc`/`cloc` adapters.

## Global Constraints

- Keep always-loaded instructions short; put heavier quality checks in `docs/skill-quality-bar.md`.
- Keep local analytics private by default. Store events under `.gauntlet/analytics/`, which is covered by the existing `/.gauntlet/` ignore rule.
- Collect computable facts automatically; require explicit annotations for subjective value judgments.
- Do not store source code, raw diffs, raw prompts, stack traces, customer data, issue bodies, PR bodies, or project names by default.
- Use Git-native metrics first. Treat `scc` and `cloc` as optional adapters that can emit `Cannot verify` when unavailable.
- Do not run the escalation bar for ordinary Patch work.
- Use user-friendly closeout language: once the plan is approved, Gauntlet can implement the accepted work end-to-end and acknowledge meaningful step changes as it goes.
- At closeout, print only useful facts by default: files changed, proof/tests completed, and unresolved risks. Commits, changelogs, pushes, merges, release publication, and archiving remain explicit user-requested actions outside the default Gauntlet closeout path.
- Preserve unrelated dirty worktree changes.

---

## Task 1: Add The Skill Quality Reference

**Files:**
- Create: `docs/skill-quality-bar.md`
- Modify: `docs/coverage-gaps.md`
- Modify: `docs/gauntlet-runs/2026-07-08-skill-writing-harness-lessons.md`

**Interfaces:**
- Consumes: GAP-008 and the ARC/RGB/Matt skill-writing research from the run log.
- Produces: the reference used by AGENTS, README, and future skill edits.

- [x] Create `docs/skill-quality-bar.md` with two sections: `Baseline Bar` for cheap always-relevant checks and `Escalation Bar` for high-impact work.
- [x] Include practical explanations for each baseline check: behavior delta, trigger clarity, completion criterion, output contract, positive steering, no-op pruning, progressive disclosure, practical explanation, and cheap harness mechanics.
- [x] Include escalation checks for two-attempt Deep planning, forward-test scenarios, adversarial skill review, impact proof review, and parallel reviewer lanes.
- [x] Add attempt-memory guidance as bounded scratchpad behavior, not permanent memory.
- [x] Add attribution guidance for Matt Pocock's `writing-great-skills` and the checked upstream tag/commit/license.
- [x] Remove GAP-008 from `docs/coverage-gaps.md` once the reference exists, is wired into the workflow, and is covered by proof.
- [x] Update the run log with the decision to create the reference and defer analytics/libraries.

**Proof:**
- `rg -n "Skill Quality Bar|Baseline Bar|Escalation Bar|writing-great-skills|bounded attempt memory|Deferred" docs/skill-quality-bar.md docs/coverage-gaps.md docs/gauntlet-runs/2026-07-08-skill-writing-harness-lessons.md`

## Task 2: Wire The Reference Into Gauntlet Without Making It Always Heavy

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `scripts/check-gauntlet-workflow.py`

**Interfaces:**
- Consumes: `docs/skill-quality-bar.md`.
- Produces: a discoverable but trigger-bounded workflow hook.

- [x] Add a `Skill Quality Bar` section to `AGENTS.md`.
- [x] Trigger it for new or meaningfully changed Gauntlet skills, role skills, workflow guidance, eval guidance, or repeated skill-quality failures.
- [x] Skip it for ordinary Patch work, copy edits, local-only docs, and narrow accepted tweaks.
- [x] Tell agents to use the baseline bar by default and the escalation bar only when the trigger earns token cost.
- [x] Update `README.md` with a short capability row and a compact section linking to the reference.
- [x] Extend `scripts/check-gauntlet-workflow.py` with marker checks so future edits do not silently drop the reference.

**Proof:**
- `python3 scripts/check-gauntlet-workflow.py`

## Task 3: Prepare The End-To-End Automation Plan

**Files:**
- Modify: `docs/skill-quality-implementation-plan.md`

**Interfaces:**
- Consumes: the user's preference that implementation should feel end-to-end after plan approval.
- Produces: bounded future work that can be accepted and executed later.

- [x] Record the user-facing rule: after plan approval, Gauntlet should implement the accepted work end-to-end and acknowledge meaningful step changes as it goes.
- [x] List future implementation hooks without building them yet: plan queue, invalidation triggers, local closeout facts, and explicit PR/changelog/GitHub helpers only when accepted by the user.
- [x] Keep archive automation separate from closeout facts so the user can keep working in the thread.

**Proof:**
- `rg -n "end-to-end|plan queue|invalidation|closeout facts|do not auto-commit|do not auto-archive" docs/skill-quality-implementation-plan.md`

## Task 4: Add Local Analytics Event Capture

**Files:**
- Modify: `scripts/gauntlet.py`
- Modify: `AGENTS.md`
- Modify: `docs/workflow-speedups.md`
- Test: `scripts/check-gauntlet-workflow.py`

**Interfaces:**
- Consumes: mode/depth/proof routing, run logs, proof commands, Git state, PR/changelog helpers, and future attempt memory.
- Produces: `.gauntlet/analytics/events.ndjson`, `.gauntlet/analytics/derived-summary.json`, and release-candidate summaries.

- [x] Add `gauntlet.py analytics emit` for append-only local events with `schema_version`, `event_id`, `run_id`, `event_type`, `created_at`, local salted project/repo/branch hashes, `agent`, `gauntlet_version`, and `payload`.
- [x] Add `gauntlet.py analytics summarize` to compute local summaries without exporting private event data.
- [x] Store analytics under `.gauntlet/analytics/`; verify the existing `/.gauntlet/` ignore rule covers it.
- [x] Add event types for `run_started`, `mode_selected`, `plan_created`, `plan_revised`, `implementation_started`, `proof_started`, `proof_completed`, `role_review_completed`, `human_review_requested`, `human_review_completed`, `plan_invalidated`, `attempt_memory_read`, `attempt_memory_written`, `commit_created`, `changelog_updated`, `pr_opened`, `closeout_completed`, and `run_completed`.
- [x] Hash or redact command strings, repo names, branch names, and file names by default; keep human-readable labels only for safe coarse commands such as `npm test`, `pytest`, `typecheck`, or `lint`.
- [x] Add an `annotation_added` event for judgments such as autonomous eligibility, mode fit, proof-scope fit, whether Gauntlet saved time, or whether attempt memory prevented rework.

**Proof:**
- `python3 scripts/check-gauntlet-workflow.py`
- `python3 scripts/gauntlet.py analytics emit --dry-run ...`
- `python3 scripts/gauntlet.py analytics summarize --path .gauntlet/analytics/events.ndjson --json`

## Task 5: Capture Planning, Human Review, And Autonomous Timing

**Files:**
- Modify: `scripts/gauntlet.py`
- Modify: `AGENTS.md`
- Test: `scripts/check-gauntlet-workflow.py`

**Interfaces:**
- Consumes: local analytics event log.
- Produces: timing metrics that distinguish active work from calendar delay.

- [x] Track `calendar_planning_span`: first user request or run start to implementation start.
- [x] Track `active_agent_planning_time`: summed agent planning work intervals before implementation.
- [x] Track `human_review_latency`: time between `human_review_requested` and `human_review_completed`.
- [x] Treat long user gaps as async review latency, not active planning effort.
- [x] Add configurable stale/wait buckets so a 48-hour user delay does not become 48 hours of planning time.
- [x] Track autonomous eligibility at implementation start with an explicit annotation, not from chat title.
- [x] Track autonomous completion separately from autonomous eligibility.

**Proof:**
- Fixtures in `scripts/check-gauntlet-workflow.py` showing a multi-day calendar span with small active planning time and separate human review latency.

## Task 6: Add Bounded Attempt Memory

**Files:**
- Modify: `scripts/gauntlet.py`
- Modify: `AGENTS.md`
- Modify: `docs/skill-quality-bar.md`
- Test: `scripts/check-gauntlet-workflow.py`

**Interfaces:**
- Consumes: failed attempts, rejected alternatives, plan invalidations, proof failures, and useful observations.
- Produces: `.gauntlet/attempt-memory.jsonl` or equivalent local scratchpad plus promoted run-log/follow-up entries when needed.

- [x] Store compact fingerprints of failed attempts, repeated errors, rejected alternatives, and useful observations.
- [x] Bound active memory by count and age; summarize repeated entries instead of growing indefinitely.
- [x] Expire scratchpad memory at run closeout when `analytics closeout --expire-attempt-memory` is used, unless the lesson becomes a run-log decision, follow-up, coverage gap, or accepted doc change.
- [x] Emit analytics events for reads/writes and repeat-failure detection.
- [x] Do not store raw source, raw diffs, secrets, prompts, stack traces, or customer data.

**Proof:**
- Fixture showing repeated failed proof gets one summarized memory entry and a bounded event count.

## Task 7: Add Local Closeout Facts Without Commit, Changelog, Or Archive Automation

**Files:**
- Modify: `scripts/gauntlet.py`
- Modify: `AGENTS.md`
- Modify: `docs/workflow-speedups.md`
- Test: `scripts/check-gauntlet-workflow.py`

**Interfaces:**
- Consumes: local analytics events, Git status, changed-file summary, proof summary, and unresolved risk notes.
- Produces: local analytics closeout events and final-response facts.

- [x] Add a closeout helper that prints a compact local summary of files changed, proof/tests completed, and unresolved risks.
- [x] Emit a `closeout_completed` analytics event with the same bounded facts.
- [x] Do not create commits, generate changelogs, push, merge, publish release notes, or auto-archive the thread from this helper.
- [x] Keep any future commit/changelog/push/archive helpers separate and explicit, so users can continue work in the same thread.

**Proof:**
- Fixture showing closeout facts are printed and recorded while commit/changelog/push/archive action lists remain empty.

## Task 8: Add Release-Candidate Impact Summaries

**Files:**
- Modify: `scripts/gauntlet.py`
- Modify: `docs/workflow-speedups.md`
- Test: `scripts/check-gauntlet-workflow.py`

**Interfaces:**
- Consumes: local analytics summaries, Git tags/branches, optional GitHub PR/release metadata.
- Produces: private release-candidate summary and optional public release evidence note.

- [x] Add a summary command that compares a baseline version/tag/window to a release-candidate version/tag/window.
- [x] If baseline or candidate is missing, return a review result asking for both labels instead of guessing.
- [x] Segment by mode, depth, proof scope, and task type before aggregating.
- [x] Report counts before percentages for small samples.
- [x] Use confidence labels: `anecdotal`, `directional`, `strong signal`, or `no claim`.
- [x] Include regressions and noisy metrics, not only wins.
- [x] Keep local/private analytics out of GitHub by default; publish only human-approved aggregate evidence notes.

**Proof:**
- Fixture comparing two tiny cohorts and producing a low-sample disclaimer.

## Accepted Metrics

- Verified completion rate.
- Autonomous eligible and autonomous completed runs.
- Time to mode selection, first plan, first code change, implementation start, proof pass, explicit commit/PR actions when they happen, and closeout.
- Calendar planning span, active agent planning time, and human review latency.
- Proof pass/fail/skip and `Cannot verify` rates.
- Plan revision and invalidation counts with reason distribution.
- Review findings by severity and closure state.
- Scope discipline: files changed, unrelated changes, and risk-surface escalation.
- Resume quality: landing pad/checkpoint presence, time to first useful action after resume, rediscovery count when available.
- Bounded attempt memory reads/writes and repeat-failure fingerprints.
- Commit, changelog, PR, and run-log closeout completion when those explicit helpers are run.
- Closeout fact completion.
- Git diff stats via `git diff --numstat`.
- Optional code size/complexity via `scc` or `cloc`.

## Out Of Scope Until Later

- Public analytics upload or hosted telemetry.
- Auto-archive as part of closeout.
- Auto-commit, auto-push, auto-merge, or auto-changelog generation as part of default Gauntlet closeout.
- Claims that Gauntlet caused impact without comparable cohorts or human annotation.
- Raw source, prompt, diff, issue, PR-body, stack-trace, or customer-data collection.
- Private/public repo split for release candidates; default to same repo branches/tags plus local private analytics.
