# Gauntlet

A product-thinking harness for AI coding agents.

<p>
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-3fb950?style=for-the-badge"></a>
  <a href="https://github.com/ajsathyan/Gauntlet/releases/tag/v2.0.2"><img alt="Version" src="https://img.shields.io/badge/version-v2.0.2-111827?style=for-the-badge"></a>
  <a href="router/AGENTS.md"><img alt="Workflow" src="https://img.shields.io/badge/workflow-global-0969da?style=for-the-badge"></a>
  <a href="skills"><img alt="Role skills" src="https://img.shields.io/badge/role_skills-13-8957e5?style=for-the-badge"></a>
  <a href="docs/coverage-gaps.md"><img alt="Coverage gaps" src="https://img.shields.io/badge/coverage_gaps-pending-f778ba?style=for-the-badge"></a>
</p>

<p>
  <a href="#-at-a-glance">At A Glance</a> |
  <a href="#v202-product-thinking-and-proof-scope">v2.0.2</a> |
  <a href="#v201-run-log-harness">v2.0.1</a> |
  <a href="#-build-stages">Build Stages</a> |
  <a href="#-run-logs">Run Logs</a> |
  <a href="#-skill-quality-bar">Skill Quality Bar</a> |
  <a href="#-coverage-gaps">Coverage Gaps</a> |
  <a href="#-production-quality-bar">Production Quality Bar</a> |
  <a href="#-install">Install</a>
</p>

Gauntlet helps AI coding agents turn rough asks into thought-through features, evidence-backed research, and verified changes. It is the single workflow authority; domain/tool skills may add capabilities without imposing a second lifecycle.

Coding agents make implementation cheaper, but they make product judgment, coherence, and review more important. Gauntlet v2.0.2 keeps the workflow strict where the feature shape or risk demands it and lighter where ceremony gets in the way: durable context is now an exceptions-first Markdown run log plus pending coverage gaps, not a separate review product.

## v2.0.2: Product Thinking And Proof Scope

Gauntlet v2.0.2 sharpens the harness around outcomes:

| Outcome | What Changed |
| --- | --- |
| Product coherence | The README and global workflow now position Gauntlet as a product-thinking harness that turns rough asks into coherent features, not just risk-managed prototypes. |
| Token efficiency | Proof scope now routes work through `smoke`, `delta`, `full`, or `not relevant`; small accepted changes can combine black-box and experience review, skip second triage unless findings exist, and run targeted changed-skill evals instead of the full suite. |
| UI quality without a design-system tax | The new UI constitution keeps frontend checks bounded to substantial UI work and separates general lint candidates from product-judgment review. |
| Better durable memory | Coverage gaps stay pending backlog items, and run logs capture exceptions, decisions, skipped proof, and new or updated gap IDs rather than proof dumps. |
| Clearer gap closeout | Final responses now list only newly added or updated gaps at the end using `Added GAP-###: Short name - why it matters`, while the full backlog remains in `docs/coverage-gaps.md`. |
| Less parallelization theater | Planner and implementer guidance now require independent files, state, and proof before using subagents, with an explicit context-cost guard. |
| Launch-grade quality without default ceremony | The Production Quality Bar applies senior implementation boundaries, release proof, and decision-oriented UI checks only to near-launch, private-beta, production-bound, hardened, or audited work. |

## v2.0.1: Run Log Harness

Gauntlet v2.0.1 replaces the default review surface with a small **Run Log** and a candidate **Coverage Gap** loop inspired by repo-local product-design guidance patterns.

The workflow is built around Research, Patch, Feature, and Release paths; Standard and Deep depth; smoke, delta, and full proof scopes; one accepted source and canonical plan; run logs; architecture hygiene; TypeScript durability classification; and triggered quality gates.

## ✨ At A Glance

