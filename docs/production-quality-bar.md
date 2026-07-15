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

Human judgment is triggered by concrete consequence. Do not summon a broad role panel for ordinary work. If the standard is missing or cannot be verified, capture `Cannot verify` or a pending `GAP-###`; do not silently invent a rule.

## Consequence-Triggered Review Funnel

Use direct parent verification for ordinary work. Trigger three independent review agents only for billing or paid actions, credentials/auth/permissions, migrations or data loss, production authority, destructive actions, or equivalent material harm. Run cheap deterministic checks before model review so reviewers do not spend turns on mechanical failures.

The three charters are fixed and non-overlapping:

1. `adversarial-reviewer`: trust boundaries, security, credentials, permissions, paid/destructive authority, and redaction.
2. `deep-code-reviewer`: failure paths, concurrency, idempotency, durable state, rollback, and recovery.
3. `black-box-tester`: observable behavior, dry-run/no-mutation proof, persisted state, required non-effects, and operator recovery.

Run them in parallel on the same exact integrated revision. Deduplicate findings by shared fix, apply one fix pass, rerun deterministic checks, and rerun only a lens whose reviewed boundary changed or whose finding needs confirmation. Then execute the repository-owned dry run and any meaningful bounded canary, reconciliation, and rollback. A dry run alone does not prove live provider permissions, races, money movement, or migration effects.
