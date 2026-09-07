---
name: orchestrate
description: Coordinate multiple agents for implementation. Use for every implementation in Gauntlet.
---

# Orchestrate

Optimize for time to an integrated result. Delegate liberally through the Codex app's internal subagents when useful independent work or meaningful speedup is available. Create user-visible tasks only when explicitly requested. Keep user intent, scope decisions, integration, approvals, and the final answer with the main agent, which stays available to the user.

Route by role, preserving explicit user overrides:

- **Bulk reader — `gpt-5.6-luna`, `xhigh`:** Answer a focused question across a bounded set of files, documents, or traces. Give the question, source boundaries, and selection criteria; return findings with exact references, coverage, and uncertainties.
- **Pattern writer — `gpt-5.6-luna`, `xhigh`:** Apply settled behavior using an established pattern. Give the reference, required differences, and owned files; match conventions and flag exceptions requiring new behavioral decisions.
- **Implementer — `gpt-5.6-sol`, `medium`:** Implement a clear outcome, make ordinary implementation choices, run checks, or handle supporting work. Give the outcome, relevant interfaces, constraints, and ownership.
- **Complex implementer or coordinator — `gpt-5.6-sol`, `high`:** Handle difficult implementation, complex writing, debugging, ambiguity, consequential reasoning, or dependent work. Give the problem, known evidence, and decision boundaries without pre-solving it.

Split by distinct deliverables or questions. Shared reading is fine; duplicate responsibility and overlapping edits are not. Keep tightly coupled changes with one owner until shared interfaces or decisions are settled. Start independent work early and integrate completed results without waiting for unrelated work. The main agent does complementary work rather than repeating delegated exploration. Readers and pattern writers are leaf workers by default; use peer messaging to resolve dependencies and reuse informed workers for related follow-ups.

Give enough relevant context to finish independently, including source paths and room to inspect related material. Avoid pre-reading everything just to delegate it. Default to `fork_turns: "none"`, using a small positive history slice when useful; explicit model overrides cannot use `"all"`. Assignment boundaries are policy, not enforced security boundaries.

Use existing deterministic tools for filtering, counting, grouping, sorting, and mechanical extraction. Split oversized inputs deliberately and disclose truncation, omissions, and unreadable sources. Reasoning effort changes reasoning depth and budget, not context-window capacity.

Writers edit owned files and return a concise change summary, check results, and unresolved issues. Keep raw logs and large outputs in referenced artifacts; inspect targeted evidence during integration. Preserve independent verification of implementation work against accepted outcomes and the exact committed candidate; worker summaries alone do not prove behavior.
