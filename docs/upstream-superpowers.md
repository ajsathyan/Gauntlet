# Superpowers Technique Attribution And Update Guide

Gauntlet is the runtime workflow. It adapts a small set of engineering techniques from **Superpowers**, created by **Jesse Vincent** and published at [obra/superpowers](https://github.com/obra/superpowers) under the **MIT License**.

Reviewed source:

- Codex curated plugin version: `5.1.3`
- Local packaged snapshot: `2f1a8948`
- Review date: `2026-07-10`
- Upstream commit: not exposed by the packaged snapshot; version and per-file SHA-256 hashes are recorded instead

Gauntlet contains adapted concepts, not vendored text. The Superpowers plugin and its workflow skills are not required at runtime.

## What Gauntlet Keeps

| Superpowers source | Adapted Gauntlet behavior | Destination |
| --- | --- | --- |
| `brainstorming` | Gate non-trivial implementation on explicit material alternatives, assumptions, edge cases, and one accepted durable design; Normal Requests bypass | `design`, `product-architect` |
| `systematic-debugging` | Reproduce, trace to earliest divergence, test a falsifiable hypothesis | `debugger` |
| `test-driven-development` | Practical RED-GREEN-REFACTOR for behavior changes | `implementer` |
| `verification-before-completion` | Evidence before completion claims | `implementer`, global completion rule |
| `receiving-code-review` | Verify feedback against spec/code/tests before applying | `implementer` |
| `requesting-code-review` | Three independent pre-build lenses plus purpose-specific exact-revision review | `adversarial-reviewer`, `verify`, specialist reviewers |
| `using-git-worktrees` | Isolate broad, risky, dirty, or delegated writes | global workflow, `github-discipline.md` |
| `dispatching-parallel-agents` | Parallelize only independent domains whose speedup beats context cost | global delegation and `planner` |
| `writing-plans`, `executing-plans` | Internal ephemeral Build planning, bounded workstream assignments, and meaningful checkpoints | `build`, `planner`, `implementer` |
| `finishing-a-development-branch` | Separate exact-revision Verify from authorized Git and external effects | `verify`, `ship`, `github-discipline.md` |
| `writing-skills` | Trigger clarity, output contracts, positive steering, and forward tests | `skill-quality-bar.md` |

Gauntlet applies explicit brainstorming and one permanent accepted design to non-trivial implementation while allowing Normal Requests to remain direct. It intentionally rejects a universal gate for trivial work, 2–5 minute implementation steps, prewritten production code, fresh-subagent-per-task execution, mandatory two-stage review for every task, and the `using-superpowers` meta-gate.

## Reviewing A Superpowers Update

After updating the upstream plugin or checking out a newer source tree:

```sh
scripts/check-superpowers-sync.py \
  --source /path/to/superpowers \
  --manifest docs/upstream-superpowers.json
```

The checker reports which reviewed source skills changed and which Gauntlet destinations require review. A changed hash is not an instruction to copy upstream text. Review the semantic delta, update the narrow Gauntlet behavior and tests if it still fits, then record the new version/hash in the manifest.

Run the workflow checks and targeted skill evals after every accepted update.

## Runtime Retirement

The one-time retirement helper is dry-run by default and only touches the allowlisted Superpowers skill names recorded in the manifest:

```sh
scripts/retire-superpowers.py \
  --active-skills "$HOME/.codex/skills" \
  --config "$HOME/.codex/config.toml" \
  --archive "$HOME/.codex/retired-skills/superpowers-5.1.3" \
  --apply
```

It moves active skill directories to a reversible archive and disables `superpowers@openai-curated`. It does not delete plugin caches or touch unrelated skills.
