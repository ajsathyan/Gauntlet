---
name: craft-customer-email
description: Use this skill to write, revise, or audit customer-facing email communication, including product, operational, transactional, incident, and lifecycle messages. Invoke it when email is the main request or when a specification, implementation plan, or code change introduces or changes customer-facing email behavior. Use it to choose the structure, draft the subject and body, and decide whether related messages should be sent, suppressed, combined, or threaded.
---

# Craft Customer Email

Write for the decision or understanding the reader needs after opening the message.

## Gather Only Material Context

Draft immediately when the supplied material establishes enough context to make a grounded recommendation.

For this skill, a question is consequential when its answer could change the composition mode, conclusion, requested behavior, timing, severity, or trusted evidence.

Useful questions include:

- Who receives this, and what should they do after reading it?
- Is this the first alert, a retry, a recovery, or the final outcome?
- Will this recur with the same fields, and should related messages share one thread?

When the primary goal is genuinely ambiguous, offer exactly:

a. **Action-oriented** — make the decision or next step unmistakable.
b. **Intuitive understanding** — explain the causal story.
c. **Lowest cognitive load** — make recurring information easy to scan and compare.

## Select One Primary Mode

### 1. Outcome-first brief

Use when the reader must decide or act quickly, or when the message has one clear conclusion.

Put the outcome and requested behavior—or the next system step—in the first sentence. Add only the cause or evidence needed to support it.

### 2. Causal state-change narrative

Use when a consequential or confusing transition needs explanation. Order the message as:

1. What changed
2. Why it matters
3. What the system attempted
4. The result and its limits
5. What happens next
6. What the reader should do

### 3. Compact status card

Use for frequent, repeated, comparative, or multi-item updates. Use stable labels, compact alignment, counts, transitions such as `3 → 2`, timestamps, and restrained state icons. Follow the structured block with one short explanation or instruction when needed.

Combine modes only when each part has a distinct purpose:

- 1 + 3: urgent conclusion followed by compact evidence
- 2 + 3: causal explanation followed by a repeatable snapshot
- 1 + 2: urgent conclusion followed by a short causal explanation

Name one primary mode. Avoid a kitchen-sink hybrid.

## Select the Emoji Treatment

Infer the treatment unless the choice is genuinely unclear and would materially change the draft:

- **Plain:** Use no emoji for formal, financial, legal, security, or sensitive communication.
- **Literal:** Use familiar, obvious icons such as ✅, ⚠️, ⏳, and 🔴 as secondary state markers for operational or recurring updates.
- **Whimsical:** Use expressive imagery only for low-severity product or lifecycle communication when the brand supports it.

Keep every state understandable if emoji are removed or inaccessible. Do not rely on color or emoji as the sole carrier of meaning.

## Write the Message

Treat the subject as interface copy. State what changed and, when useful, what happens next.

Put the conclusion, outcome, requested behavior, or next system step in the first sentence. Phrase requested behavior directly instead of placing it under a generic heading.

Use plain, specific language and active voice. Make each sentence follow logically from the previous one. Use progressive disclosure:

1. Conclusion or current outcome
2. Essential impact and evidence
3. Next system step and requested behavior
4. Optional diagnostics or links

Include only fields that matter for this message:

- Current state and user impact
- What the system already did
- What happens next
- Next update or retry time
- What the reader should do

State knowns, unknowns, and signal limits explicitly. Do not invent certainty, timelines, causes, names, or actor behavior.

Preserve authoritative product and component names. When the source is uncertain, ask rather than inventing or silently normalizing a name. Name the actor only when responsibility helps the reader understand what happened or what happens next.

Keep the voice stable while adapting detail and urgency to severity. Routine success may be compact. Failures should be calm, factual, specific, and helpful.

Use headings or labels only when they improve repeated scanning. Do not print `Bottom line` or `Action` as headings unless the user explicitly requests those labels.

## Protect Attention

Before drafting, decide whether the email should exist.

Suppress a message when it adds no new decision, outcome, state change, or useful evidence. Combine tightly related changes into one incident thread. Distinguish among the initial alert, retry or progress update, recovery, and final outcome.

Avoid sending the same event through multiple channels unless the audiences or requested behaviors differ. For an audit, identify messages that should be suppressed, combined, separated by severity or lifecycle, or replaced by an attended interface.

## Research Only When It Changes the Answer

Use supplied context and established patterns for ordinary drafting. Research current comparable products when the user asks for benchmarking, the product family materially changes the conventions, or the communication is consequential enough to justify the added latency. Prefer primary sources and extract patterns rather than copying another company's prose.

Read `references/patterns-and-examples.md` when a concrete pattern, audit example, or research rationale would improve the result.

## Return the Result

Return:

1. `Selected mode: {mode} — {one-line reason}`
2. `Emoji treatment: {plain, literal, or whimsical} — {one-line reason}` when relevant
3. `Subject: {subject}`
4. Draft body
5. An alternate mode only when it exposes a material tradeoff

For revisions and audits, show before and after for every communication unless the user requests final copy only. Follow the rewrites with consolidation and suppression recommendations.
