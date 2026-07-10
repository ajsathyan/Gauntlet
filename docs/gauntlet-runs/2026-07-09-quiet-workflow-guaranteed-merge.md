# Quiet Workflow And Guaranteed Merge Run Log

## Decisions

- Across nine attempts across seven unique validator runs, the only two recorded rejections were duplicate inline context. No recorded rejection caught a material ownership, state, secret, path, or packet hazard.
- The rejected manifests contained 148 tokens more than their accepted rewrites, or +7.7% relative to the accepted full manifests. Because the rewrites also shortened substantive detail, this is an upper bound on duplication cost rather than proof of dispatch waste.
- Actual child instructions still contained 866 repeated exact-sentence tokens out of 2,143 instruction tokens after validation. Duplicate context is therefore advisory and is handled through shared packet references; executable and safety hazards remain blocking.
- Native Codex state owns child progress. Bounded packets, write isolation, proof, and main-task merge ownership remain; title/status choreography and new thread-provenance machinery do not.
- The skill linter itself required every skill to contain a `Not relevant because...` default. That requirement enforced no-op prose, so it was removed and replaced with focused quiet-output pressure fixtures for planner and implementer.

## Cannot Verify

- Separate children still need their relevant shared constraints. The total billed or cached child context was unavailable in the traces, so no end-to-end model-cost reduction is claimed.

## Exceptions

- The first live PR run reached GitHub before Actions had registered any checks, so `gh pr checks --watch` exited instead of waiting. The merge helper now polls for the actual check-registration condition with a bounded timeout before handing off to GitHub's check watcher.
- The first live merge completed remotely but GitHub CLI returned an error while trying to switch the linked feature worktree to `main` for local branch cleanup. Merge and remote-branch deletion are now separate actions, leaving local worktree cleanup to the verified final step.
