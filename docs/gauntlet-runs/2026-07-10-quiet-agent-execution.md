# Quiet Agent Execution

Date: 2026-07-10  
Plan: `docs/gauntlet-plans/2026-07-10-quiet-agent-execution.md`

## Material decisions

- Archive merge authority is unchanged. AJS explicitly rejected making archive merging opt-in.
- The installed global file is now a compact router; repository `AGENTS.md` is contributor guidance rather than a duplicate installed payload.
- `.gauntlet/subagent-plan.json` is the only delegated-lane contract. Markdown packet references are rejected, and rendered prompts are ephemeral views.
- Routine child narration is suppressed. Safe, materially different recovery remains silent; integration receives only a compact machine receipt.
- Typed dependency/readiness, review state, WIP capacity, and a full runtime controller remain deferred.
- Phrase fixtures are scorer smoke only. Observable deterministic traces score outcomes, actions, authority, proof, routing, output budget, and recorded cost/latency; subjective criteria remain `Cannot verify`.

## Exceptions and review findings

- `main` advanced during implementation with the contextual merge and remote-cleanup work. The final branch merged that history, preserved its authority semantics, and reran the complete proof suite.
- Adversarial review found that an installed copy of `install.sh` could copy/delete its own payload, an `AGENTS.md` symlink would be replaced, and existing permissions could be reset. Self-reinstall detection, symlink-target writes, permission preservation, and regression tests were added.
- Adversarial review found that unknown manifest fields could pass validation but disappear from the rendered prompt, and write ownership could escape the project. Schema fields are now strict and write paths must remain project-relative.
- Router review found that single write-heavy child lanes and the newer contextual merge authority were missing after compaction. Both contracts were restored in the portable router.
- The generated test-plan helper could not infer focused commands for this Python/shell workflow. The repository's explicit full workflow suite and targeted skill/orchestration commands were used instead.

## Proof and limits

- Full workflow regression suite passed, including archive/merge non-regression and temporary Codex/Claude installs.
- Temporary-home install proof covers clean, legacy, managed, malformed/nested, repeated, linked-file permission, and installed self-reinstall cases. No real global agent home was changed.
- The router is 9,436 bytes, below the 32 KiB default, and installed commands render absolute Gauntlet paths rather than downstream-relative lookalikes.
- Current-run manifest validation: 4 checks accepted, 0 rejected, 0 warnings; all three implementation lanes completed.
- Targeted planner/implementer skill coverage and scorer smoke passed. Outcome canaries reject missing proof, authority violations, verbose output, and phrase-echo/wrong-action traces; subjective judgment returns `cannot_verify`.
- `Cannot verify`: representative live-model behavior, calibrated subjective-judge quality, behavior after a real global install, and hosted PR checks before the PR exists.

Architecture hygiene and final review found no remaining blocking issue. No coverage gap was added; the intentionally deferred controller work is a product decision, not missing guidance.
