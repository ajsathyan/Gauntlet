# Code-Owned Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small deterministic orchestration layer to Gauntlet that enforces mode/gate sequencing, bounded retries, resumable state, and compact worker outputs without slowing trivial Patch work.

**Architecture:** Keep Gauntlet's current prompt router for human/model judgment, but let trusted code own the mechanical workflow once a run is classified as orchestrated. Use static JSON workflow data, JSON schemas, compact local run state, and a Python driver that emits exactly one next role packet or gate action at a time. Existing role skills remain the workers.

**Tech Stack:** Python standard library, JSON, JSON Schema-compatible schema files, existing Gauntlet shell/Python scripts, existing skill eval/check framework.

## Global Constraints

- Do not use real assembly, an assembly DSL, or model-generated Python for orchestration.
- Keep Tier 0, Tier 1, and Patch Standard on the current lightweight prompt path by default.
- Use orchestration for Feature, Release, Tier 2/3, broad Patch Deep, resumed orchestrated runs, or explicit user opt-in.
- Do not duplicate trusted gate scripts; call or record outputs from existing scripts such as `scripts/require-review-brief-started.sh` and `scripts/classify-ts-durability.sh`.
- Store compact structured state and summaries, not raw transcripts.
- Require machine-readable worker results only for orchestrated runs.
- Bound retries; stop with `Needs decision` or `Blocked` rather than looping indefinitely.
- Treat code-owned orchestration as sequence enforcement, not a replacement for human/model judgment.

---

## Subagent Synthesis

Three independent planning agents received the same brief. All three converged on the same core direction:

- Static JSON workflow data instead of assembly or generated code.
- A tiny Python driver under `scripts/`.
- Compact run state under `.gauntlet/runs/<run-id>/`.
- A worker-result schema using enum verdicts.
- Existing role skills as workers.
- A tested fast-path skip for trivial Patch work.

Best additions merged into this plan:

- Use a final machine-readable result marker such as `GAUNTLET_RESULT {...}` or a fenced `gauntletReport` JSON block, so the driver never parses prose for transitions.
- Add a local `classify` command so the driver can say whether orchestration is required before starting state.
- Record override reasons when a human/model intentionally bypasses a recommended transition.
- Use word-count packet caps as the first speed/token proxy before adding provider-specific accounting.

---

### Task 1: Define Workflow And Report Contracts

**Files:**
- Create: `orchestration/workflows.v1.json`
- Create: `orchestration/orchestration-state.schema.json`
- Create: `orchestration/worker-result.schema.json`
- Modify: `.gitignore`

**Interfaces:**
- Produces: workflow ids `patch-standard-fast-path`, `feature-standard`, `release-standard`, gate ids `review-brief`, `panel-guard`, `hygiene`, `ts-durability`, verdicts `Approved`, `Needs fixes`, `Needs proof`, `Needs decision`, `Blocked`, `Cannot verify`
- Consumes: mode/depth/gate language already documented in `AGENTS.md`

- [ ] **Step 1: Add workflow manifest**

Create `orchestration/workflows.v1.json` with static mode definitions:

```json
{
  "schemaVersion": "1.0",
  "modes": {
    "Patch": {
      "standardFastPath": true,
      "orchestrateWhen": ["explicit_opt_in", "broad_patch_deep", "review_brief_required"]
    },
    "Feature": {
      "standardFastPath": false,
      "defaultSteps": ["intake", "product-architect", "planner", "implementer", "black-box-tester", "experience-reviewer", "review-brief-builder"],
      "requiredGates": ["review-brief", "hygiene"]
    },
    "Release": {
      "standardFastPath": false,
      "defaultSteps": ["intake", "planner", "issue-triager", "implementer", "hygiene", "adversarial-reviewer", "black-box-tester", "issue-triager", "deep-code-reviewer", "review-brief-builder"],
      "requiredGates": ["review-brief", "hygiene"]
    }
  },
  "retryPolicy": {
    "defaultMaxAttempts": 2,
    "onExhausted": "Needs decision"
  }
}
```

- [ ] **Step 2: Add state schema**

Create `orchestration/orchestration-state.schema.json` requiring:

```json
{
  "schemaVersion": "1.0",
  "runId": "string",
  "projectRoot": "string",
  "mode": "Patch|Feature|Release",
  "depth": "Standard|Deep",
  "triggeredGates": ["Review Brief", "Panel Guard", "Hygiene", "TS Durability"],
  "currentStep": "string",
  "stepAttempts": {},
  "status": "Not started|Running|Needs decision|Blocked|Complete",
  "overrideReason": "string|null"
}
```

- [ ] **Step 3: Add worker result schema**

Create `orchestration/worker-result.schema.json` requiring:

```json
{
  "schemaVersion": "1.0",
  "step": "string",
  "verdict": "Approved|Needs fixes|Needs proof|Needs decision|Blocked|Cannot verify",
  "summary": "string",
  "changedFiles": [],
  "proof": [],
  "cannotVerify": [],
  "agentNext": "string"
}
```

