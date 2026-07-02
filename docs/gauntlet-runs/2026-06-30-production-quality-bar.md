# Run Log: Production Quality Bar

Scope: Add a triggered near-launch Production Quality Bar to Gauntlet without making it default Patch or prototype ceremony.

## Assumptions

- The user wants the generalized guardrails implemented as Gauntlet workflow guidance, role hooks, and proof checks rather than a new standalone runtime service.
- Automated GitHub release tags belong in near-launch release proof guidance, not as an always-on requirement for every repo.

## Decisions

- Added `docs/production-quality-bar.md` as the source of truth so role skills can stay compact.
- Integrated the gate as triggered guidance in `AGENTS.md`, README, existing role skills, workflow checks, and skill evals instead of creating a new role skill.
- Added an optional near-launch release-proof line to the PR template for automated GitHub release tags, required checks, artifacts, release notes, dry-run/no-mutation proof, and rollback/support evidence.
- Classified quality-bar concerns as `Automatable`, `Guardrail`, or `Human judgment` so agents route proof to tools and decisions to reviewers.
- Kept the gate out of ordinary Patch work, early prototypes, local demos, UI-only Feature work without launch intent, and speculative refactors unless the user asks.

## Exceptions

- Things that went wrong: the red workflow check initially failed because `docs/production-quality-bar.md` did not exist; after implementation, the full workflow check exposed a targeted-eval edge case where `--only-skill planner` assumed exactly one planner eval, and an installed-copy edge case where `.github/PULL_REQUEST_TEMPLATE.md` is intentionally not installed. The checker now accepts multiple planner cases while still rejecting cross-skill leakage, and treats the PR-template assertion as source-repo-only.
- Cannot verify: real GitHub release automation behavior is not exercised by this workflow-doc change; the change documents automated GitHub release tags and release proof as near-launch evidence to require when relevant.
- Coverage gaps added: none.

## Not Relevant Because

- Runtime rollback, staging, and production deployment proof are not relevant because this changes Gauntlet workflow docs, role skills, evals, and checks rather than a shipped application.
