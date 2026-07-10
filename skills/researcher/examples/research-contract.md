# Research Contract Example

- Question: Does the kickoff checker select downstream Gauntlet behavior?
- Downstream consequence: retiring it could remove safety checks
- Scope: checker inputs, callers, and archive flow
- Non-goals: implementation changes
- Evidence plan: static call-site search and focused tests
- Findings: classification fields are advisory; title and git-risk checks are consumed
- Inference: retain the checker and deprecate mandatory narration
- Cannot verify: behavior outside the inspected repository
- Recommendation: keep compatibility parsing and safety checks
- Implementation transition: accepted conclusion only
