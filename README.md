# Gauntlet

A model-agnostic workflow harness for shaping, running, and reviewing coding-agent work.

<p>
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-3fb950?style=for-the-badge"></a>
  <a href="AGENTS.md"><img alt="Workflow" src="https://img.shields.io/badge/workflow-global-0969da?style=for-the-badge"></a>
  <a href="skills"><img alt="Role skills" src="https://img.shields.io/badge/role_skills-10-8957e5?style=for-the-badge"></a>
  <a href="templates/review-brief.html"><img alt="Review brief" src="https://img.shields.io/badge/review_brief-template-f778ba?style=for-the-badge"></a>
</p>

<p>
  <a href="#-at-a-glance">At A Glance</a> |
  <a href="#-build-stages">Build Stages</a> |
  <a href="#-how-to-choose-a-stage">How To Choose</a> |
  <a href="#-install">Install</a> |
  <a href="#-review-briefs">Review Briefs</a> |
  <a href="#-license">License</a>
</p>

Gauntlet helps engineers, PMs, and designers spend more time refining specs, scope, acceptance criteria, and review surfaces before an agent runs. Instead of treating every task as "prompt, wait, inspect, prompt again," it gives teams a shared vocabulary for deciding what kind of work is being done and how much proof it deserves.

Coding agents make implementation cheaper, but they make specification, orchestration, and review more important. Gauntlet is built around a simple bet: better-scoped work produces better agent runs, different tasks deserve different amounts of process, and humans need review briefs, not just a final diff.

## ✨ At A Glance

| Capability | What You Get |
| --- | --- |
| Intake | Turns rough intent into scope, boundaries, acceptance criteria, assumptions, and proof. |
| Build stages | Routes work through Patch, Deep Patch, Slice, or Release based on scope, risk, and desired rigor. |
| Role skills | Adds product architecture, planning, triage, implementation, adversarial review, black-box testing, experience review, and deep code review when useful. |
| Review briefs | Gives engineers, PMs, and designers a Review/Details/Changelog surface that prioritizes human decisions, proof gaps, and compact agent follow-up prompts. |
| Live review surface | Serves `review-brief.html` with `review-brief-data.json` so decisions, deviations, tradeoffs, open questions, proof, and quantitative impact stay visible while work happens. |
| Model portability | Installs as reusable instructions, skills, templates, and scripts that can be adapted to different agent environments. |

## 🧭 Build Stages

| Stage | Best For | What It Optimizes |
| --- | --- | --- |
| Patch | Small, focused changes | Speed and low overhead. |
| Deep Patch | Small surface, high-upside work | Maximum reasonable performance, security, reliability, or correctness. |
| Slice | High-fidelity product features and workflows | AI-native prototyping and product handoff. |
| Release | Production-bound or risky changes | Deeper verification, review, and regression control. |

## 🎯 How To Choose A Stage

| Signal | Recommended Stage |
| --- | --- |
| Clear copy, config, polish, or narrow bug fix | Patch |
| Small code surface where the best answer matters | Deep Patch |
| Product workflow, onboarding, activation, retention, growth, IA, or design-heavy work | Slice |
| Auth, billing, migrations, data integrity, privacy, uploads, concurrency, public APIs, large refactors, weak-test areas, or deploy-sensitive work | Release |

The rule has two parts:

```text
Choose the lightest stage for the change shape.
Choose the depth that matches the value of finding the best answer.
```

Mode is about scope and risk surface. Depth is about search effort. A performance optimization can be a tiny patch and still deserve Deep Patch if "fastest reasonable result" matters more than minimizing tokens.

## 👥 Who It Helps

| Audience | How Gauntlet Helps |
| --- | --- |
| Engineers | Turns broad requests into scoped, verifiable implementation work, adds review loops for risky changes, and produces developer review briefs that prioritize the risky parts of the diff. |
| PMs | Makes product intent executable by clarifying scope, non-goals, acceptance criteria, assumptions, behavior changes, launch risks, and open questions. |
| Designers | Preserves UX intent through clearer flows, affected interfaces, state inventories, accessibility checks, visual proof, and visible deviations from the original spec. |

## 📊 What The First Evals Show

Early local evals are directional, not benchmark-grade.

| Finding | What Changed |
| --- | --- |
| A lighter Patch path used fewer tokens on one focused performance task, but the heavier workflow found a faster optimization. | Gauntlet added Deep Patch for small-surface work where performance, security, reliability, or data integrity justify deeper search. |
| Release mode cost more than direct development on one broader product-performance task, but produced stronger review artifacts and caught a real progress-state regression during adversarial review. | Gauntlet keeps stronger claims tied to measured proof, not blanket promises. |

The current claim is not "Gauntlet always writes better code." The claim is that Gauntlet makes agent work more structured, reviewable, and measurable, with explicit tradeoffs between speed, cost, rigor, and human handoff.

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
- templates/ contains the review brief shell, schema, and example data.
- scripts/ contains the installer, review brief initializer/server, and validator.

