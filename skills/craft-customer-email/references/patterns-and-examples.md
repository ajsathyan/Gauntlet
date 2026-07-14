# Patterns And Examples

Use these examples to stabilize structure, not as templates to copy mechanically. Adapt the content, voice, evidence, and lifecycle to the product and reader.

## Design Rationale

- [Postmark](https://postmarkapp.com/guides/transactional-email-best-practices): treat transactional email as product interface; use outcome-focused subjects and direct frequent notices.
- [Mailchimp transactional email](https://mailchimp.com/resources/transactional-email-examples/) and [voice and tone](https://styleguide.mailchimp.com/voice-and-tone/): put important information first, confirm the result and next step, and keep voice stable while tone changes with context.
- [Microsoft writing style](https://learn.microsoft.com/en-us/windows/apps/design/style/writing-style): use concise, helpful, active language that says what happened and what to do next.
- [Atlassian](https://www.atlassian.com/incident-management/incident-communication) and [PagerDuty](https://response.pagerduty.com/during/external_communication_guidelines/): state current impact, next steps, and the next update while maintaining one incident lifecycle.
- [First Round](https://review.firstround.com/how-the-u-s-forest-service-can-save-your-company-from-a-crisis/): separate knowns, unknowns, and what cannot yet be said; translate technical language and avoid unsupported timelines.
- [GitHub Primer](https://primer.style/product/ui-patterns/notification-messaging/), [IBM Carbon](https://carbondesignsystem.com/components/notification/usage/), and [Shopify Polaris](https://polaris-react.shopify.com/components/feedback-indicators/banner?example=banner-in-a-card): make titles factual, keep bodies short, provide one primary resolution, and disclose detail progressively.

## Outcome-first Brief

```text
Subject: Verify your new email address by Friday

Verify your new email address by Friday to keep receiving account notices at this address.

We sent a verification link to sam@example.com. The link expires in 24 hours.

Verify email: {link}
```

## Causal State-change Narrative

```text
Subject: Your data import paused after 8,420 records

Your import paused after adding 8,420 of 10,000 records because the source file contains an invalid date. The records already added remain available and will not be duplicated.

We stopped before row 8,421 and saved the error report. Correct the date in that row, then resume the same import. If you do nothing, the completed records will remain in your workspace.

Download the error report: {link}
```

## Compact Status Card

```text
Subject: June usage: 74% used, resets July 1

Your June usage is at 74%. No action is needed unless you expect higher usage before July 1.

Used          740 of 1,000 credits
Change        61% → 74%
Resets        July 1, 00:00 UTC
Overage       Disabled

Review usage: {link}
```

## Suppression And Threading

Do not send separate messages for `order delayed`, `carrier retrying`, and `delivery date updated` when they describe one unresolved shipment and require no different decision.

Use one thread:

1. Send the first delay notice when the delivery estimate changes.
2. Add a retry update only when the state, useful evidence, or next estimate changes.
3. Add the delivered or final-exception outcome to the same thread.
4. Suppress scheduled updates that add no decision, outcome, or evidence.

## Audit Check

For every communication, verify:

- The subject states the change or outcome.
- The first sentence carries the conclusion and next behavior.
- Current state, impact, prior system action, next step, timing, and reader action appear only when relevant.
- Known facts, unknowns, and signal limits are distinct.
- Repeated fields use stable labels and units.
- Emoji remain secondary and accessible.
- The message earns the reader's attention rather than duplicating another update or interface.
