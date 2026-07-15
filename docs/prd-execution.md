# Product Task To Epic Execution

Status: authoritative Gauntlet reference for implementing an accepted PRD.

One product task may develop a coherent product across many Epics. When the user says to implement the PRD, Gauntlet freezes the complete accepted target once, creates one visible implementation task and one Execution Run per independently shippable Epic, and starts every dependency-ready Epic. The user can step away while unaffected work continues; only a decision that changes scope, cost, authority, or safety returns to the product task.

## Terms And Boundaries

| Term | Responsibility |
| --- | --- |
| PRD | Human-readable product source. It may hold several accepted, proposed, or deferred Epics and their shared context. |
| Epic | Independently shippable and reversible product outcome with stable identity, Scope Areas, release stages, and dependency boundaries. |
| Product task | User-visible task that owns product discussion, the complete launch set, cross-Epic decisions, and aggregate lifecycle copy. |
| Epic task | User-visible implementation task for exactly one Epic. It never creates another Epic task. |
| Epic launch set | Immutable controller state for target membership, source snapshot, native task IDs, one run per Epic, dependencies, blockers, and aggregate status. |
| Scope Area | Stable product responsibility inside one Epic. |
| Ticket Graph | Generated dependency graph for one Epic's current implementation. It is not a second product specification. |
| Ticket | Independently assignable implementation or triggered verification unit. |
| Cohort Verification | Optional combined proof for Tickets sharing one named interface or invariant. |
| Execution Run | Durable local implementation state for exactly one Epic. |
| Project PR | Run-backed PR for that Epic, bound to its exact verified revision. |
| Receipt | Compact evidence pointer and exact verification identity. It is not proof by itself. |

## Shape The Product, Then Launch Together

During product discussion, keep related Epics in one canonical PRD when that preserves useful shared context. Invite the user to continue fleshing out implementation ideas as distinct Epics. A target Epic is launchable only when it is accepted, build-ready, independently shippable, independently reversible, explicit about release stages, and either dependency-ready or linked to a named upstream `merged`, `deployed`, or `productionProved` boundary.

`Implementation target` lists the complete launch membership. Proposed, deferred, unresolved, or non-independent outcomes remain outside it. The product task runs `gauntlet.py epic-tasks init`, then executes only the controller's missing dependency-ready `create_thread` actions. Native task IDs and one-Epic run paths are recorded back into the launch set. Ambiguous task creation is reconciled before any retry.

The instruction **implement the PRD** authorizes this complete target through each Epic's normal end-to-end path: task creation, branch/worktree, Ticket execution, proof, Project PR, required-check merge, specified deployment and production stages, canonical-document reconciliation, and safe cleanup. It does not manufacture unavailable credentials, unsafe authority, or proof.

## One Epic Per Run

Each Epic task reads `source.snapshotPath` from the launch set and initializes one run with that immutable snapshot, the frozen launch set, and exactly one target Epic. It must not pass the mutable canonical PRD path as `prd-run.py init --source`. Use `single-final-pr` for a small reviewable Epic. Use `review-prs-plus-final` only when one large, tightly coupled Epic needs parent-owned intermediate Review Unit PRs into its integration branch. Review Units are not release boundaries.

Compile Tickets by code ownership and dependency boundaries, not by the number of PRD headings. Keep tightly coupled implementation with one owner or reuse the same child sequentially when affinity saves reconstruction. Schedule the dependency-ready critical path, integrate continuously, and release downstream Tickets as their inputs land.

Cohorts are optional. Declare one only when multiple Tickets share a material interface or invariant; otherwise run targeted Ticket checks and continue. Ordinary proof is verified by the Epic-task parent. Independent verification Tickets are reserved for a concrete consequential boundary.

## Tiered Verification

Use the smallest proof that distinguishes the intended behavior from a plausible wrong implementation:

1. Run targeted checks for each integrated Ticket.
2. Run each declared shared-invariant Cohort check once.
3. Run one fresh final Epic verification against the canonical Epic acceptance on the exact integrated commit and tree.
4. Run applicable merge, deployment, production, and rollback proof without collapsing their states.

A verification receipt may be reused only when commit and tree, command, toolchain, fixture or oracle digest, and relevant environment identity match exactly. The final Epic check is always fresh. A failed final criterion keeps `implemented` false and prevents Project PR generation.

For billing or paid actions, credentials/auth/permissions, migrations or data loss, production authority, destructive actions, or equivalent material harm, run deterministic checks first and then three parallel, distinct review lenses on the same exact revision:

- trust, security, and authority;
- failure, concurrency, and recovery;
- black-box behavior and required non-effects.

Fix findings once and rerun affected proof. Before a production-hitting action, run the repository-owned dry run and any meaningful bounded canary and rollback. Gauntlet coordinates facts and authority; the target repository owns provider-specific commands, caps, fixtures, deployment, and production oracles.

## Durable State And Completion

After launch, the launch set owns cross-Epic operational state. After an Epic Run starts, its source lock, manifest, and resume file own Epic execution state. Conversation remains the place for user decisions, not reconstructed progress.

The Epic Run lifecycle is:

```text
discussing -> accepted -> compiled -> executing -> integrating
-> cohort_verified -> epic_verified -> merged -> deployed
-> production_verified -> complete
```

`cohort_verified` is a valid no-op transition when no Cohorts are declared. Inapplicable external stages are explicitly skipped; skipped never means proved.

The deterministic completion projection keeps these facts separate:

| Fact | Mechanical condition |
| --- | --- |
| `implemented` | All Tickets integrated, declared Cohorts passed, and final Epic verification passed on exact integration HEAD. |
| `merged` | The exact verified revision is confirmed on the default branch through the recorded PR. |
| `deployed` | Deployment evidence identifies the exact merged revision. |
| `productionProved` | The production oracle passed against the deployed revision. |
| `complete` | Every release stage applicable to this Epic is closed. |

`project-pr --run` emits schema 3.0 facts from the locked Epic, changed paths, accepted criteria, verification receipts, deferrals, completion projection, and release gates. No model-authored project summary or per-Epic outcome artifact is required. A clean commit after final Epic verification invalidates the projection.

## User-Facing Lifecycle

The product task surfaces only collaborative, useful state:

- while shaping: invite the user to keep going and capture the rest of the product as Epics;
- at launch: say how many Epics started and how many wait on named dependencies, then let the user take a break;
- at Epic start: name the accepted outcome and exact-revision final verification;
- at a material blocker: give the decision, recommendation, impact, authority not granted, and unaffected Epics still moving;
- at Epic finish: say `implementation-complete`, exact revision, proof summary, pending release gates, and remaining count;
- at aggregate finish: report exact implementation and release state without implying deployment or production proof.

Routine Ticket generation, subagent progress, receipts, retries, and unchanged polls remain internal.

## Bootstrap And Convergence

This contract replaces executable multi-Epic Execution Runs, mandatory authored summary/outcome artifacts, mandatory Cohorts, default verifier Tickets, and duplicate implementation-plan documents. Historical Markdown may describe those mechanisms only as clearly superseded evidence. The installer copies the new runtime atomically, deletes retired payload files, preserves every unmanaged byte, and must pass the repository-plus-installed convergence gate before global activation.
