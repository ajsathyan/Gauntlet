# Meaningful Proof

Use the cheapest proof that can distinguish the intended behavior from a plausible wrong implementation. A green command is evidence only when its oracle—the rule that decides pass or fail—measures the claim being made.

## Define The Claim Before The Check

For each material behavior change, name:

- **Claim or invariant:** the behavior, state transition, or non-effect that must hold.
- **Observable oracle:** the externally inspectable result that would establish the claim.
- **Required checks:** commands, inspections, or artifacts that exercise the oracle.
- **Negative control:** a plausible wrong case that must fail, when risk or ambiguity earns it.
- **Required non-effects:** state, files, permissions, users, or systems that must remain unchanged.
- **Independent verification:** what the parent will rerun or inspect after integration.
- **Cannot verify:** material limits, their consequence, and the next check.

Use these fields proportionally. A direct, reversible outcome may need only a claim and an observation. Do not add empty proof ceremony.

## Evidence Boundaries

- Phrase presence, populated fields, schema validity, status labels, and self-reported results prove only structural coverage or scorer wiring. They do not prove behavior.
- A child receipt is an evidence pointer. It does not become proof until the parent resolves the referenced command or artifact and checks that it supports the claim.
- A passing test is meaningful only if the assertion would fail for a relevant wrong implementation. Prefer observing the regression fail for the intended reason before the fix when a credible harness exists.
- Child-written tests may preserve regressions, but the same child must not silently weaken, replace, bypass, or tailor the oracle to its implementation. Hidden or independent proof belongs to the parent unless the ticket explicitly assigns ownership.
- For consequential work, include a negative control, mutation check, black-box outcome, or independent review that is meaningfully separate from the implementation.
- Record what the evidence establishes and what it cannot establish. Do not turn limited evidence into a broader completion claim.

## Delegated Work

A **Gauntlet ticket** is an ephemeral child assignment from the canonical plan, not an issue-tracker record. It contains only the context the child needs. Depending on risk, it may include the proof fields above plus objective, ownership, dependencies, constraints, return contract, and ask-parent policy.

Children work quietly and retry safe materially different recoveries. Implementation children return compact receipts; research and review children return the requested artifact or findings compactly. The parent owns the oracle, independently verifies evidence, integrates child commits through the frozen parent topology, and opens the complete Project PR. Review Unit PRs, when selected for a large tightly coupled run, target only the integration branch and do not satisfy full-PRD proof. Integrate and run targeted checks as results arrive so conflicts surface early; run combined proof after all required tickets reach the all-done barrier.

## Proof Layers

Keep these claims distinct:

1. **Structural coverage:** required text, fields, schemas, or files exist.
2. **Scorer smoke:** synthetic inputs show that a scorer detects its intended signals.
3. **Execution-backed outcomes:** commands, traces, artifacts, or external state establish observable behavior and non-effects.
4. **Calibrated judgment:** subjective quality is measured against human labels or remains `Cannot verify`.

Use only the layer strong enough for the claim. Never report layers 1 or 2 as agent or product behavior.
