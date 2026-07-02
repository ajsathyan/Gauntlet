# Promotion Brief

Verdict: Candidates found

Evidence reviewed:
- `docs/gauntlet-runs/2026-07-01-live-ops.md`
- monitor tail excerpts from 2026-07-01 14:05-14:30
- subagent report `ops-auth-cap-review`
- changed code under `scripts/ops/cleanup.py`

Current evidence table:

| Surface | Latest Evidence | Stale Evidence | Confidence |
| --- | --- | --- | --- |
| Cleanup safety | Latest monitor shows joined worker plus progress after auth-cap retry. | Earlier fatal auth-cap string appears before retry. | Medium |
| Network speed | One bad sample followed by normal samples. | None. | Low |

Timeline highlights:
- Stale: 14:07 fatal auth-cap string before retry.
- Latest: 14:18 join evidence and 14:22 progress evidence after retry.

Repeated manual loops observed:
- repeated manual verification of latest auth-cap evidence before cleanup
- separating stale vs latest evidence across monitor and subagent traces

Promotion candidates:

| Candidate | Destination | Confidence | Proof Needed |
| --- | --- | --- | --- |
| Fresh-verify auth-cap before cleanup command | repo code | Medium | Unit test with stale fatal plus later join/progress evidence |
| Regression fixture for stale fatal handling | repo test | High | Failing fixture first, then passing parser test |
| General stale/latest evidence checklist | coverage gap | Low | Two more repos or run logs showing same Gauntlet-general missing guidance |
| Live terminate recommendation | Reject | High | No live operational actions are allowed |

Edge cases and tests:
- stale logs, missing timestamps, contradictory subagent reports, manual keepalive, missing RunPod id

secrets/redaction notes:
- Redact pod tokens and auth headers before quoting logs.

Do not infer:
- Do not infer that cleanup is safe from one successful sample.
- Do not infer current state from old run logs.

Agent next:
- Add a repo-local test for stale fatal plus later progress evidence.
