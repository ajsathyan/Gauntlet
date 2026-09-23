# Gauntlet

Gauntlet is a markdown-only product, proof, and release workflow for Codex. It is
for builders who want Codex to carry a change from an idea to verified code and a
consistent pull request without a controller or custom runtime.

Its entire operational surface is:

- one short, freely editable policy block for global `AGENTS.md`; and
- ten ordinary Codex skill packages.

There is no Gauntlet CLI, library, daemon, hook, installer, receipt, hash
manifest, JSON handoff, or evaluation harness.

## Workflow

```text
Research
  -> inspect and report

Normal request
  -> Orchestrate -> Verify -> Land -> Ship

Material request
  -> Design and acceptance -> Orchestrate -> Verify -> Land -> Ship
```

- **Design** resolves material decisions once and runs the main-agent Product,
  Engineering, Design, Analytics, QA, and Performance review.
- **Orchestrate** coordinates implementation when useful while preserving user
  limits on agents and delegation.
- **Verify** independently checks every accepted outcome against observable
  evidence from the exact candidate commit, tree, and checked base.
- **Land** uses native `git` and `gh` to publish, check, directly merge, prove the
  landed revision, and clean up safely.
- **Ship** observes declared deployments already triggered by the merge and keeps
  merge, deployment, and production proof separate.

The policy and skills are instructions, not authenticated enforcement. Their
value comes from explicit revision binding, observable proof, and honest limits.

## Included skills

Core workflow:

- `design`
- `adversarial-reviewer`
- `orchestrate`
- `verify`
- `land`
- `ship`

Focused procedures:

- `researcher`
- `debugger`
- `refactor-codebase`
- `refactor-performance`

## Install or update

1. In `~/.codex/AGENTS.md`, replace the entire existing Gauntlet block, including
   both marker lines, with the full contents of
   [`router/AGENTS.md`](router/AGENTS.md) exactly once. If no markers exist,
   append the source block once. If markers are missing, duplicated, reversed, or
   nested, inspect and resolve them instead of guessing. Preserve every byte
   outside the replaced block, including personal response style.
2. For each of the ten named skills above, create its target directory when
   needed and copy only its owned `SKILL.md` into `~/.codex/skills/<name>/`.
   Preserve other files in those directories and every unrelated personal skill.
3. When upgrading from an executable Gauntlet release, inspect and then remove
   the retired `~/.codex/gauntlet` directory and any Gauntlet-owned source hook.
   Preserve unrelated hook content or a backed-up user hook.
4. Restart or reload Codex.

Global instructions are intentionally user-owned after copying. Editing or
removing them is supported; there is no drift check or auto-restoration.

To uninstall, remove only the complete marked Gauntlet block and the ten owned
`SKILL.md` files. Remove a skill directory only when it is empty; preserve every
other file, instruction, and personal skill.

## Contributing

This repository intentionally contains no product code or evaluation tooling.
For changes, inspect the full diff, run `git diff --check`, check retained links
and references, and exercise changed native Git procedures in disposable
repositories. Temporary proof scripts and fixtures stay outside the product.

Additional documentation:

- [`docs/design-build-verify.md`](docs/design-build-verify.md)
- [`docs/meaningful-proof.md`](docs/meaningful-proof.md)
- [`docs/github-discipline.md`](docs/github-discipline.md)

Gauntlet is released under the MIT License.
