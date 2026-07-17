# Breakthrough Search

## Inputs

- Frozen product job, capability map, parity ledger, compatibility matrix, and baselines
- User targets and priority order

## Actions

1. Freeze one `breakthrough-evidence-packet.json` using the renderer's schema: contract version, objective, artifact paths and hashes, authority, proof/return contracts, blocker/ask-user policy, user targets, and priority order. Index its path and SHA-256 from `refactor-state.json`. Pass that expected hash to [render_agent_prompt.py](../scripts/render_agent_prompt.py) once with a shared `return-to-root` assignment. Dispatch three independent agents with `fork_turns: "none"` and that exact rendered prompt. Do not disclose a favored design or the other agents' work. Use this no-history mode only after every needed input is durable and the evidence packet hash verifies.
2. Require each agent to identify dominant accidental complexity; propose up to three structurally different compression hypotheses; select its highest-leverage end state; name the mechanism for step-change gains; estimate effects on production/test LOC, concept and dependency count, extension cost, test feedback, and runtime/resources; state compatibility/migration risks; define the smallest diverse-slice prototype; and give falsification evidence.
3. Require at least one strongest plausible redesign, not only cleanup. Search for duplicated lifecycle, controls, pipelines, persistence, rendering, exports, testing, indirection, and change amplification.
4. Synthesize by underlying mechanism. Record convergence, disagreement, unique proposals, assumptions, and estimate confidence. Do not average incompatible architectures into a compromise.
5. Retain the strongest one or two credible hypotheses for prototypes. Reject ambition only with evidence such as irreducible domain variation, failed compatibility, unsafe migration, displaced complexity, worse performance, or configuration that becomes harder than code.
6. Set a parity floor, an evidence-supported committed target, and a breakthrough target large enough to require structural change. Keep explicit user targets binding. When no useful numeric baseline exists, use measurable end-to-end outcomes without inventing percentages.

The root task assigns proposal IDs after receipt, compares mechanisms, and owns synthesis. A proposal agent cannot change the product contract, integrate a proposal, authorize deletion, or make a completion claim.

## Definition of Done

Breakthrough search is done when the frozen evidence packet hash verifies, all three compact JSON receipts satisfy the common contract, materially different mechanisms were considered, and each selected hypothesis has a falsifiable diverse-slice prototype and comparable success measures.

## Receipt

Write `breakthrough-search.md` containing the three unblended proposals, synthesis, targets, selections, rejections, and falsification criteria. Update `refactor-state.json` with its hash and selected hypothesis IDs.

## Invalidation

Repeat the independent search when the source, product job, inventory, compatibility floor, baseline, or binding target changes materially. Re-synthesize when an agent received leaked conclusions or a favored architecture.
