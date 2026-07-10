# Canonical Subagent Manifest

Use `scripts/check-subagent-plan.py` only when a plan proposes two or more genuinely parallel lanes. `.gauntlet/subagent-plan.json` is the sole lane contract; do not maintain separate Markdown task packets.

## Schema 1.2

Shared `acceptedSource` and `constraints` may be declared once at plan level. A lane can override either when its source or constraints differ. `dependencies` remains a descriptive string list in this version; it does not imply DAG, readiness, or cycle enforcement.

```json
{
  "schemaVersion": "1.2",
  "acceptedSource": "docs/plans/accepted-plan.md",
  "constraints": ["preserve unrelated work"],
  "lanes": [
    {
      "id": "C1",
      "status": "To Do",
      "title": "p1-auto: [C1][To Do] Checkout policy",
      "skill": "implementer",
      "objective": "Implement the accepted checkout policy",
      "projectRoot": ".",
      "worktreePath": ".worktrees/C1-checkout-policy",
      "scope": "Checkout policy and tests",
      "inScope": ["src/checkout/policy/**", "tests/checkout/policy/**"],
      "outOfScope": ["src/checkout/ui/**"],
      "filesRead": ["src/checkout/policy/**", "tests/checkout/policy/**"],
      "filesWrite": ["src/checkout/policy/**", "tests/checkout/policy/**"],
      "filesAvoid": ["src/checkout/ui/**"],
      "stateScope": "checkout-policy",
      "stateAccess": "mutates",
      "dependencies": [],
      "consumes": ["accepted checkout policy"],
      "produces": ["checkout policy API", "policy regression tests"],
      "proof": ["npm test -- checkout-policy"],
      "inlineContext": "Read the accepted source and work only in owned paths.",
      "askUserPolicy": "Return Needs decision to the orchestrator; do not ask the user directly."
    },
    {
      "id": "C2",
      "status": "To Do",
      "title": "p1-auto: [C2][To Do] Checkout proof",
      "skill": "black-box-tester",
      "objective": "Verify checkout behavior independently",
      "projectRoot": ".",
      "worktreePath": ".worktrees/C2-checkout-proof",
      "scope": "Black-box checkout proof",
      "inScope": ["tests/checkout/black-box/**"],
      "outOfScope": ["src/checkout/policy/**"],
      "filesRead": ["src/checkout/**", "tests/checkout/black-box/**"],
      "filesWrite": ["tests/checkout/black-box/**"],
      "filesAvoid": ["src/checkout/policy/**"],
      "stateScope": "checkout-proof",
      "stateAccess": "read-only",
      "dependencies": ["checkout policy must exist before proof"],
      "consumes": ["implemented checkout policy"],
      "produces": ["black-box checkout evidence"],
      "proof": ["npm test -- checkout-black-box"],
      "inlineContext": "Verify accepted behavior without changing the policy implementation.",
      "askUserPolicy": "Return Needs decision to the orchestrator; do not ask the user directly."
    }
  ]
}
```

`stateAccess` is `none`, `read-only`, or `mutates`. `status` is `To Do`, `In Progress`, `Blocked`, `In Review`, `Done`, or `Canceled`. Schema 1.1 and `taskPacketRef` fail with a migration message because a packet file is no longer accepted as proof of a complete handoff.

## Validate and render

```sh
scripts/check-subagent-plan.py "$PROJECT_ROOT" .gauntlet/subagent-plan.json --run-id "$RUN_ID"
scripts/check-subagent-plan.py "$PROJECT_ROOT" .gauntlet/subagent-plan.json --run-id "$RUN_ID" --render-lane C1
```

Rendering runs only after all manifest checks pass. It reuses the secret, context-size, bounded-path, overlapping-write, shared-mutable-state, duplicate-proof, and project-root checks. The compact JSON view includes the resolved accepted source and constraints, a no-narration/silent-recovery policy, and this fixed receipt shape:

```json
{"status":"Done","changedFiles":[],"proof":[],"blocker":null}
```

The renderer defaults to 12,000 characters and fails closed when `--max-render-chars` would be exceeded. A rendered prompt is an ephemeral view, not another source of truth.

Every validation appends to `.gauntlet/subagent-plan-log.jsonl` and updates `.gauntlet/subagent-plan-summary.json`. Use `--stats --run-id "$RUN_ID"` for compact final counts.
