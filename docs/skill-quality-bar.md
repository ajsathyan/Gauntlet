# Skill Quality Bar

Use this reference when creating or revising Gauntlet skills or workflow guidance. The practical question is whether the change makes future behavior more predictable and verifiable without adding needless context.

## Baseline

Every meaningful change states:

| Check | Requirement |
| --- | --- |
| Behavior delta | Name what the agent will do differently. |
| Trigger | Say when the skill or guidance applies. |
| Completion | End steps with a checkable done condition. |
| Output | Define the returned artifact, verdict, or decision. |
| Positive steering | Describe the desired behavior directly. |
| Negative case | Include a plausible wrong action or false-green path when behavior is material. |
| Proof layer | Distinguish text coverage, scorer smoke, execution-backed behavior, and judgment. |
| Authority | Keep external effects inside accepted permission. |
| Context | Remove no-ops, duplication, unrelated history, and empty fields. |
| User value | Explain the practical effect in familiar language. |

If the change cannot pass this baseline, simplify it before adding more process.

## Structure and efficiency

Keep each meaning in one authoritative place. Inline what every branch needs and disclose branch-specific reference material behind a clear pointer.

Keep stable repeated instructions first, preserve canonical order and whitespace, and place volatile task details last. Treat cache reuse as an optimization; do not claim it without host evidence.

Use deterministic scripts for repeated mechanical facts. Do not turn a prose field or self-report into an authority or completion oracle.

Delegate only when independent ownership or evidence beats the context cost. A delegated skill supplies one objective, one ownership boundary, explicit dependencies, a checkable return contract, and an ask-parent policy. Custom agent profiles are optional and chosen directly when they clearly help.

## Escalation

Use the following only when consequence or repeated failure earns the cost:

| Check | Trigger | Artifact |
| --- | --- | --- |
| Independent plan review | Concrete release harm or explicit user request | Short comparison of missed blockers, dependency order, and proof |
| Forward scenario | New or rewritten workflow behavior | Minimal scenario showing the desired action |
| Negative outcome canary | Reliability or completion claim | Wrong action that must fail despite plausible structure |
| Trigger overlap | Skill routing changes | Paired boundary cases |
| Authority trace | Autonomous or delegated behavior changes | Required and forbidden effects |
| Adversarial review | Safety, release, privacy, data integrity, broad workflow, or repeated miss | Findings with severity and terminal disposition |
| Impact proof | Reliability, speed, or autonomy claim | Measured proof path or explicit `Cannot verify` |

Name the trigger, cap, artifact, and exit condition. Ordinary patches do not pay for these checks.

## Proof layers

Use the cheapest layer that supports the claim:

1. **Text coverage** proves required guidance exists.
2. **Scorer smoke** proves deterministic scoring behavior on synthetic responses.
3. **Structured-fixture smoke** proves schema and matcher logic on authored data.
4. **Execution-backed outcome proof** resolves commands, artifacts, native traces, or external state.
5. **Calibrated judgment** handles subjective quality and must be checked against human labels before it is treated as reliable.

A phrase-echo fixture is never behavioral proof. A receipt points to evidence; it does not independently establish the outcome. Paired comparisons use the same contract and record their baseline provenance.

## Skill mechanics

Use only mechanics that help the skill’s job:

- schema retry for machine-parsed output;
- invalidation triggers for changed requirements, evidence, or source;
- read-only defaults for inspection roles;
- compact exact-revision evidence;
- consequence-triggered specialist proof.

## Provenance

Gauntlet adapts useful brainstorming, test-first, verification-before-completion, review, and skill-writing techniques while owning its runtime behavior. Upstream sources and licenses are tracked in `docs/upstream-superpowers.md` and `docs/upstream-superpowers.json`.

Matt Pocock’s `writing-great-skills` vocabulary informs no-op pruning, progressive disclosure, leading words, and completion criteria. External material remains review input rather than a runtime dependency.
