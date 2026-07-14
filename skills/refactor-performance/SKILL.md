---
name: refactor-performance
description: Measure and improve codebase performance without changing intended behavior. Use for standalone performance work, slow tests or builds, runtime latency, throughput, memory, startup, export duration, bundle size, or resource use; for establishing a reproducible performance baseline; or when refactor-codebase delegates its measurement and optimization phase.
---

# Refactor Performance

Improve measured performance while preserving correctness, behavioral coverage, supported environments, and public contracts. Treat extraordinary gains as hypotheses requiring stronger scrutiny, not permission to weaken measurement.

## Choose the mode

- `baseline-only`: establish a comparable benchmark and durable receipt, then stop. Use when another workflow needs measurements or the user did not authorize changes.
- `optimize`: establish or verify the baseline, profile, change the smallest relevant surface, and prove the result. Use when the user asks for performance improvements.

If invoked by `refactor-codebase`, use the requested mode and return artifacts that its state receipt can reference. Keep lifecycle, integration, and completion ownership in the calling workflow.

## Separate performance surfaces

Do not treat one performance category as evidence for another. Name each measured surface, such as:

- developer feedback: deterministic tests, builds, type checks, or local startup;
- user experience: startup, interaction, rendering, or export latency;
- system capacity: throughput, concurrency, memory, CPU, I/O, network, or storage;
- delivery: bundle, binary, image, or artifact size.

Report unmeasured surfaces as unmeasured. Faster tests do not prove a faster product.

## Run the workflow

1. Read [baseline-protocol.md](references/baseline-protocol.md) completely. Define the metric, workload, environment, correctness oracle, and comparison protocol before changing code.
2. Record the baseline and its variability. In `baseline-only` mode, write the benchmark receipt and stop.
3. In `optimize` mode, read [optimization-loop.md](references/optimization-loop.md) completely. Profile the representative workload, identify the dominant measured bottleneck, and state a falsifiable hypothesis.
4. Make the smallest change that tests the hypothesis. Preserve assertions, coverage intent, inputs, outputs, supported environments, and benchmark conditions.
5. Compare repeated measurements under the same protocol. Reject incomparable runs rather than normalizing them informally.
6. Inspect for displaced complexity, hidden generated work, excluded files, dependency outsourcing, degraded cold paths, and regressions on adjacent metrics.
7. Read [benchmark-receipt.md](references/benchmark-receipt.md) completely and write a durable receipt in the target repository's established Gauntlet or documentation area.

## Targets and stopping

Treat a user-supplied target as an acceptance criterion. Do not quietly lower it. If no target is supplied, do not invent one: optimize dominant material costs while the evidence shows a worthwhile gain and the next experiment remains proportionate.

Stop when the requested target is proved, no material bottleneck remains within scope, or further improvement conflicts with a higher-priority correctness or compatibility constraint. If blocked, report the exact conflict, comparable measurements, attempted hypotheses, and smallest decision needed.

## Completion gate

Claim improvement only when:

- baseline and candidate use the same declared protocol or an explicitly justified equivalent;
- repeated measurements establish the result relative to observed variance;
- correctness and behavioral coverage remain intact;
- relevant supported environments and adjacent performance surfaces were checked proportionately;
- displaced complexity and dependency costs are included in the assessment;
- the durable receipt contains raw results, summaries, commands, environment identity, changes, and limitations.

Never claim success from a single timing, profiler sample, synthetic workload with no relevance argument, reduced test coverage, warmed candidate against cold baseline, or a benchmark whose inputs changed.
