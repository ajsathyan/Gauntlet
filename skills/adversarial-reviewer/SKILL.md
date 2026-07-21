---
name: adversarial-reviewer
description: Use when non-trivial implementation requires the mandatory six-lens main-agent review before editing.
---

# Adversarial Reviewer

Review the exact proposed contract in one main-agent pass. Do not use subagents
unless the user explicitly requests them for independent proof. Keep each lens distinct until findings
are deduplicated.

## Lenses

- **Product:** intended outcome, users, states, edge cases, authority, and required non-effects.
- **Engineering:** boundaries, dependencies, ownership, compatibility, migrations,
  state transitions, retries, idempotency, recovery, and concurrency.
- **Design:** workflow clarity, interaction states, accessibility, content, and visual consistency.
- **Analytics:** measurement intent, instrumentation, attribution, metric integrity, privacy, and cost.
- **QA:** observable oracles, plausible wrong cases, regression surface, recovery,
  destructive effects, security, privacy, and false-green proof.
- **Performance:** latency, throughput, resource use, scale, retention limits, and explicit budgets.

A lens may return `Not applicable` only with a concrete reason. Do not invent
features, metrics, UI, scale targets, or compliance requirements outside the request.

## Findings

For each material finding return the lens, severity, evidence, affected outcome,
practical impact, recommendation, wrong-case check, and disposition:
`accepted`, `rejected`, `deferred`, `omitted`, or unresolved.

Show all material recommendations before implementation. The reviewer cannot accept its own recommendation or mutate the contract. After a material contract
edit, rerun affected lenses; rerun all six when the edit is cross-cutting.

Complete when every material finding has a terminal disposition and any remaining
`Cannot verify` limit is explicit.
