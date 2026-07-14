# Measurement-Led Optimization Loop

Use this loop only after the comparable baseline passes its gate.

## Profile before proposing changes

Use instrumentation appropriate to the measured surface: sampling or tracing profilers, query plans, allocation profiles, bundle analysis, test timing, I/O counters, or build traces. Profile the representative workload under conditions close enough to the baseline to preserve relevance.

Locate the dominant measured cost and its earliest causal source. Distinguish symptoms such as waiting or repeated rendering from the upstream mechanism creating them. Quantify how much of the measured total the suspected bottleneck can plausibly explain; a small component cannot produce a large end-to-end gain without another mechanism.

## State a falsifiable hypothesis

Before editing, write:

> Under workload **W**, cost **C** is dominated by mechanism **M**, evidenced by **E**. Change **X** should move metric **Y** by approximately **R** without changing oracle **O** or materially regressing **A**. The hypothesis is false if **F**.

Estimate ranges rather than false precision. Name the profiler evidence and a failure condition that would cause the change to be reverted or the hypothesis revised.

## Run the smallest discriminating experiment

Change the narrowest surface capable of testing the hypothesis. Avoid unrelated cleanup and stacked optimizations that make attribution impossible. Preserve public behavior and test intent.

Run the correctness oracle first, then the controlled comparison. If the result does not exceed observed variability or the profile does not change as predicted, treat the hypothesis as unsupported. Revert or isolate ineffective complexity rather than retaining speculative optimization.

When a target remains unmet, re-profile the candidate. Bottlenecks move; do not continue optimizing the old profile from memory.

## Check adjacent costs

Inspect proportionately for:

- cold-start versus steady-state tradeoffs;
- latency versus throughput, memory, CPU, I/O, and artifact size;
- common paths versus worst cases and tail latency;
- local speed versus CI, production, supported platforms, or constrained devices;
- parallelism that increases nondeterminism, resource contention, or failure opacity;
- caching that weakens invalidation, freshness, isolation, or memory bounds.

Do not declare an aggregate win when a material supported environment or high-consequence path regresses without explicit authority.

## Detect displaced complexity

Account for work moved rather than removed:

- production logic shifted into generated code, configuration, fixtures, build steps, services, or precomputation;
- new dependencies that absorb implementation while adding startup, install, supply-chain, portability, or maintenance cost;
- benchmark-only fast paths or caches unavailable to real workloads;
- deferred cleanup, larger artifacts, hidden background work, or slower write paths;
- reduced assertions, changed inputs, fewer cases, retries masking failures, or disabled diagnostics.

An external dependency may be the right tradeoff, but report its full cost and compatibility boundary. Do not describe dependency outsourcing as pure simplification.

## Extraordinary results

For unusually large gains, increase scrutiny. Re-run from clean state, verify process exit and output, inspect coverage and workload counts, compare profiles, and reproduce in a second relevant environment when practical. Large gains are acceptable when the mechanism explains them and the evidence survives these checks.
