# Ready Item Example

- Classification: review finding
- Decision: Ready
- Priority: P1
- Status: Ready
- Source handle or source text: RB-014
- Observed vs expected: expired invitation still opens workspace
- Evidence: reviewer reproduced with invite URL after expiry
- Repro state: exact repro
- Cannot verify: whether legacy invites should be grandfathered
- Done when: expired invites return an error and regression test passes
- Next action: add expiry check in invite accept path
- Owner/role: implementer
- WIP guidance: touch invite accept flow only
