# Subagent Plan Validator

Use `scripts/check-subagent-plan.py` before dispatching parallel subagents.

## Manifest

Write `.gauntlet/subagent-plan.json` only when a plan proposes two or more parallel lanes:

```json
{
  "schemaVersion": "1.0",
  "lanes": [
    {
      "id": "checkout-browser-proof",
      "skill": "black-box-tester",
      "scope": "Exercise checkout UI",
      "filesRead": ["src/checkout/**"],
      "filesWrite": [],
      "stateScope": "checkout-session",
      "stateAccess": "read-only",
      "proof": ["manual checkout smoke"],
      "inlineContext": "Short lane-specific context only."
    }
  ]
}
```

`stateAccess` is `none`, `read-only`, or `mutates`.

## Command

```sh
scripts/check-subagent-plan.py "$PROJECT_ROOT" .gauntlet/subagent-plan.json --run-id "$RUN_ID"
```

The validator rejects lanes with overlapping writes, shared mutable state, duplicate proof targets, missing fields, oversized inline context, or repeated long inline context.

It appends every accepted or rejected plan to `.gauntlet/subagent-plan-log.jsonl` and writes `.gauntlet/subagent-plan-summary.json`. Use `--stats --run-id "$RUN_ID"` to emit the checked/rejected/rejection counts for final summaries.
