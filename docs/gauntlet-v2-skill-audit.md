# Gauntlet v2 Skill Audit

Generated from the v2 rewrite pass and follow-up efficiency/quality hardening:
packet contracts, three-arm skill evals, behavioral prompt/response scoring,
`Cannot verify` slots, optional examples, `Not relevant because` defaults,
file-friendly handoffs, conditional subagent guidance, skill linting, and
token-efficiency review.

## Eval Method

The deterministic eval runner is `scripts/run-skill-evals.py`.

Every case compares three arms:

- `one_shot`: a concise one-shot instruction prompt from `evals/skill-evals.json`.
- `current_skill`: the frozen baseline under `evals/baselines/current/skills`.
- `new_skill`: the working skill under `skills`.

Each case scores whether the instruction source contains the contract elements
needed for that pressure scenario. This is a coverage eval, not a behavioral LLM
benchmark; it gives a stable red/green gate before model-based pressure testing.

Behavioral support now adds a four-arm prompt/scorer path:

- `no_guidance`
- `one_shot`
- `current_skill`
- `new_skill`

The runner can write behavioral prompt files and score 5+ response reps from a
JSON response pack. The bundled `evals/behavior-fixtures.json` is a deterministic
smoke test for the scorer and metrics path; replace it with real model response
reps for live behavioral pressure testing.

`scripts/lint-skills.py` now fails skills that miss the core contract shape:
frontmatter description starts with `Use when`, word budget, packet/output
contract, `Cannot verify`, `Not relevant because`, optional examples, and bounded
parallel-subagent guidance.

`scripts/install-git-hooks.sh` installs a pre-commit hook that calls
`scripts/run-skill-change-checks.sh`. When staged files include
`skills/*/SKILL.md` or `skills/*/examples/*`, the hook runs the skill evals and
skill linter before the commit can proceed. This is the automatic "every
Gauntlet skill change" guard; `scripts/check-gauntlet-workflow.py` also exercises
the same path for CI-style proof.

## Results

Latest deterministic result: all `new_skill` coverage arms passed; all
`one_shot` and `current_skill` coverage arms failed. The behavior fixture smoke
run scored `new_skill` at 5/5 reps for every case.

| Skill | New Eval | Word Delta | Stretch Audit | v2 Decision |
| --- | --- | ---: | --- | --- |
| `intake` | Pass | +5.9% | Packet fields use `None` or `Not relevant because` when not applicable; stop rule only for material risk. | Upgrade to v2.0 |
| `planner` | Pass | -12.5% | Subagents are conditional on independent files/state/proof; tightly coupled work stays serialized. | Upgrade to v2.0 |
| `product-architect` | Pass | -13.1% | Activation, retention, growth, sharing, and handoff are `Not relevant because` unless tied to accepted scope. | Upgrade to v2.0 |
| `implementer` | Pass | +5.9% | No subagent guidance added; implementation executes one ready packet and reports proof. | Upgrade to v2.0 |
| `adversarial-reviewer` | Pass | +82.9% | Added only risk-lens subagent guidance for broad Release work; not one worker per failure mode. | Upgrade to v2.0 |
| `black-box-tester` | Pass | +104.8% | Added a stop rule: stop when the charter answers the oracle or missing proof blocks validation. | Upgrade to v2.0 |
| `experience-reviewer` | Pass | +33.5% | Guards against growth/retention wishlist drift unless accepted scope makes it relevant. | Upgrade to v2.0 |
| `deep-code-reviewer` | Pass | -12.3% | Parallel review only for independent areas, with one final merge pass. | Upgrade to v2.0 |
| `issue-triager` | Pass | -8.4% | Ready state requires next action and done criteria; cleanup is deferred/rejected/no-action unless bounded. | Upgrade to v2.0 |
| `review-brief-builder` | Pass | -68.9% | Shrunk from broad process guide to normalization contract; startup detail remains in `AGENTS.md` and scripts. | Upgrade to v2.0 |

## Keep As Is

None of the current role skills should remain at v1 shape. The suite works best
as one coordinated v2.0 because the value comes from shared packet/report slots:
`Verdict`, `Evidence`, `Cannot verify`, `Residual risk`, `Agent next`, and
review-brief handle hints.

## Token Efficiency Notes

The three intentional increases are reviewer/tester skills that were previously
too short to be machine-checkable:

- `adversarial-reviewer`
- `black-box-tester`
- `experience-reviewer`

Those increases buy unified verdicts, evidence fields, proof gaps, bounded
subagent guidance, explicit `Not relevant because` defaults, and cold optional
examples. The overall suite still improves because `review-brief-builder` drops
by roughly 69%, and every skill stays below the 500-word linter budget.
