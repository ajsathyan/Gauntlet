---
name: craft-product-terminology
description: Use when naming or renaming a product, feature, capability, service, component, or internal module; when product work introduces canonical terminology; or when another Gauntlet skill needs responsibility-accurate names and a minimal public concept model.
---

# Craft Product Terminology

Create the smallest terminology system that makes the product's real responsibilities clear. Prefer names that a reader understands on first read and that still sound natural in use.

When the request concerns one thing, name that thing without manufacturing a larger taxonomy.

## Map The Capability Before Naming It

Reconstruct the smallest capability map needed for the decision. Identify:

- who uses or encounters each concept;
- what it observes or controls;
- whether it observes, decides, acts, stores state, or presents information;
- which concepts are public and which are internal;
- which neighboring concepts affect its boundary.

Follow Gauntlet's minimum-question rule. For terminology work, prioritize unresolved questions about audience, responsibility, authority, public versus internal scope, neighboring concepts, and desired tone.

Complete this step when every thing being named has an observable responsibility and boundary.

## Separate Public Concepts From Internal Components

Group related responsibilities into a few coherent public concepts. Keep implementation plumbing internal unless it has independent user-facing behavior.

Give internal components precise engineering names without automatically turning them into public product surfaces. Avoid exposing many pieces when a smaller set gives users a clean mental model.

Complete this step when users can understand the product through the minimum necessary public concepts.

## State Responsibility And Non-Responsibility

For each concept, write one sentence that says what it owns and what it does not own.

Treat observation, decision, action, durable state, and presentation as different responsibilities. Make the name reflect actual authority. An observer should sound observational, an actor should sound active, a store should sound durable, and an interface should not sound like the automation owner.

Complete this step when no proposed boundary overstates what the component can decide or do.

## Identify Established Terms

Prefer an established domain term when it describes the responsibility accurately. Preserve names the user already likes unless there is a concrete collision or misleading boundary.

For terminology research, distinguish established domain terms from company-specific branding, then adapt relevant conventions to this product's actual responsibilities, audience, neighboring concepts, and existing vocabulary. Do not copy a prominent company's name merely because it is familiar.

Treat voice transcription, uncertain wording, and apparent typos as provisional until confirmed. Never promote unverified wording into canonical terminology.

## Generate A Small Candidate Set

Generate only enough candidates to compare useful approaches:

- literal or descriptive;
- slightly branded but still legible;
- acronym-based only when the expansion is a natural descriptive name without the acronym.

Prefer literal clarity over novelty. An acronym's expansion must read like a proper name someone would choose independently. Reject filler words, forced backronyms, and phrases engineered to reach desired letters.

## Test Every Candidate

Test each candidate for:

- first-read clarity;
- actor and authority accuracy;
- sentence fit;
- interface-label fit;
- domain, trademark, or neighboring-name collisions;
- accidental implications;
- teaching cost;
- unnecessary product fragmentation.

Use real sentence and interface patterns from the product. When none are supplied, test neutral forms such as:

- "{Name} detected {condition}."
- "{Name} will {action}."
- "Open {Name}."
- "Change {setting} in {Name}."

A reader should be able to infer what the thing observes or controls, whether it acts, and where to understand or change its behavior.

## Recommend The Minimal System

Recommend one coherent terminology system. State which names are public, which remain internal, and which require teaching.

Retain existing clear names. Prefer a familiar descriptive term over a less legible acronym or invented brand. Flag any recommendation whose accuracy depends on an unresolved product boundary.

Complete the work when the recommendation exposes no more public concepts than users need and every recommended name passes the responsibility, sentence, interface, and collision tests.

## Return The Result

Return:

1. Capability map with the minimum recommended public pieces.
2. Responsibility and boundary for each piece.
3. Candidate table with:
   - Name
   - Type: literal, branded, or acronym
   - Natural expansion, if any
   - What it communicates
   - Risks
   - Sentence and interface test
4. One recommended terminology system, including which names remain internal.
5. Rejected candidates with concrete reasons.
6. Any remaining question that materially changes the result.

For a single-component request, still return its responsibility boundary, a three-to-five-row candidate table using the columns above, one recommendation, and concrete rejections. Omit only system-level concepts that do not apply.
