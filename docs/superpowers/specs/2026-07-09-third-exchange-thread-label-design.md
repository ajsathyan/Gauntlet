# Workflow Kickoff and Implementation Transition Design

## Goal

Make task kickoff and implementation transitions explicit and safe: decide priority and naming by the third exchange, reassess only at material checkpoints, packetize delegated work before implementation, and re-run edge-case detection for every genuine scope addition without adding routine chat ceremony.

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

## Pre-Implementation Subagent Packetization Gate

At the transition into implementation, record one of:

```text
Subagent packetization: required
Subagent packetization: not relevant because <specific reason>
```

Packetization is required when the user asks for subagents, the accepted plan proposes parallel lanes, or the work will be implemented by multiple agent or child-chat lanes. When required, implementation does not begin until:

- Every lane has an accepted task packet with lane id/title/status, skill and objective, project root and worktree when relevant, accepted spec or source, in/out scope, ownership, avoided areas, dependencies, consumes/produces contracts, constraints, proof, expected return format, and ask-user policy.
- `.gauntlet/subagent-plan.json` references those packets and passes `scripts/check-subagent-plan.py` for the current run.
- Write-heavy lane worktrees and file ownership are named before any delegated edit.
- The orchestrator records the accepted lane ledger and first ready lane.

Extend the manifest validation beyond lane collision checks so it rejects missing packet references, lane identity/status, skill/objective, project/worktree context, accepted source, in/out scope, ownership/avoidance, dependencies, consumes/produces contracts, proof, expected return format, and ask-user policy. If material implementation changes add or reshape delegated lanes, re-run packetization before implementing the affected scope.

This is a pre-implementation workflow gate, not merely a pre-dispatch suggestion. Runtime tool interception remains unavailable, so durable proof consists of a validated current-run manifest, referenced packets, workflow tests, and implementer guidance that refuses delegated implementation without them.

## Scope-Addition Delta Foresight

Run a focused edge-case check for every genuine addition to accepted plan scope before implementing that addition. A genuine scope addition introduces or expands behavior, interfaces, data/state, dependencies, affected systems, side effects, acceptance criteria, or proof obligations. Rewording, task splitting, status changes, and rearranging already accepted work do not count.

Record the smallest useful evidence in the plan or task packet. When nothing material changes, use only:

```text
Scope delta checked: no material change.
```

When the check finds a material delta, record:

```text
Scope addition: <added scope>
New edge cases: <items or none>
Invalidated assumptions: <items or none>
Acceptance/proof delta: <change or none>
Priority/execution delta: <change or none>
Packetization delta: <change or none>
Need user decision: <question or none>
```

The check must inspect both the added scope and its boundaries with existing scope. If every delta is `none`, write only the one-line plan/task-packet marker and say nothing in chat. The marker exists solely to make the check consistent and auditable; do not expand it into ceremony. When the check finds a material delta, update affected task packets, dependencies, acceptance criteria, and verification before implementation, then call it out when it changes the plan, proof, priority, execution mode, packetization, or requires a user decision.

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

1. Add the third-exchange deadline, first-substantive-response preference, impact-based research mapping, silent reassessment checkpoints, packetization gate, and scope-addition delta foresight to `AGENTS.md` and `docs/workflow-etiquette.md`.
2. Extend the planner and implementer contracts so implementation cannot begin when required packetization or a scope-addition delta check is missing.
3. Extend the subagent manifest and validator to cover complete lane-packet references and required handoff fields, then add red-green validator tests.
4. Add focused workflow tests for the deadline, accepted-label action, valid-title exception, research rule, change-only reassessment announcement, packetization-before-implementation rule, and scope-addition delta record.
5. Extend install verification so the installed global `AGENTS.md` is checked for the same invariants, preventing source/install drift recurrence.
6. Run targeted workflow and validator checks, then the full Gauntlet workflow check.
7. Reinstall Gauntlet for Codex and verify the installed global guidance contains the invariants.

The guidance remains the enforcement mechanism because Codex task behavior is prompt-driven. The tests prove durable propagation and required wording; a future trace-based behavioral eval can measure model compliance across three-turn fixtures, but no runtime message-counting subsystem is added for this patch.

## Failure Handling

- If the installer would overwrite unrelated global changes, compare source and installed guidance first and stop rather than discarding user-owned policy.
- If the full workflow check exposes unrelated pre-existing failures, report them separately and do not claim full verification.
- If a task cannot be classified responsibly by the third exchange, require a provisional best recommendation with the uncertainty stated; silence is not allowed.
- If required packetization is missing or rejected, block delegated implementation and return the exact missing packet or rejection evidence.
- If a scope addition reveals a material unresolved edge case, do not implement that addition until the plan, proof, or user decision is updated.

## Proof

- Red: the new focused assertions fail against the current source because no third-exchange deadline exists.
- Green: targeted workflow checks pass after the guidance change.
- Regression: the full workflow checker passes.
- Install: a temporary-home install test and the real Codex install both contain the new invariant.
- Packetization: a missing or incomplete lane packet fails implementation preflight; a complete current-run packet set passes.
- Scope addition: a fixture with a material new edge case records the resulting assumption, proof, priority, or packetization delta before implementation; a no-finding fixture produces only the one-line plan marker and no chat requirement.
- App state: both accepted task titles are confirmed through task metadata.

## Acceptance Criteria

- Global and source guidance require the priority/title recommendation by the third exchange at the latest.
- Guidance prefers the first substantive response when classification is already possible.
- Existing valid labels are not reopened.
- Accepted labels are applied with `set_thread_title`.
- Research is classified by downstream consequence and defaults to `p3` when bounded but otherwise uncertain; it is never automatically `p4`.
- Priority is silently re-assessed at implementation start and after material implementation changes.
- Unchanged priority produces no chat message; changed priority produces one reasoned callout and an updated task title.
- Required subagent packetization is validated before implementation, not merely before dispatch.
- Complete lane packets cover ownership, avoided areas, dependencies, consumes/produces contracts, proof, expected return format, and ask-user policy.
- Every genuine scope addition receives a delta-foresight check before its implementation.
- Scope additions with no material delta produce only a one-line plan/task-packet marker and no chat message; material findings update the plan and are called out.
- Automated checks fail if the deadline disappears from source or installed guidance.
- The live eval task is titled `p0-auto: build harness eval suite`.
- This task is titled `p2-auto: harden implementation transition gates`.
