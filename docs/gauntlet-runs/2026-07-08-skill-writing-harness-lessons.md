# Run Log: Skill Writing Harness Lessons

Scope: Compare ARC-style agent harness lessons with Matt Pocock's latest skill-writing guidance, sync overlapping installed Matt skills, and identify Gauntlet changes to consider next.
Proof scope: delta.

## Assumptions

- The user wants a practical explanation and candidate Gauntlet changes before broad Gauntlet workflow edits.
- Installed Matt Pocock skills in `/Users/ajsathyan/.codex/skills` are in scope for syncing when they directly overlap upstream `mattpocock/skills`.

## Decisions

- Synced only installed Matt skills that differed from upstream v1.1.0: `grilling`, `handoff`, and `writing-great-skills`.
- Left `teach` and `grill-me` unchanged because they already matched upstream.
- Treated `write-a-skill` / "skill writer" as replaced by `writing-great-skills`, based on the upstream changelog.
- Added `docs/skill-quality-bar.md` as Gauntlet's applied skill-quality reference with a cheap baseline bar and a high-impact escalation bar.
- Added `docs/skill-quality-implementation-plan.md` as the index plan for pre-analytics skill-quality and harness work.
- Wired the reference into `AGENTS.md` and `README.md` without making it a default gate for ordinary Patch work.
- Removed `GAP-008` from `docs/coverage-gaps.md` after the skill-quality reference existed, was wired into the workflow, and was covered by the workflow verifier.
- Added resolved-gap cleanup guidance so pending gaps leave the backlog once their accepted destination exists and is proved.
- Added local/private analytics helpers for append-only events, release-candidate summaries, timing metrics, closeout facts, and bounded attempt memory.
- Kept commit/changelog/push/archive behavior out of default Gauntlet closeout; those remain explicit user-requested actions.

## Exceptions

- The upstream changelog mentions both Negation and Negative Space for `writing-great-skills`, but the current v1.1.0 files contain only Negation. The analysis should cite the files as source of truth.
- No forward-test subagent was run for the synced third-party skills because they were copied exactly from upstream and the user's main ask prioritized analysis.
- Release-candidate summaries remain local/private and require explicit baseline/candidate labels before making comparisons.
- Analytics can compute local facts, but public impact claims still require enough comparable samples and human-approved aggregate evidence notes.

## Production Quality Bar

Not relevant because this was skill/workflow research and installed skill sync, not launch-bound application work.

## Resolved Coverage Gaps

- GAP-008: Skill quality bar. Resolved by `docs/skill-quality-bar.md`, workflow/README wiring, and `scripts/check-gauntlet-workflow.py` coverage; removed from `docs/coverage-gaps.md`.
