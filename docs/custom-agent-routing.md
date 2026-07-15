# Codex Custom-Agent Routing

Gauntlet selects a custom-agent profile from explicit Ticket fields. Selection is implemented by `scripts/route-codex-agent.py`; it does not call an LLM router. The parent runs that classifier, records its result, and passes it as `agent_name` in the native `spawn_agent` call. It must receive a child ID before waiting or proceeding. The parent remains responsible for ticket compilation, integration, the acceptance oracle, and every merge, release, deployment, production, or rollback decision.

## Ticket routing fields

Each delegated Ticket records these routing inputs:

- `work_class`: `scan`, `implementation`, `verification`, `research`, or `release`
- `complexity`: `routine`, `standard`, or `deep`
- `risk`: `ordinary` or `consequential`
- `authority`: `read-only`, `local-write`, `merge`, `deploy`, or `production`
- `proof`: `source`, `behavioral`, `integration`, `security`, or `release`
- `context_shape`: `bounded` or `high-volume`

These fields describe the assignment, not permission. A selected profile never gains authority that the parent and ticket do not already have.

## Pre-Dispatch Efficiency And Drift Check

Before classifying a delegated Ticket, ask:

- **Is this cache-hit friendly in every step?** Keep reusable instructions and shared contracts byte-stable; put Ticket-specific and volatile data last.
- **Are there ways to improve token efficiency?** Remove unrelated history, empty fields, duplicate contracts, and source the selected profile can discover cheaply from its owned files.
- **Is this being assigned to the right custom agent?** Recheck the routing fields against the actual work, then require the classifier result and started profile to match.
- **Is this Ticket structured to avoid response drift from its instructions?** Keep one objective, one ownership boundary, explicit dependencies, a checkable return contract, and an ask-parent policy. Split conflicting branches or keep the work in the parent.

If the first two answers expose a tightly coupled or context-heavy handoff, keep the work in the parent unless parallelism or independent evidence still beats that cost. If the third answer changes after dispatch, stop and reclassify instead of silently substituting a profile.

## Ordered selection rules

Apply the first matching rule:

1. If `work_class = verification` and `proof = security`, select `gauntlet_security_reviewer`. Create this separate read-only review only when a consequential trust, credential, permission, paid/destructive authority, migration, or production boundary triggers it; ordinary implementation uses direct parent verification.
2. If `work_class = release` or `proof = release`, select `gauntlet_release_integrator`. It prepares and verifies the release; the parent retains integration and release authority.
3. If `work_class = verification` or `proof = behavioral`, select `gauntlet_independent_verifier`. The verifier must not verify work it authored.
4. If `work_class = research`, select `gauntlet_deep_expert_researcher` only when `complexity = deep` or `risk = consequential`; otherwise keep bounded research in the parent task or use the normal Gauntlet research path.
5. If `work_class = scan`, `authority = read-only`, and either `proof = source` or `context_shape = high-volume`, select `gauntlet_fast_reader`.
6. If `work_class = implementation` and `complexity = deep`, select `gauntlet_deep_worker`. Classify cross-cutting, concurrency-sensitive, architecturally ambiguous, or materially failed prior work as `complexity = deep` before running the classifier.
7. If `work_class = implementation`, `authority = local-write`, and `complexity` is `routine` or `standard`, select `gauntlet_standard_worker`.
8. Otherwise, do not delegate. The parent resolves the inconsistent or incomplete routing fields.

`risk = consequential` does not by itself select a writer. When a concrete high-consequence boundary is present, route three distinct parallel verification charters—security/authority, failure/recovery, and black-box non-effects—after deterministic checks pass. `context_shape = high-volume` favors the fast reader only for read-only source work.

## Escalation and context

- Escalate `gauntlet_fast_reader` to `gauntlet_standard_worker` when the task changes from extraction to bounded implementation judgment.
- Escalate `gauntlet_standard_worker` to `gauntlet_deep_worker` after a meaningful failed attempt, failed proof, or discovery of a cross-cutting contract. Do not retry the same failure fingerprint.
- Route newly discovered security-sensitive surfaces to `gauntlet_security_reviewer` for independent read-only review.
- Keep tightly coupled work in the parent task when delegation would duplicate context or weaken proof.

Send a child only its compact Ticket, relevant shared contracts, named dependency outputs, and owned sources. A release bundle contains the accepted release contract, target revision, changed-surface summary, relevant proof, unresolved exceptions, rollout and rollback steps, and current state needed for the decision. Do not send the full task conversation, complete Execution Run event stream, unrelated receipts, or other child histories.

The Ticket or Execution Run records the classifier's requested profile. Codex native state records the profile actually started, model, reasoning effort, effective sandbox, and Codex version. Queue this local reconciliation as soon as start metadata is observable; do not await it in the healthy dispatch critical section:

```sh
python3 scripts/subagent-audit.py reconcile \
  --agent-home "$AGENT_HOME" \
  --agent-id "$CHILD_ID" \
  --requested-profile "$PROFILE" \
  --requested-risk "$RISK" \
  --json
```

Reconciliation classifies `profile_substitution`, `authority_substitution`, `model_substitution`, `reasoning_substitution`, `security_sandbox_violation`, and `missing_start_metadata`. Its circuit is scoped to the native Codex version and requested profile. The first mismatch opens that circuit for later affected dispatches; it does not stop an already-running ordinary child when the substituted profile has equivalent authority. Consequential substitutions, authority changes, missing required start metadata, and a non-read-only security reviewer return a fail-closed result. Never silently substitute another profile.

Operational router calls pass the same version and circuit path as part of the existing deterministic classification step:

```sh
python3 scripts/route-codex-agent.py \
  --circuit-file "$AGENT_HOME/gauntlet/state/routing-circuit.json" \
  --codex-version "$CODEX_VERSION" \
  <ticket routing fields> --json
```

An open circuit returns exit status `3` before a new spawn. A healthy route still requires exactly one native `spawn_agent` call and no model handshake. The router only reads compact circuit state; audit synchronization and rollout analytics stay outside the scheduling critical section.

## Privacy-bounded request analytics

Run `scripts/subagent-audit.py sync` after a child reaches terminal state and whenever local measurements should be refreshed. It writes three mode-`0600` local files under `$AGENT_HOME/gauntlet/logs/`:

- `subagents.jsonl` contains native start metadata; the `cwd` value is an opaque fingerprint and sandbox policy is reduced to its effective type.
- `subagent-model-requests.jsonl` contains one row per observed model request with input, cached-input, output, reasoning-output, and total token classes.
- `subagent-quarantine.jsonl` contains only agent ID, line number, and a reason code for incomplete or inconsistent native input.

The request parser derives each request from the difference between successive cumulative native counters. Repeated snapshots therefore do not add requests or tokens twice. Sync rebuilds current-child measurements deterministically and retains measurements for native records that have been pruned, so repeated sync is byte-idempotent. Unterminated JSON, malformed token records, counter regressions, and inconsistent deltas are quarantined without storing their contents. Prompts, transcripts, command output, rollout paths, and absolute private paths are never copied into these files.

The custom-agent installer binds the canonical security reviewer's `read-only` declaration and profile digest to a digest of the complete installed profile set. `verify` checks that versioned authority attestation. Runtime reconciliation separately checks the effective security sandbox for each Codex version because a live override can supersede the installed default.
