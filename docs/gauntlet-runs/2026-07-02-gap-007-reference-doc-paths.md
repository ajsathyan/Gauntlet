# Run Log: GAP-007 Reference Doc Paths

Scope: Diagnose and fix Agora RunPod GAP-007 where exported Gauntlet guidance pointed agents at `docs/production-quality-bar.md` in the target repo even when the canonical document lived in the Gauntlet install.

Proof scope: delta.

## Assumptions

- The originating Agora RunPod trace is sufficient: its `AGENTS.md` text referenced `docs/production-quality-bar.md`, that file was absent in the target repo, and the canonical file existed in this Gauntlet repo.
- Target repos should not be required to vendor all Gauntlet reference docs just because they inherit or paste Gauntlet `AGENTS.md` guidance.

## Decisions

- Fixed the Gauntlet guidance/export contract instead of modifying the Agora RunPod repo. The root issue was ambiguous path ownership: Gauntlet-owned source documents were referenced as target-repo-relative paths.
- Kept `scripts/install.sh` layout unchanged because it already installs docs under `$AGENT_HOME/gauntlet/docs`; the failure was that exported instructions did not tell agents to use that installed path.
- Tightened the canonical Production Quality Bar with live-ops-specific wording for destructive action boundaries, alerting/email expectations, and rollback/restart proof because GAP-007 named those expectations explicitly.

## Exceptions

- Did not run a global install into `/Users/ajsathyan/.codex`; proof used the existing installed-layout simulation in `scripts/check-gauntlet-workflow.py`.
- Did not update Agora RunPod `docs/coverage-gaps.md`; that repo should mark GAP-007 according to its own installed or synced Gauntlet copy.

## Production Quality Bar

Applies because this is a Release-scoped guidance packaging fix that affects production-bound checks in downstream repos. Runtime rollback proof is not relevant because no live application, migration, billing path, or external service changed.

## Release Proof

Launch cut line: downstream agents can now resolve the Production Quality Bar from the Gauntlet source repo or from `$AGENT_HOME/gauntlet/docs/production-quality-bar.md` after install; target repos no longer need a local `docs/production-quality-bar.md` for the guidance to be actionable.

| Concern | Decision | Why Not Defer | Proof | Plan Delta |
| --- | --- | --- | --- | --- |
| Exported guidance references missing target-repo docs | Conditional blocker | Release-scoped downstream work could silently skip the Production Quality Bar or rely on ad hoc judgment. | `python3 scripts/check-gauntlet-workflow.py` now asserts installed `AGENTS.md` names `$AGENT_HOME/gauntlet/docs/production-quality-bar.md`. | Update `AGENTS.md` path guidance and installed-layout regression test. |
| Live-ops expectations not explicitly named in canonical doc | Reject | GAP-007 specifically named alerting/email and rollback/restart expectations; leaving them implicit would only partially close the gap. | Workflow check now asserts `alerting/email`, `rollback/restart`, and `destructive action boundaries` markers. | Update `docs/production-quality-bar.md` with explicit live-ops guardrails. |

## Coverage Gap Candidates

No new Gauntlet coverage gap. This run fixed an externally reported gap in source guidance and regression coverage.
