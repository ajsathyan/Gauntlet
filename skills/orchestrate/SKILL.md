---
name: orchestrate
description: Coordinate multiple agents for implementation. Use for every implementation in Gauntlet.
---

# Orchestrate

All delegated work runs through internal subagents. Do not create new user-visible Codex tasks or threads unless the user explicitly asks for them.

Remain available to the user while delegating substantive work. Route agents by role and consequence:

- Run narrow, read-only scouts on `gpt-5.6-luna` with `reasoning_effort: "medium"`.
- Run clear, bounded leaf implementations that do not need delegation on `gpt-5.6-luna` with `reasoning_effort: "high"`. Use `"xhigh"` when the bounded task is unusually difficult or fragile.
- Use `gpt-5.6-sol` with `reasoning_effort: "high"` for coordinators or agents that must resolve material ambiguity, synthesize across workstreams, message peers, or delegate recursively. Their clearly bounded leaf workers may still use Luna.
- Use Sol for high-consequence security, migration, architecture, or difficult debugging work even when the task appears bounded.

An explicit model override cannot use `fork_turns: "all"`; use `"none"` or a positive number of turns and provide a self-contained assignment with the necessary context. Give each agent distinct ownership, prevent overlapping assignments, and instruct leaf workers not to delegate. Integrate the results and keep approvals with the user.