- [ ] **Step 4: Ignore local run state**

Add `.gauntlet/runs/` to `.gitignore`, preserving existing ignore rules.

- [ ] **Step 5: Proof**

Run:

```bash
python3 scripts/check-gauntlet-workflow.py
```

Expected: existing workflow checks still pass before the driver exists.

---

### Task 2: Build The Deterministic Driver

**Files:**
- Create: `scripts/gauntlet-orchestrate.py`

**Interfaces:**
- Consumes: `orchestration/workflows.v1.json`, `orchestration/orchestration-state.schema.json`, `orchestration/worker-result.schema.json`
- Produces commands: `classify`, `start`, `next`, `record-report`, `resume`, `status`, `check`

- [ ] **Step 1: Implement CLI commands**

Add `scripts/gauntlet-orchestrate.py` with Python standard-library parsing:

```text
classify --mode Patch --depth Standard --tier 1
start --project-root /path --mode Feature --depth Standard --gates "Review Brief,Hygiene"
next --run-id <id>
record-report --run-id <id> --report-file <path>
resume --run-id <id>
status --run-id <id>
check
```

- [ ] **Step 2: Make `classify` deterministic**

Rules:

```text
Skip orchestration:
- Tier 0
- Tier 1 Patch Standard with no triggered gates

Require orchestration:
- Feature
- Release
- Tier 2/3
- broad Patch Deep
- Review Brief required
- Panel Guard required
- Hygiene required after implementation
- explicit user opt-in
- resumed orchestrated run
```

- [ ] **Step 3: Emit one next packet**

`next` must write or print one compact role packet with:

```text
Project root
Mode/depth/gates
Current step
In scope
Out of scope
Required output marker
Expected verdict enum
Proof already recorded
```

Packet target: roughly 250-400 words unless a step has concrete file paths or proof handles that require more.

- [ ] **Step 4: Validate worker reports**

`record-report` must ignore prose and advance only from a valid `GAUNTLET_RESULT` JSON object or fenced `gauntletReport` block that matches the schema.

- [ ] **Step 5: Fail closed**

Invalid transitions, missing verdicts, exhausted retries, or malformed reports must return a repair instruction or stop state rather than guessing the next step.

- [ ] **Step 6: Proof**

Run:

```bash
python3 scripts/gauntlet-orchestrate.py check
```

Expected: validates workflow data and schemas, then exits `0`.

---

### Task 3: Add Orchestration Fixtures And Regression Checks

**Files:**
- Create: `evals/orchestration-fixtures.json`
- Modify: `scripts/check-gauntlet-workflow.py`

**Interfaces:**
- Consumes: driver commands from Task 2
- Produces: deterministic fixture assertions for route, next step, retry bounds, terminal state, and packet word count

- [ ] **Step 1: Add fixture cases**

Create `evals/orchestration-fixtures.json` with cases:

```json
[
  {
    "id": "patch-standard-fast-path",
    "input": {"mode": "Patch", "depth": "Standard", "tier": 1, "gates": []},
    "expected": {"orchestrationRequired": false}
  },
  {
    "id": "feature-starts-review-brief",
    "input": {"mode": "Feature", "depth": "Standard", "tier": 2, "gates": ["Review Brief", "Hygiene"]},
    "expected": {"orchestrationRequired": true, "firstStep": "intake"}
  },
  {
    "id": "release-needs-proof-routes-back",
    "input": {"mode": "Release", "depth": "Standard", "tier": 3, "workerVerdict": "Needs proof"},
    "expected": {"terminal": false, "nextStepType": "proof"}
  },
  {
    "id": "blocked-stops",
    "input": {"mode": "Release", "depth": "Standard", "tier": 3, "workerVerdict": "Blocked"},
    "expected": {"status": "Blocked"}
  }
]
```

- [ ] **Step 2: Extend workflow check**

Add checks that:

```text
Patch Standard Tier 1 returns orchestrationRequired=false
Feature and Release return orchestrationRequired=true
Unknown mode fails
Unknown verdict fails
Malformed worker result fails
Packet word count stays below cap
Resume recomputes same next step from state/events
```

- [ ] **Step 3: Proof**

Run:

```bash
python3 scripts/check-gauntlet-workflow.py
```

Expected: existing checks plus orchestration fixtures pass.

---

### Task 4: Wire Existing Gates Without Reimplementing Them

**Files:**
- Modify: `scripts/gauntlet-orchestrate.py`
- Modify: `scripts/check-gauntlet-workflow.py`

**Interfaces:**
- Consumes: `scripts/require-review-brief-started.sh`, `scripts/classify-ts-durability.sh`
- Produces: gate artifacts recorded in run state

- [ ] **Step 1: Record Review Brief gate status**

When Review Brief is required, the driver should call or instruct the caller to call:

