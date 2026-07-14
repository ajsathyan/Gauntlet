# Global Router Rule Map

This map prevents the compact global router from becoming a silent rule deletion. The source column refers to the pre-split `AGENTS.md` on `main`. `Keep` means the installed router must retain the invariant; `Move` means the detailed procedure lives in the named triggered source; `Replace` means a narrower executable contract supersedes the prose; `Delete` means the text is duplicate or creates false assurance.

| Current source | Decision | Router invariant | Detailed destination |
| --- | --- | --- | --- |
| Normal Request path | Add | Bounded, low-consequence, reversible, directly checkable work delivers the artifact first, uses proportional proof, and bypasses lifecycle ceremony. Explicit narrow scope controls unless a real safety or authority boundary appears. | `docs/workflow-etiquette.md` |
| Modes | Keep + move | Choose Patch, Feature, or Release from change shape and risk. | `docs/workflow-etiquette.md` and role skills |
| Depth | Keep + move | Use Deep only when search value or consequence earns it. | `docs/skill-quality-bar.md`, reviewer skills |
| Proof Scope | Keep + move | Prove changed behavior with an observable oracle; distinguish structural coverage and self-report from execution-backed outcomes. | `docs/meaningful-proof.md`, role skills, and `docs/production-quality-bar.md` |
| Workflow Etiquette | Keep + move | Ask only material questions; otherwise execute autonomously and quietly. | `docs/workflow-etiquette.md` |
| Minimum useful questions | Keep + move | Every skill uses existing context, asks at most three short single-decision questions only when the answer is consequential, and otherwise provides a provisional result. | `docs/workflow-etiquette.md` |
| Local product documents | Add + move | Default-on local documents materialize lazily in the primary worktree unless `.gauntlet/doc-org.disabled` opts the project out; tracked repository documentation and the existing Gauntlet lifecycle remain intact. | `docs/local-documentation.md` and relevant role skills |
| PRD execution contract | Add + move | A multi-Epic PRD remains the human source; only its build-ready target compiles into a durable Ticket Graph and end-to-end Execution Run. | `docs/prd-execution.md`, `docs/local-documentation.md`, planner and `implement-prd` |
| Priority/title mechanics | Move | Classification is internal unless it changes scope, cost, authority, proof, or a user decision. | `docs/workflow-etiquette.md` |
| Edge-case and scope-delta foresight | Keep + move | Resolve material edge cases and additions before implementation. | `intake`, `planner`, `docs/workflow-etiquette.md` |
| Git Discipline | Keep + move | Preserve dirty work, branch/worktree broad changes, use PRs as proof bundles. | Repository `AGENTS.md`, `docs/github-discipline.md` |
| Execution integration topology | Add + move | Keep `main` clean and freeze the PR strategy at run initialization: small targets use one complete Project PR; large tightly coupled targets may use parent-owned Review Unit PRs into the integration branch before one complete Project PR; independently shippable outcomes use separate runs. | `docs/prd-execution.md`, `docs/github-discipline.md`, `docs/local-documentation.md`, `skills/implement-prd/references/execution-contract.md` |
| Merge and archive procedures | Keep + move | Preserve accepted merge/archive authority; distinguish push, PR, merge, and archive requests; deterministic safety checks precede execution. | `docs/github-discipline.md`, `docs/workflow-etiquette.md`, installed `gauntlet` launcher help |
| Workflow Speedup Helpers | Move | Use helpers when their output replaces manual setup. | `docs/workflow-speedups.md`, stable installed launcher |
| Skill Quality Bar | Keep + move | Meaningful skill changes need behavior, trigger, completion, negative cases, and honest proof. | `docs/skill-quality-bar.md` |
| Promotion Scanner | Move | Promote repeated evidence only; humans approve durable standards. | `promotion-scanner`, `docs/promotion-scanner.md` |
| Task Tiers | Move | Consequence controls scope and proof. | `intake`, `docs/workflow-etiquette.md` |
| Release Panel Guardrails | Keep + move | A blocker needs concrete harm, no acceptable fallback, executable proof, and plan delta. | `planner`, `issue-triager`, `docs/production-quality-bar.md` |
| Production Quality Bar | Keep + move | Trigger only for launch/hardening risk; cap the pass and define exit proof. | `docs/production-quality-bar.md` |
| Current-Change Hygiene | Keep + move | Broad/Feature/Release work checks current-change cruft before completion. | `deep-code-reviewer`, repository `AGENTS.md` |
| TypeScript Durability Gate | Keep + move | Apply only when the classifier or explicit user request triggers it. | stable installed classifier path and `docs/workflow-etiquette.md` |
| Decision Log Gate | Keep + move | Durable logs are exceptions-first, not proof dumps. | `run-log-builder`, `docs/gauntlet-runs/` |
| Occasional/Systemic Checks | Move | Full sweeps require a concrete trigger. | Relevant role docs and skills |
| Coverage Gaps | Keep + move | Record only missing reusable guidance; remove resolved gaps. | `run-log-builder`, `docs/coverage-gaps.md` |
| Frontend Quality Gate | Keep + move | Substantial frontend work uses bounded code/browser/experience proof. | UI references and reviewer skills |
| Intake Gate | Keep + move | Establish scope, acceptance, proof, constraints, and material questions before substantial work. | `intake` |
| Role Skills | Keep + move | Route to the narrowest role skill that adds concrete value. | `skills/*/SKILL.md` |
| Child Ticket | Keep + simplify | A Ticket is a generated execution assignment within the current plan or Execution Run; the main task dispatches one bounded Ticket per child and coordinates through native state. | `planner`, `implementer`, `docs/workflow-etiquette.md` |
| Durable delegated state | Add + move | Execution artifacts own run state after dispatch, survive compaction, bound child context, and support selective ticket invalidation. | `docs/prd-execution.md` and execution helpers |
| Ticket scheduling | Add + move | Use a critical-path ready queue, affinity, interface-first work, incremental integration, selective Cohort Verification, parent-owned oracles, and named outputs. | `docs/prd-execution.md` and planner |
| Implement-the-PRD authority | Add + move | The accepted build-ready target proceeds through branch, tickets, integration, proof, PR, merge, specified deployment/production work, verification, rollback, updates, and cleanup unless a named authority or safety stop applies. | `docs/prd-execution.md`, `docs/workflow-etiquette.md` |
| Role Report Contract | Replace | Child agents return `status`, `changedFiles`, evidence pointers, and `blocker`; no routine prose. The parent independently verifies evidence. | `implementer`, `docs/meaningful-proof.md` |
| Subagent output/progress | Replace | Silent safe recovery; surface decisions, unrecoverable failure, host-required terse heartbeat, or final proof only. | Router quiet-execution contract |
| System-Level Explanation Visuals | Move | Use diagrams/illustrations only when they materially improve understanding. | Diagram and illustration skills |
| Product Features | Move | Product workflow, first value, progress, states, and next action belong to product/experience roles. | `product-architect`, `experience-reviewer` |
| Stop Conditions | Keep | Stop only for material behavior/risk/authority/cost conflicts or exhausted safe recovery. | Router |
| Completion Rule | Keep + move | Acceptance, proof, blocking review, hygiene, and concise residual risk are required. | Router and role skills |

## Explicit deletions

- Delete duplicate child tickets and routine lane ledgers that merely mirror native state.
- Delete detailed procedures duplicated between the global and repository `AGENTS.md` files.
- Delete downstream-relative Gauntlet `docs/...` and `scripts/...` references from installed guidance.
- Delete claims that phrase-presence fixture scoring proves behavioral compliance.
- Delete routine human-facing subagent progress and prose reports.
- Delete prompt duplication that sends every child the whole PRD, manifest, event history, or unrelated receipts.
- Do not add universal agent counts, retry counts, polling intervals, reviewer ratios, or token thresholds.

## Preservation boundary

Personal House Voice and every other user-owned global instruction remain outside the Gauntlet managed block. The installer may update only the bounded Gauntlet block and must abort without mutation when marker structure is malformed.