| Capability | What You Get |
| --- | --- |
| Intake | Turns rough intent into scope, boundaries, acceptance criteria, assumptions, and proof. |
| Work paths | Routes work through Research, Patch, Feature, or Release based on intent and risk, with Standard or Deep depth chosen separately. |
| Product-thinking loop | Shapes rough asks into coherent product features before implementation and checks consistency after. |
| Scoped role skills | Adds product architecture, planning, triage, implementation, black-box testing, experience review, and deep code review only at smoke, delta, or full scope when useful. |
| Run logs | Writes a tiny exceptions-first Markdown receipt for material Feature/Release work: assumptions, decisions, skipped checks, failures, `Cannot verify`, and follow-ups. |
| Local product documents | Uses a default-on, lazily materialized ignored `local-docs/` profile in the primary worktree, with an explicit per-project opt-out, while preserving tracked repository documentation and Git/PR/release traceability. |
| PRD execution | Compiles one accepted multi-Epic PRD's build-ready target into a durable Ticket Graph with bounded child context, resumable state, incremental integration, cohort proof, and end-to-end release authority. |
| Skill quality bar | Gives future skill and workflow edits a practical behavior-delta, trigger, completion, proof, and token-cost bar without making every Patch heavier. |
| Coverage gaps | Captures pending candidates when missing reusable guidance forced a material assumption or repeated review finding. |
| Workflow speedup helpers | Classifies changed surfaces, recommends bounded tests, and generates redacted review packets without making every Patch run a heavy quality gate. |
| Promotion scanner | Produces a Promotion Brief when repeated manual or agent loops should be considered for repo code, repo test, repo docs/run log, Gauntlet skill/tool, coverage gap, or Reject. |
| UI constitution | Keeps frontend quality checks bounded: general lint candidates, browser checks, experience review guidance, and gap promotion only for substantial UI work. |
| Production Quality Bar | Raises the bar for near-launch systems with ownership boundaries, invariants, durable state, state machines, threat/redaction review, no-mutation or dry-run proof, automated GitHub release tags, release proof, feedback loops, and decision-oriented UI. |
| Model portability | Installs as reusable instructions, skills, docs, scripts, and evals that can be adapted to different agent environments. |

## 🧭 Build Stages

| Stage | Best For | What It Optimizes |
| --- | --- | --- |
| Research | Audits, comparisons, recommendations, and implementation discovery | Evidence quality without implementation gates. |
| Patch | Small, focused changes | Speed and low overhead. |
| Feature | High-fidelity product features and workflows | Coherent product thinking, implementation, and consistency checks. |
| Release | Production-bound or risky changes | Deeper verification, review, and regression control. |

## 🎯 How To Choose A Stage

| Signal | Recommended Stage |
| --- | --- |
| Investigation, audit, comparison, or recommendation without a requested code change | Research |
| Clear copy, config, polish, or narrow bug fix | Patch |
| Small code surface where the best answer matters | Patch with Deep depth |
| Product workflow, onboarding, activation, retention, growth, IA, or design-heavy work | Feature |
| Auth, billing, migrations, data integrity, privacy, uploads, concurrency, public APIs, large refactors, weak-test areas, or deploy-sensitive work | Release |

The rule has two parts:

```text
Choose the lightest stage for the change shape.
Choose the depth that matches the value of finding the best answer.
```

Mode is about scope and risk surface. Depth is about search effort. A performance optimization can be a tiny Patch and still deserve Deep depth if "fastest reasonable result" matters more than minimizing tokens.

## 👥 Who It Helps

| Audience | How Gauntlet Helps |
| --- | --- |
| Engineers | Turns broad requests into scoped, verifiable implementation work, adds review loops for risky changes, and leaves a small durable trail for future agents. |
| PMs | Makes product intent executable by clarifying scope, non-goals, acceptance criteria, assumptions, behavior changes, launch risks, and open questions. |
| Designers | Preserves UX intent through clearer flows, affected interfaces, state inventories, accessibility checks, visual proof, and coverage gaps for missing standards. |

## 📊 What The First Evals Show

Early local evals are directional, not benchmark-grade.

| Finding | What Changed |
| --- | --- |
| A lighter Patch path used fewer tokens on one focused performance task, but the heavier workflow found a faster optimization. | Gauntlet separates Patch mode from Deep depth for small-surface work where performance, security, reliability, or data integrity justify deeper search. |
| Release mode cost more than direct development on one broader product-performance task, but produced stronger review artifacts and caught a real progress-state regression during adversarial review. | Gauntlet keeps stronger claims tied to measured proof, not blanket promises. |
| The old review artifact became heavier than the decisions it preserved. | v2.0.1 keeps durable repo memory but makes the default artifact a Markdown receipt. |

The current claim is not "Gauntlet always writes better code." The claim is that Gauntlet helps agents think through features before building them, check that the result hangs together, and escalate proof only when the work earns it.

## 🧾 Run Logs

For Feature and Release work, or any Tier 2/3 task with material decisions or exceptions, Gauntlet writes:

```text
docs/gauntlet-runs/YYYY-MM-DD-<slug>.md
```

