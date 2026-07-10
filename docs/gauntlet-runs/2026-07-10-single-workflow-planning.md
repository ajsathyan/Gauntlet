# Run Log: Single Workflow Planning

Scope: make Gauntlet the sole coding workflow, adapt selected Superpowers techniques with durable attribution, and retire the overlapping runtime skills safely.

Proof scope: `full`

## Assumptions

- The packaged Superpowers `5.1.3` snapshot is the reviewed upstream source; its cache remains available for future semantic update review.
- Moving active Superpowers skill directories to a dated archive satisfies removal from active discovery while preserving user-owned modifications and rollback evidence.

## Decisions

- Keep the kickoff checker for title, decision-gate, assumption, follow-up, git-risk, and archive safety. Make five-field kickoff narration warning-only and accept `Research` as a compatibility value.
- Use one accepted spec and one canonical plan. Schema `1.2` makes `.gauntlet/subagent-plan.json` the complete lane contract and rejects duplicate Markdown packet references.
- Preserve legacy Implementation Memory CLI inputs for one migration window, but remove them from active workflow routing and documentation.
- Disable the Superpowers plugin only after the Gauntlet replacements, attribution hashes, managed-block migration, and retirement preflight pass.

## Exceptions

- The first exact legacy-install simulation appended the new managed block without removing the old Gauntlet body because a house-voice insertion left one extra blank line. The migration now compares normalized blank runs without normalizing user output; the exact live layout and malformed/reversed markers have regression coverage.
- Independent review found that unresolved plugin configuration could still allow skill moves, a failed payload copy could activate the new router too early, and changelog JSON changed `source` type. Retirement now refuses unverified disablement, install activates the router last after payload validation, and `source` remains a compatibility string alongside `sources`.
- Before PR closeout, current `main` had added contextual merge automation and stricter child-lane gates across the same workflow files. The conflict resolution preserved those merge/check-cleanup capabilities while keeping the canonical manifest as the sole packet and extending its gate to single write-heavy child lanes.
- `Cannot verify`: this already-running Codex process may retain the skill catalog captured at startup. A reload/new thread is the next check for runtime catalog refresh; active config and filesystem state already show the plugin disabled and all 14 skills retired.

## Production Quality Bar

Not relevant because this changes a local agent workflow installation, not a deployed application or production data plane. Mutation safety was handled through the Release install cut line instead.

## Release Proof

Launch cut line: do not activate the global router or retire Superpowers until source checks, upstream hash sync, canonical-manifest proof, exact legacy migration, malformed-marker preservation, and retirement preflight pass. The cut line was satisfied before active mutation.

| Concern | Decision | Why Not Defer | Proof | Plan Delta |
| --- | --- | --- | --- | --- |
| Global instructions could be duplicated or lost | Ship blocker | It would damage user-owned workflow state during the required install | Exact legacy simulation plus malformed, reversed, unrelated-content, and idempotency fixtures | Activate the managed block last and preserve unmatched content |
| Dual workflow remains active | Ship blocker | Future tasks would still receive conflicting lifecycle instructions | Version/hash sync, plugin config disabled, allowlisted active directories absent, archive complete | Install Gauntlet replacements before retirement |
| Current process may cache the old catalog | Manual fallback | Configuration and files are correct, but process startup state cannot be refreshed in-place | Reload/new-thread check | Tell the user a reload is required |

## Coverage Gaps

None added or updated.
