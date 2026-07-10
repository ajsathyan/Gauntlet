# Workflow Etiquette

Status: draft reference. This is not yet an `AGENTS.md` standard or a mandatory gate.

Purpose: keep agent collaboration legible without turning planning into ceremony. Use these etiquette lanes as lightweight touchpoints when they reduce rework, protect user agency, or prevent high-impact misses.

Terminology:

- Use `Verification Scope` in internal plans when its breadth changes proof or cost. It maps to Gauntlet's older `Proof Scope` wording.
- Use `Edge Cases` for Foresight. Avoid new labels such as "watch points" unless a specific repo already uses them.
- Use `Execution Mode` as an execution posture, not a new Gauntlet mode. Default is `review`; use `autonomous` only when the user asks for autonomous work or the task is safe enough to recommend it.
- Use `review` when goals, requirements, domain relationships, or acceptable defaults still need human clarification before the agent can safely work autonomously. Do not use it for ordinary agent self-review or QA; the agent can do those autonomously.
- Use `Decision Gate` when autonomous execution can proceed up to a named boundary, but a major unresolved decision, safety failure, or new material assumption must be handled before continuing. Do not use a gate to re-ask for behavior the user already requested.

## Current Lanes

### Planning Etiquette

Use while shaping the work, especially after the user gives corrections, taste, constraints, or dislikes.

Default shape:

```text
Accounted for:
- <preference, correction, or constraint carried forward>
- <non-goal or boundary if it changed the plan>

Plan delta: <what changed because of that input>
```

Rules:

- Keep it to 1-3 bullets.
- Use only when the user's input changes the plan, resolves ambiguity, or corrects the agent's framing.
- Skip for direct factual answers, simple "go" messages, or low-context p3/p4 work where there is no plan delta.
- Do not restate the whole plan.

### Kickoff Etiquette

Use when the work becomes clear and implementation is about to begin. Select mode, depth, verification scope, execution mode, decision gate, priority, and title internally. Apply the thread title as soon as classification is responsible; do not turn clean classification into a chat receipt.

Routine workflow mechanics stay internal. User-visible updates contain a recommendation, changed assumption, meaningful result, blocker, decision, proof, or completed outcome. A clean check stays silent in chat.

Priority mapping:

- `p0`: Release-class or materially risky work.
- `p1`: Feature-class work.
- `p2`: Deep Patch, tricky patch, or small change with high consequence.
- `p3`: normal Patch or normal bounded research with a durable answer or decision artifact.
- `p4`: low-durable-output brainstorming, abandoned work, routine admin, or intentionally parked exploration.

Research is never assigned `p4` merely because it is research. Classify it by the consequence and durable decision it supports: `p0` for Release-class harm, `p1` for substantial product or strategic direction, `p2` for consequential implementation decisions, and `p3` for normal bounded research. When uncertain, default bounded research to `p3`; do not inflate priority merely because research is broad or time-consuming.

Application rule:

- For `p0`, `p1`, and `p2`, ask about priority only when the consequence class changes scope, risk appetite, proof, execution authorization, or another expectation the user should choose.
- For `p3` and `p4`, apply the label without blocking or announcing routine naming.
- After selecting a kickoff label, call `set_thread_title` immediately. Title application is internal unless it fails or the label changes the work.
- If the user supplies an alternate priority/title, call `set_thread_title` with the user's version and continue from that label.
- For an unlabeled task, suggest the priority/title on the first substantive response when classification is responsible and no later than the third user-assistant exchange. Existing valid `p0` through `p4` labels, with optional `-auto`, are not reopened merely to repeat naming ceremony.
- Before implementation, check edge cases for p0-p2 work and p3 work with side effects, state changes, user-facing behavior, or a repeated prior miss. Surface only cases that change behavior, risk, acceptance criteria, or a user decision.

Execution Mode rule:

