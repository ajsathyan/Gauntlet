# Run Log: Subagent Plan Validator

Scope: Add a programmatic pre-dispatch gate that rejects inefficient or unsafe subagent plans, logs rejection counts, and emits summary counts for final run messages.

## Assumptions

- The useful signal is rejected parallelization plans, not every possible subagent call.
- Rejection counts can later justify cheaper lane agents or packet-compression work if they recur often.

## Decisions

- Added `scripts/check-subagent-plan.py`.
- The manifest lives at `.gauntlet/subagent-plan.json` and is ignored by git with other local run artifacts.
- Every validation writes `.gauntlet/subagent-plan-log.jsonl`.
- Every validation or stats call writes `.gauntlet/subagent-plan-summary.json`.
- Invalid plans fail before dispatch, but the rejection record is still logged.
- Planner and implementer now point at the validator instead of relying on prose-only subagent guidance.

## Exceptions

- Coverage gaps added: none.
- Things that went wrong: not applicable.
- Cannot verify: actual future subagent dispatch interception depends on agents running the validator before dispatch; this release provides the enforceable gate and workflow checks, not runtime tool interception.

## Not Relevant Because

- Runtime product proof is not relevant because this changes workflow scripts, docs, and role guidance only.
