# Task Packet Example

- Task: reject expired invites
- Goal: prevent access from stale invitation links
- Files/areas to inspect: invite accept route, invite tests
- Files/areas to avoid: billing, workspace settings UI
- Inherited constraints: preserve active invite behavior
- Consumes: accepted spec
- Produces: expiry check and regression test
- Implementation outline: inspect route, add failing test, implement check, verify
- Proof: targeted invite test plus workflow smoke
- Configuration and secret handling: expiry duration comes from validated existing config; no secret values enter the plan
- Cannot verify: production legacy invite policy
- Done when: expired invite test fails before fix and passes after
- Review target: deep-code-reviewer
