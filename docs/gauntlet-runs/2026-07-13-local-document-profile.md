# Local Document Profile

## Scope

Add an opt-in primary-worktree `local-docs/` convention, scaffolding CLI, shared question discipline, and configuration/secret boundaries without replacing tracked repository documentation or creating another Gauntlet lifecycle.

## Decisions

- Use ignored `local-docs/` rather than `docs/`; tracked contracts, contributor guidance, durable architecture, runbooks, release notes, compliance evidence, and maintainer-required documentation stay in the repository's established tracked location.
- Keep one release contract in `doc_org.md`. PRDs record product release constraints and implementation plans resolve authority, proof, rollout, rollback, and release source without copying the reusable procedure.
- Put the 80/20, at-most-three-short-questions discipline in the always-loaded router and workflow etiquette. Role skills retain only their consequential decision lists.
- Prohibit hardcoded secrets and environment-specific values while allowing stable typed and tested product or protocol constants in code. PRDs state configuration requirements; plans hold the full value classification.
- Use Git's local exclude file so initializing local documents does not mutate a repository's tracked `.gitignore`.

## Exceptions

- The first workflow pass exposed existing planner and implementer word-budget pressure after the new rules were added. Duplicate orchestration prose was pruned while the established output and Release contracts were preserved.
- Adversarial review found partial-write, epic-prefix drift, Markdown-title injection, and symlink escape risks in the initial scaffold. Initialization now validates templates before mutation, installs local excludes before document writes, rejects prefix changes and invalid titles, uses atomic metadata writes, rolls back partial epic creation, and refuses canonical-path symlinks.
- Behavioral quality of the question discipline remains a judgment claim. Existing skill coverage and scorer-smoke checks prove only contract text and harness wiring; they are not evidence that questions are nuanced in live use.
- Global installation and merged-default-branch verification occur during the authorized closeout after this run log is committed.
