# Changelog

## Unreleased

- Fork Gauntlet Lite from Gauntlet with history preserved in Git for comparison, recovery, and selective upstream updates.
- Require exact Design/PRD `Acceptance` approval before non-trivial implementation, then carry the accepted scope through Implement → Verify → Land → Ship without a second production-acceptance pause.
- Keep adversarial product, engineering, and proof review with explicit coverage of state transitions, retries, idempotency, recovery, concurrency, and required non-effects.
- Keep direct tests, exact-revision Build and Architecture verdicts, pull-request creation, required-check waiting, merge, post-merge deployment, and attributable monitoring.
- Remove the sensor runtime and managed sensor toolchain, custom agent profiles and token-audit history, the durable workstream queue, duplicate skill snapshots, and obsolete documentation for those systems.
- Remove the `archive`, `build`, and `eval-*` skill packages while retaining one canonical copy of the focused product, implementation, review, verification, landing, shipping, research, debugging, and refactoring skills.
