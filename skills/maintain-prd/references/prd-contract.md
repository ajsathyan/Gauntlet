# Product PRD And Epic Launch Contract

Use one H1 for the PRD and one `## Epic <stable-id>: <title>` section per Epic. The document header contains `Document status` and `Implementation target`. The target lists every accepted Epic the user wants to start in one launch; the implementation controller creates one visible task and one Execution Run for each listed Epic.

Directly below each Epic heading, use the exact machine-readable line `Epic status: Proposed`, `Epic status: Accepted`, or `Epic status: Deferred`. The execution controller requires `Epic status: Accepted` for every Epic named by `Implementation target`.

Each target Epic also declares these exact machine-readable fields:

- `Depends on: None` or a comma-separated list such as `PAY-001@merged, DATA-002@deployed`;
- `Build ready: yes`;
- `Ships independently: yes`;
- `Rolls back independently: yes`;
- `Release stages: merge` or `merge,deployment,production-verification`.
- `High-consequence triggers: none` or a comma-separated subset of `billing-paid-actions`, `credentials-auth-permissions`, `migrations-data-loss`, `production-authority`, and `destructive-actions`.

Dependencies may cross target Epics, but they must name the required upstream boundary: `merged`, `deployed`, or `productionProved`. An Epic that cannot ship and roll back independently is not a launchable Epic yet; reshape the boundary instead of placing several Epics in one Execution Run.

Within each Epic, use the following H3 headings when applicable. Omit a truly irrelevant heading only when omission cannot hide a decision.

1. Repeat `Scope Area <ID>: <Responsibility>` for each stable product responsibility, for example `Scope Area PAY-001-S01: Stored balance`.
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
- `Build ready`, `Ships independently`, and `Rolls back independently` are all `yes`, with explicit release stages and dependency boundaries.
- the closed high-consequence trigger declaration matches the accepted scope; omission is not equivalent to `none`.

Do not call a target build-ready merely because every heading contains text.
