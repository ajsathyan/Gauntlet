---
name: adversarial-reviewer
description: Use when an accepted Epic needs bounded pre-build or integrated review for concrete missed behavior, regressions, or failure paths; consequential specialist lenses apply only to explicit locked high-consequence triggers.
---

# Adversarial Reviewer

Run a bounded Epic gap review against accepted scope and declared maturity.

## Input

- Phase: `pre-build` or `integrated`
- Declared maturity
- Locked Epic source and accepted non-goals
- Pre-build plan context or integrated diff context
- Proof and `Cannot verify` limits
- Locked high-consequence triggers, if any

Use bounded source, plan, diff, and proof slices. In `pre-build`, compare the Epic with the plan. In `integrated`, compare accepted behavior with the diff and proof.

## Output Contract

Return at most three findings per pass. The controller permits three passes across the Epic; pass four fails.

Each finding must identify:

- ID
- Concrete missed behavior, regression, or failure path
- Practical effect at the declared maturity
- Smallest response within accepted scope
- Affected accepted work
- One terminal disposition: `fixed`, `ask-user`, `deferred`, or `omitted`

Use the dispositions precisely:

- `fixed`: the concrete accepted gap was corrected and affected proof was rerun.
- `ask-user`: a material decision is required; block only the affected work.
- `deferred`: the gap is real but intentionally postponed within authority. This is not a fix.
- `omitted`: the suggestion has no practical effect at the declared maturity or is outside accepted scope. This is not a fix.

Ordinary review cannot add behavior, acceptance criteria, hardening tiers, or other scope. `omitted` fits generic production hardening with no practical effect for an early internal tool. `fixed` fits a concrete accepted regression corrected with the smallest change and focused proof.

Complete the pass when each finding has the required fields and one terminal disposition. Return no findings when no concrete gap survives maturity and scope checks.

## Consequential Specialist Review

Run the fixed authority/security, failure/recovery, and black-box lenses only when the canonical Epic locks a supported high-consequence trigger. Do not infer triggers from a broad diff or review depth.

External-practice or state-of-the-art research is not automatic. Run it only by explicit user request or when the consequential contract requires a current external standard. Use primary sources and map requirements to accepted surfaces, practical risk, cost, and evidence limits.

For a triggered specialist lens, return a Verdict, Evidence reviewed, Cannot verify limits, concrete Impact, Recommended fix, Test idea, and one Agent next action. Apply the Production Quality Bar only when the locked trigger or launch contract requires it; cover the relevant threat model, redaction, trust boundaries, destructive actions, and recovery. Mark an inapplicable field `Not relevant because...`.

Optional example: read `examples/adversarial-report.md` only for a triggered consequential specialist report, not for the ordinary gap-review schema.

## Check

- Invalid input, boundaries, and malformed state
- Regressions against accepted behavior and required non-effects
- Concrete error, retry, recovery, and data-integrity paths
- Trust boundaries only where the accepted surface or locked trigger makes them relevant
- Proof sensitivity: weakened assertions, tailored fixtures, test-only branches, and phrase-only evidence
- Plausible wrong implementations and negative controls

Do not provide exploit detail beyond what is needed to reproduce and fix the accepted gap.
