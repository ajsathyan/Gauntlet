# Codex Custom-Agent Routing

Gauntlet selects a custom-agent profile from explicit Ticket fields. Selection is implemented by `scripts/route-codex-agent.py`; it does not call an LLM router. The parent runs that classifier, records its result before dispatch, and remains responsible for ticket compilation, integration, the acceptance oracle, and every merge, release, deployment, production, or rollback decision.

## Ticket routing fields

Each delegated Ticket records these routing inputs:

- `work_class`: `scan`, `implementation`, `verification`, `research`, or `release`
- `complexity`: `routine`, `standard`, or `deep`
- `risk`: `ordinary` or `consequential`
- `authority`: `read-only`, `local-write`, `merge`, `deploy`, or `production`
- `proof`: `source`, `behavioral`, `integration`, `security`, or `release`
- `context_shape`: `bounded` or `high-volume`

These fields describe the assignment, not permission. A selected profile never gains authority that the parent and ticket do not already have.

## Ordered selection rules

Apply the first matching rule:

1. If `work_class = verification` and `proof = security`, select `gauntlet-security-reviewer`. Security-sensitive implementation or release work gets its normal writer or release profile plus a separate security-verification Ticket in the same Cohort Verification group.
2. If `work_class = release` or `proof = release`, select `gauntlet-release-integrator`. It prepares and verifies the release; the parent retains integration and release authority.
3. If `work_class = verification` or `proof = behavioral`, select `gauntlet-independent-verifier`. The verifier must not verify work it authored.
4. If `work_class = research`, select `gauntlet-deep-expert-researcher` only when `complexity = deep` or `risk = consequential`; otherwise keep bounded research in the parent task or use the normal Gauntlet research path.
5. If `work_class = scan`, `authority = read-only`, and either `proof = source` or `context_shape = high-volume`, select `gauntlet-fast-reader`.
6. If `work_class = implementation` and `complexity = deep`, select `gauntlet-deep-worker`. Classify cross-cutting, concurrency-sensitive, architecturally ambiguous, or materially failed prior work as `complexity = deep` before running the classifier.
7. If `work_class = implementation`, `authority = local-write`, and `complexity` is `routine` or `standard`, select `gauntlet-standard-worker`.
8. Otherwise, do not delegate. The parent resolves the inconsistent or incomplete routing fields.

`risk = consequential` does not by itself select a writer. It strengthens review and proof requirements. `context_shape = high-volume` favors the fast reader only for read-only source work; it does not override security, release, verification, or deep-work rules.

## Escalation and context

- Escalate `gauntlet-fast-reader` to `gauntlet-standard-worker` when the task changes from extraction to bounded implementation judgment.
- Escalate `gauntlet-standard-worker` to `gauntlet-deep-worker` after a meaningful failed attempt, failed proof, or discovery of a cross-cutting contract. Do not retry the same failure fingerprint.
- Route newly discovered security-sensitive surfaces to `gauntlet-security-reviewer` for independent read-only review.
- Keep tightly coupled work in the parent task when delegation would duplicate context or weaken proof.

Send a child only its compact Ticket, relevant shared contracts, named dependency outputs, and owned sources. A release bundle contains the accepted release contract, target revision, changed-surface summary, relevant proof, unresolved exceptions, rollout and rollback steps, and current state needed for the decision. Do not send the full task conversation, complete Execution Run event stream, unrelated receipts, or other child histories.

The Ticket or Execution Run records the classifier's requested profile. Codex native state records the profile actually started, its effective sandbox, and its approval mode; `scripts/subagent-audit.py` exports those actual values into the local Gauntlet audit. Reconcile the two after start when the run has durable dispatch state. A mismatch or unavailable named profile is a routing failure; do not silently substitute another profile. For `gauntlet-security-reviewer`, also require the effective sandbox to be read-only. The profile default and prose constraint are not a security boundary because a parent's live runtime override can supersede them.
