# Gauntlet Lite

Gauntlet Lite is a product-thinking, adversarial-review, and verification workflow for Codex. It keeps the parts of Gauntlet that shape a complete change—an accepted Design/PRD, independent review, implementation orchestration, exact-revision verification, pull-request landing, and post-merge production follow-through—without the sensor runtime, custom agent profiles, or durable workstream queue.

The repository is a history-preserving fork of Gauntlet. Git ancestry remains available for blame, comparison, recovery, and selective upstream updates; retired runtime files are not kept merely for history.

## Workflow

```text
Design / PRD acceptance
  -> Build (ephemeral plan)
  -> Implement
  -> Verify
  -> Land
  -> Ship and monitor
```

### Design / PRD acceptance

Normal requests remain direct: make the bounded, reversible change and run its smoke check.

Before non-trivial implementation, Gauntlet Lite creates or updates one Design/PRD, considers materially different approaches, resolves assumptions and edge cases, and runs three independent lenses:

- product completeness and user-visible states;
- engineering boundaries, dependencies, compatibility, and migrations;
- proof, false-green paths, consequences, and required non-effects.

For stateful or cross-cutting work, adversarial review explicitly examines state transitions, retries, idempotency, recovery after partial failure, concurrency, and behavior that must remain unchanged. These are the cases where a small happy-path benchmark is least representative of real engineering risk.

The user must accept the exact `Acceptance` section before implementation begins. That accepted section is the canonical Build Contract and authorizes the scoped lifecycle through the repository's ordinary declared production deployment. Gauntlet Lite does not ask for a second production acceptance after merge.

### Build and implement

Build is the ephemeral planning and orchestration phase; it no longer needs a separate `build` skill package. Implementation follows that plan. The parent task keeps product meaning, shared contracts, integration, publication, and external authority. Native subagents are used only for genuinely independent files, state, or evidence; each receives a compact assignment and returns changed artifacts, proof, and risk.

There is no custom-profile classifier, token-usage audit, or durable queue. Parallel candidates are integrated deliberately against the current base, and base drift invalidates stale proof.

### Verify

Independent Verify reads the original request, accepted Design/PRD, and exact integrated revision. It returns two separate verdicts:

- **Build:** every accepted outcome and required non-effect is observably true.
- **Architecture:** applicable boundaries, dependencies, compatibility, and code shape hold.

Proof comes from direct repository tests, black-box behavior, targeted inspections, and independent review. A green command counts only when its oracle would reject a plausible wrong implementation. Gauntlet Lite has no Sensor Contract, Sensor verdict, sensor CLI, or managed sensor toolchain.

### Land and ship

After verification, `land` pushes the implementation branch, creates or updates the pull request, waits for required CI and blocking review state, merges to the default branch, verifies the landed revision, and performs only safe cleanup.

After merge, `ship` continues automatically within the accepted scope. It lets merge-triggered deployment run or invokes the repository's declared standard deployment mechanism, monitors the landed revision, and checks attributable production behavior. Pull-request CI alone is not production proof.

Unexpected destructive, paid, credential, migration, privacy, security, or production effects outside the accepted Design/PRD still stop for a real scope decision. Installation and rollback also retain separately scoped authority.

## Durable local Designs

Private product documents are materialized only for covered document work:

```sh
python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs ensure \
  --project-root "$PROJECT_ROOT"

python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs design create \
  --project-root "$PROJECT_ROOT" --title "Message surfaces"

python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs design accept \
  --project-root "$PROJECT_ROOT" --design PROJECT-001
```

The profile uses ignored `doc_org.md` and `local-docs/` paths in the primary worktree. Direct user edits, arbitrary sections, and legacy accepted PRDs remain valid. See [Local Design Documentation](docs/local-documentation.md).

## Skills kept in Lite

Gauntlet Lite installs one canonical copy of each retained skill:

- core flow: `design`, `implementer`, `verify`, `land`, `ship`;
- shaping and coordination: `intake`, `product-architect`, `planner`, `issue-triager`;
- research and debugging: `researcher`, `debugger`;
- independent review: `adversarial-reviewer`, `black-box-tester`, `experience-reviewer`, `deep-code-reviewer`;
- focused workflows: `craft-customer-email`, `craft-product-terminology`, `promotion-scanner`, `refactor-codebase`, `refactor-performance`.

The former `archive`, `build`, and `eval-*` skill packages are intentionally absent. Implementation remains a workflow phase driven by the accepted Design/PRD and the `implementer` skill; removing the `build` package does not remove implementation planning or orchestration.

## Install, upgrade, and uninstall

Gauntlet Lite installs only for Codex on this machine:

```sh
./scripts/install.sh --target codex --instructions-reviewed
```

The installer preserves unrelated instructions and configuration, records ownership, removes only safe stale managed files during upgrades, and leaves modified or unowned files with a finding.

Uninstall removes receipt-owned Gauntlet Lite files and its managed instruction block while preserving user-owned and modified files:

```sh
./scripts/install.sh --target codex --uninstall
```

Restart Codex after installing or upgrading so the new global instructions and skills are loaded.

## References

- [Design, Implement, Verify, Land, Ship](docs/design-build-verify.md)
- [Workflow Etiquette](docs/workflow-etiquette.md)
- [Meaningful Proof](docs/meaningful-proof.md)
- [GitHub Discipline](docs/github-discipline.md)
- [Local Design Documentation](docs/local-documentation.md)
- [Skill Quality Bar](docs/skill-quality-bar.md)
- [Skills](skills)
- [Workflow helper CLI](scripts/gauntlet.py)
- [Deterministic evaluation harness](evals)

Gauntlet Lite is released under the [MIT License](LICENSE).
