# Gauntlet 3

Gauntlet is a lean implementation and release workflow for GPT-5.6 Sol in Codex. It is designed primarily for hobbyists and independent builders who want Codex to carry a change from an idea to verified code and a consistently structured pull request without accumulating unnecessary process.

Version 3 removes controllers, queues, context machinery, specialist handoffs, and release simulations.

The remaining workflow is intentionally small: classify the request, accept material decisions once, orchestrate implementation, verify the exact candidate, land it through a consistent pull request, and follow the repository’s declared deployment path when appropriate.

Gauntlet is designed to reduce repeated instructions and process overhead, unnecessary hedging after approval, speculative architecture or performance work, unsupported completion claims, and inconsistent pull requests.

## Workflow

```text
Research
  -> inspect and report

Normal request
  -> Orchestrate
  -> Verify
  -> Land
  -> Ship

Material request
  -> Design and acceptance
  -> Orchestrate
  -> Verify
  -> Land
  -> Ship
```

- **Proportional workflow:** routine and reversible work proceeds directly, research remains read-only, and only material decisions require Design and explicit acceptance.
- **Orchestrate:** every implementation can use as many agents as the work warrants. The main Codex task retains the requirements, approvals, and final integration.
- **Verify:** checks every accepted outcome using observable evidence from the exact candidate commit, tree, and base. A known failure fails verification, while missing required proof blocks landing.
- **Land:** creates or updates a pull request using the same Problem, Solution, Changelog, and Testing format, waits for required checks and blocking reviews, and merges the verified candidate.
- **Ship:** follows the repository’s declared deployment and monitoring path while keeping merged, deployed, and production-proved status separate.

## Who it is for

Gauntlet’s default lifecycle is best suited to personal and owner-controlled repositories.

**Work repositories:** Land creates the pull request, waits for required checks and reviews, and then merges it. Ship handles deployment and monitoring. If your organization requires human merge approval, make Land PR-only and disable Ship unless it matches your production controls.

## Included skills

The core workflow uses:

- `design`
- `adversarial-reviewer`
- `orchestrate`
- `verify`
- `land`
- `ship`

Gauntlet also includes focused procedures for research, debugging, broad codebase refactoring, and performance refactoring:

- `researcher`
- `debugger`
- `refactor-codebase`
- `refactor-performance`

Planning and implementation remain native Codex behavior. The skills add durable guidance where consistency, proof, or release authority matters.

## Install

Gauntlet installs only for Codex:

```sh
./scripts/install.sh --target codex --instructions-reviewed
```

The installer owns only its marked router block and receipt-listed runtime files. It preserves unrelated instructions and files, removes unchanged stale Gauntlet files during upgrades, and leaves separately installed personal skills outside Gauntlet’s ownership.

Restart or reload Codex after installation.

To uninstall Gauntlet:

```sh
./scripts/install.sh --target codex --uninstall
```

Uninstall removes only files owned by the Gauntlet installation receipt.

## Development

Install the development dependencies and run the repository checks:

```sh
python3 -m pip install -e '.[dev]'
scripts/run-skill-change-checks.sh
python3 scripts/check-gauntlet-workflow.py
```

The deterministic evaluation tools are repository development infrastructure. They are not installed into the Codex runtime.

Additional documentation:

- [`docs/design-build-verify.md`](docs/design-build-verify.md)
- [`docs/meaningful-proof.md`](docs/meaningful-proof.md)
- [`docs/github-discipline.md`](docs/github-discipline.md)

Gauntlet is released under the MIT License.
