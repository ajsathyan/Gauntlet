---
name: verify
description: Use for independent exact-revision verification against requested outcomes, any accepted design, the Architecture Contract, and the Sensor Contract with separate verdicts.
---

# Verify

Independently verify the exact integrated revision. Read the user request and any
accepted design directly; never substitute a worker-authored plan, child receipt,
narrowed checklist, pull-request summary, or sensor selection.

## Inputs

- User-requested outcomes and conversation decisions
- Any exact accepted design and canonical Build Contract
- Exact integrated revision and tree
- Applicable Architecture Contract
- Applicable Sensor Contract and raw evidence references

If required outcomes or exact-revision evidence are missing or stale, return
`Cannot verify` and block the completion claim and landing of that candidate.

When using the optional exact-design proof path, begin with a passing
`workflow verify-entry` from the installed Gauntlet CLI against the bound
temporary contract and accepted design. Its absence does not invalidate a
request-based independent verification.

## Procedure

1. Enumerate every requested outcome and required non-effect, including every item in an applicable design's `Acceptance` section.
2. Inspect and exercise externally observable evidence for each item. Include a plausible wrong case when it can distinguish the implemented outcome from a shallow or narrowed pass.
3. Inspect the exact revision against the Architecture Contract independently of product behavior.
4. Verify that all required configured sensors actually executed against the exact revision. Run or rerun `sensors run` when required evidence is missing, stale, failed, unavailable, or not run.
5. Return three separate verdicts:
   - **Build Verdict:** `Pass`, `Fail`, or `Cannot verify` for every requested or accepted product outcome and required non-effect.
   - **Architecture Verdict:** `Pass`, `Fail`, `Not applicable`, or `Cannot verify`.
   - **Sensor Verdict:** `Pass`, `Fail`, `Not applicable`, or `Cannot verify`.
   `Not applicable` is valid only when the accepted source has no nonempty exact
   section for that Architecture or Sensor Contract.
6. When using the optional exact-design proof path, use
   `workflow record-verdict` to record each of those three verdicts, passing
   the updated temporary contract forward each time. Build outcome evidence uses
   a distinct `revision:<commit>#path:<candidate-relative-file>` reference for
   every accepted outcome. The referenced file must exist in that exact Git
   revision.
7. For the optional exact-design proof path, run `workflow completion-check`; a
   failed command blocks that proof claim. Remove task-temporary workflow files
   after handoff; never preserve them as product documents or controller state.

The Build Verdict is authoritative for requested and accepted outcomes.
Architecture or Sensor success cannot turn a Build failure into completion. A
green sensor pass and narrowed worker checklist must fail when any requested
user outcome is absent. Applicable Architecture and Sensor failures still block
completion, but neither substitutes for Build.

## Output

- Exact revision verified
- Build Verdict with requested and acceptance-item evidence
- Architecture Verdict with contract evidence
- Sensor Verdict with execution evidence
- Negative control or required non-effect result
- `Cannot verify` limits and next check

## Completion

Completion and non-production landing are allowed only when the Build Verdict
passes independently and every required Architecture and Sensor verdict passes
on the same exact revision. Report each verdict even when another one already
blocks completion.
