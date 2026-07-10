# Skill Quality Bar

Use this reference when creating or revising Gauntlet skills, role skills, workflow guidance, or skill-like checklists. The bar answers one practical question: will this change make future agents behave better in a way the user can understand and verify?

This is Gauntlet's applied standard, not a fork of Matt Pocock's skill-writing skill. It uses Gauntlet's product/workflow harness lessons and credits Matt Pocock's `writing-great-skills` vocabulary where it helps explain why skill changes succeed or fail.

## Baseline Bar

Run this cheap check for every meaningful skill or workflow-guidance change. It belongs in the main workflow because it should not add much token or runtime cost.

| Check | Practical Benefit | What Changes Versus Today |
| --- | --- | --- |
| Behavior delta | Names what the agent will do differently in plain language. | Prevents skill edits that sound thoughtful but do not change runtime behavior. |
| Trigger clarity | Makes it obvious when the skill should load or when the guidance applies. | Reduces missed invocation and accidental overuse. |
| Completion criterion | States the condition that proves the step or review is done. | Reduces premature "looks good" completion. |
| Output contract | Defines the artifact, report slots, or decision the agent must return. | Makes downstream roles and final summaries easier to trust. |
| Positive steering | Describes the target behavior directly. | Avoids prohibition-heavy wording that keeps the unwanted behavior in context. |
| No-op pruning | Removes sentences that the model would already follow by default. | Keeps Gauntlet lean instead of slowly accumulating process prose. |
| Progressive disclosure | Keeps always-loaded guidance short and points to heavier references only when needed. | Protects token budget while preserving deeper help for complex edits. |
| Practical explanation | Explains the user-facing value of the change, not just the internal mechanism. | Helps AJS and future users decide whether the process earns its cost. |
| Cheap harness mechanics | Prefer checkable schemas, bounded attempt notes, local proof commands, and `Cannot verify` slots where useful. | Makes failures easier to debug without turning every Patch into a ceremony. |
| Eval claim scope | Labels text coverage, scorer smoke, deterministic outcomes, and subjective judgment as separate proof layers. | Prevents phrase checks from being reported as agent behavior. |

If a proposed skill change cannot pass the baseline bar, rewrite it before adding more process.

## Escalation Bar

Use this section only when the work is high-impact: new Gauntlet role skills, major workflow changes, Release guidance, repeated failures, eval infrastructure, or user-approved Deep work. These checks can spend meaningful tokens, so they must name their trigger, cap, artifact, and exit condition.

| Escalation | Use When | Artifact |
| --- | --- | --- |
| Two-attempt Deep planning | A skill or workflow rule could materially change future implementation quality, risk routing, or user trust. | A short comparison of missed blockers, dependency order, proof requirements, first ready task, deferrals, and rejected alternatives. |
| Forward-test scenario | The skill is new, rewritten, or correcting an observed failure mode. | A minimal pressure scenario showing the desired behavior and the proof that the skill now steers it. |
| Negative outcome canary | The change claims behavioral or orchestration improvement. | A wrong action, missing proof, authority violation, or other observable failure that contains expected language and must still fail. |
| Trigger-overlap check | The change alters skill or mode routing. | Paired cases at the routing boundary, including the expected choice and a plausible wrong choice. |
| Completion and authority trace | The change alters autonomous execution or delegation. | Observable required/forbidden actions, proof, authority, and quiet-output budgets; claimed completion alone is insufficient. |
| Baseline provenance | A current-versus-candidate comparison informs a durable decision. | The release, commit, fixture-pack version, and shared contract used by both arms. |
| Adversarial skill review | The skill touches safety, release, privacy, data integrity, broad orchestration, or repeated prior misses. | Findings by severity, `Cannot verify`, and the one next action. |
| Impact proof review | The skill claims to improve reliability, speed, autonomy, or review quality. | A concrete proof path or a deferred analytics question, not invented certainty. |
| Parallel reviewer lanes | Review dimensions are independent and the expected value beats context cost. | A validated `.gauntlet/subagent-plan.json` and role reports using the shared report contract. |

Do not run the escalation bar for ordinary Patch work, copy edits, local-only docs, or accepted narrow skill tweaks unless the user asks.

## Eval Layers

Use the cheapest layer that can support the claim, and name that layer in the result:

1. **Text coverage** checks whether required guidance exists in the skill. It does not show that an agent followed it.
2. **Scorer smoke** feeds synthetic responses through a scorer. A phrase-echo fixture may pass here because this layer proves scorer wiring only.
3. **Deterministic outcome traces** score observable outcomes, actions, authority, proof, routing, output budget, and recorded cost or latency. Include a negative canary for the failure being prevented.
4. **Calibrated judgment** is required for subjective criteria such as product quality or trust. Until its judgments are calibrated against human labels, return `Cannot verify`; never treat deterministic success or expected phrases as a substitute.

Paired current-versus-candidate traces must use the same contract. Record baseline provenance before using the comparison for release or workflow policy. Prefer machine receipts and externally visible artifacts over agent explanations of what they did.

## Harness Mechanics For Skills

Use these mechanics when they directly help the skill's job:

- Schema retry: if a skill expects structured output, define the shape and retry malformed output before handing it downstream.
- Invalidation trigger: name the facts that force the plan or review to be refreshed, such as changed score, failing proof, changed user requirement, or conflicting file state.
- Bounded attempt memory: record compact fingerprints of failed attempts, rejected alternatives, and useful observations during a run; summarize repeated items and expire the scratchpad at closeout unless it becomes a run-log decision, follow-up, or coverage gap.
- Read-only analyzer default: when a role is meant to inspect, keep it read-only unless the task packet explicitly gives it write authority.
- Cost-aware delegation: use subagents only when files, state, and proof are independent enough to beat the context cost.

These mechanics are not etiquette-specific. They sit above individual roles as harness behavior. A role skill may own one mechanic when it is central to that role, but the quality bar asks whether the mechanic belongs in the skill at all.

## Bringing Matt Pocock's Skill Guidance Into Gauntlet

Gauntlet should not silently absorb third-party skill text. Use this pattern instead:

- Keep Gauntlet's portable behavior in this reference and the relevant role skills.
- Attribute the source when Gauntlet uses concepts from Matt Pocock's `writing-great-skills`.
- If Gauntlet vendors exact or adapted third-party files later, include the upstream license/notice and source path in the repo.
- Treat `writing-great-skills` as a deeper reference for skill authors; use this document as the applied Gauntlet bar.

Source checked for this run: `mattpocock/skills` tag `v1.1.0`, commit `d574778f94cf620fcc8ce741584093bc650a61d3`, MIT license.

## Deferred

Analytics event schemas, release effectiveness summaries, engineering productivity metrics, and library choices are intentionally not specified here yet. They need a separate decision pass before they become Gauntlet behavior.
