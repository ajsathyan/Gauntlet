---
name: refactor-codebase
description: Use for a comprehensive, behavior-preserving rebuild or major simplification of an existing codebase, especially when the request includes an independent fork, shared architecture, declarative extension points, parity across routes or fixtures, large LOC reduction, faster tests or runtime, and black-box or visual proof. Do not use for a narrow local cleanup, a single bug fix, or performance-only work.
---

# Refactor Codebase

Rebuild accidental complexity while preserving the product. Treat behavior, compatibility, correctness, and accessibility as the floor; pursue step-change simplification and performance above it.

## Keep The Source Immutable

Create an independent local repository from the approved source snapshot. Give it its own Git directory, index, configuration, hooks, and working tree. Treat the source as read-only; run installs, generators, formatters, tests, and implementation only in the destination or a disposable clone. Create a hosted fork only with explicit authority.

Preserve every evidenced user-observable capability. Broken implementation does not make a capability removable. Remove only implementation artifacts with no distinct observable contract, or copies superseded by proved shared behavior. Preserve ambiguous capabilities and surface any material unresolved decision.

Use this priority order when goals conflict:

1. Behavioral and data compatibility
2. Export and saved-workflow compatibility
3. Correctness, accessibility, security, and privacy
4. Shared architecture and removal of accidental complexity
5. Deterministic test quality
6. LOC, test-time, and runtime targets

Keep user-supplied quantitative targets as acceptance criteria. Do not lower them silently. Never reach a target by weakening coverage, compressing readable code, moving logic outside measurement, hiding it in generated/configuration artifacts, or outsourcing essential behavior to a new dependency.

## Persist The Run

Choose a tracked or explicitly approved private work area in the destination repository. Store `refactor-state.json` there as the state index; never store run artifacts in the source. Treat `source-snapshot.json` as sensitive by default and keep it private unless a human has reviewed and approved it for tracking; its path and symlink tokens avoid raw local metadata but may still disclose information through hashes and repository state. Record the current phase, source and artifact hashes, gate results, open mismatches, temporary scaffolding, and invalidation status.

Each phase writes concise filesystem evidence before advancing. Prefer JSON or TSV for inventories and measurements, Markdown for decisions, and links rather than duplicated prose. Another agent must be able to resume from the repository without chat history.

Use these canonical artifact names exactly: `refactor-state.json`, `source-snapshot.json`, `baseline.json`, `capability-map.md`, `parity-ledger.json`, `compatibility-matrix.tsv`, `breakthrough-search.md`, `architecture-decision.md`, `prototype-results.json`, `migration-strategy.md`, `migration-register.tsv`, `temporary-scaffolding.tsv`, `performance-results.json`, and `final-verification.md`. Index additional raw evidence from `refactor-state.json` instead of substituting another format for a canonical artifact.

Keep the state index compact and machine-readable. Include:

- approved source snapshot identifier and integrity status;
- current and last-passed phase;
- product job and inventory version;
- artifact paths, hashes, and measurement protocol versions;
- selected breakthrough hypothesis, contract version, and migration strategy;
- gate results, open mismatches, blocked decisions, and `Cannot verify` items;
- temporary scaffolding and its next review point;
- invalidated phases and the evidence that invalidated them.

Use only these phase states: `source_baselined`, `inventory_frozen`, `breakthrough_selected`, `architecture_proven`, `strategy_selected`, `migration_complete`, and `verification_complete`. Never advance state from prose compliance alone; link observable artifacts and proof.

Before every phase:

1. Read `refactor-state.json` and the phase's required artifacts.
2. Verify their hashes and preceding gate.
3. Check invalidation conditions.
4. Reopen the earliest invalid phase when an assumption changed.

Apply these gates regardless of migration strategy:

- Do not design the target architecture before freezing capability evidence.
- Do not scale migration beyond prototypes before diverse slices pass.
- Do not delete a superseded path before its parity rows and consumers pass.
- Do not claim completion while a material inventory area, mismatch, or target remains unresolved.

## Keep Ambition Falsifiable

Let the migration strategy control coexistence and risk, not the radicalness of the destination. An incremental migration may still end in a fundamentally smaller architecture.

Treat large gains as hypotheses to prove. Search for structural compression before accepting routine cleanup, but increase scrutiny when results appear extraordinary. Measure essential complexity that moved into configuration, generated code, dependencies, fixtures, or migration scaffolding.

## Run The Phase Chain

Load only the current phase reference and any selected strategy reference.