- If the user asks for "do this autonomously", "do it without me watching", or similar, use autonomous execution unless the task has stop-condition risk.
- Use `Decision Gate` when code or local fixture work can proceed autonomously, but a major unresolved decision, safety failure, or new material assumption must be handled before the next step.
- Durable external actions include renaming or archiving real threads, creating follow-up threads, pushing or merging git branches, changing production/external services, deleting or mutating durable data, or changing global policy/install behavior. If one of these actions is the accepted requirement and its deterministic safety checks pass, execute it instead of pausing just because it is durable.
- If execution mode is `autonomous`, title the thread as `p#-auto: four word goal`.
- If execution mode is `review`, keep the normal `p#: four word goal` title.
- If execution mode is `autonomous`, use `p#-auto:` even when a Decision Gate exists; the suffix means the agent can work without being watched until the named gate.
- Recheck execution mode after Foresight and before side-effectful Execution. Promote to `autonomous` once goals, requirements, domain relationships, and acceptable defaults are clear enough to proceed.
- Demote to `review` when product judgment, external side effects, irreversible decisions, uncertain domain relationships, or unclear requirements need the user before autonomous execution would be responsible.
- When demoting to `review`, ask the smallest useful clarifying question and include the agent's recommended answer so the user can accept or correct it quickly.
- Silently reassess priority and execution mode when implementation begins and when implementation materially changes scope, affected systems, external side effects, risk, proof burden, or reversibility. If the priority is unchanged, say nothing about it. If it changes, state the old and new priority once, name the trigger, and update the thread title. Call out an execution-mode change only when the suffix changes between review and `-auto`.

User override always wins.

### Foresight Etiquette

Use before implementation for p0-p3 when the plan can plausibly miss high-impact edge cases.

This is the lightweight premortem lane: imagine the work failed, regressed, confused users, created weird state, or caused avoidable rework. Name only edge cases that change implementation, verification, scope, or a user decision. Keep clean reasoning in the plan rather than narrating a Foresight heading.

Rules:

- Keep it to 2-4 real edge cases.
- Do not produce a generic risk laundry list.
- Do not run for p4.
- For p3, run only when there is a concrete side-effect surface, state transition, user-facing behavior, or repeated prior miss.
- For p0-p2, run by default before implementation, but keep it bounded.
- Do not hide unclear requirements by calling them edge cases. If the uncertainty changes product behavior, data, money, privacy, security, or acceptance criteria, route it through Planning or Kickoff instead.
- Run scope-addition delta foresight before implementing every genuine addition to accepted scope. Inspect the addition and its boundary with existing scope for new edge cases, invalidated assumptions, acceptance/proof changes, priority/execution changes, and packetization changes.
- A clean scope-addition check records only `Scope delta checked: no material change.` in the plan/task packet and stays silent in chat. Material findings update the affected task packets, dependencies, acceptance criteria, and proof before implementation and are called out only when they change the plan or need a decision.
- If the work depends on how domain entities relate and that relationship is not explicit in code, docs, tests, or prior accepted context, demote execution mode to `review`.
- When latency matters, solidify the safe default or create a specific lane so future autonomous execution can move quickly without repeated ceremony.

High-value trigger surfaces:

- Live operations, paid infrastructure, or destructive actions.
- Auth, billing, credits, refunds, permissions, privacy, migrations, data integrity, concurrency, queues, public APIs, uploads, or durable workflows.
- Control-plane policy, state machines, automation, monitoring, retries, idempotency, or background processes.
- Latency-sensitive live operations, such as scarce-capacity provisioning or urgent pod termination.
- Domain model relationships, such as lifecycle states, ownership, source/action separation, profile defaults vs exceptions, compatibility names vs new product names, or override/suppression behavior.
- Product workflows where the user's correction shows the current model is too blunt.
- Frontend experiences where missing states, accessibility, responsive layout, or trust cues can invalidate the feature.

Low-value surfaces:

- Pure brainstorming.
- Narrow copy/docs edits.
- Simple local Patch work with obvious verification and no user-facing or durable side effects.

