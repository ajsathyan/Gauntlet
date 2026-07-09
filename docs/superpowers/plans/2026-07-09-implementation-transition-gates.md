# Implementation Transition Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce timely task naming, impact-based research priority, priority reassessment, pre-implementation subagent packetization, and scope-addition edge-case checks across Gauntlet source and installed guidance.

**Architecture:** Keep policy in `AGENTS.md` and `docs/workflow-etiquette.md`, route planning and editing behavior through the planner/implementer skills, and strengthen `check-subagent-plan.py` so accepted manifests reference complete lane packets. `check-gauntlet-workflow.py` provides red-green contract, validator, and install-propagation proof.

**Tech Stack:** Markdown workflow guidance, Python 3 standard library validators/tests, Bash installer, Git.

## Global Constraints

- Surface a best priority/title recommendation on the first substantive response when possible and no later than the third user-assistant exchange.
- Research is never automatically `p4`; classify it by consequence and default bounded research to `p3` when uncertain.
- Reassess priority and execution mode at implementation start and material implementation changes; say nothing when unchanged.
- Required subagent packetization must pass before implementation, not merely before dispatch.
- Every genuine scope addition receives delta foresight before implementation.
- A no-finding scope check produces only `Scope delta checked: no material change.` in the plan/task packet and no chat message.
- Preserve unrelated `house-voice-plans.md` and any other user-owned dirty work.
- Runtime subagent-tool interception remains out of scope; current-run manifest/packet proof and role refusal are the enforceable boundary.

## Implementation Transition Record

Subagent packetization: not relevant because this patch changes one tightly coupled workflow contract across source guidance, validator schema, role skills, and their shared proof runner; parallel edits would overlap files and proof.

Scope addition: pre-implementation packetization and per-scope delta foresight
New edge cases: old manifest schema could bypass complete packets; packet references could point outside the project or to missing files; install checks could pass while global guidance remains stale; routine plan edits could trigger ceremony.
Invalidated assumptions: pre-dispatch validation alone is not sufficient to prove packetization before implementation.
Acceptance/proof delta: add manifest packet-reference validation, missing-packet rejection, role refusal guidance, delta-foresight markers, and installed-guidance assertions.
Priority/execution delta: none.
Packetization delta: not relevant for this implementation; required for future multi-lane implementations under the new contract.
Need user decision: none.

---

### Task 1: Add Failing Workflow-Contract Checks

**Files:**
- Modify: `scripts/check-gauntlet-workflow.py`
- Test: `scripts/check-gauntlet-workflow.py`

**Interfaces:**
- Consumes: approved design at `docs/superpowers/specs/2026-07-09-third-exchange-thread-label-design.md`.
- Produces: `test_kickoff_and_implementation_transition_gates_are_documented()` and install-layout assertions that fail until source policy and role skills contain the accepted contract.

- [ ] **Step 1: Add the focused failing contract test**

Add this test before `test_skill_quality_bar_is_trigger_bounded`:

```python
def test_kickoff_and_implementation_transition_gates_are_documented():
    agents = read(AGENTS_MD)
    etiquette = read(ROOT / "docs" / "workflow-etiquette.md")
    planner = read(SKILLS / "planner" / "SKILL.md")
    implementer = read(SKILLS / "implementer" / "SKILL.md")

    for marker in [
        "no later than the third user-assistant exchange",
        "Research is never assigned `p4` merely because it is research",
        "If the priority is unchanged, say nothing about it",
        "Subagent packetization: required",
        "before implementation, not merely before dispatch",
        "Scope delta checked: no material change.",
    ]:
        assert_contains("\n".join([agents, etiquette]), marker, "implementation-transition guidance")

    for marker in [
        "Subagent packetization: required",
        "Scope delta checked: no material change.",
        "before implementation",
    ]:
        assert_contains(planner, marker, "planner implementation-transition gate")

    for marker in [
        "Refuse delegated implementation",
        "current-run manifest",
        "scope-addition delta",
    ]:
        assert_contains(implementer, marker, "implementer implementation-transition gate")
```

Append the function to the `tests` list in `main()` immediately after `test_subagent_parallelism_is_context_efficient`.

- [ ] **Step 2: Add failing install-propagation assertions**

In `assert_installed_gauntlet_layout`, add:

```python
    for marker in [
        "no later than the third user-assistant exchange",
        "Research is never assigned `p4` merely because it is research",
        "Subagent packetization: required",
        "Scope delta checked: no material change.",
    ]:
        assert_contains(installed_agents, marker, "installed implementation-transition guidance")
```

In `test_codex_install_layout_supports_workflow_check`, assert the same four markers against the root installed `AGENTS.md`.

- [ ] **Step 3: Run the workflow checker and verify RED**

