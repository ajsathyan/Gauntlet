# Workflow Etiquette Flow

Metadata:

- ID: `workflow-etiquette-flow-2026-07-04`
- Feature: `workflow-etiquette`
- Source thread/title: `p1 - Indexed implementation context docs`
- Tags: `gauntlet`, `etiquette`, `planning`, `execution`, `archive`, `execution-mode`, `decision-gate`, `follow-up`
- Related files: `docs/workflow-etiquette.md`

Purpose: show the current workflow-etiquette loop from planning through archival, including review/autonomous execution mode, decision gates, delegation, follow-up strength, and pause/reentry.

```mermaid
flowchart LR
    subgraph Main["Main Path"]
        A["Planning"] --> B["Kickoff"]
        B --> M["Execution Mode<br/>review | auto"]
        M --> J["Decision Gate?<br/>optional stop point"]
        J --> C["Foresight"]
        C --> D["Delegation?"]
        D --> E["Execution"]
        E --> F["Debrief"]
        F --> G["Archival"]
    end

    subgraph Review["Review Loops"]
        R{"Domain model, latency,<br/>or stop-condition risk?"}
        Q["Clarify<br/>with recommendation"]
    end

    subgraph Side["Side Captures"]
        P["Continuity<br/>Pause Work Packet"]
        U["Follow-Up<br/>strong or later"]
    end

    C --> R
    R -- "needs review" --> Q
    Q --> C
    R -- "safe" --> D

    D -- "implementation memory needed" --> D1["Implementation Memory<br/>Lane Index"]
    D1 --> E

    E --> X{"Checkpoint"}
    X -- "continue" --> E
    X -- "model changed" --> C
    X -- "new lane" --> D1
    X -- "gate reached" --> J
    X -- "done" --> F

    E -. "pause" .-> P
    P -. "resume" .-> E

    E -. "future topic" .-> U
    U -. "captured" .-> E

    G --> Z{"Strong follow-up?"}
    Z -- "none or resolved" --> H["Archive"]
    Z -- "finish here" --> E
    Z -- "new chat" --> N["Same-repo chat<br/>with context"]
    N --> H
    Z -- "archive anyway" --> H
```
