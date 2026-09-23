---
name: verify
description: Verify the exact committed candidate outcome by outcome, separating behavior from proof availability and architecture.
---

# Verify

Verify independently from implementation when the accepted workflow requires it.
Read the user request, accepted Acceptance, exact repository path, candidate
commit and tree, checked base revision, and any applicable Architecture Contract.
Do not treat the implementer's rationale, self-verdict, plan, PR text, or a green
command as behavioral proof.

First confirm the binding with native Git: the commit exists, its tree matches the
reported tree, the checked base exists, and the inspected worktree or archive is
the stated repository. Record the commands and outputs that establish those facts.

## Outcome verification

For every accepted outcome and required non-effect report:

- **Behavior:** `Passed`, `Failed`, or `Unknown`.
- **Proof availability:** `Available` or `Unavailable`.
- the observable oracle and exact evidence;
- one plausible wrong case when it distinguishes the result; and
- the remaining check when proof is unavailable.

Run every executable target-specific check. A blocked broad suite does not end
defect-finding or hide a known failure. Use black-box behavior where possible;
also inspect ownership, state, compatibility, regressions, accessibility, and
content when they are part of the accepted outcome.

Derive Build mechanically: any failed behavior is `Failed`; otherwise any
required unknown behavior or unavailable proof is `Blocked`; otherwise it is
`Passed`. Report Architecture separately as `Passed`, `Failed`, `Blocked`, or
`Not applicable`. Architecture cannot override Build. Landing requires both Build
and applicable Architecture to pass on the same commit, tree, and checked base.

Return the repository path, commit, tree, checked base, commands/environment,
per-outcome results, both aggregate verdicts, negative-control result, limits,
and next unresolved check. A Markdown table or concise prose is sufficient; no
JSON handoff, schema, generated artifact, or validator is required.

These instructions are coordination, not authentication. State who performed the
verification and any independence limit honestly. Complete only when every
accepted outcome has a verdict and the exact revision binding is explicit.
