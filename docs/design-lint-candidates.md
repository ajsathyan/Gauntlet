# Design Lint Candidates

These candidates capture general, framework-independent UI checks that can graduate into linters.

## Candidate Checks

| Candidate | When Code Can Enforce It | Suggested Action |
| --- | --- | --- |
| Prevent nested modals | Component tree exposes nested modal/dialog usage. | Error or warning because nested modals break focus, keyboard navigation, and layering. |
| Prefer radio buttons for 2-3 static options | A select has exactly 2-3 static options and no dynamic source. | Warn that radio buttons keep every choice visible. |
| Require accessible names | Icon buttons or form controls lack labels, `aria-label`, or an associated label. | Error with the missing control location. |
| Require semantic button/link usage | A navigation element is implemented as a button, or a non-navigation action is implemented as a link. | Warn or error because action and navigation semantics affect keyboard behavior, accessibility, and expectations. |
| Require associated input labels | An input, select, or textarea lacks an associated label or equivalent accessible name. | Error because clicking the label should focus the field and assistive tech needs a name. |
| Require form semantics for submit flows | A submit button and editable fields appear without a wrapping form or equivalent submit handler. | Warn because Enter-to-submit is a platform expectation. |
| Require appropriate input types | Known field names such as email, password, tel, url, or number use a generic text input. | Warn with a suggested input type when the field purpose is clear. |
| Disallow interactive tooltip content | Tooltip/popover content used as a tooltip contains buttons, links, inputs, or other focusable controls. | Error because hover tooltips should not become hidden interaction surfaces. |

## Review Guidance

Use `docs/ui-constitution.md` for frontend checks that need rendered behavior, browser proof, or product judgment.

## Promotion Rule

Use code for clear rules only:

```text
Can code identify the failure without rendering?
No -> keep as agent guidance.
Yes -> can the rule avoid likely false positives?
No -> keep as agent guidance.
Yes -> does the violation have a concrete fix?
Yes -> consider lint or autofix.
No -> warning or guidance.
```

Needs product or codebase context: use agent guidance.
Establishes a new product policy: require a human decision.
For either path, add an example or eval that can catch regressions.
