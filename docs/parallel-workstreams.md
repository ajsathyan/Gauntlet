# Parallel Workstreams

Use parallel work only when independent ownership or evidence makes it faster or more trustworthy than one lane.

## Assignment

Each child receives one compact packet:

1. requested outcome slice;
2. owned files or state;
3. dependency and consumes/produces contracts;
4. constraints and authority;
5. proportional proof;
6. return contract and ask-parent policy.

Keep stable instructions first and volatile values last. Omit empty fields, unrelated history, and duplicate contract text.

## Ownership

The parent keeps requested product meaning, shared contracts, integration,
publication, merge, release, and rollback. Children do not co-own mutable state
or weaken the outcome oracle.

## Integration

Integrate coherent atomic changes as they arrive. Serialize candidates that share a base. A queue candidate must contain both its claimed default head and the queued source commit; a base-only or unrelated revision is not a candidate. Binding records the candidate commit and its exact tree.

Reject stale proof after base drift. A merge release or interrupted reconciliation succeeds only when the current default head matches the exact bound candidate tree proof. The bound commit itself and a non-descendant tree-equivalent integration commit are valid. Any later descendant, even an empty commit with the same tree, is stale and needs a fresh candidate binding and proof. Run focused integration checks, then send that exact candidate to independent Verify.

Native task state is sufficient for live coordination. Custom profiles are optional and selected directly when they clearly improve a bounded lane.
