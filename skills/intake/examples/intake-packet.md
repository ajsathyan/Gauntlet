# Intake Packet Example

- Tier and reason: Tier 2, multi-file user-visible behavior
- Recommended mode and depth: Feature / Standard
- Goal: add saved search creation
- In scope: create, list, delete saved searches
- Out of scope: sharing and alerts
- Affected interfaces: search page, saved-search API
- Acceptance criteria: user can save a query and reopen it
- Verification/proof: saving and reopening reproduces the original query; a malformed query is rejected; existing search URLs remain unchanged. Run targeted state tests and a browser flow, then have the parent rerun the flow
- Constraints: preserve existing search URLs
- Assumptions: auth already identifies the user
- Open questions: None
- Cannot verify: production quota limits; next proof is config lookup
- First implementation step: inspect existing search state model
