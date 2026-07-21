---
name: refactor-performance
description: Measure and improve runtime or workflow performance without changing accepted behavior.
---

# Refactor Performance

Define the user-visible metric, workload, environment, warm-up, repetitions,
statistic, and regression budget before optimizing. Capture a source-bound
baseline and candidate with identical commands and inputs.

Profile before changing code. Optimize the measured bottleneck at its
authoritative owner, then rerun correctness and performance checks. Count work
moved into caches, generated files, dependencies, setup, or memory.

Report raw samples, median and relevant tail, absolute and percentage change,
environment limits, and behavior proof. Do not claim model quality, production
latency, or general speed from a local microbenchmark.
