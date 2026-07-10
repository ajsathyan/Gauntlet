# Canonical Subagent Manifest

Use `.gauntlet/subagent-plan.json` for two or more parallel lanes or any write-heavy child implementation lane. A single small read-only exploration/review lane does not need this gate. The manifest is the complete lane contract; do not maintain separate Markdown task packets.

## Schema 1.2

```json
{
  "schemaVersion": "1.2",
  "runId": "2026-07-10-checkout-policy",
  "shared": {
    "projectRoot": ".",
    "acceptedSource": "user-approved direction in the parent task",
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
      "dependsOn": [],
      "consumes": ["accepted checkout policy"],
      "produces": ["checkout policy API", "regression tests"],
      "laneConstraints": ["Preserve the current UI contract."],
      "proof": ["npm test -- checkout-policy"],
      "contextDelta": "Use the existing policy boundary; do not redesign checkout UI."
    }
  ]
}
```

Shared source, constraints, return contract, and ask-user policy live once in `shared`. Lane objects contain only ownership and lane-specific deltas. `dependsOn` contains lane IDs only. Native Codex state owns progress; the manifest does not require chat titles or status fields.

## Validation

```sh
scripts/check-subagent-plan.py "$PROJECT_ROOT" .gauntlet/subagent-plan.json --run-id "$RUN_ID"
```

The validator rejects unsupported/legacy schemas, duplicate packet fields such as `taskPacketRef`, missing fields, unknown/self/cyclic dependencies, no ready lane, project-root mismatch, overlapping writes, shared mutable state, duplicate proof targets, secret-bearing or repeated context, and overbroad paths. Warnings do not delay implementation unless they expose a real dependency, ownership conflict, or user decision.

The first ready lane has no unresolved dependencies; a dependency is resolved only when native orchestration reports it complete. Rendered child prompts are views of the manifest, never a second source of truth.

Every validation appends to `.gauntlet/subagent-plan-log.jsonl` and updates `.gauntlet/subagent-plan-summary.json`. Successful validation is durable internal evidence; keep clean validation and summary counts out of chat.
