# Response Style Installation

Scope: Install one user-approved response-style policy through Gauntlet for Codex and Claude, add Codex response defaults, and prevent installation from silently overriding conflicting user guidance.

Proof scope: full

## Decisions

- Keep the response policy in one installer-owned `router/response-style.md` source rendered through `router/AGENTS.md`. Codex receives it in the managed global `AGENTS.md` block; Claude receives the same policy through its managed `CLAUDE.md` import. The contributor `AGENTS.md` no longer repeats a second response-style paragraph.
- Apply `model_verbosity = "low"` and `personality = "none"` only to Codex. Missing values are added; different existing values stop installation until the user chooses Gauntlet values, existing values, or no config mutation.
- Treat semantic instruction conflicts as a user decision rather than claiming shell code can understand arbitrary prose. The installer stores hashes of user-owned and candidate instructions and reopens the review gate when either changes. The installing agent must show conflicting passages and ask which should remain active.
- Support both valid voice-conflict outcomes. `--response-style gauntlet` installs the shared policy; `--response-style existing` omits that policy while retaining the rest of Gauntlet.
- Never edit user-owned instruction bytes inside the installer. If the user chooses to deactivate a conflicting passage, the installing agent preserves a user-visible backup before making that separately authorized edit.
- Keep installation noninteractive and automation-safe. Conflicts exit before payload or config mutation and provide explicit rerun flags. `closeout execute` runs the same preflight before committing or merging.
- Preserve the supplied response policy verbatim. Its concise-output direction and detailed-product framing create mild tension, but the text resolves it by requiring material details and making examples conditional on practical benefit.

## Exceptions

- The initial design gated only first installs without an existing managed block. Adversarial review found that an update could replace Gauntlet guidance beside changed user-owned instructions without another review. Hash-based re-review replaced that design.
- A second review found that acknowledging a conflict was insufficient when the user chose an existing voice: the installer still had no way to omit Gauntlet's conflicting style. A render-time response-style choice now supports that outcome without forking the workflow router.
- Semantic compatibility remains human or agent judgment. Deterministic proof covers the stop, preservation, explicit-choice, hashing, and routing behavior; it cannot prove that every prose conflict will be identified correctly.
- The real global Gauntlet installation was not changed from this branch. Repository tests use temporary agent homes, and local activation remains a later merge/install action.

## Production Quality Bar

Not relevant because this changes a local agent workflow installer, not a deployed production data plane. Mutation safety is covered by preflight, temporary-home tests, atomic writes, and explicit conflict choices.

## Coverage Gap Candidates

None. The missing update-time conflict gate was resolved in this change rather than deferred.