The run log is exceptions-first. It records only what future agents would regret losing:

- Material assumptions.
- Non-obvious decisions.
- Things that went wrong.
- Checks skipped or proof that could not be completed.
- `Cannot verify` items and follow-ups.
- For Release, a compact proof summary or launch cut line when it affects risk.

Routine successful checks stay in the final chat summary. The run log should feel like a receipt, not a project report.

## Local Product Documents

Private local PRDs, research, decisions, plans, and run history use the default-on profile. It materializes only when a covered document task needs it:

```sh
python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs ensure \
  --project-root "$PROJECT_ROOT" \
  --epic-prefix PROJECT
```

The profile creates ignored `doc_org.md` and `local-docs/` paths in the primary worktree through Git's local exclude file. It never repurposes or ignores the repository's tracked `docs/` directory. Linked implementation worktrees read the primary copies and return durable updates to the main task. To opt out for one project, run `python3 "$GAUNTLET_ROOT/scripts/gauntlet.py" docs disable --project-root "$PROJECT_ROOT"`; `docs enable` removes that project's marker.

`doc_org.md` owns one release contract. A human-readable PRD may contain multiple Epics organized by stable Scope Areas; only its explicit build-ready target compiles into the generated Ticket Graph. The resulting Execution Run keeps authoritative state on disk, survives conversation compaction, gives each child only bounded context, and verifies tickets individually and in meaningful cohorts before full PRD proof. See [docs/local-documentation.md](docs/local-documentation.md) and [docs/prd-execution.md](docs/prd-execution.md).

“Implement the PRD” carries that accepted target through branch/worktree setup, implementation, proof, PR, merge, specified deployment and production changes, verification, rollback when required, durable updates, and cleanup. It stops rather than guessing when authority, credentials, safety, rollout/rollback validity, or required production proof is missing.

## 🧰 Skill Quality Bar

[docs/skill-quality-bar.md](docs/skill-quality-bar.md) is the reference for creating or meaningfully changing Gauntlet skills, role skills, workflow guidance, eval guidance, or skill-like checklists.

The baseline bar asks whether the change creates a practical behavior delta, has a clear trigger, defines completion and output, steers positively, prunes no-op prose, uses progressive disclosure, and keeps cheap harness mechanics such as schemas, bounded attempt notes, and `Cannot verify` slots where they help. The escalation bar is reserved for high-impact work that earns extra tokens: forward-test scenarios, adversarial skill review, two-attempt Deep planning, impact proof review, or parallel reviewer lanes.

Gauntlet credits Matt Pocock's `writing-great-skills` for the skill-writing vocabulary that informs this reference, while keeping Gauntlet's applied bar in its own docs.

## 🕳 Coverage Gaps

Coverage gaps live in [docs/coverage-gaps.md](docs/coverage-gaps.md). They are pending candidates, not standards.

Agents may add or update a gap when a run exposes missing reusable guidance:

- A material assumption was needed because no rule/reference existed.
- A reviewer says the same issue keeps coming up.
- A finding is `Cannot verify` because the expected standard is missing.
- The same class of issue appears across multiple run logs.
- A lint/check cannot decide safely without product context.
- A rule has too many exceptions and should move back to guidance.

A human decides whether a candidate becomes a rule, reference, exemplar, lint, eval, coverage gap, or no change.

## 🧭 UI Constitution

[docs/ui-constitution.md](docs/ui-constitution.md) is the lightweight frontend quality gate. It is not a design system. It runs for substantial frontend work, major prototype surfaces, broad responsive/state changes, or repeated UI findings; it stays out of narrow Patch work.

The pass routes reliable code-detectable issues to [docs/design-lint-candidates.md](docs/design-lint-candidates.md), browser-visible behavior to `black-box-tester`, and workflow/state/product feel to `experience-reviewer`. When a reliable failure with a concrete fix has no reusable guidance, the agent adds or updates a pending `GAP-###` and names it in the final response.

## 🚦 Production Quality Bar

[docs/production-quality-bar.md](docs/production-quality-bar.md) is a near-launch gate for launch-ready, private-beta, production-bound, hardened, or audited work. It checks implementation boundaries, invariants, launch-critical proof, durable state, state machines, operator/user feedback, threat model and redaction policy, release proof, and decision-oriented UI.

