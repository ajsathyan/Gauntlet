# Changelog

## Unreleased

- Remove obsolete dashboard remnants, historical run reports, and legacy local-document terminology after the Design → Build → Verify → Ship migration.

- GAUNTLET-011 replaces the Epic controller, ticket compiler, dashboard, analytics, and fixed routing layer with Design → Build → Verify → Ship: one permanent Design and canonical Build Contract, three pre-build lenses, ephemeral implementation planning, compact native workstreams with a current-base queue, separate exact-revision Build/Architecture/Sensor verdicts, phased sensors with compact handoffs, and preservation-safe Codex install, upgrade, and uninstall behavior.

- Adaptive sensors now discover changed code, execute repository-owned checks, block completion on required failures or stale evidence, and hand Codex compact attention items while preserving full raw evidence by reference. The Codex installer includes pinned Semgrep, coverage.py, and Gitleaks in an isolated owned generation unless `--without-sensor-tools` is supplied.

- Reconcile completion metadata into flexible accepted PRDs without requiring legacy Epic headings.

- Implement GAUNTLET-009: Adaptive code quality sensors.

- Implement GAUNTLET-008: Repository workflow mode selection.

- Omit empty named acceptance groups from generated run-backed Project PR facts.

- Gauntlet now plans proportional language-aware code-quality sensors from repository-owned configuration, normalizes compact evidence, and validates behavior-preserving readability rewrites without installing optional tools.

- Name follow-up PRD drafts after their features and preserve a valid working directory after landed-worktree cleanup.

- Gauntlet now provides `land execute` as one CLI flow for PR merge, exact-revision push monitoring, local default-branch synchronization, and preservation-safe branch and worktree cleanup.

- Gauntlet CI now runs policy, installer, lifecycle, PRD, and orchestration checks as parallel matrix jobs behind one stable aggregate `gauntlet` result, while preserving the complete sequential local checker.

- Gauntlet now owns a `land` skill for explicit merge-to-default requests, defaults GitHub operations to the authenticated `gh` CLI, completes landed-revision monitoring and safe cleanup, and leaves installation and task archival to `/Archive`.

- Explicit merge or land requests now carry required CI, landed-revision verification, applicable post-merge monitoring, local default-branch sync, and safe remote branch, isolated-worktree, and local-branch cleanup; `/Archive` performs task archival only after that closeout passes.

- Gauntlet installs an exact manifest-declared runtime payload, excludes development tests and UI dependencies, safely reconciles previously managed stale files, and checks manifest drift in CI and pre-commit.

- Gauntlet now packages the execution-run controller behind its unchanged CLI, calls the default controller in process, and preserves the trusted development override subprocess path.

- Gauntlet now extracts accepted-Epic launch contracts and Epic task orchestration into a registered stdlib-only package while preserving launch snapshots, task packets, dependency readiness, lifecycle events, document reconciliation, merge leases, CLI behavior, and legacy imports.

- Gauntlet now packages the unchanged live-progress projection and dashboard supervisor while preserving the legacy projection import path, dashboard lifecycle, and Epic progress CLI.

- Gauntlet now extracts unchanged closeout, archive, follow-up, memory, and changelog workflows into a registered stdlib-only package while preserving preflight, scoped mutation, installation, and returned app-action contracts.

- Gauntlet now extracts the unchanged contextual merge workflow into a registered stdlib-only package while preserving run binding, merge authority, lease recovery, PR checks, and branch cleanup behavior.

- Gauntlet now extracts unchanged merge-handoff contracts and the Review Unit workflow into registered stdlib-only packages while preserving validation findings and review-merge command ordering.

- Gauntlet now extracts the unchanged local product-document lifecycle into a registered stdlib-only docs package while preserving private file modes and execution-contract migration safeguards.

- Gauntlet now routes its unchanged CLI surface through a shared command shell and extracts local analytics and bounded attempt memory into a stdlib-only registered domain package.

- Gauntlet now centralizes shared stdlib-only process, redaction, serialization, atomic file, timestamp, and finding primitives while preserving each script's established contracts.

- Gauntlet now defines stdlib-only Python package scaffolding and runs conservative Ruff linting on changed Python files.

- Phase 7 moves development tests into discovery-native `tests/` modules, splits workflow checks by domain, preserves compatibility entry points, and adds a fast workflow smoke mode.

- Implement GAUNTLET-005: Live Epic progress.

- Gauntlet now automatically starts or recovers one launch-scoped live Epic progress dashboard, opens it through a secret-free Codex Browser action when available, refreshes run and usage facts continuously, and cleans it up only after every sibling reaches a terminal state.

- Gauntlet now starts product work from guided Founding Hypothesis or Peter Yang drafts, requires explicit promotion and acceptance without inferred product boundaries, loads accepted Epics once through compact task envelopes, and uses bounded gap review with deterministic dispositions and reusable-gap capture. Always-loaded and invoked model guidance is 57.8% smaller across the measured surfaces while legacy PRDs and the existing Epic dashboard flow remain supported.

