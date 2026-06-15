# Global Agent Coding Workflow

Gauntlet chooses the lightest mode and depth that can responsibly produce and prove the requested change.

## Modes

Recommend one mode before non-trivial work. State the recommendation, why, depth, and any escalation triggers. The user can override with "use Patch", "use Deep Patch", "use Slice", or "use Release".

### Patch

Use Patch for small, clear, low-risk changes where the product behavior and proof path are obvious.

Default loop:

1. quick intake check
2. implementer
3. verify
4. self-review
5. concise summary

Examples: copy fixes, localized UI polish, simple config changes, narrow bug fixes with obvious tests.

### Deep Patch

Use Deep Patch when the code surface is small but the objective rewards deeper search or stronger proof.

Default loop:

1. intake with appetite check
2. planner or mini-plan
3. implementer
4. compare alternatives when practical
5. adversarial-reviewer or deep-code-reviewer
6. benchmark, security check, or targeted proof
7. concise summary with tradeoff and winner

Examples: performance optimization, security audit findings, reliability hardening, data-loss prevention, hot-path correctness, and high-leverage bug fixes. Deep Patch should still keep the patch narrow, but it may spend more tokens to find the best available small change rather than the first acceptable one.

### Slice

Use Slice for user-facing workflows, product concepts, high-fidelity product slices, onboarding, activation, retention, growth, information architecture, or design-heavy work.

Default loop:

1. intake
2. product-architect
3. planner
4. implementer
5. black-box-tester
6. experience-reviewer
7. review-brief-builder

Product slices must look like the real product surface. Do not put meta commentary, prototype labels, agent notes, or "no metric needed" style text inside user-facing UI. Metrics appear in the product only when they help the user understand real progress, quality, confidence, speed, completion, improvement over time, or next action.

### Release

Use Release for production-bound, broad, risky, ambiguous, security/privacy-sensitive, billing, migration, auth, data-integrity, upload, concurrency, public API, or weak-test-coverage work.

Default loop:

1. intake
2. planner
3. issue-triager
4. implementer
5. adversarial-reviewer
6. black-box-tester
7. issue-triager
8. deep-code-reviewer
9. review-brief-builder

Escalate Patch or Slice to Release when the work touches auth, permissions, billing, migrations, destructive writes, private data, uploads, concurrency, public API contracts, production deploys, large refactors, or any area where a regression could materially harm users.

## Depth

Mode describes the change shape and risk surface. Depth describes how hard Gauntlet should search before settling.

- Standard depth: use the simplest responsible path and prove it works.
- Deep depth: compare plausible approaches, measure before/after when relevant, run adversarial review, and document why the chosen approach is best within the appetite.

Choose Deep depth when the user asks for "best", "maximum", "fastest", "most secure", "audit", "harden", "optimize", "benchmark", "regression-proof", or when small code changes could have large performance, security, reliability, or data-integrity impact.

When depth is ambiguous for optimization or security work, ask whether the user wants an acceptable improvement or the best improvement worth searching for. If the cost appetite is unclear and the likely extra cost is meaningful, stop and ask.

## Task Tiers

- Tier 0 trivial: edit, verify, summarize.
- Tier 1 small: Patch.
- Tier 1 high-upside: Deep Patch.
- Tier 2 medium: Slice or focused Release depending on risk.
- Tier 3 large or risky: Release with role subagents.

## Intake Gate

Before substantial implementation, ensure the task has: goal, scope, non-goals, affected interfaces, acceptance criteria, verification/proof, constraints, and assumptions/open questions.

Ask only questions that materially affect implementation, product behavior, risk, UX, data, API behavior, verification, or scope. Otherwise make a reasonable assumption, record it, and proceed.

When mode or depth selection depends on missing information, ask the minimum useful questions. For Deep Patch, prioritize objective function, baseline, acceptable vs best target, measurement method, and cost appetite. For Slice work, prioritize who the user is, the workflow, the first-value moment, acceptance criteria, and any product constraints. For Release work, prioritize rollback, data integrity, security/privacy boundaries, and proof requirements.

Treat `/intake` or "use intake" as an explicit request to run the intake skill before planning or implementation. For follow-ups, run delta intake: identify what changed, which assumptions are invalid, which acceptance criteria are new, and what new proof is required.

## Role Skills

Use these skills on demand:

- intake: turns rough intent into an implementable spec.
- product-architect: turns user-facing intent into a coherent product slice with workflow, IA, meaningful metrics, assumptions, and PM/design acceptance criteria.
- planner: turns accepted specs into ordered implementation slices.
- issue-triager: converts plans/findings into prioritized ready tasks.
- implementer: executes scoped code changes.
- adversarial-reviewer: stress-tests assumptions, edge cases, trust boundaries, and regressions.
- black-box-tester: validates behavior externally.
- experience-reviewer: reviews user-facing slices for workflow clarity, IA, progress feedback, states, accessibility, trust, activation, retention, and growth.
- deep-code-reviewer: reviews correctness, maintainability, tests, and regression risk.
- review-brief-builder: creates human review surfaces for engineers, PMs, and designers from the spec, diff, notes, proof, and findings.
- ian-xiaohei-illustrations: creates English-only Xiaohei explanation illustrations. For Slice or Release work with system-level changes or system-level scope, create a Mermaid diagram when formal structure would help and invoke this skill when an accompanying visual explanation would help reviewers understand architecture, code paths, workflows, process boundaries, trust boundaries, or operational flow.

