# Quiet Workflow, Material Packet Validation, And Guaranteed Merge Handoffs

**Date:** 2026-07-09

**Status:** Proposed for user sign-off. This document records the corrected design only; no runtime behavior has been implemented.

## Goal

Make Gauntlet rigorous without making the conversation feel like a workflow log. Preserve the child-work controls that prevent unsafe parallel implementation, remove checks and narration that have not earned their cost, and make “merge this” perform a complete PR handoff with a useful description and matching `CHANGELOG.md` entry.

## Evidence From Real Traces

Seven unique packet-validation runs produced nine attempts. Seven attempts passed initially. Two attempts were rejected, corrected, and then accepted. Both rejections were only `duplicated_inline_context`; no recorded run caught overlapping writes, shared mutable state, secrets, missing packet files, invalid roots, broad write ownership, or duplicate proof targets.

Using the `o200k_base` tokenizer on the before/after manifests:

| Trace | Rejected manifest | Accepted manifest | Full-manifest increase | Inline-context increase |
| --- | ---: | ---: | ---: | ---: |
| RunPod reconciliation | 1,366 tokens | 1,325 tokens | +3.1% | +17.2% |
| Analytics design plan | 706 tokens | 599 tokens | +17.9% | +150.7% |
| Combined | 2,072 tokens | 1,924 tokens | **+7.7%** | **+47.9%** |

The accepted rewrites removed 148 tokens, or 7.1% of the rejected files. This is an upper bound on the cost caused by duplication because the edits also removed substantive detail; the traces do not isolate duplicate text from general shortening.

The actual child calls are more revealing. Across the 11 dispatched child instructions in those two traces, 866 of 2,143 instruction tokens were repeated exact sentences beyond their first occurrence. That is 40.4% of the instruction text. The validator did not prevent this because the dispatch prompts were written separately after validation. Separate children still need the same safety constraints, so these tokens are not all removable, but the result proves that paraphrasing a manifest to pass a shingle test is not a useful control over real context cost.

## Design Decision

Use reference-based packet composition plus a material-risk validator.

Two alternatives were rejected:

1. **Keep the current duplicate blocker.** It saved a small amount of manifest text but did not govern actual dispatch prompts and encouraged semantically identical paraphrases.
2. **Remove packet validation entirely.** The sample is too small to conclude that overlap, shared-state, secret, ownership, or missing-packet checks are unnecessary. Those checks can also be preventing errors before they reach the log.

The selected design prevents duplication structurally and limits blocking validation to conditions that can corrupt work, leak data, or make a lane non-executable.

## Child-Work Contract

Keep these guarantees:

- The main task owns user decisions, accepted scope, integration, PR creation, and merge.
- Every child implementation lane receives a bounded packet before implementation begins.
- Packets name owned and avoided files, state access, dependencies, inputs, outputs, proof, and the `Needs decision` return path.
- Write-heavy lanes use isolated worktrees unless they are tiny and provably disjoint.
- Child lanes return a compact report to the main task and never push directly to `main`.

Remove these requirements:

- No child-task title lifecycle or `[To Do]` / `[In Progress]` / `[Done]` renames.
- No new fork, provenance, thread-ID, or child-archive machinery.
- No required `title` or `status` field in the packet manifest; native Codex state is sufficient.
- No packetization declaration when no child implementation lanes exist.
- No chat or final-summary announcement for a clean packet validation.

### Reference-Based Packet Shape

Schema `1.2` moves shared material out of every lane:

```json
{
  "schemaVersion": "1.2",
  "runId": "2026-07-09-example",
  "shared": {
    "projectRoot": ".",
    "acceptedSource": "docs/specs/example.md",
    "constraints": ["Preserve unrelated work."],
    "askUserPolicy": "Return Needs decision to the main task.",
    "expectedReturn": "Verdict, evidence, residual risk, and one next action."
  },
  "lanes": [
    {
      "id": "C1",
      "skill": "implementer",
      "objective": "Implement the bounded policy change.",
      "worktreePath": ".worktrees/C1-policy",
      "scope": "Policy implementation and tests",
      "inScope": ["src/policy/**", "tests/policy/**"],
      "outOfScope": ["src/ui/**"],
      "filesRead": ["src/policy/**", "tests/policy/**"],
      "filesWrite": ["src/policy/**", "tests/policy/**"],
      "filesAvoid": ["src/ui/**"],
      "stateScope": "policy",
      "stateAccess": "mutates",
      "dependencies": [],
      "consumes": ["accepted policy spec"],
      "produces": ["policy behavior", "regression proof"],
      "laneConstraints": [],
      "proof": ["python3 -m unittest tests.policy"],
      "contextDelta": "Use the existing policy boundary; do not redesign the UI.",
      "taskPacketRef": ".gauntlet/packets/C1.md"
    }
  ]
}
```

The main task or dispatcher composes `shared` plus the lane delta. Common safety language remains exact instead of being rewritten differently for each child. A source reference is preferred over copying a large accepted spec into every prompt. This reduces manifest and prompt boilerplate, although each independent child still must ingest the shared constraints it needs.

The validator runs for two or more parallel lanes and for any write-heavy child lane, including a single write-heavy lane. A single small read-only exploration/review child still receives a bounded prompt but does not need a manifest-validation gate.

### Blocking Versus Advisory Findings

Block implementation for:

- Missing required packet fields or packet/source files.
- Invalid project root or path escape.
- Overlapping write ownership.
- Shared mutable state without an explicit dependency/order.
- Secrets in shared or lane context.
- Overbroad write ownership.