### Delegation Etiquette

Use when the work is broad, parallelizable, high-context, or likely to be implemented by multiple work lanes.

This is the implementation-memory lane. It writes agent-native context so future agents or work lanes can execute without rereading the whole trace. It is separate from Foresight: Foresight asks "what edge cases could change the next move?" Delegation asks "what context should be indexed so work can be sliced and handed off cheaply?"

Pre-implementation packetization gate:

- Every child implementation lane receives a bounded packet before implementation.
- For two or more parallel lanes or any write-heavy child implementation lane, use schema `1.2` with a top-level shared block and lane-specific deltas. The referenced packets and accepted current-run `.gauntlet/subagent-plan.json` must exist before implementation, not merely before dispatch.
- A single small read-only exploration or review child receives a bounded prompt but does not need the manifest gate.
- Every validated lane packet covers lane id, skill/objective, project/worktree context, accepted source, in/out scope, ownership/avoidance, dependencies, consumes/produces, constraints, proof, expected return format, and ask-user policy.
- Do not record packetization when no child implementation lanes exist. Successful packet validation stays silent; surface only blocking findings or warnings that change execution or remain a real risk.
- If material scope changes add or reshape lanes, update packets and revalidate before implementing the affected scope.

Trigger rules:

- Default for p0 and broad p1 work when multiple sessions, agents, repos, or verification lanes will need the same background.
- Use for p2 only when the work has shared vocabulary, coupled state, non-obvious invariants, or likely handoff/resume cost.
- Skip for p3/p4 unless the user explicitly asks or a later archive/resume would clearly lose critical context.
- Do not require it for every Feature. A small, accepted UI/workflow change can stay in the normal plan plus final summary.

Implementation Memory contents:

- Goal, scope, non-goals, current state, and source-of-truth files.
- Scan Index: canonical search keys, read-first order, affected surfaces, and risk lanes.
- Preserved context: user constraints, taste/preferences that changed the plan, live-state notes, compatibility vocabulary, and redaction boundaries.
- Implementation map by bounded work lane, such as backend, frontend, policy, workflow, ops, or verification.
- Lane entries with a human-legible goal, agent-facing search keys, source files, dependencies, edge cases, and verification focus.
- Edge cases and invariants to preserve.
- Verification required, `Cannot verify`, and known deferrals.
- Token-efficient usage instructions, such as "rg these terms, read these sections, then check Edge Cases and Verification."

Child chat orchestration:

- The main chat is the orchestrator. It owns the user-facing ledger, user questions, merge decisions, and final synthesis.
- Child chats are bounded execution lanes. They receive a task packet, do the work, return a compact report, and do not ask the user directly.
- If a child lane needs product clarification, credentials, risky scope expansion, or an unsafe side effect, it reports `Needs decision` to the main chat.
- Native Codex state owns child progress; do not require title/status churn.
- Use lane ids as stable packet/report handles when the main task needs to match a result to owned scope.

Worktree defaults:

- Create a separate git worktree by default for write-heavy child chats: implementation, broad refactors, multi-file edits, uncertain file ownership, or more than a tiny patch.
- A read-only review, exploration, summarization, or log-analysis child lane does not need a worktree by default.
- A tiny implementation lane with clearly disjoint files may share the current worktree, but the task packet must name owned and avoided files.
- The child task packet should name the worktree path, branch, owned files, avoided files, dependencies, proof, and report format.
- The main chat integrates or merges child work only after proof and ownership checks pass.

Child task packet shape:

```text
Lane: [C1] Backend policy layer
Worktree: ../project-C1-policy
Owns: backend policy files and backend tests
Avoids: dashboard UI, unrelated docs, unrelated dirty files
Depends on: none
Consumes: Implementation Memory sections <exact names>
Produces: compact report with changed files, proof, blockers, and next action
Ask-user policy: do not ask user directly; return Needs decision to the main chat
```

