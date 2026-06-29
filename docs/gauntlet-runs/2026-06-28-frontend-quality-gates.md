# Run Log: Frontend Quality Gates

Scope: Add bounded frontend quality guidance, gap promotion, and Rauno-inspired UI checks to Gauntlet without creating a full design-system workflow.

## Assumptions

- Frontend quality checks should run only for substantial UI work, major prototype surfaces, frontend Release work, or repeated UI findings.
- Early prototypes need a small UI constitution, not a speculative design system or local UI convention layer.

## Decisions

- Added `docs/ui-constitution.md` as the bounded source for frontend lint, black-box, and experience checks.
- Removed the speculative local-rule bucket from the active design-lint list.
- Routed reliable code-detectable failures to lint candidates and behavior/product checks to `black-box-tester` or `experience-reviewer`.
- Made the Vercel-style promotion rule explicit: reliable failure plus concrete fix becomes a pending `GAP-###` candidate, not an automatic standard.

## Exceptions

- Coverage gaps added: none. The user approved adding guidance directly instead of recording this as a missing-standard gap.
- Things that went wrong: not applicable.
- Cannot verify: no live frontend app is in scope for this Gauntlet docs change.

## Not Relevant Because

- Release proof is not relevant because this is workflow documentation and skill guidance, not a production deployment.
