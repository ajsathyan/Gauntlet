# Run Log: Gauntlet Skill Bundle

Scope: Distribute Gauntlet's shared skill tree through Codex and Claude Code plugins, add `craft-customer-email`, and adopt the upstream eval suite under an `eval-` namespace.

## Decisions

- Keep one authoritative `skills/` tree. Both plugin manifests point to it, and the direct installer copies from it.
- Keep the global router in `AGENTS.md` or `CLAUDE.md`; on-demand plugin skills do not replace always-loaded workflow guidance.
- Use `craft-` for customer-visible artifacts, `eval-` for evaluation capabilities, and unprefixed names for lifecycle roles.
- Vendor `hamelsmu/evals-skills` at commit `814ebeae0ecef6151a4d3846e19ab123e1832137`, preserve its MIT notice, and change only names and cross-skill references.
- Keep customer-email examples cross-domain. Use product-family research only when it materially changes the answer, and use source Agora cases only as disposable forward-test inputs.
- Keep deterministic role-skill contract checks scoped to lifecycle roles. Domain skills receive structural lint plus task-appropriate forward testing instead of phrase-based proxy checks.

## Exceptions And Proof Limits

- Claude Code is not installed on this host, so `claude plugin validate` cannot run. JSON parsing, shared-path assertions, and the repository workflow check cover the Claude manifest shape locally; live Claude installation remains unverified.
- Customer-email forward tests ran ephemerally and were deleted after review. They covered action-first billing, a causal import pause, recurring operational status, bounded intake, and suppression/threading.
- The Codex plugin can be installed from GitHub only after the branch merges to `main`. The direct installer remains available for the required global router installation.