Run:

```sh
python3 scripts/check-gauntlet-workflow.py
```

Expected: exit 1 at `test_kickoff_and_implementation_transition_gates_are_documented`, with a missing third-exchange marker before the install tests run.

- [ ] **Step 4: Commit the failing test**

```sh
git add scripts/check-gauntlet-workflow.py
git commit -m "test: require implementation transition gates"
```

### Task 2: Implement Workflow Guidance and Role Gates

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/workflow-etiquette.md`
- Modify: `skills/planner/SKILL.md`
- Modify: `skills/implementer/SKILL.md`
- Test: `scripts/check-gauntlet-workflow.py`

**Interfaces:**
- Consumes: marker contract from Task 1.
- Produces: global source guidance and planner/implementer refusal rules that satisfy the transition contract.

- [ ] **Step 1: Update the priority mapping and kickoff deadline**

In both workflow guidance files, change the `p4` mapping to exclude research and add:

```markdown
Research is never assigned `p4` merely because it is research. Classify research by the consequence and durable decision it supports: `p0` for Release-class harm, `p1` for substantial product or strategic direction, `p2` for consequential implementation decisions, and `p3` for normal bounded research. When uncertain, default bounded research to `p3`.

For an unlabeled task, suggest the priority/title on the first substantive response when classification is responsible and no later than the third user-assistant exchange. Existing valid labels are not reopened.
```

- [ ] **Step 2: Add silent reassessment and scope-delta guidance**

Add the following compact contract to both workflow guidance files:

```markdown
Silently reassess priority and execution mode when implementation begins and when implementation materially changes scope, affected systems, external side effects, risk, proof burden, or reversibility. If the priority is unchanged, say nothing about it. If it changes, state the old and new priority once, name the trigger, and update the thread title.

