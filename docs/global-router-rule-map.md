# Global Router Rule Map

This map keeps the compact installed router aligned with the detailed triggered guidance.

| Router invariant | Detailed destination |
| --- | --- |
| Normal Requests deliver the bounded artifact directly and use only a smoke check. | `docs/workflow-etiquette.md` |
| Non-trivial implementation uses Design acceptance → Build/Implement → Verify → Land → Ship. | `docs/design-build-verify.md` |
| The user accepts the exact `Acceptance` section before non-trivial implementation. | `design`, `docs/local-documentation.md` |
| Build planning is internal and ephemeral. | `planner`, `implementer` |
| Native children receive bounded assignments only when parallelism earns its context cost. | `implementer`, `docs/workflow-etiquette.md` |
| Independent Verify reports separate Build and Architecture verdicts on the exact revision. | `verify`, `docs/meaningful-proof.md` |
| Security and production checks run only for concrete accepted consequences. | `docs/production-quality-bar.md`, specialist skills |
| Titles are silent, plain, descriptive, and at most four words. | `docs/workflow-etiquette.md` |
| The request or accepted Design authorizes merge and ordinary deployment without a second acceptance gate. | `ship`, `land`, `docs/github-discipline.md` |
| Skills use clear triggers, checkable completion, negative cases, and honest proof layers. | `docs/skill-quality-bar.md` |

The installer owns only the marked Gauntlet block. User-owned instructions outside it remain unchanged.
