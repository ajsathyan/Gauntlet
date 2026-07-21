# Meaningful Proof

Use the cheapest proof that can distinguish the intended behavior from a plausible wrong implementation. A green command is evidence only when its oracle—the rule that decides pass or fail—measures the claim being made.

## Define the claim before the check

For each material behavior change, name proportionally:

- **Claim or invariant:** the behavior, state transition, or non-effect that must hold.
- **Observable oracle:** the externally inspectable result that establishes the claim.
- **Required checks:** commands, inspections, or artifacts that exercise the oracle.
- **Negative control:** a plausible wrong case that must fail when risk or ambiguity earns it.
- **Required non-effects:** state, files, permissions, users, or systems that must remain unchanged.
- **Independent verification:** what the parent reruns or inspects after integration.
- **Cannot verify:** material limits, their consequence, and the next check.

For non-trivial implementation, take claims directly from the user request, conversation decisions, and the accepted Design/PRD's exact `Acceptance` section. That section is the canonical Build Contract. An implementation plan, child assignment, pull-request summary, or worker-authored checklist may organize evidence but cannot narrow an accepted outcome.

## Evidence boundaries

- Phrase presence, populated fields, schema validity, statuses, and self-reports prove only structural coverage.
- A child receipt is an evidence pointer. The parent checks that the referenced command or artifact supports the accepted outcomes.
- Reuse evidence only when the commit and tree, command, toolchain, fixture or oracle, and relevant environment still match.
- A passing test is meaningful only if its assertion would fail for a relevant wrong implementation. Observe the regression fail first when a credible harness exists.
- Child-written tests may preserve regressions, but the same child must not weaken, replace, bypass, or tailor the oracle to its implementation.
- Consequential work uses a negative control, black-box outcome, mutation check, or independent review that is meaningfully separate from implementation.
- Record what evidence establishes and what it cannot establish.

Gauntlet Lite does not add a generic sensor layer around these checks. Repository tests and purpose-specific tools run directly when their claims require them.

## Delegated work

A delegated assignment is temporary implementation context, not product truth. It contains only the outcome slice, ownership, dependencies, constraints, authority, proportional proof, return contract, and ask-parent policy that the child needs.

Children work quietly and return changed artifacts, compact proof, and risk. The parent owns accepted product meaning, integrates coherent changes, resolves child evidence, and runs one fresh independent Verify pass against the exact integrated revision.

## Exact-revision verdicts

Verify reports two verdicts without collapsing them:

1. **Build Verdict:** every requested or accepted product outcome and required non-effect is established.
2. **Architecture Verdict:** the exact revision satisfies the applicable Architecture Contract.

The Build Verdict is authoritative for accepted outcomes. Architecture success cannot compensate for a Build failure or `Cannot verify`; an applicable Architecture failure still blocks landing.

## Proof layers

Keep these claims distinct:

1. **Structural coverage:** required text, fields, schemas, or files exist.
2. **Scorer smoke:** synthetic inputs show that a scorer detects intended signals.
3. **Execution-backed outcomes:** commands, traces, artifacts, or external state establish observable behavior and non-effects.
4. **Calibrated judgment:** subjective quality is measured against human labels or remains `Cannot verify`.

Never report structural coverage or scorer smoke as product behavior.