It stays out of ordinary Patch work, early prototypes, local demos, copy/config/docs-only tweaks, and UI-only Feature work with no launch intent unless the user asks. Automatable checks belong in CI, local proof scripts, dry-runs, no-mutation tests, release-tag automation, and artifact verification; product and engineering judgment stays with the existing Gauntlet roles.

## 🧪 Design Lint Candidates

[docs/design-lint-candidates.md](docs/design-lint-candidates.md) captures general UI lint ideas that can graduate into linters. The active set is intentionally small:

- Prevent nested modals.
- Prefer radio buttons over selects for 2-3 static options.
- Require accessible names for icon buttons and form controls.
- Require semantic button/link usage.
- Require associated input labels, form semantics for submit flows, appropriate input types, and non-interactive tooltip content.

## ⚡ Install

Copy this into your AI coding agent:

```text
Install Gauntlet globally for my coding agent.

Source repo:
https://github.com/ajsathyan/Gauntlet

Goal:
Make the Gauntlet workflow available across all my projects, not just one repo.

Use the repo's files as the source of truth:
- router/AGENTS.md is the compact portable global workflow/router.
- AGENTS.md is the contributor guide for this repository.
- skills/ contains reusable role skills.
- docs/ contains run-log, coverage-gap, and design-lint guidance.
- scripts/ contains the installer, durability classifier, workflow speedup helpers, skill evals, and skill checks.
- evals/ contains deterministic skill-eval fixtures and baselines.

Install or adapt those files into whatever persistent global instruction, skill, memory, workflow, or config system this agent environment supports.

Before changing anything, inspect the target agent's existing global instructions and configuration. Preserve unrelated user content byte-for-byte. Compare existing guidance with Gauntlet's candidate guidance for semantic conflicts, including voice, tone, verbosity, workflow authority, approval, sandbox, merge, and destructive-action rules. When guidance conflicts, show both conflicting passages to the user, explain the practical difference, and ask which one should remain active. Do not install through an unresolved conflict or silently remove, disable, or rewrite user-owned guidance.

For Codex, Gauntlet's response defaults are:

```toml
model_verbosity = "low"
personality = "none"
```

If either key already has a different value, show the existing and Gauntlet values and ask which to keep. For Claude Code, install the response-style guidance through the managed `CLAUDE.md` import; do not add Codex-only configuration keys.

Preserve these concepts:
- Patch, Feature, and Release build stages
- Standard and Deep depth
- Proof scope: smoke | delta | full | not relevant
- Intake before substantial work
- Exceptions-first Markdown run logs for Feature/Release work
- Pending coverage gaps for missing reusable guidance
- Promotion Brief scans for repeated manual or agent loops after Release or live-ops wrap-up, not ordinary Patch
- Bounded UI constitution checks for substantial frontend work
- Triggered Production Quality Bar checks for near-launch, private-beta, production-bound, hardened, or audited work
- Scoped role skills for planning, implementation, triage, adversarial review, black-box testing, experience review, deep code review, and run-log building

Do not delete or overwrite unrelated existing user instructions. A user's explicit conflict choice authorizes resolving only the identified conflict; preserve the original passage in a user-visible backup before removing it from active instructions.

After installing, tell me:
1. What files you installed or adapted
2. Where you installed them
3. Whether I need to restart or reload anything
4. One quick test I can run to confirm Gauntlet is active
```

Already cloned the repo?

```sh
# Codex
./scripts/install.sh --target codex

# Claude Code
./scripts/install.sh --target claude
```

If the target already contains global instructions, the first install stops before changing files. Later installs stop again when either the user-owned instructions or Gauntlet's candidate guidance has changed since the last acknowledged review. Review the two, resolve or confirm compatibility, then rerun with:

```sh
./scripts/install.sh --target codex --instructions-reviewed
./scripts/install.sh --target claude --instructions-reviewed
```

`--instructions-reviewed` is an acknowledgement, not a conflict override. Do not pass it until the comparison is complete. The installer never removes or rewrites user-owned instructions; it owns only its marked Gauntlet block.

When a voice or response-style passage conflicts, use `--response-style gauntlet` to install Gauntlet's policy or `--response-style existing` to omit Gauntlet's policy while retaining the rest of its workflow. Choosing Gauntlet does not authorize the installer to delete the old passage; deactivate it separately only after the user chooses, and preserve the original in a visible backup.

Use `--check` to run the same marker, instruction-review, and Codex-preference preflight without installing anything. Gauntlet's guarded `closeout execute` command runs this check before it commits or merges, so an unresolved local conflict cannot be discovered only after the repository change lands.

