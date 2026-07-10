# Canonical Subagent Manifest

Use `scripts/check-subagent-plan.py` only when a plan proposes two or more genuinely parallel lanes. `.gauntlet/subagent-plan.json` is the canonical lane contract; do not maintain separate Markdown task packets.

## Schema 1.2

```json
{
  "schemaVersion": "1.2",
  "acceptedSource": "user-approved direction in the parent task",
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
      "dependsOn": [],
      "consumes": ["accepted checkout policy"],
      "produces": ["checkout policy API", "regression tests"],
      "proof": ["npm test -- checkout-policy"],
      "inlineContext": "Read the accepted source and work only in owned paths.",
      "expectedReturn": "Changed files, proof, blockers, and next action",
      "askUserPolicy": "Return Needs decision to the orchestrator."
    }
  ]
}
```

Shared `acceptedSource` and `constraints` may be declared once at the top. Lane-specific overrides are optional. `dependsOn` contains lane IDs only.

## Validation

```sh
scripts/check-subagent-plan.py "$PROJECT_ROOT" .gauntlet/subagent-plan.json --run-id "$RUN_ID"
```

The validator rejects unsupported/legacy schemas, missing fields, unknown/self/cyclic dependencies, no ready lane, project-root mismatch, overlapping writes, shared mutable state, duplicate proof targets, secret-bearing or repeated context, and overbroad paths.

The first ready lane has no unresolved dependencies; a dependency is resolved when its lane status is `Done`. The manifest may be rendered into a child prompt, but rendered text is a view—not a second source of truth.

Every accepted or rejected validation appends to `.gauntlet/subagent-plan-log.jsonl` and updates `.gauntlet/subagent-plan-summary.json`.
