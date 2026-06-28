# Gauntlet

A model-agnostic prototyping harness for shaping, running, reviewing, and remembering coding-agent work with subagents.

<p>
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-3fb950?style=for-the-badge"></a>
  <a href="https://github.com/ajsathyan/Gauntlet/releases/tag/v2.0.1"><img alt="Version" src="https://img.shields.io/badge/version-v2.0.1-111827?style=for-the-badge"></a>
  <a href="AGENTS.md"><img alt="Workflow" src="https://img.shields.io/badge/workflow-global-0969da?style=for-the-badge"></a>
  <a href="skills"><img alt="Role skills" src="https://img.shields.io/badge/role_skills-10-8957e5?style=for-the-badge"></a>
  <a href="docs/coverage-gaps.md"><img alt="Coverage gaps" src="https://img.shields.io/badge/coverage_gaps-pending-f778ba?style=for-the-badge"></a>
</p>

<p>
  <a href="#-at-a-glance">At A Glance</a> |
  <a href="#v201-run-log-harness">v2.0.1</a> |
  <a href="#-build-stages">Build Stages</a> |
  <a href="#-run-logs">Run Logs</a> |
  <a href="#-coverage-gaps">Coverage Gaps</a> |
  <a href="#-install">Install</a>
</p>

Gauntlet helps engineers, PMs, and designers spend more time refining specs, scope, acceptance criteria, and reusable repo memory before an agent runs. Instead of treating every task as "prompt, wait, inspect, prompt again," it gives teams a shared vocabulary for deciding what kind of work is being done, how much proof it deserves, and which decisions should survive the chat.

Coding agents make implementation cheaper, but they make specification, orchestration, and review more important. Gauntlet v2.0.1 keeps the workflow strict where risk demands it and lighter where ceremony got in the way: durable context is now an exceptions-first Markdown run log plus pending coverage gaps, not a separate review product.

## v2.0.1: Run Log Harness

Gauntlet v2.0.1 replaces the default review surface with a small **Run Log** and a candidate **Coverage Gap** loop inspired by repo-local product-design guidance patterns.

The workflow is built around Patch, Feature, and Release modes; Standard and Deep depth; run logs; release panel guardrails; architecture hygiene; TypeScript durability classification; skill-change evals; and design lint candidates. The intent is still not to add process everywhere. It is to apply just enough structure that long agent runs stay bounded, verifiable, and easier to pick up later.

## ✨ At A Glance

| Capability | What You Get |
| --- | --- |
| Intake | Turns rough intent into scope, boundaries, acceptance criteria, assumptions, and proof. |
| Build stages | Routes work through Patch, Feature, or Release based on scope and risk, with Standard or Deep depth chosen separately. |
| Role skills | Adds product architecture, planning, triage, implementation, adversarial review, black-box testing, experience review, and deep code review when useful. |
| Run logs | Writes a tiny exceptions-first Markdown receipt for material Feature/Release work: assumptions, decisions, skipped checks, failures, `Cannot verify`, and follow-ups. |
| Coverage gaps | Captures pending candidates when missing reusable guidance forced a material assumption or repeated review finding. |
| Design lint candidates | Documents Vercel-inspired UI lint ideas such as nested modal prevention, accessible names, focus token checks, and static select-to-radio guidance. |
| Model portability | Installs as reusable instructions, skills, docs, scripts, and evals that can be adapted to different agent environments. |

## 🧭 Build Stages

| Stage | Best For | What It Optimizes |
| --- | --- | --- |
| Patch | Small, focused changes | Speed and low overhead. |
| Feature | High-fidelity product features and workflows | AI-native prototyping and product handoff. |
| Release | Production-bound or risky changes | Deeper verification, review, and regression control. |

## 🎯 How To Choose A Stage

| Signal | Recommended Stage |
| --- | --- |
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

The current claim is not "Gauntlet always writes better code." The claim is that Gauntlet makes agent work more structured, reviewable, and measurable, with explicit tradeoffs between speed, cost, rigor, and human handoff.

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

## 🧪 Design Lint Candidates

[docs/design-lint-candidates.md](docs/design-lint-candidates.md) captures UI lint ideas that can graduate into project-specific checks. The first set mirrors patterns named in Vercel's product-design post:

- Prevent nested modals.
- Prefer radio buttons over selects for 2-3 static options.
- Require accessible names for icon buttons and form controls.
- Reject custom focus rings that bypass shared focus tokens.
- Prevent ad hoc visual overrides of design-system components.
- Require a modal body/content primitive when overflow is possible.
- Prefer theme-aware shadows and component-owned borders.
- Flag arbitrary spacing off a 4px grid.
- Autofix safe deprecated Tailwind utility migrations.

## ⚡ Install

Copy this into your AI coding agent:

