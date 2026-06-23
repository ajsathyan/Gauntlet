# Adversarial Report Example

- Verdict: Needs fixes
- Evidence reviewed: changed upload route, permission check, happy-path test
- Findings by priority:
  - P1: unauthorized retry can reuse a stale upload token. Impact: private file exposure. Recommended fix: bind token to user/session and expire after use. Test idea: retry the token from another user.
- Cannot verify: storage provider audit logs; next proof is a log query after retry.
- Residual risk: large-file timeout behavior still needs black-box proof.
- Agent next: add stale-token regression test and fix token binding.
