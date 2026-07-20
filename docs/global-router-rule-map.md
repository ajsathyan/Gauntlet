# Global Router Rule Map

This map keeps the compact installed router aligned with the detailed triggered guidance.

| Router invariant | Detailed destination |
| --- | --- |
| Normal Requests deliver the bounded artifact directly and use only a smoke check. | `docs/workflow-etiquette.md` |
| Non-trivial implementation uses Design → Build → Verify → Ship. | `docs/design-build-verify.md` |
| Design acceptance and advisory findings do not block implementation or non-production landing. | `design`, `adversarial-reviewer` |
| An accepted design’s exact `Acceptance` section remains the canonical Build Contract for optional exact-design proof. | `design`, `docs/local-documentation.md` |
| Build planning is internal and ephemeral. | `build`, `planner` |
| Native children receive bounded workstreams only when parallelism earns its context cost. | `docs/parallel-workstreams.md`, `implementer` |
| Independent Verify reports separate Build, Architecture, and Sensor verdicts on the exact revision. | `verify`, `docs/meaningful-proof.md` |
| Green sensors cannot substitute for an absent requested or accepted outcome. | `verify`, `docs/code-quality-sensors.md` |
| Security and production checks run only for concrete accepted consequences. | `docs/production-quality-bar.md`, specialist skills |
| Titles are silent, plain, descriptive, and at most four words. | `docs/workflow-etiquette.md` |
| An implementation request authorizes commit through non-production PR merge; production, installation, and archival retain separate authority. | `ship`, `land`, `docs/github-discipline.md` |
| Skills use clear triggers, checkable completion, negative cases, and honest proof layers. | `docs/skill-quality-bar.md` |

The installer owns only the marked Gauntlet block. User-owned instructions outside it remain unchanged.