```bash
scripts/require-review-brief-started.sh "$PROJECT_ROOT"
```

Record `.gauntlet-review-brief-started.json` path and returned URL in state.

- [ ] **Step 2: Record TS Durability gate status**

When TS Durability is triggered, the driver should call or instruct the caller to call:

```bash
scripts/classify-ts-durability.sh "$PROJECT_ROOT"
```

Record `.gauntlet-ts-durability.json` path and `durabilityRequired`.

- [ ] **Step 3: Proof**

Use temporary projects in `scripts/check-gauntlet-workflow.py` to prove:

```text
Review Brief starts once
Review Brief state is recorded
TS classifier is skipped when TypeScript is out of scope
TS classifier result is recorded when triggered
```

---

### Task 5: Add Machine-Readable Worker Result Guidance

**Files:**
- Modify: `AGENTS.md`
- Modify: selected examples under `skills/*/examples/`

**Interfaces:**
- Consumes: worker report schema from Task 1
- Produces: orchestrated-run output contract for role skills

- [ ] **Step 1: Add AGENTS guidance**

Add a short section:

```text
When a Gauntlet orchestration packet asks for a machine-readable result, end the role report with a single `GAUNTLET_RESULT` JSON object or fenced `gauntletReport` block. The JSON is the only source the driver uses for state transitions; prose remains reviewer context.
```

- [ ] **Step 2: Keep schema small**

Required fields:

```json
{
  "schemaVersion": "1.0",
  "step": "implementer",
  "verdict": "Needs proof",
  "summary": "Change applied; targeted test passed; full suite not run.",
  "changedFiles": ["src/example.ts"],
  "proof": [{"type": "test", "command": "npm test -- example", "status": "passed"}],
  "cannotVerify": [{"reason": "No staging credentials available"}],
  "agentNext": "Run black-box verification for the changed flow."
}
```

- [ ] **Step 3: Add examples**

Update one or two role examples first, not every skill, to avoid bloating all skill docs at once.

- [ ] **Step 4: Proof**

Run:

```bash
python3 scripts/lint-skills.py
python3 scripts/run-skill-evals.py --results evals/results/orchestration-skill-check.json
```

Expected: existing skill contract checks still pass.

---

### Task 6: Document Routing And Install The New Files

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `scripts/install.sh`

**Interfaces:**
- Consumes: generated workflow files and driver
- Produces: installed orchestration support in persistent Gauntlet installs

- [ ] **Step 1: Document fast path**

In `README.md` and `AGENTS.md`, state:

```text
Patch Standard Tier 0/1 remains prompt-owned and fast by default. Code-owned orchestration is for Feature, Release, Tier 2/3, broad Patch Deep, resumptions, and explicit opt-in.
```

- [ ] **Step 2: Document token strategy**

Add:

```text
The driver stores compact state and emits one role packet at a time. Logs reference proof handles, files, and summaries instead of full transcripts.
```

- [ ] **Step 3: Install orchestration assets**

Update `scripts/install.sh` so the installed Gauntlet bundle includes:

```text
orchestration/
scripts/gauntlet-orchestrate.py
evals/orchestration-fixtures.json
```

- [ ] **Step 4: Proof**

Run:

```bash
GAUNTLET_SKIP_GIT_HOOKS=1 ./scripts/install.sh
python3 scripts/check-gauntlet-workflow.py
```

Expected: install copy contains orchestration assets and workflow check passes.

---

### Task 7: Final Hygiene And Decision Record

**Files:**
- Modify: `docs/` with a short design/decision note if no review brief is active
- Modify: `review-brief-data.json` only if this implementation is run under a live review brief

**Interfaces:**
- Consumes: implementation proof from Tasks 1-6
- Produces: bounded decision record and final proof summary

- [ ] **Step 1: Run hygiene checks**

Run:

```bash
python3 scripts/check-gauntlet-workflow.py
python3 scripts/lint-skills.py
python3 scripts/run-skill-evals.py --results evals/results/orchestration-final-skill-check.json
```

- [ ] **Step 2: Check for current-change cruft**

Search:

```bash
rg "TODO|TBD|placeholder|sample data|implementation-notes" AGENTS.md README.md scripts orchestration evals skills
```

Expected: no new unresolved placeholders or forbidden review-brief anti-patterns.

- [ ] **Step 3: Record decision**

Record:

```text
Rejected: assembly DSL, model-generated Python, autonomous multi-agent runner, always-on orchestration, raw transcript logging.
Accepted: static JSON workflow, Python driver, compact worker result schema, tested Patch fast path.
```

- [ ] **Step 4: Done when**

Done requires:

```text
Patch fast-path fixture passes
Feature/Release route fixtures pass
Invalid worker reports fail closed
Resume fixture recomputes same next step
Install check includes orchestration assets
Existing skill evals and skill lint pass
No blocking hygiene findings remain
```