Boundaries:

- Implementation Memory is not a mandatory gate by itself. Packetization is mandatory only when the trigger above says it is required.
- It is not a run log. Run logs capture decisions and exceptions after or during a run; Implementation Memory makes future implementation cheaper before or across runs.
- It is not a task packet. Task packets should cite exact sections of Implementation Memory instead of copying the whole thing.
- It should not contain secrets, raw private data, or unredacted operational state.
- It must carry a stale-context warning when live systems, branch state, external APIs, or product decisions can drift.

Good fit examples:

- Control-plane or live-ops work where policy vocabulary, supervisor behavior, and verification state matter.
- Feature or Release work where several agents would otherwise receive the same large background packet.
- Product/architecture work where the user has refined terms that future implementation must preserve.
- Long-running p1/p0 threads that will be archived but later searched for implementation context.

Bad fit examples:

- A one-shot Patch with obvious verification.
- Brainstorming that has not settled into an implementation direction.
- Implementation Memory that merely restates the chat summary.
- A subagent split where each lane has independent files and verification and does not need shared rationale.

### Execution Etiquette

Use while implementation is in progress.

The goal is not silence. The goal is senior-engineer communication: brief updates when judgment changes, risk changes, verification changes, or user attention is useful. Mechanical progress should move through tools, scripts, logs, or artifacts instead of chat narration.

Print in chat:

- Decisions and plan changes.
- New edge cases, blockers, warnings, or tradeoffs.
- Failed or surprising verification.
- User decisions needed.
- Short status updates during long work.
- Final outcome, verification, residual risk, and unresolved follow-ups.

Keep quiet or move to tools:

- Routine file reads, searches, formatting, linting, and test command setup.
- Repeated command output that adds no new decision.
- Generated packet/log content unless the user asked to see it.
- Mechanical extraction that can be done by CLI.

Downsides to watch:

- Too-quiet execution can hide drift until the end, making the user feel surprised by decisions.
- Too many terse updates can become cryptic. If a decision matters, include the reason.
- If everything is hidden in artifacts, the chat stops functioning as the shared working surface.
- Tool automation can make a wrong assumption faster; surface assumptions before side-effectful work.

Execution mode boundaries:

- In `autonomous`, continue through reversible local choices, routine implementation decisions, and expected verification fixes without waiting for the user.
- In `review`, keep the trace legible because the user may need to clarify goals, requirements, domain relationships, or acceptable defaults before the agent can safely continue autonomously.
- At a `Decision Gate`, stop only for the named major unresolved decision, safety failure, or new material assumption; do not re-open already-settled requirements.
- Do not use `review` for ordinary agent self-review, fixture inspection, code review, or QA. Those can run autonomously unless they reveal a requirement or domain assumption that needs the user.
- Stop or demote to `review` when the work hits data loss, migration, billing, security, privacy, destructive external action, production deploy, unclear product behavior, conflicting instructions, failed verification that changes scope, unexpected dirty files, missing credentials, or uncertain domain-entity relationships.
- If demoted, ask a targeted clarifying question with a recommended default instead of merely reporting the ambiguity.
- Record material assumptions at the end when they did not justify stopping.
- Prefer deterministic checks for objective state. The model can notice many unclear assumptions, but it is not reliable enough to be the only gate.

Assumptions Made shape:

```text
Assumptions Made:
- Assumptions made: <only material assumptions>
- Ambiguity handled: <what was unclear and why the chosen path was safe>
- Verification: <what ran or could not run>
```

### Continuity Etiquette

Use when the user pauses, asks to park work, asks for a landing pad, or when interruption would make reentry expensive.

This is the reentry lane. It preserves the thread state, next move, open loops, and enough context for future-you or future Codex to resume without replaying the whole chat.

Default durable artifact, only when useful:

```text
Pause Work Packet:
- Current Goal
- State
- Last Useful Context
- Next Best Move
- Open Loops
- Verification State
- Reentry Prompt
```

