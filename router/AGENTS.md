<!-- BEGIN GAUNTLET MANAGED BLOCK -->
# Gauntlet

Use the lightest workflow that responsibly completes the request.

## Route

- **Normal:** bounded, reversible, directly checkable work. Implement, check, and
  continue through the accepted Git lifecycle without a Design gate.
- **Research:** inspect and report only. Do not add implementation ceremony.
- **Material:** behavior, authority, architecture, durable contracts, release, or
  consequential effects require Design before implementation.

Keep routing internal unless it changes scope, authority, risk, cost, or proof.
Preserve unrelated work and explicit user limits.

## Design

A complete user task may serve as Design. Otherwise create one concise Design
with an exact `Acceptance` section. Before non-trivial implementation, the main
agent reviews the final contract through Product, Engineering, Design, Analytics,
QA, and Performance lenses. Show every material recommendation before acting; a
lens may be not applicable only with a reason.

Present Acceptance in delivery phases, not extra approval gates. Require its
acceptance once and reuse that authority unless scope or consequences materially
change. It authorizes scoped implementation, verification, commit, push, pull
request, merge, ordinary declared deployment, and monitoring. Stop for an
unaccepted destructive, credential, migration, privacy, security, data-loss, or
production effect.

## Build and Verify

Before coding, write down credible failure modes and intended observable proof,
or briefly state why none are material. Invoke `test-design` when tests are
planned, written, changed, reviewed, or audited, or when the proof boundary is
unclear. It does not require a new test for every edit.

Invoke `orchestrate` for implementation and respect explicit delegation limits.
Commit one coherent candidate before independent Verify. Verify each accepted
outcome against observable evidence from the exact commit, tree, and checked base:
a known failure is `Failed`; missing required proof is `Blocked`; complete
applicable proof is `Passed`. Continue available target-specific checks despite
an unrelated blocked check. Report Architecture separately. Instructions,
documents, and green commands are not authenticated behavioral proof.

## Land and Ship

After Verify passes, use `land` without another routine prompt. Land uses native
`git` and `gh`, resolves writable head and PR base separately, preserves the
established PR format, refuses ambiguity or drift, waits only for required checks
and blocking reviews, directly merges with expected-head matching, verifies the
landed revision, and cleans up only represented work.

Then use `ship` to observe declared deployments already triggered by the merge
and their attributable monitoring. Never dispatch or rerun deployment or generic
CI workflows, require generic CI, or create synthetic monitoring. Keep
implemented, committed, pushed, merged, deployed, and production-proved claims
separate. Missing attributable proof is `Cannot verify`.
<!-- END GAUNTLET MANAGED BLOCK -->
