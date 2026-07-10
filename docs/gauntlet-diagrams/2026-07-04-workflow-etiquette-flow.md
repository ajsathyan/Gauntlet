# Workflow Etiquette Flow

Metadata:

- ID: `workflow-etiquette-flow-2026-07-04`
- Feature: `workflow-etiquette`
- Source thread/title: `p1-auto: Simplify Gauntlet planning workflow`
- Tags: `gauntlet`, `etiquette`, `planning`, `execution`, `archive`, `execution-mode`, `decision-gate`, `follow-up`
- Related files: `docs/workflow-etiquette.md`

Purpose: show the lean Gauntlet loop from research or intake through one canonical plan, execution, proof, and archival.

```mermaid
flowchart LR
    subgraph Main["Main Path"]
        A{"Research or change?"}
        A -- "Research" --> R["Evidence-bounded research"]
        R --> Z{"Implementation requested?"}
        Z -- "No" --> O["Answer with confidence<br/>and Cannot verify"]
        Z -- "Yes" --> S["Accepted spec"]
        A -- "Change" --> S
        S --> P["One canonical plan"]
        P --> E["Implementation"]
        E --> V["Proof and review"]
        V --> G["Closeout or archive"]
    end

    subgraph Control["Triggered Controls"]
        J["Decision gate only for<br/>a material unresolved choice"]
        D{"Parallel lanes earned?"}
        M["Bounded child prompts<br/>from the canonical plan"]
    end

    subgraph Side["Side Captures"]
        C["Continuity<br/>landing pad"]
        U["Follow-Up<br/>strong or later"]
    end

    S -. "material decision" .-> J
    J -. "resolved" .-> P
    P --> D
    D -- "No" --> E
    D -- "Yes" --> M
    M --> E

    E -. "pause" .-> C
    C -. "resume" .-> E

    E -. "future topic" .-> U
    U -. "captured" .-> E
```
