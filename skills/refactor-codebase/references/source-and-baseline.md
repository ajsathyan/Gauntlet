# Source And Baseline

## Inputs

- Source repository, requested destination, and user-supplied targets
- Current Git, submodule, LFS, ignored-file, and working-tree state
- Existing build, test, benchmark, and product-run instructions

## Actions

1. Decide what “exactly as it exists” means. If staged, unstaged, untracked, ignored-but-required, modified-submodule, or unavailable LFS state would be omitted by a clone, inventory it and obtain the one material choice: committed `HEAD` or current filesystem.
2. Record the approved commit, branch, remotes, status, tracked-file hashes, submodule commits, LFS pointers, and relevant local-state manifest in `source-snapshot.json`.
3. Create an independent local repository at the destination and verify that its Git directory, index, config, hooks, and working tree are not shared with the source. Do not create or push a hosted fork without explicit authority.
4. Run potentially mutating baseline commands in a disposable clone of the approved snapshot.
5. Measure production/test logical LOC with declared inclusions and exclusions. Report generated, vendored, minified, fixture-data, snapshot, and build output separately.
6. Invoke `$refactor-performance` to define reproducible test-feedback and product-performance baselines. Preserve its commands, environment, dependency state, cache policy, concurrency, warm-up, run count, and statistic in `baseline.json`.
7. Record dependency count, major code concentration, duplication or change-amplification signals, and observable start commands without interpreting product parity yet.

## Gate

Pass when the source snapshot is unambiguous, the destination is independently mutable, source hashes still match, and every requested quantitative target has a comparable baseline or an explicit `Cannot verify` reason.

## Receipt

Write `source-snapshot.json` and `baseline.json`. Update `refactor-state.json` with their paths, hashes, protocol versions, gate result, and open baseline limits.

## Invalidation

Restart this phase when source content or dependencies change, local state is redefined, the destination shares mutable repository state, or a measurement protocol changes. Discard measurements that are no longer comparable.