Rules:

- Keep Pause Work Packets short.
- Preserve the work state, not every detail.
- Mark parked ideas so they stop competing with the next action.
- On resume, read the latest relevant Pause Work Packet before asking the user to restate context.
- Do not turn every ordinary stop into a durable artifact.

### Debrief Etiquette

Use after implementation only when something surprised the plan, the user corrected a material assumption, tests/review found a non-obvious issue, or Foresight missed an edge case.

This is the lightweight postmortem lane. It checks whether the premortem was sufficient and whether a reusable pattern should be captured.

Default shape:

```text
Debrief:
- Covered: <edge case that was handled>
- Missed: <surprise or correction, if any>
- Pattern: <keep local | update reference | no change>
```

Rules:

- Skip routine clean completions.
- Keep it to 1-3 bullets.
- Route repo-specific lessons to repo code, tests, docs, or run logs.
- Route Gauntlet-general missing guidance through coverage-gap or reference-doc updates.
- Use Promotion Scanner only when repeated manual/agent work, repeated `Cannot verify`, Release/live-ops evidence, or explicit user request earns it.
- Do not turn every bug into a new rule.

### Follow-Up Etiquette

Use when the user or agent says a future topic should happen after the current work, such as "after this, we should discuss CLI speedups."

This is a capture lane, not a research lane. Preserve the future thread seed without spending tokens investigating a topic the user may never pursue.

Default shape:

```text
Follow-up captured:
- Topic: <short name>
- Strength: <strong follow-up|follow-up for later>
- Why it matters: <one sentence from current context>
- Context already known: <only what surfaced naturally in this chat>
- Suggested opener: <first ask for a future chat>
```

Rules:

- Capture during Planning or Execution when the topic appears.
- Mention unresolved follow-ups at completion when they remain relevant.
- Mark a `strong follow-up` when the follow-up is clearly needed to complete the current thought or work idea, high-value enough to preserve now, or likely to be expensive to reconstruct later.
- Mark a `follow-up for later` when it is useful but not needed to close the current work.
- During Archival, run one final follow-up check after git/archive blockers are resolved and before archiving.
- If a strong follow-up remains, pause closeout and offer: complete it in this chat, create a new same-repo chat with context, or archive anyway.
- Do not perform new searches or trace reads just to enrich a follow-up seed.
- If the user wants a new chat, create it in the same repo and send the captured context plus an opener that asks the new chat to suggest its own priority and title before continuing.
- If the user does not want a new chat, leave the follow-up as captured context and archive normally.

Current follow-up retrieval:

- Use `docs/gauntlet-runs/2026-07-04-thread-changelog.md` for follow-ups captured from the Workflow Etiquette implementation thread. GitHub discipline is resolved in `docs/github-discipline.md`; House voice workflow and remaining Gauntlet CLI speedups remain separate follow-up lanes.

### Saved Diagram Etiquette

Use only when the user explicitly asks to save a diagram or when a diagram becomes a durable reference for planning, implementation memory, or debrief.

Default location:

```text
docs/gauntlet-diagrams/YYYY-MM-DD-<feature>-<slug>.md
docs/gauntlet-diagrams/index.md
```

Rules:

- Save Mermaid source in Markdown with searchable metadata: id, title, feature, source thread/title, tags, and related files.
- Update the diagram index with one row per saved diagram.
- Do not render bitmap/SVG output unless the user asks or a consumer requires it.
- Prefer stable feature names and tags over long prose so CLI lookup can use `rg`.
- Save during Planning when the diagram clarifies the work model; save after Execution/Debrief when the diagram describes what actually shipped.

### Archival Etiquette

Use when the user asks to archive a chat.

Flow:

