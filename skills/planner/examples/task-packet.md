# Task Packet Example

- Task: reject expired invites
- Goal: prevent access from stale invitation links
- Files/areas to inspect: invite accept route, invite tests
- Files/areas to avoid: billing, workspace settings UI
- Global Constraints: preserve active invite behavior
- Consumes: accepted intake packet, run log or source text
- Produces: expiry check and regression test
- Steps: inspect route, add failing test, implement check, verify
- Proof: targeted invite test plus workflow smoke
- Cannot verify: production legacy invite policy
- Done when: expired invite test fails before fix and passes after
- Review target: deep-code-reviewer
