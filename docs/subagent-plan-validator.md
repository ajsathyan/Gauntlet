# Subagent Plan Validator

Use `scripts/check-subagent-plan.py` before implementation when subagent packetization is required, not merely before dispatching parallel subagents. Runtime tool interception is unavailable, so the accepted current-run manifest and referenced task packets are the durable preflight evidence.

## Manifest

Write `.gauntlet/subagent-plan.json` only when a plan proposes two or more parallel lanes:

```json
{
  "schemaVersion": "1.1",
  "lanes": [
    {
      "id": "C1",
      "status": "To Do",
      "title": "p1-auto: [C1][To Do] Checkout policy",
      "skill": "implementer",
      "objective": "Implement the accepted checkout policy",
      "projectRoot": ".",
      "worktreePath": ".worktrees/C1-checkout-policy",
      "acceptedSource": "docs/specs/checkout-policy.md",
      "scope": "Implement checkout policy and tests",
      "inScope": ["src/checkout/policy/**", "tests/checkout/policy/**"],
      "outOfScope": ["src/checkout/ui/**"],
      "filesRead": ["src/checkout/policy/**", "tests/checkout/policy/**"],
      "filesWrite": ["src/checkout/policy/**", "tests/checkout/policy/**"],
      "filesAvoid": ["src/checkout/ui/**", "docs/unrelated/**"],
      "stateScope": "checkout-policy",
      "stateAccess": "mutates",
      "dependencies": [],
      "consumes": ["accepted checkout policy spec"],
      "produces": ["checkout policy API", "policy regression tests"],
      "constraints": ["preserve unrelated dirty work"],
      "proof": ["npm test -- checkout-policy"],
      "inlineContext": "Read the accepted spec and work only in the owned policy paths.",
      "taskPacketRef": ".gauntlet/packets/C1.md",
      "expectedReturn": "Compact implementation report with changed files, proof, blockers, and next action",
      "askUserPolicy": "Return Needs decision to the orchestrator; do not ask the user directly."
    },
    {
      "id": "C2",
      "status": "To Do",
      "title": "p1-auto: [C2][To Do] Checkout proof",
      "skill": "black-box-tester",
      "objective": "Verify checkout behavior independently",
      "projectRoot": ".",
      "worktreePath": ".",
      "acceptedSource": "docs/specs/checkout-policy.md",
      "scope": "Run checkout black-box proof",
      "inScope": ["tests/checkout/black-box/**"],
      "outOfScope": ["src/checkout/policy/**"],
      "filesRead": ["src/checkout/**", "tests/checkout/black-box/**"],
      "filesWrite": ["tests/checkout/black-box/**"],
      "filesAvoid": ["src/checkout/policy/**", "docs/unrelated/**"],
      "stateScope": "checkout-proof",
      "stateAccess": "read-only",
      "dependencies": ["C1 checkout policy API"],
      "consumes": ["implemented checkout policy"],
      "produces": ["black-box checkout report"],
      "constraints": ["do not mutate production services"],
      "proof": ["npm test -- checkout-black-box"],
      "inlineContext": "Verify the accepted behavior without changing the policy implementation.",
      "taskPacketRef": ".gauntlet/packets/C2.md",
      "expectedReturn": "Verdict, evidence, residual risk, and one next action",
      "askUserPolicy": "Return Needs decision to the orchestrator; do not ask the user directly."
    }
  ]
}
```

`stateAccess` is `none`, `read-only`, or `mutates`. `status` is `To Do`, `In Progress`, `Blocked`, `In Review`, `Done`, or `Canceled`. `taskPacketRef` must be a relative path inside the project root and the referenced packet must exist before validation.

## Command

```sh
scripts/check-subagent-plan.py "$PROJECT_ROOT" .gauntlet/subagent-plan.json --run-id "$RUN_ID"
```

The validator rejects unsupported schemas; incomplete or missing packet references; invalid lane status or project root; overlapping writes; shared mutable state; duplicate proof targets; secret-bearing, oversized, or repeated inline context; and overbroad paths.

It appends every accepted or rejected plan to `.gauntlet/subagent-plan-log.jsonl` and writes `.gauntlet/subagent-plan-summary.json`. Use `--stats --run-id "$RUN_ID"` to emit the checked/rejected/rejection counts for final summaries.
