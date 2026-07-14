# Multi-Epic PRD Contract

Use one H1 for the PRD and one `## Epic <stable-id>: <title>` section per Epic. The document header contains `Document status` and `Implementation target`. The target lists only accepted, build-ready Epic IDs.

Within each Epic, use the following H3 headings when applicable. Omit a truly irrelevant heading only when omission cannot hide a decision.

1. `Scope Areas`: stable IDs for product responsibilities, for example `PAY-001-S01`.
2. `Primary User`, `User Situation`, `User Job`, `First Value`.
3. `Objectives`, `Principles`, `Scope`, `Non-goals`.
4. `User Workflow`, `Information Architecture`, `Deterministic Rules`.
5. `States`, `Failures And Recovery`.
6. `Trust And User Hesitation`, `Privacy And Sensitive Data`, `Security Boundaries`, `Authority Model`.
7. `Configuration Requirements`.
8. `Product Acceptance`, `Design Acceptance`, `Engineering Acceptance`.
9. `Affected Interfaces`, `Test Expectations`, `Verification Strategy`.
10. `Dependencies`, `Assumptions`, `Open Questions`, `Cannot Verify`.
11. `Rollout Constraints`, `Rollback Constraints`.

## Build-Ready Gate

An Epic may enter `Implementation target` only when:

- objectives, scope, non-goals, and material product behavior are accepted;
- affected interfaces and dependencies are bounded;
- product, design, and engineering acceptance are observable;
- Test Expectations name a behavior claim or invariant, an observable oracle, a plausible wrong case, and required non-effects where proportionate;
- authority, privacy, security, configuration, rollout, and rollback questions that could change implementation are resolved or explicitly gated;
- every remaining `Open Question` or `Cannot Verify` item is non-blocking and has an owner or decision gate.

Do not call a target build-ready merely because every heading contains text.