Run delta foresight before implementing every genuine scope addition. Check the added scope and its boundary with accepted work for new edge cases, invalidated assumptions, acceptance/proof changes, priority/execution changes, and packetization changes. A clean check records only `Scope delta checked: no material change.` in the plan/task packet and stays silent in chat. Material findings update the plan and are called out.
```

- [ ] **Step 3: Add the pre-implementation packetization gate**

Add the following to `AGENTS.md`, then mirror the detailed version in `docs/workflow-etiquette.md`:

```markdown
At implementation transition, record `Subagent packetization: required` or `Subagent packetization: not relevant because...`. It is required when the user asks for subagents, the accepted plan proposes parallel lanes, or multiple agent/child-chat lanes will implement the work. Required packets and the current-run manifest must validate before implementation, not merely before dispatch.
```

Keep the existing handoff-packet list and add packet reference, lane objective, accepted source, dependencies, consumes/produces, expected return, and ask-user policy when absent.

- [ ] **Step 4: Update planner and implementer contracts**

Add these planner outputs:

```markdown
- Subagent packetization: `required` or `Not relevant because...`
- Scope-addition delta foresight: material delta or `Scope delta checked: no material change.`
```

Add these rules:

```markdown
- When packetization is required, create accepted lane packets and validate the current-run manifest before implementation, not merely before dispatch.
- For every genuine scope addition, run scope-addition delta foresight before implementing it; keep clean checks to the one-line plan marker.
```

Add these implementer rules:

```markdown
- Refuse delegated implementation when required lane packets or an accepted current-run manifest are missing.
- Before implementing added scope, require its scope-addition delta to be resolved; a clean check may be represented by `Scope delta checked: no material change.`
```

- [ ] **Step 5: Run the workflow checker through the contract test**

Run:

```sh
python3 scripts/check-gauntlet-workflow.py
```

Expected: the new guidance/role contract test passes; the run may still fail later because the validator and install schema have not yet been updated.

- [ ] **Step 6: Commit the guidance change**

```sh
git add AGENTS.md docs/workflow-etiquette.md skills/planner/SKILL.md skills/implementer/SKILL.md
git commit -m "feat: gate implementation transitions"
```

### Task 3: Require Complete Lane Packets in the Validator

**Files:**
- Modify: `scripts/check-subagent-plan.py`
- Modify: `docs/subagent-plan-validator.md`
- Modify: `scripts/check-gauntlet-workflow.py`
- Test: `scripts/check-gauntlet-workflow.py`

**Interfaces:**
- Consumes: current `validate_plan(data, max_inline_words, max_total_inline_words)` API.
- Produces: schema `1.1`, complete lane packet validation, safe `taskPacketRef` resolution, and accepted/rejected regression fixtures.

- [ ] **Step 1: Write failing complete-packet validator fixtures**

Add a test that creates a schema `1.1` plan with the existing fields but omits `taskPacketRef`, `filesAvoid`, `dependencies`, `consumes`, `produces`, `constraints`, `expectedReturn`, and `askUserPolicy`. Assert failure codes include `missing_field`.

Add a sibling fixture containing `taskPacketRef: ".gauntlet/packets/C1.md"` without creating the file and assert `task_packet_missing`.

Add both tests to `main()` and update existing valid/invalid plan fixtures to schema `1.1` with complete packet fields and real temporary packet files so their original assertions remain targeted.

- [ ] **Step 2: Run and verify RED**

Run:

```sh
python3 scripts/check-gauntlet-workflow.py
```

Expected: exit 1 because the current validator accepts the incomplete packet or omits `task_packet_missing`.

- [ ] **Step 3: Extend the validator schema minimally**

Add:

```python
VALID_SCHEMA_VERSION = "1.1"
VALID_LANE_STATUS = {"To Do", "In Progress", "Blocked", "In Review", "Done", "Canceled"}
REQUIRED_LANE_FIELDS = [
    "id", "status", "title", "skill", "objective", "projectRoot", "worktreePath",
    "acceptedSource", "scope", "inScope", "outOfScope", "filesRead", "filesWrite",
    "filesAvoid", "stateScope", "stateAccess", "dependencies", "consumes", "produces",
    "constraints", "proof", "inlineContext", "taskPacketRef", "expectedReturn", "askUserPolicy",
]
```

Reject an unsupported schema version. Validate string/list field types, lane status, and non-empty proof. Resolve the path portion of `taskPacketRef` relative to `project_root`, reject absolute/outside-root paths, and emit `task_packet_missing` when the referenced file does not exist.

Pass `project_root` into `validate_plan`:

```python
rejections = validate_plan(data, project_root, args.max_inline_words, args.max_total_inline_words)
```

- [ ] **Step 4: Update validator documentation**

Replace the schema example with `1.1` and a complete lane object. State explicitly that validation is required before implementation when packetization is required, while runtime tool interception remains unavailable.

- [ ] **Step 5: Run and verify GREEN**

Run:

```sh
python3 scripts/check-gauntlet-workflow.py
```

Expected: all workflow, validator, and temporary install checks print `PASS` and exit 0.

- [ ] **Step 6: Commit the validator change**

```sh
git add scripts/check-subagent-plan.py docs/subagent-plan-validator.md scripts/check-gauntlet-workflow.py
git commit -m "feat: validate complete subagent packets"
```

### Task 4: Verify, Install Globally, and Publish

**Files:**
- Modify through installer: `/Users/ajsathyan/.codex/AGENTS.md`
- Modify through installer: `/Users/ajsathyan/.codex/gauntlet/**`
- Modify through installer: `/Users/ajsathyan/.codex/skills/{planner,implementer}/**`
- Verify: repository and installed copies

**Interfaces:**
- Consumes: passing source workflow and validator tests.
- Produces: fresh installed global guidance, verified task titles, clean intended Git diff, and pushed commits.

- [ ] **Step 1: Compare source and installed personal guidance before overwrite**

Run:

```sh
git diff --no-index /Users/ajsathyan/.codex/AGENTS.md AGENTS.md
```

Expected: differences are stale Gauntlet workflow sections only; the personal house-voice block remains identical. If user-owned content exists only in the installed copy, preserve it before installation.

- [ ] **Step 2: Run fresh source verification**

```sh
python3 scripts/check-gauntlet-workflow.py
python3 scripts/lint-skills.py
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 3: Install to the active Codex home**

```sh
./scripts/install.sh --target codex --agent-home /Users/ajsathyan/.codex
```

Expected: `Installed Gauntlet for codex to /Users/ajsathyan/.codex`.

- [ ] **Step 4: Verify the installed invariant**

```sh
rg -n "third user-assistant exchange|Research is never assigned.*p4|Subagent packetization: required|Scope delta checked: no material change" /Users/ajsathyan/.codex/AGENTS.md /Users/ajsathyan/.codex/gauntlet/AGENTS.md /Users/ajsathyan/.codex/skills/planner/SKILL.md /Users/ajsathyan/.codex/skills/implementer/SKILL.md
/Users/ajsathyan/.codex/gauntlet/scripts/check-gauntlet-workflow.py
```

Expected: all four invariants appear in the relevant installed files and the installed workflow checker exits 0.

- [ ] **Step 5: Verify repository scope and task titles**

```sh
git status --short
git log -8 --oneline --decorate
```

Expected: only `house-voice-plans.md` remains as unrelated untracked user work; implementation commits are visible. Confirm app metadata still reports `p2-auto: harden implementation transition gates` and `p0-auto: build harness eval suite`.

- [ ] **Step 6: Push the current branch**

```sh
git push origin main
```

Expected: push succeeds and `origin/main` advances to the final implementation commit.