Warn without blocking for:

- Repeated lane context that could move to `shared`.
- Oversized shared or lane context.
- Duplicate proof targets.
- Overbroad read scope on read-only review lanes.

Warnings are stored in the validation artifact and surfaced only if they change the plan, invalidate a lane, or need a user decision. A successful validation remains silent.

## Quiet Main-Conversation Contract

Gauntlet continues to make internal decisions but stops narrating routine machinery.

- Assign and apply a priority/title on the first responsible substantive response and no later than the third exchange. Do it silently unless the label changes what the user should expect or needs confirmation.
- Research is never `p4` merely because it is research. Use consequence and durable decision value; normal bounded research defaults to `p3`.
- Reassess priority when implementation begins and when scope materially changes. Mention it only when the priority changes.
- Keep mode, depth, proof scope, gate selection, skill selection, worktree creation, packet success, and review transitions out of chat unless they produce a decision, blocker, material finding, or changed expectation.
- Run edge-case foresight for every genuine scope addition. A clean result may use the internal plan marker `Scope delta checked: no material change.` for consistency, but it is not narrated or copied into the run log/final response. Material findings update the plan and are called out.
- Fold architecture hygiene into the normal final review. Name it only when it finds something, is explicitly requested, or is required for a release decision.
- Do not run advisory helpers, full sweeps, role panels, skill suites, or production gates without their existing trigger.

User-visible updates should contain one of: a recommendation, a changed assumption, a meaningful progress result, a blocker, a decision request, proof, or a completed outcome.

## Guaranteed Merge Contract

“Merge this,” “land this,” or “merge this to main” authorizes the complete safe lifecycle for the current scoped work:

1. Preserve unrelated dirty work and use the task branch/worktree.
2. Run the relevant proof and self-review.
3. Create or update `CHANGELOG.md` under `Unreleased`; create the file when absent.
4. Create coherent commits. A quick task normally has one behavioral commit with its tests and changelog. Multiple commits are kept only when each is independently meaningful.
5. Push the task branch.
6. Create or update one PR against the default branch with the format below.
7. Verify that the PR `## Changelog` entry exactly matches the `CHANGELOG.md` entry.
8. Wait for required checks and blocking review state. Any new commit refreshes proof and the PR body.
9. Merge with the repository’s configured method; use a merge commit when the repository allows multiple methods and provides no override.
10. Delete the remote branch, remove the local branch/worktree only when safe, and verify the merged result on the default branch.

For this repository, protect `main` by requiring a PR and the green `gauntlet` check, without requiring a separate human approval. Keep conversation resolution required and force pushes/deletion disabled. This preserves the quick local-prototype loop while making the PR proof bundle unavoidable for merges.

## PR And Commit Format

### Title and commit subject

Use `<area>: <imperative behavioral outcome>`, for example:

```text
workflow: generate contextual merge handoffs
```

The subject explains the behavior a reviewer gets, not the files the commit touched.

### PR body

```markdown
## Problem

Explain the higher-level problem, who it affects, and why the previous behavior was insufficient. Include the causal mechanism only when it helps a reviewer understand the change.

## Solution

Describe the resulting behavior, important invariants and design choices, what stays unchanged, and any meaningful non-goals. Do not provide a file/function tour.

## Changelog

- One concise user- or operator-visible release-note entry. This exact line is also written to `CHANGELOG.md` under `Unreleased`.

## Testing

- `exact command` — PASS/FAIL — what the result proves.
- Include before/after evidence, unchanged behavior, or `Cannot verify` when relevant.

## PR Note

Record the material tradeoff, compatibility/recovery context, meaningful non-goal, or merge rationale that a future maintainer should know.

## Security / Risk

Include only when material. State the concrete risk and mitigation or recovery path. Omit this section rather than writing empty boilerplate.
```

The PR renderer must take the user goal and accepted decisions as its primary source. The diff is used only to verify factual completeness, not to choose the narrative structure.

## Acceptance Criteria

- The two recorded duplicate-context cases are documented as +7.7% full-manifest overhead, not presented as proof of a material dispatch failure.
- Duplicate context no longer blocks a packet; it is preventable through `shared` references and advisory normalization.
- Material packet hazards still block before parallel/write-heavy child implementation.
- Child packets retain ownership, state, proof, and main-task control without title/status churn or new child-thread provenance machinery.
- Priority assignment happens by the third exchange, research is consequence-ranked, and unchanged reassessments stay silent.
- Clean scope-delta, packet, mode, gate, skill, worktree, and review mechanics stay out of user-visible chat.
- “Merge this” creates/updates `CHANGELOG.md`, commits, pushes, opens/updates a contextual PR, waits for required checks, merges, cleans the branch/worktree, and verifies `main`.
- The PR contains Problem, Solution, Changelog, Testing, and PR Note in the agreed format; Security / Risk appears only when material.
- The PR changelog line exactly matches the committed `CHANGELOG.md` entry.
- Tests prove the new packet schema, blocking/advisory split, quiet guidance, PR renderer, changelog consistency, and merge action ordering.

## Non-Goals

- Eliminating shared safety/context from each independent child’s model context.
- Depending on prompt caching for correctness or guaranteed savings.
- Adding child-task fork/provenance/thread-ID enforcement.
- Requiring human approval for every solo-repository PR.
- Publishing a GitHub release or external release notes for every merge.
- Turning routine clean checks into a run-log or final-summary checklist.
