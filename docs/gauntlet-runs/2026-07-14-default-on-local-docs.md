# Run Log: Default-On Local Documents

Scope: make Gauntlet's local `doc_org.md` organization default-on globally, lazily materialized per project, and explicitly opt-outable without moving tracked documentation.

Proof scope: `full`

## Assumptions

- “Global” means the installed router, skills, CLI, templates, and documentation under the agent home; it does not mean writing ignored files into every repository during installation.
- The project opt-out must survive absent or deleted `doc_org.md`, so it uses the ignored primary-worktree marker `.gauntlet/doc-org.disabled`.

## Decisions

- Add `docs ensure` for first-use materialization, inferring a stable Epic prefix from the primary repository name when none is supplied.
- Keep `docs check` read-only and report `default-on`, `opted-out`, or materialized state.
- Add `docs disable` and `docs enable`; neither deletes or rewrites existing canonical local documents.
- Make Epic creation honor the default profile automatically while respecting opt-out.
- Preserve the primary-worktree-only rule and Git local-exclude boundary.

## Exceptions

- Existing historical run logs still describe the original opt-in introduction because they record the state of those completed runs. Current source guidance, templates, tests, and the changelog now state the default-on policy.
- A running agent process may retain instruction or skill state captured before reinstall; a fresh thread or reload is the next runtime check.

## Release Proof

The source workflow suite passed, including lazy default activation, opt-out/re-enable, linked-worktree placement, tracked-document collision, symlink safety, install-layout, merge, and PRD-run checks. Targeted changed-skill checks passed with skill linting and structural/orchestration coverage.

## Coverage Gaps

None added or updated.
