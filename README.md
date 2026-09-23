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

1. In `~/.codex/AGENTS.md`, replace only the text between
   `BEGIN GAUNTLET MANAGED BLOCK` and `END GAUNTLET MANAGED BLOCK` with the block
   from [`router/AGENTS.md`](router/AGENTS.md). Add the block if it is absent.
   Preserve every byte outside those markers, including personal response style.
2. Copy the ten named directories above from `skills/` into
   `~/.codex/skills/`, replacing only directories with those exact names.
   Preserve every other personal skill.
3. When upgrading from an executable Gauntlet release, inspect and then remove
   the retired `~/.codex/gauntlet` directory and any Gauntlet-owned source hook.
   Preserve unrelated hook content or a backed-up user hook.
4. Restart or reload Codex.

Global instructions are intentionally user-owned after copying. Editing or
removing them is supported; there is no drift check or auto-restoration.

To uninstall, remove only the marked Gauntlet block and the ten exact skill
directories listed above. No other personal instructions or skills are owned.

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
