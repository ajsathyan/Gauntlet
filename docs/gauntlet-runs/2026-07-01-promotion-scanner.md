# Promotion Scanner

Scope: Add a Gauntlet-general promotion-scanner skill, trigger policy, docs, eval coverage, and installable artifacts.

Mode: Release, Standard
Proof scope: delta

## Assumptions

- The scanner should be a skill plus docs/eval guidance, not a new always-on CLI gate.
- High-value findings may become `GAP-###` candidates only when they expose Gauntlet-general missing guidance; repo-specific loops belong in repo code, repo test, repo docs/run log, or issues.

## Decisions

- Named the capability `promotion-scanner` because it describes the job without implying live ops action.
- Triggered use is explicit request, Release or live-ops wrap-up, repeated manual verification, repeated `Cannot verify`, or repeated run-log evidence.
- Ordinary Patch work remains out of scope.

## Exceptions

- No new `GAP-###` was added because the implementation covers trigger and routing guidance directly rather than exposing a separate missing standard.
- `Cannot verify`: no real multi-repo promotion corpus exists yet; coverage is contract/eval based.

## Proof

- `scripts/check-gauntlet-workflow.py` passed.
- `scripts/run-skill-change-checks.sh --changed-files skills/promotion-scanner/SKILL.md skills/promotion-scanner/examples/promotion-brief.md` passed.
- `python3 scripts/lint-skills.py --skills-root skills --only promotion-scanner --json` passed.
- `python3 scripts/run-skill-evals.py --only-skill promotion-scanner --results evals/results/promotion-scanner-check.json` passed with `new_skill=PASS 16/16`.
- `python3 -m py_compile` passed for workflow and helper scripts.
- `./scripts/install.sh` installed to `/Users/ajsathyan/.codex`.
- `/Users/ajsathyan/.codex/gauntlet/scripts/check-gauntlet-workflow.py` passed from the installed copy.

## Follow-Ups

- Build a small promotion-scanner eval corpus from future run logs if the skill is used in more than one real repo.
