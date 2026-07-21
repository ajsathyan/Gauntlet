---
name: verify
description: Verify the exact committed candidate outcome by outcome, separating behavior from proof availability and architecture.
---

# Verify

Read the user request, accepted Acceptance section, exact candidate commit and
tree, checked base revision, and applicable Architecture Contract. Do not use the
implementer's rationale, self-verdict, plan, or PR summary as proof.

## Outcome verification

For every accepted outcome and required non-effect record:

- **Behavior:** `Passed`, `Failed`, or `Unknown`.
- **Proof availability:** `Available` or `Unavailable`.
- observable oracle and evidence;
- one plausible wrong case when it would distinguish the result;
- remaining check when proof is unavailable.

Run all executable target-specific checks. A blocked broad suite does not end
defect-finding or hide a known candidate failure.

Use triggered modes inside this skill when applicable: black-box public behavior;
code ownership, state, compatibility, and regression risk; and user experience,
accessibility, responsive behavior, and content.

## Verdicts

Derive Build mechanically: any `Failed` behavior is `Failed`; otherwise any
required `Unknown` or unavailable proof is `Blocked`; otherwise it is `Passed`.
Report Architecture separately as `Passed`, `Failed`, `Blocked`, or
`Not applicable`. Architecture cannot override Build. Landing requires both
Build and applicable Architecture to pass on the same commit, tree, and base.

Return exact revision evidence, per-outcome results, both aggregate verdicts,
negative-control result, environment limits, and the next unresolved check.
