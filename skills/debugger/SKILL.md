---
name: debugger
description: Use when a bug, failing test, or unexpected behavior must be reproduced, isolated, and explained before a fix is implemented.
---

# Debugger

Find the earliest evidence-backed divergence between expected and actual behavior.

## Output Contract

Return a **Debug Report**. Optional example: `examples/debug-report.md`.

- Symptom and user-visible impact
- Reproduction: exact, partial, intermittent, or Cannot verify
- Expected vs observed
- Evidence at relevant boundaries
- Root-cause hypothesis and discriminating check
- Root cause: confirmed, narrowed, rejected, or Cannot verify
- Smallest source fix
- Regression proof
- Residual risk and next action

If debugging is outside scope, return `Not relevant because...`.

## Rules

- Reproduce before changing code when possible.
- Trace backward from the symptom to the earliest incorrect state or assumption; do not stop at the nearest visible failure.
- State one falsifiable hypothesis at a time and run the smallest check that distinguishes it from alternatives.
- Regression proof must exercise the observable failure and a plausible wrong case or required non-effect when practical. A passing command or matched phrase alone does not confirm the cause or fix.
- Do not increase timeouts, add retries, or mask errors without evidence that timing or recovery policy is the cause.
- After confirming the cause, hand the bounded fix and regression proof to the implementer. Diagnosis alone does not authorize unrelated cleanup.
- If three hypotheses fail without new evidence, stop repeating variants; report Cannot verify and name the missing observation.

## Attribution

The root-cause-first, backward-tracing, and hypothesis-testing method is adapted from Jesse Vincent's Superpowers `systematic-debugging` skill, version 5.1.3 (MIT). See `docs/upstream-superpowers.md`.
