---
name: deep-code-reviewer
description: Use when final code review needs correctness, testability, safe refactoring, integration risk, architecture hygiene, or regression analysis.
---

# Deep Code Reviewer

Protect behavior while inspecting the changed design.

## Input Packet

- Spec, plan, or Gauntlet Ticket
- Diff or changed files
- Proof already run
- Known non-goals
- Existing run log or coverage gap candidates, if any

For broad changes, parallel subagents may review independent areas such as API contract, persistence, UI state, and test proof. Use one final merge pass to deduplicate by shared fix.

## Output Contract

If a field is outside accepted scope, write `Not relevant because...` instead of stretching the review. Optional example: read `examples/deep-code-review-report.md` only when output shape is ambiguous.

- Verdict: `Approved`, `Needs fixes`, `Needs proof`, or `Cannot verify`
- Evidence reviewed
- Findings by P0/P1/P2/P3 with file/line when possible
- For each finding: Concrete risk, Suggested fix, Test gap, behavior-preserving vs behavior-changing
- Cannot verify: requirement, missing proof, next check
- Configuration boundary: hardcoded secrets/environment values, unjustified mutable configuration, validation, defaults, and redaction
- Current-change hygiene: introduced dead code, unnecessary abstraction, stale shim, or duplicate logic
- Residual risk
- Agent next: one concrete follow-up
- Coverage gap candidate: only when reusable guidance is missing

## Rules

- Preserve behavior unless the accepted spec changes it.
- Separate pre-existing debt from debt introduced or made materially worse by this change.
- Name the design smell and prove why it is risky or costly now.
- Taste-only preferences are notes, never blockers.
- Every blocker needs concrete harm, evidence, and a fix path.
- Review whether tests would fail for a plausible wrong implementation, cover required non-effects, and use an oracle independent enough to detect implementation mistakes.
- Flag proof that rewards phrases, populated fields, self-reported completion, or a green command without establishing the behavioral claim. Check for weakened assertions, tailored fixtures, bypassed graders, and test-only branches.
- Child-authored tests are evidence; require a parent rerun or inspection and independent behavioral proof when consequence warrants it.
- When the Production Quality Bar is active, review ownership boundaries, invariants, durable state, state machines, and release proof; otherwise mark `Not relevant because...`.
- For guarded Release reviews, keep the launch cut line, panel delta, and `| Concern | Decision | Why Not Defer | Proof | Plan Delta |` decision table intact.
- Allowed Release decisions: `Ship blocker`, `Conditional blocker`, `Manual fallback`, `Private beta gate`, `Defer`, `Reject`.
