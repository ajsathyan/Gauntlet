# Gauntlet Contributor Guide

Gauntlet is a markdown-only product, proof, and release workflow for Codex. Its
operational surface is the short global policy in `router/AGENTS.md` plus the ten
skill packages in `skills/`.

## Invariants

- Keep Research, Normal, and Material routing proportional to consequence.
- Material work gets one accepted outcome contract and the main-agent Product,
  Engineering, Design, Analytics, QA, and Performance review.
- Invoke `orchestrate` for implementation while respecting explicit limits on
  agents or delegation.
- Verify observable behavior against an exact candidate commit, tree, and checked
  base. Instructions and self-reports are not authenticated enforcement.
- Land with native `git` and `gh`, only after independent Verify passes. Preserve
  established PR sections, required checks, blocking reviews, drift checks, and
  safe cleanup.
- Ship only observes declared deployment and monitoring paths already triggered
  by the merge.

Gauntlet intentionally has no custom CLI, library, installer, manifest, receipt,
hook, evaluator, or workflow daemon. Do not reintroduce executable enforcement or
generated verification contracts. Global instructions remain freely editable.

## Repository checks

For policy or skill changes, inspect the complete diff, run `git diff --check`,
confirm every retained reference resolves, and exercise changed Git procedures in
disposable repositories. Do not keep temporary proof harnesses in this product.

Preserve unrelated work and personal skills. Retired behavior belongs in Git
history, not aliases, fixtures, or compatibility shims.
