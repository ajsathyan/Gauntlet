# Autonomous Epic Execution Cutover

Date: 2026-07-14
Status: Active contract

## Decision

One product task may keep shaping many independently shippable Epics in one canonical PRD. One authorized launch freezes the complete accepted membership and immutable PRD snapshot. Gauntlet then creates one visible implementation task, one Execution Run, one integration branch, and one Project PR per Epic. Dependency-ready Epics start independently; downstream Epics wait only on their declared `merged`, `deployed`, or `productionProved` boundary.

Each Epic Run uses targeted Ticket proof, optional Cohort proof only for a named shared invariant, and one fresh final Epic verification on the exact integrated revision. Controller facts keep `implemented`, `merged`, `deployed`, `productionProved`, and `complete` separate. Schema 3.0 Project PR facts come from accepted criteria, changed paths, receipts, deferrals, and gates without a model-authored project summary or per-Epic outcome artifact.

High-consequence work still earns three distinct review lenses after deterministic checks and a repository-owned dry run, bounded canary, and rollback gate before a production-hitting action. Ordinary work does not inherit those model turns.

## One-Time Cutover

- Remove the duplicate `IMPLEMENTATION_PLAN.md.tmpl`; the PRD owns product intent and the Ticket Graph owns generated execution assignments.
- Install the canonical lifecycle-copy template and current single-Epic policy, skills, docs, and local-document scaffolds.
- Remove active commands and guidance for multi-Epic runs, mandatory Cohorts, default verifier Tickets, `verify-prd`, `record-project-summary`, `record-epic-outcome`, and schema 2 Project PRs.
- Preserve completed run logs and changelog entries as historical evidence with explicit supersession where they could be mistaken for current instructions.
- Run repository and temporary-home convergence checks. A repeat install must preserve unmanaged instruction bytes and must not restore a retired payload.

## Rollback Boundary

Do not mix old and new run state. Existing in-flight legacy Execution Runs remain historical/controller-version-bound evidence. A new launch must use the current Epic launch set, its immutable `source.snapshotPath`, one target per `prd-run.py init`, `verify-epic`, `completion`, `run-facts`, and schema 3.0 `project-pr` output.