- Gauntlet's Codex installer now defaults to no built-in personality, low response verbosity, concise reasoning summaries, visible context-window usage, and installed and enabled Browser and Computer Use plugins while preserving explicit conflict choices and unrelated configuration.

- Gauntlet's Codex installer now configures `agents.max_threads = 24` through the existing conflict-aware preference flow while preserving unrelated configuration and idempotent reinstalls.

- Gauntlet now lets one product task shape and launch many independently shippable Epics while giving each Epic its own visible task, Execution Run, exact-revision verification, schema 3.0 Project PR, dependency-aware lifecycle copy, and release state. The cutover retires duplicate implementation-plan and model-authored completion-summary mechanics, makes Cohorts optional, and preserves stronger consequence-triggered review and production dry-run gates.

- Gauntlet now documents how existing local-document profiles are migrated without overwriting canonical documents or rewriting completed Execution Run evidence.

- Gauntlet now freezes each PRD run's review topology, supports parent-owned Review Unit PRs for large tightly coupled targets, and generates one schema v2 Project PR with deterministic Epic and Scope Area coverage.

- Gauntlet now includes a version-pinned Codex CLI evaluation adapter, same-cell enforcement, trusted automatic scoring, and same-harness/model A/A equivalence checks while leaving the twelve core tasks undefined.

- Gauntlet now uses a durable orchestration architecture for material work: deterministic generated context, per-child routing and model-request analytics, independent Ticket progress inside context-affine lanes, isolated automatic evaluation tasks, and condition-blind paired experiments with sealed core-study slots; Normal Requests remain lightweight.

- Gauntlet skill creation now checks cache-friendly prompt structure, token efficiency, custom-agent fit, and instruction-drift resistance, with the same review applied before delegated Ticket dispatch.

- Gauntlet now installs seven deterministic Codex custom-agent profiles, routes bounded Tickets by explicit work and risk fields, and maintains a privacy-bounded local usage audit backed by Codex native state.

- Gauntlet now maintains human-readable multi-Epic PRDs and compiles build-ready targets into durable Ticket Graph runs with bounded cache-oriented child context, parent-owned verification, cohort gates, and authorized end-to-end release handling.

- Gauntlet refactor workflows now isolate bounded proposal and review agents with stable artifact-backed prompts, prefer the built-in Browser for web verification, preserve explicit Computer Use requests, and record execution-efficiency metrics only when observable.

- Gauntlet now includes staged `refactor-codebase` and measure-first `refactor-performance` skills with durable phase receipts, independent breakthrough search, migration strategy gates, parity proof, and deterministic refactor helpers.

- Gauntlet now uses a default-on, lazily materialized `local-docs/` profile with stable epic scaffolding, primary-worktree canonical documents, explicit per-project opt-out, tracked-document boundaries, one release contract, configuration and secret classification, and a global three-question discipline shared by every skill.

- Gauntlet now includes `craft-product-terminology` for naming public product concepts and internal system pieces from their actual responsibilities and boundaries.

- Gauntlet now uses prose delegation tickets with proportional behavioral proof, treats child receipts and declared trace fields as evidence pointers instead of proof, and labels phrase-based skill checks as structural coverage only.

- Gauntlet now ships one Codex plugin bundle from its shared skills tree, adds the `craft-customer-email` workflow, namespaces the vendored eval suite under `eval-`, and limits intake to three high-value questions.

- Gauntlet now installs a precision-preserving response style for Codex, applies conflict-aware verbosity and personality defaults, and stops before layering over unreviewed user instructions.

- Gauntlet now silently applies a conforming root-task title as soon as the goal is clear and no later than the third substantive user-authored message.

- Gauntlet now provides /Archive and a guarded closeout command that commits explicit paths, merges through required PR checks, installs the merged workflow locally, and returns Codex archive actions.

- Gauntlet now requires plain, concise, coherent user-facing prose and preserves shipped changelog entries under dated version headings.

- Gauntlet now routes bounded, reversible normal requests through minimum-scope execution, delivering the requested artifact before proportional proof and bypassing unnecessary lifecycle ceremony.

- Gauntlet now automatically delegates independent work when parallelism beats coordination cost, without requiring a user request or Release classification, while keeping child execution quiet.

- Gauntlet now rejects legacy or non-four-word task titles and blocks archive actions until a visible Archive Summary is queued immediately before thread archival.

- Gauntlet installs now remove workflow scripts deleted from the source payload, preventing retired orchestration helpers from lingering locally.

- Gauntlet now uses one lean Research/Patch/Feature/Release workflow, folds selected Superpowers techniques into attributed native skills, and safely retires overlapping runtime skills.

- Gauntlet now installs a compact path-safe global router inside a preservation-safe managed block, coordinates bounded child lanes through native Codex state with quiet receipts, and separates scorer smoke from observable orchestration outcome checks.
- Gauntlet remote-branch cleanup now treats concurrent GitHub auto-deletion as a successful postcondition.
- Gauntlet merge cleanup now deletes remote branches without asking GitHub CLI to manipulate linked local worktrees.
- Gauntlet now keeps routine workflow controls out of the conversation and automatically creates contextual PR and changelog handoffs when merging work.
