# Run Log: Gauntlet v2.0.2 Product Thinking And Proof Scope

Scope: Publish the product-thinking, proof-scope, frontend-quality, targeted-eval, and subagent context-efficiency changes as v2.0.2.

## Assumptions

- `v2.0.2` should describe the current outcome shift, while historical v2.0.1 run-log docs remain unchanged.
- The user wants the current working tree pushed together, including the new UI constitution and run logs.

## Decisions

- Positioned Gauntlet as a product-thinking harness for AI coding agents.
- Added proof-scope routing: `smoke`, `delta`, `full`, and `not relevant`.
- Scaled down repeated work: targeted changed-skill evals, conditional second Release triage, delta product/experience review, and combined black-box/experience passes for small UI changes.
- Added a bounded UI constitution instead of a design system.
- Kept design lint candidates general and removed project-adapter-style lint ideas.
- Added coverage-gap promotion guidance so reliable failures with concrete fixes become pending backlog items, not automatic standards.
- Added subagent context-efficiency guidance so parallelism must beat repeated handoff cost.

## Outcomes

- Token efficiency: routine skill edits now run targeted evals; full suites, broad UI sweeps, global install checks, and second triage passes are trigger-based.
- Product quality: Feature work now emphasizes first-value, coherent workflow, meaningful metrics only when useful, and consistency review.
- Review quality: run logs capture decisions, exceptions, skipped proof, and new or updated gap IDs instead of routine proof dumps.
- Frontend quality: substantial UI work gets a bounded constitution covering semantics, states, accessibility basics, black-box checks, and experience review.

## Exceptions

- Coverage gaps added: none.
- Things that went wrong: not applicable.
- Cannot verify: no runtime product feature changed; proof is limited to workflow checks, targeted skill-change evals, linter checks, and installed-copy verification.

## Not Relevant Because

- Release runtime rollback proof is not relevant because this release changes workflow docs, skills, checks, and installable agent guidance rather than a deployed application.
