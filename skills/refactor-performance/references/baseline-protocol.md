# Comparable Baseline Protocol

Use this protocol before changing code. Preserve enough evidence for another agent to reproduce or invalidate the comparison.

## Define the performance question

Record:

- the named performance surface and metric, including unit and direction of improvement;
- the representative workload, inputs, scale, setup, and correctness oracle;
- why the workload represents the user, developer, or system cost under investigation;
- the requested target, if any, without manufacturing one;
- non-goals and adjacent metrics that must not regress materially.

Separate latency percentiles, throughput, memory, CPU, I/O, artifact size, and test feedback. Do not combine unlike metrics into a vague speed score.

## Fix comparison conditions

Use the same, or record a justified equivalent, for baseline and candidate:

- machine, operating system, architecture, power mode, and relevant resource limits;
- runtime, compiler, package manager, dependency lockfile, build flags, and environment variables;
- command, inputs, dataset size, concurrency, process topology, and timeout;
- cache policy, including cold, warm, or both;
- setup, services, network conditions, isolation, and background load;
- instrumentation and profiler overhead.

Record the source revision and working-tree state. Avoid including secrets in commands or receipts. If the environment cannot be controlled, record the uncontrolled factors and use interleaved or paired runs where practical.

## Measure variability

Run at least one unmeasured warm-up when warm performance is relevant; declare a cold cache policy and use zero warm-ups for a cold-path comparison. Then collect repeated measured runs. Use at least five normally. A prohibitively expensive workload may use three only when the benchmark protocol records `expensiveRunException: true` and a concrete `expensiveRunReason`. Preserve raw samples, failures, and outliers. Do not discard an outlier without a predeclared rule and recorded cause.

Report a suitable summary such as median with range or percentile distribution. The bundled comparator uses directional non-overlapping observed ranges as a conservative proof gate. When ranges overlap, increase samples or use a separately documented paired/interleaved method; the bundled comparison must remain unproved. A difference smaller than ordinary run-to-run variation is not a proved improvement.

Measure cold and warm paths separately when users experience both. Avoid changing benchmark concurrency merely to improve throughput at the cost of latency or resources.

## Preserve the oracle

Before accepting the baseline, verify that the workload succeeds and that its output or side effects satisfy the same correctness oracle required of the candidate. For test-suite measurements, preserve test selection, assertions, retries, timeouts, sharding semantics, and failure behavior. Faster execution caused by skipped work is a correctness failure.

For product workloads, compare outputs, ordering, precision, files, state, errors, and other relevant contracts. Include representative failure and cancellation paths when they contribute materially to cost or safety.

## Baseline gate

The baseline is usable only when the receipt can answer:

1. What exact cost is measured?
2. Under what reproducible conditions?
3. What raw variation was observed?
4. What proves the measured work completed correctly?
5. Which environments or adjacent metrics remain unmeasured?

If any answer is missing, repair the protocol before optimizing.