`./scripts/install.sh` defaults to `--target codex`, which installs Gauntlet into `$HOME/.codex` unless `AGENT_HOME` or `GAUNTLET_AGENT_HOME` is set. For Claude Code, use `./scripts/install.sh --target claude` or `GAUNTLET_INSTALL_TARGET=claude ./scripts/install.sh`; this installs into `$HOME/.claude` by default.

The Codex target writes or replaces one Gauntlet managed block inside the agent-home `AGENTS.md`, preserving unrelated instructions outside the block. It also adds `model_verbosity = "low"` and `personality = "none"` as top-level settings in `config.toml`, and installs seven named profiles under `~/.codex/agents/`. The agent installer owns only files recorded in its hash manifest; it refuses unowned collisions and modified managed files, preserves unrelated profiles, and safely removes an unchanged profile only after Gauntlet retires it. Restart or reload Codex after installation so the profiles are discovered.

Ticket routing is deterministic and documented in [docs/custom-agent-routing.md](docs/custom-agent-routing.md). It selects an explicit profile from the Ticket's work class, complexity, risk, authority, proof type, and context shape. The parent remains responsible for integration, pull requests, merges, deployment, production changes, and rollback decisions.

Codex immediately records started subagents in its local native state. Gauntlet's audit exporter durably merges profile, model, reasoning effort, effective sandbox and approval mode, IDs, timestamps, working directory, source, nickname, and token count into `~/.codex/gauntlet/logs/subagents.jsonl`; it never exports prompts or transcript content. Records survive native-state pruning, and a missing or unreadable native database fails without replacing the audit. Refresh or inspect it with:

```sh
python3 ~/.codex/gauntlet/scripts/subagent-audit.py sync
python3 ~/.codex/gauntlet/scripts/subagent-audit.py summary --json
```

When Codex already has a different value, the installer stops before changing any files and prints both the existing and candidate values. After asking the user, rerun with one explicit choice:

```sh
# Use Gauntlet's low-verbosity, no-personality defaults.
./scripts/install.sh --target codex --codex-preferences gauntlet

# Keep existing values while adding only missing Gauntlet defaults.
./scripts/install.sh --target codex --codex-preferences existing

# Leave config.toml completely unchanged.
./scripts/install.sh --target codex --codex-preferences skip
```

The Claude Code target writes or updates `CLAUDE.md` with a managed import block pointing at the installed portable router because Claude Code reads `CLAUDE.md` rather than `AGENTS.md`. The imported router contains the same response-style policy used by Codex, without duplicating it in the adapter. Claude installs do not create or modify `config.toml`.

Both targets reject malformed managed markers and replace their own block idempotently. Shell code cannot reliably decide whether arbitrary prose instructions conflict, so the installation prompt requires the installing agent to perform that semantic comparison, show both conflicting passages, and ask the user. The direct installer stores only hashes of the reviewed user-owned and candidate instructions; it reopens the review gate when either hash changes without copying private instruction text into its state.

Both targets install only the Gauntlet files that live in this repository: the global workflow, Gauntlet role skills, docs, scripts, and eval fixtures. They do not import personal skills or instructions from elsewhere on your machine.

The same `skills/` tree is also distributed as one Gauntlet plugin for Codex and Claude Code. Codex reads `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json`; Claude Code reads `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`. New Gauntlet-owned skills created under `skills/<name>/` enter both bundles automatically. Use the direct installer or the plugin for skills in one environment, not both, to avoid duplicate skill discovery; the direct installer remains the path that installs Gauntlet's always-loaded global router.

Install the shared bundle from GitHub:

```sh
# Codex
codex plugin marketplace add ajsathyan/Gauntlet
codex plugin add gauntlet@gauntlet

# Claude Code
claude plugin marketplace add ajsathyan/Gauntlet
claude plugin install gauntlet@gauntlet
```

The installer also adds a Gauntlet pre-commit hook in this repo. When staged files include `skills/*/SKILL.md` or `skills/*/examples/*`, the hook runs skill text coverage, declared trace-field scorer contracts, and structural lint before the commit can proceed. These checks do not establish live agent behavior. Set `GAUNTLET_SKIP_GIT_HOOKS=1` for headless installs that should not touch git hooks.

## 📦 What Gets Installed

