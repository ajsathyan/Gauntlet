# Debug Report Example

- Symptom: installer duplicates the managed block
- Impact: global instructions load twice
- Reproduction: run install twice against a temporary agent home
- Expected: one managed block
- Observed: two blocks
- Evidence: marker count after the second run
- Root-cause hypothesis: replacement misses the closing marker
- Discriminating check: test the marker regex directly
- Root cause: confirmed or Cannot verify
- Smallest fix: replace the matched block atomically
- Regression proof: idempotent temporary-home install test
- Residual risk: malformed legacy blocks still require an explicit failure