1. If the thread title already starts with `/^p[0-4](-auto)?:/`, skip naming.
2. If not, generate a `p#:` or `p#-auto:` four-word-goal title.
3. Generate or reuse the PR changelog or closeout content and pass it to `scripts/gauntlet.py archive plan --content` so the Archive Summary is visible before any archive decision; use `--content -` to pipe the content without creating another file.
4. If straightforward, rename, push/merge if needed and safe, then archive.
5. Resolve blockers, warnings, or user decisions.
6. Run the final Follow-Up Etiquette check.
7. If a strong follow-up remains, offer to complete it now, create a new same-repo chat with context, or archive anyway.
8. Archive.

Safe automatic archive conditions:

- No repo or no code changes.
- Changes already pushed and merged.
- Branch is clearly attributable to the thread, checks pass, no conflicts, no required human review pending, and no unrelated dirty files.

Block or ask conditions:

- Dirty files, especially unrelated files.
- Local commits not pushed.
- Pushed branch not merged.
- Failed/pending checks.
- Multiple repos touched.
- Squash-merge or branch state cannot be reconciled.
- Any uncertainty about whether the work is attributable to this thread.

Delegation and Continuity interaction:

- If the title already starts with `/^p[0-4](-auto)?:/`, skip Kickoff naming during archive.
- For p0 or broad p1 work, archive may check whether Implementation Memory, a run log, or a Pause Work Packet already exists when future resume cost would be high.
- Do not pause archive solely because no Implementation Memory or Pause Work Packet exists. Pause only if missing context would make the current git/archive action unsafe, the user explicitly asked to preserve it, or a strong follow-up should be handled before closeout.
- If repeated manual work or repeated `Cannot verify` is visible during closeout, surface it as a Debrief/Promotion candidate, but do not run a heavy promotion scan for ordinary archive.

### Git Discipline Etiquette

Use `docs/github-discipline.md` for the full GitHub strategy. The active default is intentionally teachable for people who are new to Git: branch from `main`, commit coherent checkpoints, open a PR, verify, merge with a merge commit, and delete the branch.

Default behavior:

- Use a branch for persisted code, docs, or policy changes.
- Use a separate worktree when the workspace is dirty, the task is p0-p2, the work is broad, or child implementation lanes need isolated writes.
- Use PRs as memory and proof bundles, even for solo builders.
- Preserve useful checkpoint commits with merge commits. Squash, rebase, or direct-push to `main` only when the user or repo explicitly asks.
- Let the main chat own the final branch, PR, user questions, child-lane ledger, and merge decision.
- Let child chats return reports; child implementation lanes may use isolated branches or worktrees, but should not direct-push to `main`.

Code-owned checks should stay objective: dirty state, upstream state, default-branch detection, PR presence, PR checks, review state, mergeability, and accepted merge command shape. Repo-culture choices and history preferences stay conversational unless the repo has explicit rules.

## Implementation Stance

Use a split: LLM judgment for subjective etiquette, deterministic helpers for objective state.

LLM-owned decisions:

- Suggested p priority and four-word title.
- Whether Foresight is useful and which 2-4 edge cases matter.
- Whether Delegation or Continuity is warranted.
- Which user preferences or plan deltas deserve a Planning Etiquette receipt.
- Whether Debrief found a reusable pattern or just normal implementation friction.
- Whether a follow-up seed is worth preserving.

Code-owned checks:

- Use `scripts/check-workflow-etiquette.py` for kickoff/archive etiquette validation.
- Use `scripts/gauntlet.py archive plan|execute` for archive checks, safe git actions, and app-action packets.
- Pass the PR changelog or closeout content to `scripts/gauntlet.py archive plan --content` whenever available; the helper prints the Archive Summary even when archive is blocked.
- Use `scripts/gauntlet.py install verify` after install/global workflow changes.
- Use the command table in `docs/workflow-speedups.md` for diff/test/review packets, Implementation Memory linting, PR/changelog drafts, follow-up notes, and follow-up thread packets.
- Use `scripts/gauntlet.py diagram find` for saved Mermaid lookup.

Not yet automated by the local helper:

