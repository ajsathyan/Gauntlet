# Gauntlet Lite

Gauntlet Lite is a compact workflow for shaping, proving, landing, and shipping
Codex work. It keeps the safety and product decisions that matter without custom
agent routing, sensors, durable queues, role handoffs, or simulated release stages.

## Flow

```text
Normal request or accepted Design
  -> implement and commit candidate
  -> exact-revision Verify
  -> Land through pull request
  -> Ship and monitor
```

Research remains read-only and pays no implementation ceremony. Non-trivial work
uses one accepted outcome contract and a mandatory main-agent review through six
lenses: Product, Engineering, Design, Analytics, QA, and Performance. Irrelevant
lenses say `Not applicable` with a reason. Recommendations are shown before
implementation and never silently adopted.

Verify evaluates every outcome independently, separating behavior from proof
availability. Land preserves the existing Problem, Solution, Changelog, Testing,
and conditional Security / Risk pull-request format. It directly merges without a
Gauntlet or GitHub queue requirement. Ship accounts separately for deployment and
attributable production proof.

## Retained skills

- `design`
- `adversarial-reviewer`
- `researcher`
- `debugger`
- `verify`
- `land`
- `ship`
- `refactor-codebase`
- `refactor-performance`

Planning, implementation, and finding disposition are native agent behavior.
Black-box, code, and experience review are triggered Verify modes. Comprehensive
refactoring keeps capability, compatibility, ownership, rollback, and
proof-before-retirement safeguards while making extra destinations, ledgers,
proposal rounds, and specialist passes conditional.

## Install

Gauntlet Lite installs only for Codex:

```sh
./scripts/install.sh --target codex --instructions-reviewed
```

The installer owns only its marked router block and receipt-listed runtime files.
It preserves unrelated instructions and files, safely removes unchanged stale
Gauntlet files, and leaves the existing personal email, terminology, and promotion
skills installed but outside Gauntlet ownership.

Uninstall removes only receipt-owned files:

```sh
./scripts/install.sh --target codex --uninstall
```

Restart or reload Codex after installation.

## Development

```sh
scripts/run-skill-change-checks.sh
python3 scripts/check-gauntlet-workflow.py
```

The deterministic evaluation tools remain repository development infrastructure;
they are not installed into the Codex runtime.

See `docs/design-build-verify.md`, `docs/meaningful-proof.md`, and
`docs/github-discipline.md`.

Gauntlet Lite is released under the MIT License.