| File Or Directory | Purpose |
| --- | --- |
| [router/AGENTS.md](router/AGENTS.md) | Compact portable global router installed into the target agent home with rendered stable Gauntlet paths. |
| [router/response-style.md](router/response-style.md) | Single response-style policy rendered into the portable router unless the user keeps a conflicting existing style. |
| [agents/codex/](agents/codex) | Seven canonical named Codex profiles with fixed models, reasoning effort, authority boundaries, and quiet return contracts. |
| [AGENTS.md](AGENTS.md) | Repository contributor guide for changing and proving Gauntlet itself; it is not installed as the portable router. |
| `CLAUDE.md` | Claude Code adapter created by `--target claude`; imports the installed Gauntlet `AGENTS.md` through a managed block while preserving existing Claude instructions. |
| [skills/intake/SKILL.md](skills/intake/SKILL.md) | Turns rough intent into an implementable spec. |
| [skills/researcher/SKILL.md](skills/researcher/SKILL.md) | Produces bounded evidence-backed research without importing implementation ceremony. |
| [skills/debugger/SKILL.md](skills/debugger/SKILL.md) | Reproduces and isolates root cause before a fix is implemented. |
| [skills/product-architect/SKILL.md](skills/product-architect/SKILL.md) | Shapes Feature work around workflow, IA, activation, retention, growth, trust, and handoff. |
| [skills/maintain-prd/SKILL.md](skills/maintain-prd/SKILL.md) | Maintains one canonical human-readable multi-Epic PRD without starting implementation. |
| [skills/planner/SKILL.md](skills/planner/SKILL.md) | Converts accepted specs into bounded implementation steps. |
| [skills/issue-triager/SKILL.md](skills/issue-triager/SKILL.md) | Routes plans, findings, test failures, bugs, and open questions into ready tasks. |
| [skills/implementer/SKILL.md](skills/implementer/SKILL.md) | Executes scoped code changes while preserving repo patterns and collecting proof. |
| [skills/implement-prd/SKILL.md](skills/implement-prd/SKILL.md) | Compiles a build-ready PRD into a durable Ticket Graph and coordinates its authorized end-to-end release path. |
| [skills/adversarial-reviewer/SKILL.md](skills/adversarial-reviewer/SKILL.md) | Stress-tests assumptions, edge cases, trust boundaries, and regressions. |
| [skills/black-box-tester/SKILL.md](skills/black-box-tester/SKILL.md) | Validates behavior externally through user-visible outcomes. |
| [skills/experience-reviewer/SKILL.md](skills/experience-reviewer/SKILL.md) | Reviews workflow clarity, IA, states, metrics, accessibility, trust, activation, retention, and growth. |
| [skills/deep-code-reviewer/SKILL.md](skills/deep-code-reviewer/SKILL.md) | Reviews correctness, maintainability, tests, integration risk, and regression risk. |
| [skills/run-log-builder/SKILL.md](skills/run-log-builder/SKILL.md) | Creates exceptions-first run logs and pending coverage-gap candidates. |
| [skills/promotion-scanner/SKILL.md](skills/promotion-scanner/SKILL.md) | Produces bounded Promotion Briefs for repeated manual or agent loops without recommending live operational actions. |
| [skills/archive/SKILL.md](skills/archive/SKILL.md) | Runs the guarded local-install, PR-merge, cleanup, and Codex task-archive sequence when `/Archive` is invoked. |
| [skills/craft-customer-email/SKILL.md](skills/craft-customer-email/SKILL.md) | Writes, revises, and audits customer-facing product, operational, transactional, incident, and lifecycle email. |
| [skills/craft-product-terminology/SKILL.md](skills/craft-product-terminology/SKILL.md) | Creates minimal, responsibility-accurate names for public product concepts and internal system pieces. |
| [skills/refactor-codebase/SKILL.md](skills/refactor-codebase/SKILL.md) | Runs staged behavior-preserving codebase simplification with durable parity evidence and migration gates. |
| [skills/refactor-performance/SKILL.md](skills/refactor-performance/SKILL.md) | Improves measured test or product performance through comparable baselines, profiling, and falsifiable experiments. |
| [skills/eval-audit/SKILL.md](skills/eval-audit/SKILL.md) | Audits whether an LLM evaluation pipeline is trustworthy. |
| [skills/eval-error-analysis/SKILL.md](skills/eval-error-analysis/SKILL.md) | Identifies and categorizes failure modes from LLM traces. |
| [skills/eval-judge-prompt/SKILL.md](skills/eval-judge-prompt/SKILL.md) | Designs binary LLM-as-Judge evaluators for subjective failure modes. |
| [skills/eval-rag/SKILL.md](skills/eval-rag/SKILL.md) | Evaluates retrieval and generation quality in RAG pipelines. |
| [skills/eval-review-interface/SKILL.md](skills/eval-review-interface/SKILL.md) | Builds browser interfaces for reviewing traces and collecting human labels. |
| [skills/eval-synthetic-data/SKILL.md](skills/eval-synthetic-data/SKILL.md) | Generates varied synthetic inputs for LLM evaluation. |
| [skills/eval-validate-evaluator/SKILL.md](skills/eval-validate-evaluator/SKILL.md) | Calibrates an LLM judge against human labels. |
| [docs/upstream-superpowers.md](docs/upstream-superpowers.md) | Attributes adapted techniques and explains selective upstream update review and runtime retirement. |
| [docs/upstream-eval-skills.md](docs/upstream-eval-skills.md) | Records the vendored eval-skill source, namespace mapping, update procedure, and license location. |
| [docs/local-documentation.md](docs/local-documentation.md) | Defines the default-on lazy local-document profile, explicit project opt-out, tracked/private boundary, canonical primary-worktree rule, and release/configuration contracts. |
| [docs/prd-execution.md](docs/prd-execution.md) | Defines PRD/Epic/Scope Area/Ticket Graph terminology, durable execution artifacts, ready-queue scheduling, bounded child context, verification layers, and end-to-end implementation authority. |
| [docs/custom-agent-routing.md](docs/custom-agent-routing.md) | Defines deterministic Ticket-to-profile selection, escalation, bounded context, and audit requirements. |
| [docs/coverage-gaps.md](docs/coverage-gaps.md) | Pending missing-guidance candidates. |
| [docs/github-discipline.md](docs/github-discipline.md) | Beginner-friendly branch, worktree, commit, PR, merge, child-chat, and solo-builder defaults. |
| [docs/ui-constitution.md](docs/ui-constitution.md) | Bounded frontend quality gate for prototypes and product UI. |
| [docs/production-quality-bar.md](docs/production-quality-bar.md) | Near-launch quality gate for boundaries, invariants, durable state, state machines, release proof, threat/redaction, feedback loops, and decision-oriented UI. |
| [docs/workflow-speedups.md](docs/workflow-speedups.md) | Advisory changed-surface, test-planning, review-packet, and child-dispatch guidance. |
| [docs/promotion-scanner.md](docs/promotion-scanner.md) | Trigger policy and gap-routing guidance for promotion scans. |
| [docs/design-lint-candidates.md](docs/design-lint-candidates.md) | General lint ideas for project-specific UI checks. |
| [scripts/gauntlet.py](scripts/gauntlet.py) | Deterministic CLI for guarded one-command closeout, merge/archive actions, analytics, install verification, follow-up packets, compatibility memory linting, and PR/changelog drafts. |
| [templates/local-docs/](templates/local-docs) | Scaffolds `doc_org.md`, the local index, epic PRDs, research, decisions, implementation plans, and run logs. |
| [scripts/install.sh](scripts/install.sh) | Installs the global workflow, skills, docs, scripts, and evals with instruction-conflict preflight and conflict-aware Codex response defaults. |
| [scripts/install-codex-agents.py](scripts/install-codex-agents.py) | Validates, installs, retires, and verifies Gauntlet-owned Codex profiles without overwriting user-owned agents. |
| [scripts/subagent-audit.py](scripts/subagent-audit.py) | Idempotently exports privacy-bounded Gauntlet subagent usage from Codex native local state. |
| [scripts/route-codex-agent.py](scripts/route-codex-agent.py) | Deterministically maps validated Ticket routing fields to an explicit named Codex profile. |
| [scripts/classify-ts-durability.sh](scripts/classify-ts-durability.sh) | Classifies whether TypeScript durability standards are required for the current work. |
| [scripts/diff-intel.py](scripts/diff-intel.py) | Writes advisory changed-file, package-root, risk-trigger, dirty-worktree, confidence, and `Cannot verify` intel. |
| [scripts/test-plan.py](scripts/test-plan.py) | Recommends focused and broader verification commands from diff intel without defaulting to huge suites. |
| [scripts/review-pack.py](scripts/review-pack.py) | Generates a bounded, redacted review packet from diff intel, accepted spec/plan context, and test-plan summaries. |
| [scripts/check-superpowers-sync.py](scripts/check-superpowers-sync.py) | Reports upstream Superpowers technique changes and affected Gauntlet destinations. |
| [scripts/retire-superpowers.py](scripts/retire-superpowers.py) | Reversibly retires allowlisted active Superpowers skills and disables the plugin. |
| [scripts/run-skill-evals.py](scripts/run-skill-evals.py) | Runs deterministic one-shot/current/new skill-text coverage and one positive/negative phrase-matcher contract. |
| [scripts/run-orchestration-evals.py](scripts/run-orchestration-evals.py) | Unit-tests hand-authored outcome, action, authority, proof, routing, output-budget, cost, and latency fields. It does not observe agent behavior or resolve proof references. |
| [scripts/lint-skills.py](scripts/lint-skills.py) | Lints skill frontmatter, word budget, contract slots, optional examples, and bounded subagent guidance. |
| [scripts/run-skill-change-checks.sh](scripts/run-skill-change-checks.sh) | Runs skill text coverage, declared trace-field scorer contracts, and linting when staged Gauntlet skill files change. |
| [scripts/install-git-hooks.sh](scripts/install-git-hooks.sh) | Installs the pre-commit hook that enforces skill-change checks. |
| [scripts/prd-run.py](scripts/prd-run.py) | Creates, validates, resumes, and advances deterministic disk-backed PRD Execution Runs. |
| [evals/skill-evals.json](evals/skill-evals.json) | Pressure scenarios for skill contract coverage. |
| [evals/scorer-smoke-fixtures.json](evals/scorer-smoke-fixtures.json) | One positive and one negative matcher canary that prove phrase-scorer wiring—not agent behavior. |
| [evals/orchestration-trace-fixtures.json](evals/orchestration-trace-fixtures.json) | Paired declared trace-field scorer cases, including wrong-outcome, self-attested-proof, different-prose, authority, verbosity, and subjective-judgment canaries. |
| [evals/baselines/current/skills](evals/baselines/current/skills) | Frozen current-skill baseline used by the three-arm evals. |

