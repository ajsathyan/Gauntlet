# Meaningful Proof Policy Rewrite

Scope: audit and rewrite Gauntlet's delegation, testing, evaluation, and proof policy so superficial phrases, populated fields, and self-reported results cannot be mistaken for behavioral proof.

Proof scope: full

## Decisions

- Use concise prose **Gauntlet tickets** for ephemeral child assignments. Proof fields are optional and proportional to risk.
- Define meaningful proof as a claim or invariant, an observable oracle, a plausible wrong case or negative control, required non-effects, protected oracle ownership, parent verification, and explicit limits where applicable.
- Treat child receipts, merge handoff testing records, and declared trace fixtures as evidence pointers. The integrating parent or trusted harness must resolve or rerun them before accepting the behavioral claim.
- Keep phrase and field matchers only as labeled structural-coverage and scorer-wiring checks. Semantic claims require execution, source-grounded comparison, or a validated judge.
- Integrate independent child changes into one parent branch as they arrive, run targeted checks per integration, then run combined proof once all lanes are integrated.

## Exceptions

- The first integrated workflow run found stale assertions for retired task-packet wording. The assertions and skill coverage fixtures were updated to the ticket contract rather than restoring obsolete phrases.
- The planner rewrite initially dropped the full guarded Release decision vocabulary and duplicate-panel comparison rule. Both contracts were restored.
- The planner initially exceeded the 500-word skill budget. Redundant narration and attribution prose were removed without weakening the ticket or proof contract.
- Final review found that explicit test ownership could still legitimize a weakened oracle. Oracle edits now invalidate acceptance until the parent independently reviews or redefines the oracle.
- Final review found nested prompt/template files and referenced guidance could still be classified as docs-only. The classifier and regression fixture now cover nested prompt paths, skill examples, router guidance, behavior-bearing Gauntlet docs, and bare `prompt:` configuration keys.
- Final review found `passRate` had silently changed from actual matcher passes to expectation matches, and string `"false"` could be coerced to true. The original metric was restored, `expectationMatchRate` was added, and fixture booleans are now type-checked.
- `Cannot verify`: this repository run does not measure live Codex, Claude Code, or other harness delegation behavior. A representative cross-harness benchmark is still needed before claiming behavioral improvement or token savings.

## Production Quality Bar

Not relevant because this changes local workflow instructions and deterministic harnesses, not a production runtime, deployment, durable customer data path, or live release.

## Coverage Gap Candidates

No new candidate. The audit found reusable proof-policy gaps and resolved them in the central guidance, skills, classifiers, and regression suite during this run.
