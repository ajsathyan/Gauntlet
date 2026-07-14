# Source And Baseline

## Inputs

- Source repository, requested destination, and user-supplied targets
- Current Git, submodule, LFS, ignored-file, and working-tree state
- Existing build, test, benchmark, and product-run instructions

## Actions

1. Decide what “exactly as it exists” means. If staged, unstaged, untracked, ignored-but-required, modified-submodule, or unavailable LFS state would be omitted by a clone, inventory it and obtain the one material choice: committed `HEAD` or current filesystem.
2. Run [source_integrity.py](../scripts/source_integrity.py) in `snapshot` mode with output outside the source. Supplement its read-only snapshot with approved remotes and any relevant ignored-file or LFS interpretation it cannot infer.
3. Create an independent local repository at the destination and verify that its Git directory, index, config, hooks, and working tree are not shared with the source. Do not create or push a hosted fork without explicit authority.
4. Run potentially mutating baseline commands in a disposable clone of the approved snapshot.
5. Run [measure_loc.py](../scripts/measure_loc.py) against the approved snapshot. Use its physical nonblank LOC as the canonical source measure, preserve its emitted rules hash, and report production/test, generated, configuration, fixture, and migration categories separately. Record any additional exclusions such as vendored or minified inputs.
6. Invoke `$refactor-performance` to define reproducible test-feedback and product-performance baselines. Preserve its commands, environment, dependency state, cache policy, concurrency, warm-up, run count, and statistic in `baseline.json`.
7. Record dependency count, major code concentration, duplication or change-amplification signals, and observable start commands without interpreting product parity yet.

## Gate

Pass when the source snapshot is unambiguous, the destination is independently mutable, `source_integrity.py compare` reports a match, and every requested quantitative target has a comparable baseline or an explicit `Cannot verify` reason.

## Receipt

Write `source-snapshot.json` and `baseline.json`. Update `refactor-state.json` with their paths, hashes, protocol versions, gate result, and open baseline limits.

## Invalidation

Restart this phase when source content or dependencies change, local state is redefined, the destination shares mutable repository state, or a measurement protocol changes. Discard measurements that are no longer comparable.
