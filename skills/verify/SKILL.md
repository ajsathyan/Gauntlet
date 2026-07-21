---
name: verify
description: Use for independent exact-revision verification against requested outcomes, the accepted Design or PRD, and the Architecture Contract with separate verdicts.
---

# Verify

Independently verify the exact integrated revision. Read the user request and
accepted Design/PRD directly; never substitute a worker plan, child receipt,
narrowed checklist, or pull-request summary.

## Inputs

- User-requested outcomes and conversation decisions
- Exact accepted Design/PRD and canonical Build Contract
- Exact integrated revision and tree
- Applicable Architecture Contract

If required outcomes or exact-revision evidence are missing or stale, return
`Cannot verify` and block landing of that candidate.

When using the optional exact-design proof path, begin with a passing
`workflow verify-entry` against the temporary contract and accepted design. Its
absence does not invalidate request-based independent verification.

## Procedure

1. Enumerate every requested outcome and required non-effect, including every item in the accepted `Acceptance` section.
2. Exercise externally observable evidence for each item. Include a plausible wrong case, state transition, retry, recovery path, concurrency case, or required non-effect when it distinguishes the intended result.
3. Inspect the exact revision against the Architecture Contract independently of product behavior.
4. Return two separate verdicts:
   - **Build Verdict:** `Pass`, `Fail`, or `Cannot verify` for every requested or accepted product outcome and required non-effect.
   - **Architecture Verdict:** `Pass`, `Fail`, `Not applicable`, or `Cannot verify`.
5. For the optional exact-design proof path, record Build and Architecture verdicts against the same temporary contract, then run `workflow completion-check`. Build evidence uses a distinct `revision:<commit>#path:<candidate-relative-file>` reference for each accepted outcome.
6. Remove task-temporary workflow files after handoff.

The Build Verdict is authoritative for requested and accepted outcomes.
Architecture success cannot turn a Build failure into completion, and an
applicable Architecture failure still blocks landing.

## Output

- Exact revision verified
- Build Verdict with requested and acceptance-item evidence
- Architecture Verdict with contract evidence
- Negative control or required non-effect result
- `Cannot verify` limits and next check

## Completion

Landing is allowed only when the Build Verdict passes independently and the
applicable Architecture Verdict passes on the same exact revision. Report both
verdicts even when one already blocks completion.
