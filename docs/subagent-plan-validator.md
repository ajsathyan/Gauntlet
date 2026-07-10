# Canonical Subagent Manifest

Use the manifest for two or more parallel lanes or any write-heavy child implementation lane, including a single write-heavy lane. A single small read-only exploration or review lane does not need this gate.

`.gauntlet/subagent-plan.json` is the sole lane contract. Do not maintain a second Markdown task packet. The validator checks the accepted current-run manifest before implementation, and `--render-lane` creates the bounded child prompt directly from it.

## Schema 1.2

Schema `1.2` stores common context once. Lane objects contain ownership and lane-specific deltas:

```json
{
  "schemaVersion": "1.2",
  "runId": "2026-07-10-checkout-policy",
  "shared": {
    "projectRoot": ".",
    "acceptedSource": "docs/specs/checkout-policy.md",
    "constraints": ["Preserve unrelated work."],
    "askUserPolicy": "Return Needs decision to the main task.",
    "expectedReturn": "Compact status, changed files, proof, and blocker only."
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
      "contextDelta": "Use the existing policy boundary; do not redesign checkout UI."
    }
  ]
}
```

`stateAccess` is `none`, `read-only`, or `mutates`. `shared.acceptedSource` must be a relative file path inside the project root and must exist before validation. `contextDelta` is required but may be empty when the shared accepted source fully defines the lane. Native Codex state owns progress; the manifest does not require chat titles or status choreography.

`dependencies` remains a descriptive string list in this version. It may declare a simple ordering safety hint, but it does not provide typed DAG, readiness, cycle, review, or completion enforcement.

Schema 1.1 and `taskPacketRef` fail with a migration message because a packet file is no longer accepted as proof of a complete handoff.

## Findings

Validation blocks implementation for unsupported, incomplete, or unknown schema fields; accepted-source or write-ownership paths outside the project; project-root escapes; overlapping write ownership; unordered shared mutable state; secrets; and overbroad write ownership. Strict fields keep the renderer from silently dropping lane context.

Repeated or oversized lane context, duplicate proof targets, and broad read scope are advisory. Warnings delay work only when they expose a real dependency, ownership conflict, or user decision.

## Validate and render

```sh
scripts/check-subagent-plan.py "$PROJECT_ROOT" .gauntlet/subagent-plan.json --run-id "$RUN_ID"
scripts/check-subagent-plan.py "$PROJECT_ROOT" .gauntlet/subagent-plan.json --run-id "$RUN_ID" --render-lane C1
scripts/check-subagent-plan.py "$PROJECT_ROOT" --stats --run-id "$RUN_ID"
```

Rendering happens only after validation passes. The compact JSON prompt contains shared context, the selected lane, a no-narration and bounded silent-retry policy, and this receipt shape:

```json
{"status":"Done","changedFiles":[],"proof":[],"blocker":null}
```

The renderer defaults to 12,000 characters and fails closed when `--max-render-chars` is exceeded. A rendered prompt is an ephemeral view, not another source of truth.

Every validation appends to `.gauntlet/subagent-plan-log.jsonl` and updates `.gauntlet/subagent-plan-summary.json`. Successful validation is internal evidence, not a required chat update.
