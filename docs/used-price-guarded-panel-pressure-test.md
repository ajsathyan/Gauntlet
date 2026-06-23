# Used Price Guarded Panel Pressure Test

Date: 2026-06-19

## Prompt

Prepare Used Price for a private-beta paid launch where credits, Stripe webhook handling, Supabase-backed account/session data, support inbox, observability, and rollback evidence must be production-safe enough for a limited external beta.

## Runs

Three read-only throwaway planner runs were generated against `/Users/ajsathyan/Documents/CC/used-price`:

- Legacy/current guarded-panel style Release plan.
- Upgraded guarded-panel Release plan, run 1.
- Upgraded guarded-panel Release plan, run 2, using the same prompt and compact decision-table contract as run 1.

## Comparison

| Check | Legacy/current run | Upgraded run 1 | Upgraded run 2 | Result |
| --- | --- | --- | --- | --- |
| Blocker count | 8 blockers, including env, observability, OpenRouter cap, and legal signoff as flat blockers. | 4 ship blockers, 2 conditional blockers, 2 private-beta gates, 1 defer, 1 reject row. | 5 ship blockers, 2 private-beta gates, 2 conditional blockers, 1 reject, 1 defer row. | Upgraded output reduces blocker inflation by forcing decision classes instead of one flat blocker list. |
| Proof specificity | Mostly executable commands, but grouped under generic blocker rows. | Proof includes replay, RLS, staging smoke, rollback drill, env/private-beta fallback, and rejection scans per row. | Proof adds concrete order: Supabase migration/RLS, Stripe replay, quote/dispute, support smoke, rollback drill. | Upgraded output keeps proof attached to decision and fallback rationale. |
| Dependency order | Env sanity first, then Supabase, Stripe, support/observability, rollback/legal. | Supabase proof before live Stripe keys; Stripe replay first external paid proof; rollback before invites. | Supabase before Stripe; env proof before external smoke; implementation starts only for failed proof. | Upgraded outputs converge on evidence-first order with clearer stop conditions. |
| Deferrals and rejections | Defers public launch, growth, dashboards, support status UI; rejects unsafe money/data shortcuts. | Explicitly defers public launch/rich tooling and rejects client grants, runtime schema/file store, raw PII evidence, webhook-off rollback. | Explicitly rejects public-launch-or-nothing for capped beta and unsafe money/data fallbacks. | Upgraded output makes deferral/rejection part of the launch cut line instead of prose. |
| First ready task | Run private-beta launch evidence pass without code changes. | Run private-beta evidence pack in staging. | Run private-beta staging evidence pass, stop at first failed proof. | All runs agree; upgraded plans make the stop condition crisper. |
| Panel delta | Says role lenses helped reclassify risk. | Names concrete deltas: Stripe/Supabase first, Upstash downgraded to private-beta gate, rollback moved up, public launch below cut. | Names concrete deltas: public-scale items downgraded, money/data/security/rollback stay blockers, public-launch-or-nothing rejected. | Upgraded output better satisfies the anti-theater test. |

## Concrete Improvements

- `Upstash` moved from a flat launch blocker into a `Private beta gate` with cap, owner, sunset, and public-launch block. That is a better tradeoff for a limited beta.
- `Rollback evidence` became a `Ship blocker` because rollback is the recovery path and cannot itself be unproven when money has been collected.
- `Public paid launch readiness` was explicitly `Defer` or `Reject` for this private-beta scope, preventing scope creep.
- Unsafe fallbacks such as client-side credit grants, runtime schema/file-store production fallback, raw PII evidence, and disabling webhooks during rollback were explicitly `Reject`.
- The upgraded runs varied in classification of support/observability/legal, but the variation stayed inside the decision vocabulary rather than expanding into a broad wishlist.

## Remaining Weaknesses

- The upgraded runs still produce 10-11 table rows. For very large releases, the orchestrator should group rows by release capability before finalizing.
- Support path classification varied between `Ship blocker` and `Conditional blocker`. The engineering lead must decide based on whether a manual audited fallback truly exists for the beta.
- The pressure test used generated planning outputs, not a full implementation run. It proves better plan shape and stronger proof contracts, not launch readiness.

## TypeScript Durability Classifier Pressure

The classifier was run against Used Price and the pre-existing Used Price `.gauntlet-ts-durability.json` artifact was restored afterward.

| Case | Input | Result | Why |
| --- | --- | --- | --- |
| UI-only | `scripts/classify-ts-durability.sh /Users/ajsathyan/Documents/CC/used-price src/components/UsedPriceApp.tsx` | `durabilityRequired: false` | UI-only changed files suppress existing durable pattern triggers when no durable surface is touched. |
| Auth/backend | `scripts/classify-ts-durability.sh /Users/ajsathyan/Documents/CC/used-price src/lib/session.ts` | `durabilityRequired: true` | The changed path matches the `auth` trigger and the repo has existing durable patterns via `zod`. |

This supports the intended gate behavior: lightweight UI stays light, while auth/session work activates durability standards for concrete reasons.
