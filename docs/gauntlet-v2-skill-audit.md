# Gauntlet v2 Skill Audit

Updated for v2.0.1: exceptions-first run logs, coverage-gap candidates, packet contracts, three-arm skill evals, behavioral prompt/response scoring, `Cannot verify` slots, optional examples, `Not relevant because` defaults, file-friendly handoffs, conditional subagent guidance, skill linting, and token-efficiency review.

## Eval Method

The deterministic eval runner is `scripts/run-skill-evals.py`.

Every case compares three arms:

- `one_shot`: a concise one-shot instruction prompt from `evals/skill-evals.json`.
- `current_skill`: the frozen baseline under `evals/baselines/current/skills`.
- `new_skill`: the working skill under `skills`.

Each case scores whether the instruction source contains the contract elements needed for that pressure scenario. This is a coverage eval, not a behavioral LLM benchmark; it gives a stable red/green gate before model-based pressure testing.

Behavioral support adds a four-arm prompt/scorer path:

- `no_guidance`
- `one_shot`
- `current_skill`
- `new_skill`

The runner can write behavioral prompt files and score 5+ response reps from a JSON response pack. The bundled `evals/behavior-fixtures.json` is a deterministic smoke test for the scorer and metrics path; replace it with real model response reps for live behavioral pressure testing.

`scripts/lint-skills.py` fails skills that miss the core contract shape: frontmatter description starts with `Use when`, word budget, packet/output contract, `Cannot verify`, `Not relevant because`, optional examples, and bounded parallel-subagent guidance.

`scripts/install-git-hooks.sh` installs a pre-commit hook that calls `scripts/run-skill-change-checks.sh`. When staged files include `skills/*/SKILL.md` or `skills/*/examples/*`, the hook runs the skill evals and skill linter before the commit proceeds.

## Results

Latest deterministic target: all `new_skill` coverage arms pass; `one_shot` and `current_skill` remain comparison arms, not release blockers. The behavior fixture smoke run should score `new_skill` at 5/5 reps for every case.

| Skill | v2.0.1 Decision |
| --- | --- |
| `intake` | Keep packet shape. |
| `planner` | Keep bounded task packets and Release panel table preservation. |
| `product-architect` | Route non-obvious rationale to run logs, not product UI. |
| `implementer` | Report run-log-friendly exceptions instead of review handles. |
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
