# Meaningful Proof

Proof must distinguish the intended behavior from a plausible wrong implementation.

For every accepted outcome record the claim, observable oracle, evidence, required
non-effects, and a wrong case when it discriminates. Report behavior separately
from proof availability:

- any known behavior failure -> `Failed`;
- no failure with unavailable required proof -> `Blocked`;
- complete applicable proof -> `Passed`.

Run all executable target-specific checks even when an unrelated broad check is
blocked. A receipt, manifest, document, status, reviewer agreement, or green
command proves only what its underlying oracle observes.

Evidence is revision-bound. Reuse it only when the candidate commit/tree, checked
base, command, fixture, toolchain, and relevant environment still match.
Architecture is a separate verdict and cannot turn a behavior failure into success.

Keep structural coverage, synthetic scorer smoke, execution-backed behavior, and
calibrated judgment as distinct claim classes. Missing production proof is
`Cannot verify`, never inferred health.
