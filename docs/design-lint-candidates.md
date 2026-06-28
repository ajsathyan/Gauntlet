# Design Lint Candidates

These candidates mirror UI lint ideas called out in Vercel's product-design guidance pattern. They are not universal Gauntlet rules. Copy them into a project only when the design system and component APIs make the check reliable.

## Candidate Checks

| Candidate | When Code Can Enforce It | Suggested Action |
| --- | --- | --- |
| Prevent nested modals | Component tree exposes nested modal/dialog usage. | Error or warning because nested modals break focus, keyboard navigation, and layering. |
| Prefer radio buttons for 2-3 static options | A select has exactly 2-3 static options and no dynamic source. | Warn that radio buttons keep every choice visible. |
| Require accessible names | Icon buttons or form controls lack labels, `aria-label`, or an associated label. | Error with the missing control location. |
| Reject custom focus rings | Custom classes override shared focus tokens. | Error or autofix to shared focus utilities. |
| Block ad hoc visual overrides | `className` changes a design-system component color, radius, or shadow. | Reject visual token overrides while allowing layout classes. |
| Require modal body/content primitive | Modal content can overflow without a dedicated body/container primitive such as `Modal.Body`. | Warn so headers and footers can remain stable while body content scrolls. |
| Replace raw shadows | Raw shadow utilities bypass theme-aware Material or elevation classes. | Warn or autofix when a direct mapping exists. |
| Avoid duplicate borders | A border duplicates a design-system Material/component built-in treatment. | Warn when the component already owns the boundary. |
| Keep spacing on the 4px grid | Arbitrary spacing falls outside the project spacing scale. | Suggest the closest standard utility. |
| Migrate deprecated Tailwind utilities | Deprecated utility names have direct safe replacements. | Autofix safe migrations. |

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