1. **Protect and baseline.** Read [source-and-baseline.md](references/source-and-baseline.md). Freeze the approved snapshot, prove isolation, and record comparable size, dependency, test, and product-performance baselines. Use the bundled integrity and LOC helpers. Invoke `$refactor-performance` for its measurement contract; do not recreate its profiling procedure here.
2. **Map capabilities and parity.** Read [capability-and-parity.md](references/capability-and-parity.md). Invoke `$craft-product-terminology` in `capability-map` mode. Freeze the product job, capability map, parity ledger, and compatibility matrix. Validate the ledger with the bundled helper before advancing.
3. **Search for a breakthrough.** Read [breakthrough-search.md](references/breakthrough-search.md). Give three independent agents the same frozen evidence packet and output contract without a favored architecture or one another's conclusions. Compare mechanisms and retain the strongest credible step-change hypotheses.
4. **Prove architecture.** Read [architecture-proof.md](references/architecture-proof.md). Prototype the leading hypothesis against common, most-complex, and structural-outlier slices. Freeze shared contracts only after all three pass.
5. **Select one migration strategy.** Choose from the evidence, then read exactly one of [strategy-mechanical.md](references/strategy-mechanical.md), [strategy-incremental.md](references/strategy-incremental.md), or [strategy-dual-run.md](references/strategy-dual-run.md). Record why its preconditions hold.
6. **Migrate and retire.** Read [migration-execution.md](references/migration-execution.md). Move bounded capabilities through parity gates. Delete replaced code only after its ledger rows pass and no supported consumer remains.
7. **Verify completion.** Read [verification-and-completion.md](references/verification-and-completion.md). Invoke `$refactor-performance` for the optimization and comparison pass. Preserve an explicitly requested verification surface; otherwise use the built-in Browser for web workflows and Computer Use for native, OS-level, cross-app, or browser-inaccessible workflows. Finish only from complete external evidence.

## Enforce Shared Architecture

An invariant is a rule or guarantee that must remain true across contexts. Give each genuinely shared invariant one authoritative owner at the narrowest common layer. Consolidate duties only when they share semantics, data ownership, lifecycle, and reasons to change. Similar-looking behavior with different guarantees remains separate or uses a narrow adapter.

Make a standard capability primarily declarative when the domain supports it. Keep irreducible variation in narrow renderer, adapter, or transformation boundaries. Reject manifests that accumulate hidden control flow, lifecycle policy, or a harder-to-understand programming language.

Track every migration-only adapter, bridge, dual implementation, or tool with an owner, reason, comparison method, deletion condition, and review point. Count temporary scaffolding in complexity and LOC reports until deleted.

## Control Delegation

Keep product interpretation, shared-contract design, ledger adjudication, integration, deletion decisions, and completion claims in the root task. After contracts pass the diverse-slice gate, delegate only disjoint subsystems with explicit ownership and separate proof.

Use `fork_turns: "none"` only for a bounded agent whose complete context exists in durable artifacts and whose task packet identifies every required input. The agent receives no parent conversation, so keep any task with an unstored product decision, unresolved contract, shared integration state, deletion authority, or completion judgment in the root task. Give validation agents the frozen observable contract and artifacts without implementer reasoning. Use no-history packets for compatibility, architecture/metric, or black-box review only after their observable contracts are frozen. Treat reviewer convergence as evidence, not proof.

Use the stable packet templates in [breakthrough-agent-packet.md](assets/breakthrough-agent-packet.md) and [observable-review-agent-packet.md](assets/observable-review-agent-packet.md). Freeze the complete packet first and index its SHA-256 from `refactor-state.json`. Render it with [render_agent_prompt.py](scripts/render_agent_prompt.py), passing that indexed value through `--expected-packet-sha256`; the renderer rejects incomplete packet schemas, unknown assignment fields, stale packet or artifact hashes, and paths outside the approved Git root. It preserves the complete template as the exact prompt prefix and appends canonical variable assignment JSON only at the end. Prefer artifact paths and hashes over copied evidence. Index the renderer's metadata receipt from `refactor-state.json`. Reuse one rendered breakthrough prompt unchanged for all three proposal agents.

Require delegated lanes to return only the template's compact machine receipt with owned scope, evidence paths, proof result, mismatches, and blocker. Reject malformed receipts before integration. Keep breakthrough proposals separate through the independent round, then let the root task synthesize them.

When the host exposes usage data, keep an indexed raw `efficiency-receipt.json` with packet template version/hash, fork context mode, delegated agent count, Browser and Computer Use action/retry counts, and total/cached input tokens. Mark unavailable fields `Cannot verify`; never estimate them. This receipt measures workflow efficiency and cannot substitute for parity or completion proof.

## Stop And Return Evidence

Stop for a material product decision, ambiguous data-loss or compatibility risk, missing authority, or a target that cannot be met without violating a higher-priority constraint. Report the exact conflict, measurements, attempted hypotheses, and smallest needed decision.

Complete only when the source-integrity proof passes, every inventory area is resolved, every retained ledger row and compatibility case has evidence, quantitative comparisons use valid baselines, temporary scaffolding is retired or explicitly accepted, and external verification passes. Return links to the state index, parity ledger, compatibility matrix, architecture decision, measurements, and final verification; state residual risks and `Cannot verify` items.

If work stops before completion, return the last passed phase, invalid or blocked gate, exact artifact paths, and smallest next action. Do not reconstruct or summarize evidence that already exists in the destination.
