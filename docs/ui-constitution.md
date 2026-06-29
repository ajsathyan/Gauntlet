# UI Constitution

The UI constitution is a small set of frontend standards for prototypes and product work. It is not a design system, and it does not create one. It prevents obvious drift while letting the product search stay cheap.

## When To Use

Run a bounded pass for:

- new or materially changed frontend components
- user-facing Feature work
- design-heavy prototypes
- frontend Release work
- broad responsive, accessibility, or state changes
- repeated UI findings across runs

Skip the pass for copy-only patches, narrow visual tweaks, config, backend-only changes, and local throwaway experiments unless the user asks.

## What Belongs Here

- Lint candidates when code can detect a reliable failure and there is a concrete fix.
- Black-box checks when the behavior must be proven in a browser.
- Experience checks when the answer depends on workflow, state, hierarchy, or user trust.

Do not create a design system at prototype start. Do not add speculative local UI conventions. Use existing repo conventions when they exist; otherwise keep checks general.

## Static Lint Candidates

See `docs/design-lint-candidates.md`. The default set stays general: nested modals, small static select-to-radio, accessible names, semantic button/link usage, associated labels, form semantics, clear input types, and non-interactive tooltip content.

## Black-Box Checks

Use these only when relevant to the changed surface:

- Labels focus their inputs.
- Enter submits normal forms.
- Pending submits prevent accidental duplicate requests.
- Feedback appears near the trigger or field it explains.
- Empty states point to a next action.
- Loading, error, success, disabled, and partial-data states can be reached or are explicitly out of scope.
- Responsive and touch behavior is usable at the target viewport sizes.
- Frequent interactions are not slowed by unnecessary animation.

## Experience Checks

- The first useful action is obvious.
- The user can tell what happened, what is happening, and what to do next.
- Error recovery keeps user input when possible.
- Icon-only actions have labels and, when useful, tooltips.
- Disabled controls are not the only place where an explanation appears.
- Visual hierarchy supports the task before decoration.
- New UI does not contain agent notes, draft labels, or process commentary.

## Promotion Rule

When a frontend review finds a new class of issue:

```text
Can code or browser proof detect it reliably?
No -> keep as experience guidance.
Yes -> is there a concrete fix?
No -> record an eval or guidance idea.
Yes -> add or update a pending GAP-### candidate.
```

Human review decides whether a gap becomes a lint, eval, reference, exemplar, permanent coverage gap, or no change.

## Once-In-A-While Checks

These checks are too expensive for every small change. Run them for major frontend work, before demos/releases, or when repeated failures suggest drift:

- accessibility keyboard and screen-reader smoke pass
- responsive viewport sweep
- visual regression screenshot sweep
- motion and media performance pass
- dead component and unused style cleanup
- UI constitution gap review and promotion
