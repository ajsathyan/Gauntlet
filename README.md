# Gauntlet

Gauntlet helps teams get more useful work from Codex by giving coding agents clearer specs, tighter execution loops, and reviewable proof.

It is built primarily for engineers working in real codebases. PMs and designers benefit through better artifacts: scope, assumptions, deviations, open questions, proof of completion, and user-visible behavior checks.

## Why This Exists

Coding agents can now work for longer stretches, but longer autonomy creates two problems:

1. They need better upfront structure so they do not stall or wander.
2. Humans need a clear record of what the agent decided, changed, verified, and left uncertain.

Gauntlet solves those problems with a lightweight workflow:

```text
Intake -> Plan -> Triage -> Implement -> Review -> Test -> Triage -> Deep Review
```

Small tasks stay small. Larger or riskier tasks get more structure.

## Primary Goal

Gauntlet is designed to let agents keep moving without becoming opaque.

The workflow is based on two principles:

1. Agents do better work from self-contained specs with clear boundaries, acceptance criteria, and proof requirements.
2. Humans can delegate more safely when assumptions, deviations, tradeoffs, open questions, and verification evidence are captured during implementation.

## Who It Helps

### Engineers

Gauntlet helps engineers turn broad requests into scoped, verifiable implementation work. It adds review loops for risky changes and requires proof instead of vague completion summaries.

### PMs

Gauntlet helps PMs make product intent executable. It makes scope, non-goals, acceptance criteria, assumptions, and open questions explicit before implementation starts.

### Designers

Gauntlet helps designers preserve UX intent through clearer flows, affected interfaces, behavior checks, and visible deviations from the original spec.

## What Gauntlet Adds

Gauntlet installs a small global `AGENTS.md` router plus seven Codex skills:

- `intake`: turns rough intent into an implementation-ready spec.
- `planner`: breaks accepted specs into ordered slices.
- `issue-triager`: turns work and findings into ready tasks.
- `implementer`: executes scoped code changes.
- `adversarial-reviewer`: hunts edge cases, trust-boundary issues, and regressions.
- `black-box-tester`: validates user-visible behavior.
- `deep-code-reviewer`: reviews correctness, maintainability, tests, and regression risk.

For non-trivial work, Gauntlet also maintains `implementation-notes.html` so agent decisions stay inspectable:

- Design decisions
- Intentional deviations
- Tradeoffs
- Open questions
- Proof of completion
- Quantitative impact, displayed with Tufte-style minimal visualization when useful

For Tier 2/3 work, the agent should create the notes file, start a local notes server, give you the URL before implementation continues, and keep updating the page as work progresses. The template auto-refreshes in the browser so you can watch the decision log live.

## Task Tiers

- Tier 0 trivial: edit, verify, summarize.
- Tier 1 small: quick intake check, implement, verify, self-review.
- Tier 2 medium: intake, plan, implement with notes, targeted review/test.
- Tier 3 large or risky: full loop with role subagents.

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
