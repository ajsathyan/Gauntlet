# Production Quality Bar

The Production Quality Bar is a near-launch quality gate for systems that are launch-ready, in private beta, production-bound, or explicitly being hardened or audited. It should make uncertainty, state, cost, safety, and proof first-class without turning every ordinary Patch into release ceremony.

At its core, the gate asks whether the launch path has clear boundaries, explicit invariants, automated proof, durable state where needed, visible state machines, an operator/user feedback loop, threat and redaction clarity, and UI that helps users decide what to do.

## When To Use

Run a bounded pass for:

- near-launch, launch-ready, private beta, production-bound, or deploy-sensitive work
- explicit harden, audit, security review, reliability review, or productionize requests
- Release work that touches auth, billing, payments, uploads, migrations, public APIs, private data, concurrency, durable workflows, or external services
- features where a regression could materially affect users, money, data, safety, trust, or support recovery

Skip the pass for ordinary Patch work, early prototype work, local demo code, copy/config/docs-only tweaks, narrow visual polish, UI-only Feature work with no launch intent, and speculative refactors unless the user asks.

## Guardrails

| Guardrail | What To Check | Kind |
| --- | --- | --- |
| Control plane boundaries | The control plane or core workflow has clear ownership boundaries such as state store, external clients, observers, planners, executors, alerting, read models, UI surfaces, and policy config. | Human judgment |
| Explicit invariants | The code, tests, or docs name invariants: when resources are consumed, legal state transitions, destructive action rules, forbidden logs/user outputs, and module guarantees. | Guardrail |
| Launch-critical proof | CI or local release proof names the launch invariant and observable oracle, covers syntax/type checks, meaningful tests and lint where useful, and includes a state-inspecting no-mutation or dry-run check for the main workflow. | Automatable |
| Automated release evidence | Production releases should have automated GitHub release tags or an audited release script, plus execution-backed proof that required checks, generated artifact hashes/content, release notes, and the shipped version agree. | Automatable |
| Durable state | Review whether in-process locks or ad hoc JSON writes should become file locks, SQLite, idempotency keys, leases, atomic transitions, append-only logs, or recovery sweeps. | Human judgment |
| State machines | Provisioning, payment, upload, migration, job execution, auth, live-ops notification, and recovery flows expose state machines, terminal states, impossible transitions, and destructive action boundaries in code, tests, or docs. | Guardrail |
| Operator/user feedback loop | Track action outcomes, false positives, retries, costs, alert usefulness, alerting/email expectations, completion, support recovery, and learning signals so operators or users know what to believe next. | Human judgment |
| Threat model and redaction | Define threat model, secret/data classes, trust boundaries, external services, CI/runtime risks, redaction guarantees, and incident/debugging posture. | Guardrail |
| Rollback and restart | Production-bound automation names rollback/restart expectations, recovery commands, idempotency assumptions, and the proof that interrupted or repeated runs do not perform unsafe duplicate work. | Guardrail |
| Decision-oriented UI | Launch-ready UI shows confidence, freshness, sample size, blockers, next action, why the system is not acting, and evidence behind recommendations. | Human judgment |

## Proof Routing

Automatable checks belong in CI, local scripts, tests, linters, browser checks, dry-run commands, no-mutation proofs, release-tag automation, and artifact verification.

Apply `docs/meaningful-proof.md` to every launch claim. A dry run must assert relevant before/after state, and restart, rollback, repeated-run, or duplicate-action claims need a representative failure or negative-control scenario when feasible. Field presence, release-note text, a receipt, or a self-reported pass is not launch proof.

Human judgment belongs in product architecture, planning, deep review, adversarial review, experience review, issue triage, and launch cut-line decisions. If the standard is missing or cannot be verified, capture `Cannot verify` or a pending `GAP-###`; do not silently invent a rule.

## Role Routing

- `planner`: decide whether the Production Quality Bar is triggered, cap it, name deferrals, and attach release proof.
- `product-architect`: define trust, feedback loops, and decision-oriented UI only when launch scope makes them relevant.
- `deep-code-reviewer`: inspect ownership boundaries, invariants, durable state, state machines, and release proof.
- `adversarial-reviewer`: inspect threat model, redaction, trust boundaries, destructive actions, retries, rollback, and recovery.
- `black-box-tester`: prove observable outcomes, dry-run/no-mutation behavior, persisted state, logs, release artifacts, and user-visible recovery.
- `experience-reviewer`: validate confidence, freshness, sample size, blockers, evidence, completion, and next action in launch-ready UI.
- `issue-triager`: classify launch findings as `Ship blocker`, `Conditional blocker`, `Manual fallback`, `Private beta gate`, `Defer`, `Reject`, or `Ready`.
- `run-log-builder`: record only material assumptions, decisions, skipped proof, `Cannot verify`, launch cut lines, release proof, and gap candidates.
