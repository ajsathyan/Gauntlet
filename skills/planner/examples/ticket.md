# Gauntlet Ticket Example

- Objective: reject expired invites without changing active-invite behavior
- Ownership: invite accept route and invite tests; avoid billing and workspace settings
- Dependencies: accepted invite-expiry policy
- Constraints and authority: preserve active invites; do not change legacy policy
- Proof:
  - Claim: expired invites cannot open a workspace while active invites still can
  - Observable oracle: accept route rejects an invite just past expiry and accepts one just before expiry
  - Required checks: targeted invite tests plus workflow smoke
  - Negative control: removing or bypassing the expiry check makes the expired-invite test fail
  - Required non-effects: active invite acceptance and existing error responses remain unchanged
  - Integrity: do not weaken shared assertions or fixtures; parent reruns the targeted test and inspects both boundary cases
  - Cannot verify: production policy for legacy invites
- Return: changed paths, behavioral proof and limits, blocker if integration cannot continue
- Ask parent: only for a policy decision, new authority, unrecoverable blocker, or safety stop
