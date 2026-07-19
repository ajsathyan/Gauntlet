---
name: verify
description: Use for independent exact-revision verification against the accepted design, Architecture Contract, and Sensor Contract with separate verdicts.
---

# Verify

Independently verify the exact integrated revision. Read the accepted design directly; never substitute a worker-authored plan, child receipt, narrowed checklist, pull-request summary, or sensor selection.

## Inputs

- Exact accepted design and its canonical Build Contract
- Exact integrated revision and tree
- Applicable Architecture Contract
- Applicable Sensor Contract and raw evidence references

If any required input is missing, stale, or does not identify the same revision, return `Cannot verify` and block completion.

## Procedure

1. Enumerate every accepted outcome and required non-effect from the design's `Acceptance` section.
2. Inspect and exercise externally observable evidence for each item. Include a plausible wrong case when it can distinguish the implemented outcome from a shallow or narrowed pass.
3. Inspect the exact revision against the Architecture Contract independently of product behavior.
4. Verify that all required configured sensors actually executed against the exact revision. Run or rerun `sensors run` when required evidence is missing, stale, failed, unavailable, or not run.
5. Return three separate verdicts:
   - **Build Verdict:** `Pass`, `Fail`, or `Cannot verify` for every accepted product outcome and required non-effect.
   - **Architecture Verdict:** `Pass`, `Fail`, `Not applicable`, or `Cannot verify`.
   - **Sensor Verdict:** `Pass`, `Fail`, `Not applicable`, or `Cannot verify`.

The Build Verdict is authoritative for the accepted outcome. Architecture or Sensor success cannot turn a Build failure into completion. A green sensor pass and narrowed worker checklist must fail when any accepted user outcome is absent. Applicable Architecture and Sensor failures still block completion, but neither substitutes for Build.

## Output

- Exact revision verified
- Build Verdict with acceptance-item evidence
- Architecture Verdict with contract evidence
- Sensor Verdict with execution evidence
- Negative control or required non-effect result
- `Cannot verify` limits and next check

## Completion

Completion is allowed only when the Build Verdict passes independently and every applicable Architecture and Sensor verdict passes on the same exact revision. Report each verdict even when another one already blocks completion.
