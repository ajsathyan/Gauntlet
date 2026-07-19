# Parallel Workstreams

Use parallel work only when independent ownership or evidence makes it faster or more trustworthy than one lane.

## Assignment

Each child receives one compact packet:

1. accepted outcome slice;
2. owned files or state;
3. dependency and consumes/produces contracts;
4. constraints and authority;
5. proportional proof;
6. return contract and ask-parent policy.

Keep stable instructions first and volatile values last. Omit empty fields, unrelated history, and duplicate contract text.

## Ownership

The parent keeps product decisions, shared contracts, integration, publication, merge, release, and rollback. Children do not co-own mutable state or weaken the acceptance oracle.

## Integration

Integrate coherent atomic changes as they arrive. Serialize candidates that share a base. Reject stale proof after base drift. Run focused integration checks, then send the exact candidate to independent Verify.

Native task state is sufficient for live coordination. Custom profiles are optional and selected directly when they clearly improve a bounded lane.