Install or adapt those files into whatever persistent global instruction, skill, memory, workflow, or config system this agent environment supports.

Preserve these concepts:
- Patch, Deep Patch, Slice, and Release build stages
- Intake before substantial work
- Review/Details/Changelog briefs for Slice and Release work
- Live review-brief.html plus review-brief-data.json when progress should be visible during Tier 2/3 work
- Role skills for planning, implementation, triage, adversarial review, black-box testing, experience review, and deep code review

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

## 🔎 Review Briefs

For Slice and Release work, Gauntlet can create a human review surface:

```text
Review -> Details -> Changelog
```

The brief is designed for a solo reviewer first: open it, see the top decisions and proof gaps, inspect one item, then copy a compact handle-based prompt for the next agent.

Recommended generated files:

```text
review-brief.html
review-brief-data.json
review-brief-data.schema.json
review-brief-assets/
```

To initialize a live review brief from a project root:

```sh
path/to/Gauntlet/scripts/init-review-brief.sh
```

To serve a review brief from a project root:

```sh
path/to/Gauntlet/scripts/serve-review-brief.sh
```

The review shell treats generated data as untrusted text, uses stable handles like `RB-002` and `CU-001`, and avoids falling back to sample data when real review data is missing.

## 📦 What Gets Installed

| File Or Directory | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Global router for task tiers, intake, stage selection, role skills, review briefs, stop conditions, and completion rules. |
| [skills/intake/SKILL.md](skills/intake/SKILL.md) | Turns rough intent into an implementable spec. |
| [skills/product-architect/SKILL.md](skills/product-architect/SKILL.md) | Shapes Slice work around workflow, IA, activation, retention, growth, trust, and handoff. |
| [skills/planner/SKILL.md](skills/planner/SKILL.md) | Converts accepted specs into bounded implementation slices. |
| [skills/issue-triager/SKILL.md](skills/issue-triager/SKILL.md) | Routes plans, findings, test failures, bugs, and open questions into ready tasks. |
| [skills/implementer/SKILL.md](skills/implementer/SKILL.md) | Executes scoped code changes while preserving repo patterns and collecting proof. |
| [skills/adversarial-reviewer/SKILL.md](skills/adversarial-reviewer/SKILL.md) | Stress-tests assumptions, edge cases, trust boundaries, and regressions. |
| [skills/black-box-tester/SKILL.md](skills/black-box-tester/SKILL.md) | Validates behavior externally through user-visible outcomes. |
| [skills/experience-reviewer/SKILL.md](skills/experience-reviewer/SKILL.md) | Reviews workflow clarity, IA, states, metrics, accessibility, trust, activation, retention, and growth. |
| [skills/deep-code-reviewer/SKILL.md](skills/deep-code-reviewer/SKILL.md) | Reviews correctness, maintainability, tests, integration risk, and regression risk. |
| [skills/review-brief-builder/SKILL.md](skills/review-brief-builder/SKILL.md) | Builds human review briefs for Slice and Release work. |
| [templates/review-brief.html](templates/review-brief.html) | Human review brief template. |
| [templates/review-brief-data.schema.json](templates/review-brief-data.schema.json) | Data contract for generated review briefs. |
| [templates/review-brief-data.example.json](templates/review-brief-data.example.json) | Example review brief data for local testing. |
| [scripts/install.sh](scripts/install.sh) | Installs the global workflow, skills, templates, and scripts. |
| [scripts/init-review-brief.sh](scripts/init-review-brief.sh) | Initializes a live review brief shell, schema, data file, and assets folder. |
| [scripts/serve-review-brief.sh](scripts/serve-review-brief.sh) | Starts a localhost server for a generated review brief and sidecar JSON. |
| [scripts/validate-review-brief-data.py](scripts/validate-review-brief-data.py) | Validates review brief JSON handles, enums, links, and proof state. |

## 🧠 Inspiration

Gauntlet is partly inspired by [Simon Last's framing of agent work](https://x.com/simonlast/status/2057978156183957995?s=20) as a higher-throughput software factory: the bottleneck moves from typing code to shaping clear specs, boundaries, and review loops so agents can keep working.

It is also inspired by [trq212's implementation-notes pattern](https://x.com/trq212/status/2056415973125796184?s=20): long agent runs become easier to trust when decisions, deviations, tradeoffs, and open questions are captured while the work happens. Gauntlet adapts that idea into the review brief Changelog rather than a separate implementation notes file.

Gauntlet combines those ideas into a workflow harness: define the work clearly, choose the right build stage, let the agent keep moving, and give humans a review surface that explains what changed and why.

## 📚 Repository Files

| File | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Global workflow instructions. |
| [skills/](skills) | Role-specific reusable instructions. |
| [templates/](templates) | Review brief shell, schema, and example data. |
| [scripts/](scripts) | Installer, review brief server, initializer, and validator. |
| [LICENSE](LICENSE) | MIT license. |

## 📄 License

MIT. See [LICENSE](LICENSE).
