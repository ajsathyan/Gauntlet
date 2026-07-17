# Source And Baseline

## Inputs

- Source repository, requested destination, and user-supplied targets
- Current Git, submodule, LFS, ignored-file, and working-tree state
- Existing build, test, benchmark, and product-run instructions

## Actions

1. Decide what “exactly as it exists” means. If staged, unstaged, untracked, ignored-but-required, modified-submodule, or unavailable LFS state would be omitted by a clone, inventory it and obtain the one material choice: committed `HEAD` or current filesystem. The integrity helper hashes approved untracked content but rejects dirty initialized submodules; commit or otherwise freeze a dirty submodule before continuing rather than accepting an unverifiable current-filesystem snapshot.
2. Run [source_integrity.py](../scripts/source_integrity.py) in `snapshot` mode with output outside the source. It emits stable tokens instead of raw paths and symlink targets. Treat the resulting `source-snapshot.json` as sensitive and private by default because hashes and repository metadata can still disclose information; track it only after explicit human review and approval. The helper excludes Git-ignored content by default. Record that exclusion explicitly, and create a separately reviewed content-hash receipt for each ignored path approved as part of the source. Supplement the snapshot with approved remotes and any LFS interpretation it cannot infer. If the source is not a Git work tree, the helper cannot prove it: create and review an equivalent filesystem content manifest before proceeding and mark Git-only fields not applicable.
3. Create an independent local repository at the destination and verify that its Git directory, index, config, hooks, and working tree are not shared with the source. Do not create or push a hosted fork without explicit authority.
4. Run potentially mutating baseline commands in a disposable clone of the approved snapshot.
5. Run [measure_loc.py](../scripts/measure_loc.py) against the approved snapshot. Inspect and freeze its rules first. Add behavior-bearing declarative sources, such as Markdown skills, templates, or notebooks, when they execute or define product behavior; do not count ordinary documentation merely to enlarge the baseline. Use physical nonblank LOC as the canonical source measure, preserve the emitted rules hash, tree digest, and excluded-file inventory, and report production/test, generated, configuration, fixture, and migration categories separately. Record additional exclusions such as vendored or minified inputs. Treat a production/test reduction accompanied by any excluded-content change or growth in non-production categories as displaced complexity until reviewed; the comparator blocks that result. Saved receipts compare offline by default for resumability; use `compare --verify-live` while the recorded roots exist to prove freshness against the filesystem.
6. Invoke `$refactor-performance` to define reproducible test-feedback and product-performance baselines. Preserve its commands, environment, dependency state, cache policy, concurrency, warm-up, run count, and statistic in `baseline.json`.
7. Record dependency count, major code concentration, duplication or change-amplification signals, and observable start commands without interpreting product parity yet.

## Definition of Done

Baseline work is done when the source snapshot is unambiguous, the destination is independently mutable, `source_integrity.py compare` reports a match, and every requested quantitative target has a comparable baseline or an explicit `Cannot verify` reason.

## Receipt

Write `source-snapshot.json` and `baseline.json`. Update `refactor-state.json` with their paths, hashes, protocol versions, Definition of Done result, and open baseline limits.

## Invalidation

Restart this phase when source content or dependencies change, local state is redefined, the destination shares mutable repository state, or a measurement protocol changes. Discard measurements that are no longer comparable.