- Token-shape enforcement.
- Direct follow-up thread creation from the shell.
- Saved Mermaid rendering.
- Multi-repo attribution.

Mastra or another durable workflow runtime may be useful later for stateful archive orchestration, cross-thread triggers, scheduled follow-ups, or deterministic multi-step workflows. It is probably overkill for the first version of etiquette because the hardest parts are judgment-heavy and still being calibrated. Start with docs, templates, and small helper checks; promote to a workflow runtime only after repeated runs show that Codex is doing the same mechanical sequence reliably enough to automate.

## Trace Scan Summary

Scan date: 2026-07-04.

Scope: recent local Codex session JSONL files under `~/.codex/sessions/2026/06`, `~/.codex/sessions/2026/07`, and `~/.codex/archived_sessions`, limited to visible user/agent messages.

Heuristic counts:

- 458 recent session files contained visible user/agent messages.
- 80 session files matched user-correction or edge-case language such as "did you think", "doesn't seem proper", "state explosion", "weird states", "side effects", or "edge cases".
- 89 session files matched surprise/hazard language such as "stale cache", "old supervisor", "restarted", "caught a real", "unexpected", "hazard", or "unsafe".
- Only 1 session directly used "premortem" or "postmortem" wording, so the pattern exists mostly as behavior, not as named process.

Representative findings:

- Agora autoscaler/conserve-mode planning: the first model was too blunt. User correction exposed that base profile, exceptions, signal source, and action needed separate axes. Foresight would have been high value before implementation.
- Agora live fleet retirement: post-verification found stale cache and a live old autoscaler loop that could fight the user's conserve intent. Foresight and Debrief are high value for live ops, destructive actions, and background supervisors.
- Used Price Release work: repeated verification/review caught trust-boundary ordering, refund/account ownership, support/recredit flow, analytics PII, rollback verification, and launch-gate external evidence gaps. Foresight is high value for money/auth/privacy surfaces; Debrief is useful only when surprises change reusable verification or guidance.
- Gauntlet validator path drift: a reported failure showed installed guidance assumed project-local scripts. Regression verification plus stale-reference scan caught adjacent drift. Foresight is high value for install/global workflow changes because target-repo layout can differ from Gauntlet source layout.
- Dashboard/product review: edge-case review produced PRD-ready acceptance criteria around stale/live data, export blocking, evidence inspectors, accessibility, and avoiding generic dashboard output. Foresight is high value for product/feature definition, but should stay PRD-shaped rather than become implementation ceremony.
- Indexed implementation context docs: a p1 planning thread identified a recurring gap between chat traces, run logs, task packets, and subagent packets. Delegation is valuable when future agents need stable vocabulary, source-of-truth files, edge cases, verification expectations, and scan keys without rereading the whole trace.

Conclusion:

Premortem/postmortem behavior is valuable often enough to formalize as trigger-based etiquette, not as an always-on gate. The most valuable pre-work pass is Foresight Etiquette for p0-p2 and concrete-side-effect p3 work. The most valuable post-work pass is Debrief Etiquette only when the plan was surprised, a user correction revealed a missed model, or verification found a reusable failure pattern.

## Promotion Brief

Verdict: Candidates found.

Evidence reviewed:

- Recent session-index titles and visible-message JSONL traces.
- Representative live-ops, release, product-review, and Gauntlet workflow/tooling sessions.
- Existing Gauntlet docs: `docs/promotion-scanner.md`, `docs/workflow-speedups.md`, and `docs/coverage-gaps.md`.

Repeated manual loops observed:

- User asks agent to flag side effects or edge cases before implementation.
- User corrects a too-blunt plan after the agent has already proposed or started a direction.
- Agent discovers stale caches, restarted supervisors, path drift, or trust-boundary misses during verification.
- Agent later explains a distinction that should have been in the pre-work risk model.

Promotion candidates:

