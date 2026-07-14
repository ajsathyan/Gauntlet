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

1. If `work_class = verification` and `proof = security`, select `gauntlet_security_reviewer`. Security-sensitive implementation or release work gets its normal writer or release profile plus a separate security-verification Ticket in the same Cohort Verification group.
2. If `work_class = release` or `proof = release`, select `gauntlet_release_integrator`. It prepares and verifies the release; the parent retains integration and release authority.
3. If `work_class = verification` or `proof = behavioral`, select `gauntlet_independent_verifier`. The verifier must not verify work it authored.
4. If `work_class = research`, select `gauntlet_deep_expert_researcher` only when `complexity = deep` or `risk = consequential`; otherwise keep bounded research in the parent task or use the normal Gauntlet research path.
5. If `work_class = scan`, `authority = read-only`, and either `proof = source` or `context_shape = high-volume`, select `gauntlet_fast_reader`.
6. If `work_class = implementation` and `complexity = deep`, select `gauntlet_deep_worker`. Classify cross-cutting, concurrency-sensitive, architecturally ambiguous, or materially failed prior work as `complexity = deep` before running the classifier.
7. If `work_class = implementation`, `authority = local-write`, and `complexity` is `routine` or `standard`, select `gauntlet_standard_worker`.
8. Otherwise, do not delegate. The parent resolves the inconsistent or incomplete routing fields.

`risk = consequential` does not by itself select a writer. It strengthens review and proof requirements. `context_shape = high-volume` favors the fast reader only for read-only source work; it does not override security, release, verification, or deep-work rules.

## Escalation and context

- Escalate `gauntlet_fast_reader` to `gauntlet_standard_worker` when the task changes from extraction to bounded implementation judgment.
- Escalate `gauntlet_standard_worker` to `gauntlet_deep_worker` after a meaningful failed attempt, failed proof, or discovery of a cross-cutting contract. Do not retry the same failure fingerprint.
- Route newly discovered security-sensitive surfaces to `gauntlet_security_reviewer` for independent read-only review.
- Keep tightly coupled work in the parent task when delegation would duplicate context or weaken proof.

Send a child only its compact Ticket, relevant shared contracts, named dependency outputs, and owned sources. A release bundle contains the accepted release contract, target revision, changed-surface summary, relevant proof, unresolved exceptions, rollout and rollback steps, and current state needed for the decision. Do not send the full task conversation, complete Execution Run event stream, unrelated receipts, or other child histories.

The Ticket or Execution Run records the classifier's requested profile. Codex native state records the profile actually started, its effective sandbox, and its approval mode; `scripts/subagent-audit.py` exports those actual values into the local Gauntlet audit. Reconcile the two after start when the run has durable dispatch state. A mismatch or unavailable named profile is a routing failure; do not silently substitute another profile. For `gauntlet_security_reviewer`, also require the effective sandbox to be read-only. The profile default and prose constraint are not a security boundary because a parent's live runtime override can supersede them.
