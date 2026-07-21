---
name: debugger
description: Use when a bug or failing check must be reproduced, isolated, and tied to a regression oracle.
---

# Debugger

1. State the observed failure and smallest reproduction.
2. Separate candidate defects from baseline or environment failures.
3. Trace the real caller, state, and dependency path.
4. Form the smallest falsifiable cause hypothesis and test it.
5. Define a regression check that fails for the observed or a plausible wrong case.
6. If a fix is authorized, change the authoritative owner and rerun focused proof.

Do not broaden cleanup or hide a known failure behind `Cannot verify`. Return the
cause, evidence, affected behavior, regression oracle, and remaining uncertainty.