## 🧠 Inspiration

Gauntlet is partly inspired by Simon Last's framing of agent work as a higher-throughput software factory: the bottleneck moves from typing code to shaping clear specs, boundaries, and review loops so agents can keep working.

It is also influenced by Vercel's product-design guidance pattern: accepted decisions live near the code, repeated mechanical checks graduate into linters, missing standards stay visible as coverage gaps, and humans approve what becomes guidance.

Gauntlet combines those ideas into a product-thinking harness: define the feature clearly, choose the right build stage and proof scope, let the agent keep moving, and leave small durable repo memory behind.

Selected techniques are adapted from Jesse Vincent's [Superpowers](https://github.com/obra/superpowers) under MIT. The version/hash update map lives in [docs/upstream-superpowers.md](docs/upstream-superpowers.md); Superpowers is not a runtime dependency.

## 📚 Repository Files

| File | Purpose |
| --- | --- |
| [router/AGENTS.md](router/AGENTS.md) | Portable global workflow router. |
| [router/response-style.md](router/response-style.md) | Portable response-style policy rendered by the installer. |
| [.codex-plugin/plugin.json](.codex-plugin/plugin.json) | Codex plugin manifest for the shared Gauntlet skill bundle. |
| [.claude-plugin/plugin.json](.claude-plugin/plugin.json) | Claude Code plugin manifest for the shared Gauntlet skill bundle. |
| [.agents/plugins/marketplace.json](.agents/plugins/marketplace.json) | Codex marketplace entry for installing the bundle. |
| [.claude-plugin/marketplace.json](.claude-plugin/marketplace.json) | Claude Code marketplace entry for installing the bundle. |
| [AGENTS.md](AGENTS.md) | Contributor guidance for this repository. |
| [skills/](skills) | Role-specific reusable instructions. |
| [docs/](docs) | Coverage gaps, UI constitution, Production Quality Bar, workflow speedups, promotion scanner, design lint candidates, and historical plans. |
| [templates/](templates) | Reusable downstream scaffolds, including the default-on local product-document profile. |
| [scripts/](scripts) | Installer, durability classifier, workflow speedup helpers, workflow checks, skill evals, and skill linter. |
| [evals/](evals) | Skill coverage, scorer-smoke, orchestration-trace fixtures, and baselines. |
| [LICENSE](LICENSE) | MIT license. |

## 📄 License

MIT. See [LICENSE](LICENSE).
