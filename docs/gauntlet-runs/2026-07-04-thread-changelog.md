# Workflow Etiquette Thread Change Log

Date: 2026-07-04
Purpose: compact retrieval artifact for the Gauntlet changes shipped from this thread.

## PRs

| PR | Status | Change | Read First |
| --- | --- | --- | --- |
| [#5](https://github.com/ajsathyan/Gauntlet/pull/5) | Merged | Added Workflow Etiquette guidance, priority/thread labels, review/autonomous execution mode, archive checks, and the saved workflow diagram. | `docs/workflow-etiquette.md`, `docs/gauntlet-runs/2026-07-04-workflow-etiquette-checker.md`, `scripts/check-workflow-etiquette.py`, `AGENTS.md` |
| [#6](https://github.com/ajsathyan/Gauntlet/pull/6) | Merged | Added target-aware install support for Codex and Claude Code, preserving existing Claude memory through a managed `CLAUDE.md` block. | `README.md`, `docs/gauntlet-runs/2026-07-04-claude-install-target.md`, `scripts/install.sh` |
| [#7](https://github.com/ajsathyan/Gauntlet/pull/7) | In progress | Adds the `gauntlet.py` CLI for deterministic archive planning/execution, install verification, follow-up note formatting, and saved diagram lookup. | `scripts/gauntlet.py`, `docs/gauntlet-runs/2026-07-04-archive-execution-cli.md`, `docs/workflow-etiquette.md` |

## Follow-Ups

Follow-up captured:
- Topic: GitHub discipline and strategy
- Strength: strong follow-up
- Why it matters: branch protection, PR merge strategy, dirty-worktree policy, worktree orchestration, and open-source/private posture affect how Gauntlet safely ships work.
- Context already known: branch protection blocked direct pushes and made PR checks useful; archive automation now uses merge commits for green PRs; `archive anyway` can bypass unresolved follow-ups but needs explicit confirmation before ignoring dirty, unpushed, or unmerged code.
- Suggested opener: Review Gauntlet's GitHub discipline strategy; explain branch protection, merge methods, dirty-file policy, worktree orchestration, and when Gauntlet should express product opinions.

Follow-up captured:
- Topic: House voice workflow
- Strength: strong follow-up
- Why it matters: the house voice work is a separate conceptual lane from archive/Git automation and already has local planning context.
- Context already known: `house-voice-plans.md` is intentionally untracked and should be handled in its own feature chat.
- Suggested opener: Continue the house voice workflow from `house-voice-plans.md`; suggest priority and title before implementation.

Follow-up captured:
- Topic: Remaining Gauntlet CLI speedups
- Strength: follow-up for later
- Why it matters: archive/install/follow-up/diagram helpers are a start, but more deterministic helpers may reduce chat narration and token use.
- Context already known: possible next helpers include token-shape checks, Implementation Memory linting, follow-up thread creation, Mermaid rendering, multi-repo attribution, and review-pack integration.
- Suggested opener: Review remaining Gauntlet CLI speedup candidates and recommend which ones deserve code versus guidance.
