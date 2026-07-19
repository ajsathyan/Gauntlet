# Thin Contract Assessment

This assessment compares the accepted GAUNTLET-011 candidate with the clean
GAUNTLET-010/Build 1 source at `abd3fea`. It measures the whole retained
repository, not only the files named for deletion.

## Result

| Surface | Before | Candidate | Change |
| --- | ---: | ---: | ---: |
| Measured nonblank lines | 44,815 | 29,704 | 33.7% fewer |
| Production and test lines | 40,033 | 27,607 | 31.0% fewer |
| Full workflow feedback | 90.332s median | 61.0s sample | 32.5% faster |
| Fast sensor feedback | no distinct phase | 2.19s sample | new edit loop |
| Dashboard direct dependencies | 3 runtime + 6 development | 0 | removed |
| Default workflow states | Epic, Ticket, Run, journal, dashboard, analytics | Design, ephemeral plan, exact revision | controller removed |

The line-count comparison uses the same physical-nonblank-line rules against a
disposable clean clone of `abd3fea` and the candidate filesystem. Generated,
configuration, and fixture categories also fell; the reduction was not moved
into a new dependency or generated-code layer. Timing is directional because
the frozen baseline used repeated warm samples while the candidate figures are
single successful samples on the same machine.

## What changed structurally

- Product meaning has one durable owner: the accepted Design. Its exact
  `Acceptance` section is the Build Contract read directly by Build and Verify.
- Brainstorming, completeness, edge-case, and three-lens gap review are semantic
  gates. They do not create a second requirements database.
- Parallelism uses native tasks plus a small FIFO Git-bound queue. The queue
  owns serialization and stale-candidate rejection, not product planning.
- Build, Architecture, and Sensor proof have separate exact-revision verdicts.
  The GAUNTLET-009 negative case fails Build even when sensors pass.
- Sensor handoff is exceptions-first. The recurring payload contains the phase,
  source fingerprint, pass IDs, counts, bounded attention, and an evidence
  reference; commands, versions, raw passing output, and repeated context stay
  out of the handoff. Fast proof runs the repository smoke workflow directly
  with proportional lint and security checks; coverage remains reserved for the
  final integrated revision.
- The dashboard, controller, launch compiler, run state, recovery journal,
  controller-specific pull-request model, telemetry, analytics, deterministic
  agent routing, and permanent implementation-memory surface are gone.

## Retained core

Generic Git/PR/land behavior, safe Codex installation, local Design documents,
generated context, evaluation, debugging, consequence-triggered specialist
review, and adaptive sensor execution remain. The dashboard's Node dependency
tree is gone; Python runtime code still has no third-party dependency.

The retained architecture uses narrow entrypoints and explicit outbound clients.
The workstream queue keeps Git process access in `git_client.py`; contract
validation stays independent of Git, GitHub, Codex task control, and sensor
tools. Large modules were not split merely to reduce file size: the remaining
installer, merge, closeout, document, and sensor modules expose narrow public
interfaces and hide cohesive complexity.

## Context cost

The current router plus Design, Build, and Verify skills contain 14,409 unique
bytes. Reusing the 6,412-byte router as a stable prefix avoids 12,824 repeated
bytes across the three stages, roughly 2,565–3,664 tokens by the repository's
coarse estimator. Child assignments remain compact because they carry only an
outcome slice, ownership, dependencies, constraints, proof, and return policy.

## Further changes only if evidence earns them

The next likely code-shape candidates are the installer shell boundary and
overlap among generic merge, land, and closeout. They should be changed only
after a concrete defect or repeated co-change shows that their current deep
module boundaries are costly; splitting them now would mostly create more
interfaces.

Do not rebuild progress, recovery, analytics, permanent implementation plans,
automatic routing, or controller projections as convenience features. A future
addition should attach to Design, Build, Verify, Ship, or a narrow outbound
adapter and must demonstrate an observable job that the existing spine cannot
handle.