| Candidate | Destination | Confidence | Why |
| --- | --- | --- | --- |
| Foresight Etiquette | Gauntlet reference guidance | High | Repeated high-impact misses occur before implementation on live ops, release, control-plane, and product workflow tasks. |
| Debrief Etiquette | Gauntlet reference guidance | Medium | Valuable when surprises happen, but wasteful for routine clean completions. |
| Planning Etiquette receipt | Gauntlet reference guidance | Medium | Useful after user correction; too expensive if repeated every turn. |
| Delegation Etiquette | Gauntlet reference guidance plus optional template/tooling | Medium | Useful for broad p1/p0 work where task packets or subagent prompts would otherwise duplicate large context. |
| Continuity Etiquette | Gauntlet reference guidance | Medium | Useful when interruption or reentry would otherwise force the user or agent to reconstruct state. |
| Always-on premortem gate | Reject | High | Would inflate tokens and duplicate existing Release/Product/Review gates. |
| Always-on postmortem gate | Reject | High | Routine completions do not need extra ceremony. |
| Always-on Implementation Memory gate | Reject | High | Would turn most Features into artifact maintenance even when resume cost is low. |

Recommended destination:

Keep this document as draft reference guidance. Promote only the trigger rules into `AGENTS.md` if later runs show the reference is repeatedly needed and consistently saves rework. If Delegation earns promotion, place the operational guidance in `docs/workflow-speedups.md`, add a planner template, and let review/task packets cite Implementation Memory sections instead of copying the body.

Verification needed before stronger promotion:

- At least two future runs where Foresight Etiquette prevents a material implementation change or avoids rework.
- At least one future Debrief that identifies a reusable pattern worth adding to repo tests, repo docs, or Gauntlet guidance.
- At least one future p0/p1 implementation where Implementation Memory measurably reduces duplicate prompt/context packets or prevents stale vocabulary.
- Evidence that the added text remains short in actual chat turns.

Do not infer:

- Do not infer every p3 needs Foresight.
- Do not infer every completed task needs Debrief.
- Do not infer user-correction language always indicates agent failure; some corrections are normal collaborative shaping.
- Do not route repo-specific operational lessons into Gauntlet-general rules.
- Do not infer every p1 needs Implementation Memory; shared context and likely resume cost are the trigger.

## Token Budget Rules

- Planning Etiquette receipt: max 3 bullets plus one plan-delta line.
- Kickoff Etiquette: max one label, one execution mode, one read, one signals line.
- Foresight Etiquette: max 4 edge cases.
- Delegation Etiquette: one path, one Lane Index or Scan Index line, one use rule in chat; Implementation Memory can be longer, but task packets should cite sections.
- Execution Etiquette: brief decision/status updates only; routine mechanical output stays in tools or artifacts.
- Assumptions Made: max 3 bullets.
- Continuity Etiquette: one Pause Work Packet only when pausing or reentry would otherwise lose meaningful context.
- Follow-Up Etiquette: max one topic, strength, why, known context, and suggested opener.
- Saved Diagram Etiquette: one Markdown file and one index row.
- Debrief Etiquette: max 3 bullets and only when triggered.
- Archival Etiquette: quiet happy path; only explain blockers/warnings.

## Open Decisions

- Whether `Debrief Etiquette` is the final name for the post-work lane.
- Whether the priority-title format should require exactly four words or allow four-ish words when grammar suffers.
- Whether autonomous work with a Decision Gate should always use `p#-auto:` or whether future evidence earns a separate title shorthand.
- Whether a future `git plan` helper should generalize the archive-time Git checks before push, PR creation, and merge decisions.
- Whether `Delegation Etiquette` and `Implementation Memory` are the final names for indexed implementation context docs.
- Whether Implementation Memory promotion should add a template beyond the linter.
- Whether Mastra or another workflow runtime should be revisited after helper checks prove the mechanical archive/context flows are stable.
- Whether future evidence should become a pending `GAP-###` or stay inside this reference until the rule earns promotion.
