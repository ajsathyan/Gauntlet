# Gauntlet

Gauntlet helps people and agents build in the same structured loop: spec, build, prove, review, and hand off.

It is a single-player and multiplayer product-development harness for Codex. Solo builders can get team-like structure around agent work. Teams can review the same change through PM, design, and engineering lenses without losing the reasoning behind it.

## Why This Exists

Coding agents can now work for longer stretches, but longer autonomy creates two problems:

1. They need better upfront structure so they do not stall or wander.
2. Humans need a clear record of what the agent decided, changed, verified, and left uncertain.

Gauntlet solves those problems with adaptive modes:

```text
Patch   -> small, focused, low-risk changes
Slice   -> coherent user-facing product slices
Release -> production-bound, deeply verified changes
```

Small tasks stay small. User-facing workflows get product architecture. Risky production work gets deeper proof and review.

## Primary Goal

Gauntlet is designed to let agents keep moving without becoming opaque.

The workflow is based on three principles:

1. Agents do better work from self-contained specs with clear boundaries, acceptance criteria, and proof requirements.
2. Humans can delegate more safely when assumptions, deviations, tradeoffs, open questions, and verification evidence are captured during implementation.
3. People should review one current version of the change through the role lens that fits their job.

## Who It Helps

### Engineers

Gauntlet helps engineers turn broad requests into scoped, verifiable implementation work. It adds review loops for risky changes, requires proof instead of vague completion summaries, and produces developer review briefs that prioritize the risky parts of the diff.

### PMs

Gauntlet helps PMs make product intent executable. It makes scope, non-goals, acceptance criteria, assumptions, behavior changes, launch risks, and open questions explicit before implementation starts and after the current slice is built.

### Designers

Gauntlet helps designers preserve UX intent through clearer flows, affected interfaces, state inventories, accessibility checks, visual proof, and visible deviations from the original spec.

## Modes

### Patch

Patch is for small, clear, low-risk changes.

Use it for copy fixes, localized UI polish, simple config updates, and narrow bug fixes with obvious verification. Patch avoids full-process overhead.

### Slice

Slice is for coherent user-facing product work.

Use it for onboarding, activation, retention, growth, high-fidelity product experiences, information architecture, new workflows, and design-heavy features. A Slice should look like the real product, not a prototype explanation. Product UI should not contain agent notes or meta commentary.

Slice adds a `product-architect` before implementation and an `experience-reviewer` after implementation.

### Release

Release is for production-bound or risky work.

Use it for auth, billing, migrations, data integrity, privacy, uploads, concurrency, public APIs, large refactors, weak-test areas, and deploy-sensitive changes. Release runs the full loop and creates a developer review brief.

## What Gauntlet Adds

Gauntlet installs a small global `AGENTS.md` router plus Codex skills:

- `intake`: turns rough intent into an implementation-ready spec.
- `product-architect`: turns user-facing intent into a coherent product slice.
- `planner`: breaks accepted specs into ordered slices.
- `issue-triager`: turns work and findings into ready tasks.
- `implementer`: executes scoped code changes.
- `adversarial-reviewer`: hunts edge cases, trust-boundary issues, and regressions.
- `black-box-tester`: validates user-visible behavior.
- `experience-reviewer`: reviews product slices for workflow, IA, states, trust, accessibility, activation, retention, and growth.
- `deep-code-reviewer`: reviews correctness, maintainability, tests, and regression risk.
- `review-brief-builder`: creates PM, design, and developer review surfaces.

For non-trivial work, Gauntlet also maintains `implementation-notes.html` so agent decisions stay inspectable:

- Design decisions
- Intentional deviations
- Tradeoffs
- Open questions
- Proof of completion
- Quantitative impact, displayed with Tufte-style minimal visualization when useful

For Tier 2/3 work, the agent should create the notes file, start a local notes server, give you the URL before implementation continues, and keep updating the page as work progresses. The template auto-refreshes in the browser so you can watch the decision log live.

For Slice and Release work, Gauntlet can also create `review-brief.html`. That brief is the canonical human review surface: what changed, what needs review, why it matters, what proof exists, and what is still uncertain.

## Task Tiers And Modes

- Tier 0 trivial: edit, verify, summarize.
- Tier 1 small: Patch.
- Tier 2 medium: Slice or focused Release depending on risk.
- Tier 3 large or risky: Release with role subagents.

The rule is simple:

```text
Choose the lightest mode that can responsibly produce and prove the requested change.
```

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

## Inspiration

Gauntlet was inspired by two agent-workflow patterns:

- Simon Last on running coding agents as a higher-throughput software factory: https://x.com/simonlast/status/2057978156183957995
- trq212 on implementation notes for making autonomous agent decisions reviewable: https://x.com/trq212/status/2056415973125796184

The synthesis:

```text
Workflow without notes is fast but opaque.
Notes without workflow are transparent but not rigorous.
Gauntlet combines both: agents keep moving, while their assumptions, deviations, proof, and risks remain inspectable.
```