```text
Install Gauntlet globally for my coding agent.

Source repo:
https://github.com/ajsathyan/Gauntlet

Goal:
Make the Gauntlet workflow available across all my projects, not just one repo.

Use the repo's files as the source of truth:
- AGENTS.md is the global workflow/router.
- skills/ contains reusable role skills.
- docs/ contains run-log, coverage-gap, and design-lint guidance.
- scripts/ contains the installer, durability classifier, skill evals, and skill checks.
- evals/ contains deterministic skill-eval fixtures and baselines.

Install or adapt those files into whatever persistent global instruction, skill, memory, workflow, or config system this agent environment supports.

Preserve these concepts:
- Patch, Feature, and Release build stages
- Standard and Deep depth
- Intake before substantial work
- Exceptions-first Markdown run logs for Feature/Release work
- Pending coverage gaps for missing reusable guidance
- Role skills for planning, implementation, triage, adversarial review, black-box testing, experience review, deep code review, and run-log building

Do not delete or overwrite unrelated existing user instructions. Merge carefully.

After installing, tell me:
1. What files you installed or adapted
2. Where you installed them
3. Whether I need to restart or reload anything
4. One quick test I can run to confirm Gauntlet is active
```

Already cloned the repo?

```sh
./scripts/install.sh
```

The installer also adds a Gauntlet pre-commit hook in this repo. When staged files include `skills/*/SKILL.md` or `skills/*/examples/*`, the hook runs the skill evals and skill linter before the commit can proceed. Set `GAUNTLET_SKIP_GIT_HOOKS=1` for headless installs that should not touch git hooks.

## 📦 What Gets Installed

| File Or Directory | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Global router for task tiers, intake, stage selection, role skills, run logs, stop conditions, and completion rules. |
| [skills/intake/SKILL.md](skills/intake/SKILL.md) | Turns rough intent into an implementable spec. |
| [skills/product-architect/SKILL.md](skills/product-architect/SKILL.md) | Shapes Feature work around workflow, IA, activation, retention, growth, trust, and handoff. |
| [skills/planner/SKILL.md](skills/planner/SKILL.md) | Converts accepted specs into bounded implementation steps. |
| [skills/issue-triager/SKILL.md](skills/issue-triager/SKILL.md) | Routes plans, findings, test failures, bugs, and open questions into ready tasks. |
| [skills/implementer/SKILL.md](skills/implementer/SKILL.md) | Executes scoped code changes while preserving repo patterns and collecting proof. |
| [skills/adversarial-reviewer/SKILL.md](skills/adversarial-reviewer/SKILL.md) | Stress-tests assumptions, edge cases, trust boundaries, and regressions. |
| [skills/black-box-tester/SKILL.md](skills/black-box-tester/SKILL.md) | Validates behavior externally through user-visible outcomes. |
| [skills/experience-reviewer/SKILL.md](skills/experience-reviewer/SKILL.md) | Reviews workflow clarity, IA, states, metrics, accessibility, trust, activation, retention, and growth. |
| [skills/deep-code-reviewer/SKILL.md](skills/deep-code-reviewer/SKILL.md) | Reviews correctness, maintainability, tests, integration risk, and regression risk. |
| [skills/run-log-builder/SKILL.md](skills/run-log-builder/SKILL.md) | Creates exceptions-first run logs and pending coverage-gap candidates. |
| [docs/coverage-gaps.md](docs/coverage-gaps.md) | Pending missing-guidance candidates. |
| [docs/design-lint-candidates.md](docs/design-lint-candidates.md) | Vercel-inspired lint ideas for project-specific UI checks. |
| [scripts/install.sh](scripts/install.sh) | Installs the global workflow, skills, docs, scripts, and evals. |
| [scripts/classify-ts-durability.sh](scripts/classify-ts-durability.sh) | Classifies whether TypeScript durability standards are required for the current work. |
| [scripts/run-skill-evals.py](scripts/run-skill-evals.py) | Runs deterministic one-shot/current/new skill evals. |
| [scripts/lint-skills.py](scripts/lint-skills.py) | Lints skill frontmatter, word budget, contract slots, optional examples, and bounded subagent guidance. |
| [scripts/run-skill-change-checks.sh](scripts/run-skill-change-checks.sh) | Runs skill evals and linting when staged Gauntlet skill files change. |
| [scripts/install-git-hooks.sh](scripts/install-git-hooks.sh) | Installs the pre-commit hook that enforces skill-change checks. |
| [evals/skill-evals.json](evals/skill-evals.json) | Pressure scenarios for skill contract coverage. |
| [evals/behavior-fixtures.json](evals/behavior-fixtures.json) | Five-rep smoke fixtures for behavioral skill-eval scoring and metrics. |
| [evals/baselines/current/skills](evals/baselines/current/skills) | Frozen current-skill baseline used by the three-arm evals. |

## 🧠 Inspiration

Gauntlet is partly inspired by Simon Last's framing of agent work as a higher-throughput software factory: the bottleneck moves from typing code to shaping clear specs, boundaries, and review loops so agents can keep working.

It is also influenced by Vercel's product-design guidance pattern: accepted decisions live near the code, repeated mechanical checks graduate into linters, missing standards stay visible as coverage gaps, and humans approve what becomes guidance.

Gauntlet combines those ideas into a workflow harness: define the work clearly, choose the right build stage, let the agent keep moving, and leave small durable repo memory behind.

## 📚 Repository Files

| File | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Global workflow instructions. |
| [skills/](skills) | Role-specific reusable instructions. |
| [docs/](docs) | Coverage gaps, design lint candidates, and historical plans. |
| [scripts/](scripts) | Installer, durability classifier, workflow checks, skill evals, and skill linter. |
| [evals/](evals) | Skill eval definitions, behavior fixtures, and baselines. |
| [LICENSE](LICENSE) | MIT license. |

## 📄 License

MIT. See [LICENSE](LICENSE).
