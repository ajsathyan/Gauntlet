# Subagent Plan Validator

Use the manifest for two or more parallel lanes or any write-heavy child implementation lane, including a single write-heavy lane. Every child implementation lane still receives a bounded packet; a single small read-only exploration or review lane does not need this manifest gate.

The accepted current-run manifest and referenced task packets must exist before implementation. Runtime interception is not the proof boundary, so validation happens before work begins rather than immediately before dispatch.

## Manifest

Schema `1.2` stores common context once. Lane objects contain only ownership and lane-specific deltas:

```json
{
  "schemaVersion": "1.2",
  "runId": "2026-07-10-checkout-policy",
  "shared": {
    "projectRoot": ".",
    "acceptedSource": "docs/specs/checkout-policy.md",
    "constraints": ["Preserve unrelated work."],
    "askUserPolicy": "Return Needs decision to the main task.",
    "expectedReturn": "Verdict, evidence, residual risk, and one next action."
  },
  "lanes": [
    {
      "id": "C1",
      "skill": "implementer",
      "objective": "Implement the accepted checkout policy",
      "worktreePath": ".worktrees/C1-checkout-policy",
      "scope": "Checkout policy implementation and regression tests",
      "inScope": ["src/checkout/policy/**", "tests/checkout/policy/**"],
      "outOfScope": ["src/checkout/ui/**"],
      "filesRead": ["src/checkout/policy/**", "tests/checkout/policy/**"],
      "filesWrite": ["src/checkout/policy/**", "tests/checkout/policy/**"],
      "filesAvoid": ["src/checkout/ui/**"],
      "stateScope": "checkout-policy",
      "stateAccess": "mutates",
      "dependencies": [],
      "consumes": ["accepted checkout policy spec"],
      "produces": ["checkout policy behavior", "policy regression proof"],
      "laneConstraints": ["Preserve the current UI contract."],
      "proof": ["npm test -- checkout-policy"],
      "contextDelta": "Use the existing policy boundary; do not redesign checkout UI.",
      "taskPacketRef": ".gauntlet/packets/C1.md"
    }
  ]
}
```

`stateAccess` is `none`, `read-only`, or `mutates`. `taskPacketRef` and `shared.acceptedSource` must be relative paths inside the project root and must exist before validation. Native Codex state owns child progress; the manifest does not require chat titles or status choreography.

## Findings

Validation blocks implementation when the packet is unsafe or non-executable:

- Unsupported or incomplete schema.
- Missing or invalid accepted-source and task-packet references.
- Invalid project root or a reference that escapes it.
- Overlapping write ownership.
- Shared mutable state without an explicit lane dependency.
- Secrets in shared or lane context.
- Overbroad write ownership.

These context-efficiency findings are advisory:

- Repeated lane context that belongs in `shared`.
- Oversized lane or total context.
- Duplicate proof targets.
- Overbroad read scope.

Warnings do not delay implementation unless they reveal a real dependency, ownership conflict, or user decision. Move common safety language to `shared` instead of paraphrasing it independently in every lane.

## Commands

```sh
scripts/check-subagent-plan.py "$PROJECT_ROOT" .gauntlet/subagent-plan.json --run-id "$RUN_ID"
scripts/check-subagent-plan.py "$PROJECT_ROOT" --stats --run-id "$RUN_ID"
```

Every attempt is appended to `.gauntlet/subagent-plan-log.jsonl`; the current-run rollup is written to `.gauntlet/subagent-plan-summary.json`. Successful validation is durable internal evidence and is not a chat or final-summary event. Warnings are surfaced only when they materially change execution or remain a real risk.
