# Gauntlet

A model-agnostic workflow harness for shaping, running, and reviewing coding-agent work.

Gauntlet helps engineers, PMs, and designers spend more time refining specs, scope, acceptance criteria, and review surfaces before the agent runs. Instead of treating every task as "prompt, wait, inspect, prompt again," it gives teams a shared vocabulary for deciding what kind of work is being done and how much proof it deserves.

## Build Stages

| Stage | Best for | What it optimizes |
|---|---|---|
| Patch | Small, focused changes | Speed and low overhead |
| Deep Patch | Small surface, high-upside work | Maximum reasonable performance, security, reliability, or correctness |
| Slice | High-fidelity product features and workflows | AI-native prototyping and product handoff |
| Release | Production-bound or risky changes | Deeper verification, review, and regression control |

## Why Gauntlet Exists

Coding agents make implementation cheaper, but they make specification, orchestration, and review more important.

Gauntlet is built around a simple bet:

- Better-scoped work produces better agent runs.
- Different tasks deserve different amounts of process.
- Humans need live notes and review briefs, not just a final diff.
- Engineers, PMs, and designers should be able to reason from the same build stages.

## What It Gives You

| Artifact | Purpose |
|---|---|
| Intake | Turns rough intent into scope, boundaries, acceptance criteria, and proof |
| Planner | Converts accepted specs into ordered implementation slices |
| Implementation notes | Captures decisions, deviations, tradeoffs, open questions, proof, and quantitative impact while work happens |
| Review brief | Shows what changed, what needs review, why it matters, and what remains uncertain |
| Role skills | Adds product architecture, adversarial review, black-box testing, and deep code review when useful |

## Who It Helps

### Engineers

Gauntlet helps engineers turn broad requests into scoped, verifiable implementation work. It adds review loops for risky changes, requires proof instead of vague completion summaries, and produces developer review briefs that prioritize the risky parts of the diff.

### PMs

Gauntlet helps PMs make product intent executable. It makes scope, non-goals, acceptance criteria, assumptions, behavior changes, launch risks, and open questions explicit before implementation starts and after the current slice is built.

### Designers

Gauntlet helps designers preserve UX intent through clearer flows, affected interfaces, state inventories, accessibility checks, visual proof, and visible deviations from the original spec.

## How The Stages Work

### Patch

Patch is for small, clear, low-risk changes.

Use it for copy fixes, localized UI polish, simple config updates, and narrow bug fixes with obvious verification. Patch avoids full-process overhead.

### Deep Patch

Deep Patch is for small code surfaces where the goal is worth deeper search.

Use it for performance improvements, security audits, reliability hardening, data-loss prevention, hot-path correctness, and high-leverage bugs. Deep Patch keeps the patch narrow, but asks the agent to compare plausible approaches, benchmark or test the outcome, and explain why the chosen change is best within the user's appetite.

### Slice

Slice is for high-fidelity product features and workflows.

Use it for onboarding, activation, retention, growth, information architecture, new workflows, and design-heavy features. Slice is best for AI-native prototyping and product handoff. A Slice should look like the real product, not a prototype explanation. Product UI should not contain agent notes or meta commentary.

### Release

Release is for production-bound or risky work.

Use it for auth, billing, migrations, data integrity, privacy, uploads, concurrency, public APIs, large refactors, weak-test areas, and deploy-sensitive changes. Release runs the full loop and creates a developer review brief.

## Task Tiers And Stages

- Tier 0 trivial: edit, verify, summarize.
- Tier 1 small: Patch.
- Tier 1 high-upside: Deep Patch.
- Tier 2 medium: Slice or focused Release depending on risk.
- Tier 3 large or risky: Release with role subagents.

The rule has two parts:

```text
Choose the lightest stage for the change shape.
Choose the depth that matches the value of finding the best answer.
```

Mode is about scope and risk surface. Depth is about search effort. A performance optimization can be a tiny patch and still deserve Deep Patch if "fastest reasonable result" matters more than minimizing tokens.

## What The First Evals Show

Early local evals are directional, not benchmark-grade.

In one focused performance task, the lighter Patch path used fewer tokens, but the heavier workflow found a faster optimization. That led to Deep Patch: a small-surface stage for cases where performance, security, reliability, or data integrity justify deeper search.

In one broader product-performance task, Release mode cost more than direct development, but produced stronger review artifacts and caught a real progress-state regression during adversarial review.

The current claim is not "Gauntlet always writes better code." The claim is that Gauntlet makes agent work more structured, reviewable, and measurable, with explicit tradeoffs between speed, cost, rigor, and human handoff.

## Install

From this repo:

```bash
./scripts/install.sh
```

Then restart Codex.

## Live Notes

To start live implementation notes from a project root:

```bash
path/to/Gauntlet/scripts/serve-notes.sh
```

The script creates `implementation-notes.html` if needed, serves the project on an available localhost port, and prints the notes URL.

## What Gets Installed

Gauntlet installs a small global `AGENTS.md` router plus Codex skills:

- `intake`
- `product-architect`
- `planner`
- `issue-triager`
- `implementer`
- `adversarial-reviewer`
- `black-box-tester`
- `experience-reviewer`
- `deep-code-reviewer`
- `review-brief-builder`

It also installs reusable templates for `implementation-notes.html` and `review-brief.html`.

## Inspiration

Gauntlet is partly inspired by Simon Last's framing of agent work as a higher-throughput software factory: the bottleneck moves from typing code to shaping clear specs, boundaries, and review loops so agents can keep working.

It is also inspired by trq212's implementation-notes pattern: long agent runs become easier to trust when decisions, deviations, tradeoffs, and open questions are captured while the work happens.

Gauntlet combines those ideas into a workflow harness: define the work clearly, choose the right build stage, let the agent keep moving, and give humans a review surface that explains what changed and why.

## License

MIT
