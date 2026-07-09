# Third-Exchange Thread Label Design

## Goal

Make priority and task naming decisions visible and actionable in every Codex task no later than the third user-assistant exchange, while preserving the existing Gauntlet priority mapping and avoiding repeated naming ceremony.

## Behavioral Contract

- If the current task already has a valid title matching `p0` through `p4`, with optional `-auto`, keep it.
- Otherwise, propose a `p#:` or `p#-auto:` title with a four-word goal on the first substantive assistant response whenever the task can be classified responsibly.
- If early ambiguity prevents responsible classification, the assistant may defer once or twice, but it must surface its best priority/title recommendation by the end of the third user-assistant exchange.
- `p0`, `p1`, and `p2` labels remain review-gated before implementation unless the user has already accepted the label or continues without objecting.
- `p3` and `p4` labels remain non-blocking.
- Once accepted, apply the label with `set_thread_title`; do not leave it as chat-only advice.
- Re-evaluate the `-auto` suffix when execution mode materially changes, without reopening an already settled priority unless scope or risk changes.

## Priority Reassessment

Silently re-assess priority at these checkpoints:

1. When the work transitions from research, design, or planning into implementation.
2. When an implementation update materially changes scope, affected systems, external side effects, risk, proof burden, or reversibility.

Ordinary progress, a plan-status update, or a small code edit does not trigger a reassessment. If the priority is unchanged, say nothing about it. If the priority changes:

- State the old and new priority once.
- Name the concrete scope or risk change that caused it.
- Apply the updated `p#:` or `p#-auto:` title with `set_thread_title`.
- Follow the existing review gate if the new priority or newly discovered risk requires a user decision; otherwise continue without adding a ceremonial pause.

Re-assess execution mode at the same checkpoints. Call it out only when the suffix changes between review and `-auto`, and update the title accordingly.

## Research Priority Semantics

Research is never assigned `p4` merely because it is research. Classify it by the consequence and durable decision it supports:

- `p0`: research whose failure could drive Release-class, security, privacy, legal, financial, data-integrity, or similarly material harm.
- `p1`: research that shapes a substantial product, feature, workflow, positioning, or strategic direction.
- `p2`: research that informs a consequential implementation or bounded high-impact decision.
- `p3`: normal bounded research with a durable answer or decision artifact.
- `p4`: low-durable-output brainstorming, abandoned work, routine admin, or intentionally parked exploration.

When classification is uncertain, default bounded research to `p3`, not `p4`, and raise it when downstream consequence warrants it. Do not inflate priority solely because research is broad or time-consuming.

## Scope

Change the Gauntlet source guidance, its workflow checks, and installation verification. Reinstall the updated guidance into the active Codex home so new tasks receive the rule immediately after reload. Rename the currently active workflow-fix task and the live `harness-evals` task as direct recovery actions.

Out of scope:

- A background service that counts messages.
- Automatic priority inference outside the agent workflow.
- Renaming already-valid labeled tasks.
- Reprioritizing tasks based on urgency; the existing mapping remains based on work class and consequence.
- Building a separate research-only priority system.

## Implementation Design

1. Add the third-exchange deadline, first-substantive-response preference, impact-based research mapping, and silent reassessment checkpoints to `AGENTS.md` and `docs/workflow-etiquette.md`.
2. Add a focused workflow test that fails until both source surfaces contain the deadline, accepted-label action, valid-title exception, research rule, and change-only reassessment announcement.
3. Extend install verification so the installed global `AGENTS.md` is checked for the same invariant, preventing a source/install drift recurrence.
4. Run targeted workflow checks, then the full Gauntlet workflow check.
5. Reinstall Gauntlet for Codex and verify the installed global guidance contains the invariant.

The guidance remains the enforcement mechanism because Codex task behavior is prompt-driven. The tests prove durable propagation and required wording; a future trace-based behavioral eval can measure model compliance across three-turn fixtures, but no runtime message-counting subsystem is added for this patch.

## Failure Handling

- If the installer would overwrite unrelated global changes, compare source and installed guidance first and stop rather than discarding user-owned policy.
- If the full workflow check exposes unrelated pre-existing failures, report them separately and do not claim full verification.
- If a task cannot be classified responsibly by the third exchange, require a provisional best recommendation with the uncertainty stated; silence is not allowed.

## Proof

- Red: the new focused assertions fail against the current source because no third-exchange deadline exists.
- Green: targeted workflow checks pass after the guidance change.
- Regression: the full workflow checker passes.
- Install: a temporary-home install test and the real Codex install both contain the new invariant.
- App state: both accepted task titles are confirmed through task metadata.

## Acceptance Criteria

- Global and source guidance require the priority/title recommendation by the third exchange at the latest.
- Guidance prefers the first substantive response when classification is already possible.
- Existing valid labels are not reopened.
- Accepted labels are applied with `set_thread_title`.
- Research is classified by downstream consequence and defaults to `p3` when bounded but otherwise uncertain; it is never automatically `p4`.
- Priority is silently re-assessed at implementation start and after material implementation changes.
- Unchanged priority produces no chat message; changed priority produces one reasoned callout and an updated task title.
- Automated checks fail if the deadline disappears from source or installed guidance.
- The live eval task is titled `p0-auto: build harness eval suite`.
- This task is titled `p2-auto: enforce third-turn priority labels`.