When spawning subagents, explicitly point each subagent at the relevant skill.

## System-Level Explanation Visuals

For Slice or Release work with system-level changes or system-level scope, create a Mermaid diagram whenever formal structure would make the system, code, workflow, or process easier to understand. Use `ian-xiaohei-illustrations` whenever an explanatory image would make the same scope easier to understand. Treat them as complementary: Mermaid carries precise structure, while Xiaohei carries intuition, risk, boundary, failure mode, or operational flow. If one is created and the other would also help, create both; omit either only when it would be redundant or impossible, and state that rationale briefly in the review brief or final summary.

For Gauntlet review briefs, save Xiaohei assets under `review-brief-assets/`, include the credit in the asset caption or adjacent proof/note text, and record why the visual helps the reviewer.

When a Xiaohei image is generated, credit the author directly under the image with this Markdown line:

```markdown
Credit: [helloianneo](https://github.com/helloianneo/ian-xiaohei-illustrations)
```

## Product Slices

For Slice mode, the product-architect owns the product workflow and defines what progress means. The experience-reviewer validates whether the implemented experience communicates that progress well.

Product-architect priorities:

- Define the user's first-value moment.
- Shape the workflow and information architecture.
- Identify onboarding, activation, retention, growth, trust, and completion moments.
- Include metrics only when they are meaningful to the user's task.
- Prefer behavior-based metrics over vanity metrics.
- Record metric rationale in notes or review briefs, not inside the product UI.
- Make the next best action obvious.

Experience-reviewer priorities:

- Check whether the slice feels like the real product, not a prototype explanation.
- Verify loading, empty, error, success, disabled, and partial-data states when relevant.
- Check whether progress, completion, and next action are clear.
- Surface PM/design questions separately from engineering defects.

## Implementation Notes

For Tier 2/3 implementation, maintain `implementation-notes.html` in the project root unless the user specifies another location.

Before implementation continues, create the notes file if missing, start a local notes server, and give the user the URL. Prefer `scripts/serve-notes.sh` from Gauntlet when available; otherwise use `python3 -m http.server` from the project root on an available localhost port. The notes page should auto-refresh so the user can watch progress live.

The orchestrator owns the notes file. Subagents report findings; the orchestrator normalizes them.

Record only meaningful entries:

- Design decisions where the spec was ambiguous
- Intentional deviations from the spec and why
- Tradeoffs and alternatives considered
- Open questions for the user
- Proof of completion
- Quantitative impact

Do not turn notes into a changelog or a diary of trivial choices. Do not include secrets or sensitive data.

When notes include quantitative impact, present it with Tufte-style minimal visualization: compact tables, sparklines, small multiples, or simple charts with direct labels, high data-ink ratio, accessible contrast, and concise annotations. Use the `tufte-data-viz` skill when available.

## Review Briefs

For Slice and Release work, create `review-brief.html` in the project root unless the user specifies another location. Prefer `templates/review-brief.html` from Gauntlet when available.

The review brief is the canonical human review surface. It should show one current version of the change, not a diary. Include role sections when relevant:

- Overview: what changed, current status, and who should review what.
- PM brief: assumptions, behavior changes, acceptance criteria, launch risk, open product questions.
- Design brief: screens, states, interaction changes, responsive behavior, accessibility, visual diffs, design-system drift.
- Developer brief: risk-ranked code areas, files to inspect, trust boundaries, tests, performance/security concerns.
- Proof: checks run, screenshots, benchmarks, logs summarized, and what was not proven.
- Decisions: meaningful decisions, deviations, and tradeoffs.
- Handoff: how to run, what remains, and links or commands.

Do not ask humans to review everything equally. Prioritize the places where human judgment is most valuable and explain why.

## Stop Conditions

Stop and ask before proceeding when:

- A decision materially changes product behavior
- Data loss, migration, billing, security, or privacy risk is ambiguous
- The requested behavior conflicts with existing architecture or policy
- The likely cost exceeds the stated appetite
- Required credentials, permissions, or external state are unavailable

## Completion Rule

A coding task is complete only when acceptance criteria are met, relevant checks ran or limitations are stated, implementation notes are updated when required, no blocking review/test/triage findings remain, and the final response includes what changed, what was verified, and remaining risks.

For Tier 2/3 work, add one short workflow lesson when useful: whether a recurring failure should update a skill, test, checklist, or this file.
