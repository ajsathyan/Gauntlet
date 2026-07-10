# Gauntlet v2 Skill Audit

Updated for v2.0.2: exceptions-first run logs, coverage-gap candidates, packet contracts, three-arm skill coverage, explicit scorer smoke, observable orchestration traces, `Cannot verify` slots, conditional subagent guidance, skill linting, and token-efficiency review.

## Eval Method

The deterministic eval runner is `scripts/run-skill-evals.py`.

Every case compares three arms:

- `one_shot`: a concise one-shot instruction prompt from `evals/skill-evals.json`.
- `current_skill`: the frozen baseline under `evals/baselines/current/skills`.
- `new_skill`: the working skill under `skills`.

Each case scores whether the instruction source contains the contract elements needed for that pressure scenario. This is a coverage eval, not an agent-behavior benchmark; it gives a stable red/green gate for missing skill text.

Scorer smoke adds a four-arm phrase-matcher path:

- `no_guidance`
- `one_shot`
- `current_skill`
- `new_skill`

The runner can write scorer-smoke prompts and score response fixtures. The bundled `evals/scorer-smoke-fixtures.json` intentionally lets a phrase echo pass. It proves that the phrase matcher and aggregation path work; it makes no claim about whether an agent took the right action. The runner exits nonzero when `new_skill` misses text coverage or a configured scorer-smoke response pack lacks the minimum passing reps. The old `--behavior-responses` and `--behavior-prompts-dir` flags remain hidden compatibility aliases, but result files use only `scorerSmoke` names.

Observable orchestration outcomes use `scripts/run-orchestration-evals.py`, the schema in `evals/orchestration-trace-schema.json`, and paired traces in `evals/orchestration-trace-fixtures.json`. The deterministic scorer checks:

- task outcome;
- required and forbidden actions;
- action authority;
- passing proof evidence;
- routing choice when the contract specifies one;
- user-visible message count and word budget; and
- cost and latency limits when those metrics are recorded.

The scorer pack contains passing traces plus missing-proof, authority-violation, verbose-output, and phrase-echo/wrong-action failures. The canary contains expected report language but fails because its observable action, outcome, routing, and proof are wrong. Subjective criteria always return `cannot_verify` until a separately calibrated judgment process exists; deterministic success cannot auto-green them.

Run the local layers with:

```sh
scripts/run-skill-evals.py --scorer-smoke-responses evals/scorer-smoke-fixtures.json
scripts/run-orchestration-evals.py --pack evals/orchestration-trace-fixtures.json
```

Neither command calls a model or the network. Representative live-model behavior and judgment calibration remain `Cannot verify`.

`scripts/lint-skills.py` fails skills that miss the core contract shape: frontmatter description starts with `Use when`, word budget, packet/output contract, `Cannot verify`, `Not relevant because`, optional examples, and bounded parallel-subagent guidance.

`scripts/install-git-hooks.sh` installs a pre-commit hook that calls `scripts/run-skill-change-checks.sh`. When staged files include `skills/*/SKILL.md` or `skills/*/examples/*`, the hook runs the skill evals and skill linter before the commit proceeds.

## Results

Latest deterministic target: all `new_skill` coverage arms pass; `one_shot` and `current_skill` remain comparison arms, not release blockers. Scorer smoke should score `new_skill` at 5/5 reps for every case. Orchestration trace fixtures pass only when every arm produces its expected `pass`, `fail`, or `cannot_verify` verdict.

| Skill | Current Decision |
| --- | --- |
| `intake` | Keep packet shape. |
| `planner` | Keep bounded main-plan tasks; use one canonical manifest instead of duplicate subagent packets. |
| `product-architect` | Route non-obvious rationale to run logs, not product UI. |
| `implementer` | Return compact machine receipts for delegated lanes and run-log-friendly exceptions only when material. |
| `adversarial-reviewer` | Report concrete risk and optional coverage gap candidates. |
| `black-box-tester` | Keep external charters and proof limits. |
| `experience-reviewer` | Keep PM/design separation and optional coverage gap candidates. |
| `deep-code-reviewer` | Keep architecture hygiene and current-change risk focus. |
| `issue-triager` | Keep ready/deferred/rejected flow control. |
| `run-log-builder` | Replace the old default artifact with exceptions-first Markdown and pending gap capture. |

## Token Efficiency Notes

The `run-log-builder` deliberately avoids proof-dump behavior:

- Routine passing checks stay in final chat.
- Run logs store material assumptions, decisions, exceptions, `Cannot verify`, and follow-ups.
- Release work keeps compact proof and panel decisions because launch risk needs durable context.
- Coverage gaps remain pending candidates until a human chooses rule, reference, exemplar, lint, eval, coverage gap, or no change.
