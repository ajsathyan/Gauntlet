# Quiet Workflow And Guaranteed Merge Handoffs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve material child-work safeguards, remove unearned workflow ceremony from chat, and make “merge this” automatically produce a contextual PR plus an identical committed changelog entry before safely landing on `main`.

**Architecture:** Replace repeated lane prose with a schema-level `shared` packet plus lane-specific deltas, and split validator results into blocking material hazards and non-blocking efficiency warnings. Keep workflow classifications internal unless they change a user decision. Add a deterministic merge-handoff renderer and a two-phase merge helper so local preparation is committed before external PR/merge actions.

**Tech Stack:** Python 3 standard library, Git, GitHub CLI, Markdown, JSON, existing Gauntlet workflow tests and skill evals.

## Global Constraints

- Do not implement any task until the user approves this plan.
- Preserve `/Users/ajsathyan/Documents/CC/Gauntlet/house-voice-plans.md` and every unrelated dirty file.
- Work only in `/Users/ajsathyan/Documents/CC/Gauntlet-guaranteed-merge-child-workflows` on `codex/guarantee-merge-child-workflows` until the PR merge step.
- Keep child ownership, state, dependency, proof, worktree, `Needs decision`, main-task integration, and no-direct-push guarantees.
- Do not add child fork/provenance/thread-ID machinery or child title/status lifecycle requirements.
- A clean internal check remains silent in chat and in the final summary unless its artifact is required for consistency.
- Normal bounded research defaults to `p3`; research is never `p4` merely because it is research.
- Priority/title assignment occurs no later than the third exchange; unchanged priority reassessments are silent.
- Every genuine scope addition receives edge-case delta foresight before implementation. A clean check may be recorded only as `Scope delta checked: no material change.` inside the affected plan/task packet.
- Every requested merge creates or updates `CHANGELOG.md`; the PR `## Changelog` bullet must match that committed entry byte-for-byte.
- PR framing comes from the user goal and accepted decisions. The diff only verifies facts; it must not drive a code/file tour.
- PR title and commit subjects use `<area>: <imperative behavioral outcome>`.
- Required PR sections are `Problem`, `Solution`, `Changelog`, `Testing`, and `PR Note`. `Security / Risk` appears only when material.
- Keep quick prototype commits coherent: one commit for one inseparable behavioral change; multiple commits only when each checkpoint is independently reviewable.
- Do not claim context savings beyond the measured instruction/manifest text; separate child model contexts still ingest necessary shared constraints.

---

## File Responsibility Map

| File | Responsibility after this change |
| --- | --- |
| `scripts/check-subagent-plan.py` | Validate schema `1.2`, block material hazards, record advisory efficiency warnings, and keep successful validation quiet by default. |
| `docs/subagent-plan-validator.md` | Document shared packet data, lane deltas, blocking findings, warnings, and when validation is required for multi-lane or write-heavy child work. |
| `AGENTS.md` | Define the quiet conversation contract, consequence-based priority, scope-delta behavior, retained child controls, and automatic merge lifecycle. |
| `docs/workflow-etiquette.md` | Provide the expanded operational reference without requiring procedural narration. |
| `skills/planner/SKILL.md` | Produce shared packet manifests only for real parallel/write-heavy child implementation lanes. |
| `skills/implementer/SKILL.md` | Require accepted material-risk packets for delegated implementation and keep clean checks out of reports. |
| `scripts/gauntlet.py` | Validate/render merge handoffs, update changelog content idempotently, plan GitHub actions, and safely execute push/PR/check/merge actions. |
| `.github/PULL_REQUEST_TEMPLATE.md` | Show the agreed reviewer-oriented PR structure rather than an internal process checklist. |
| `docs/github-discipline.md` | Explain automatic merge semantics, commit style, PR framing, changelog identity, and cleanup. |
| `scripts/check-gauntlet-workflow.py` | Prove packet, silence, handoff, changelog, and merge behavior end to end. |
| `scripts/check-workflow-etiquette.py` | Stop requiring user-visible mode/edge-case/packet boilerplate while preserving material decision checks. |
| `CHANGELOG.md` | Durable `Unreleased` history; created by this change and used by every future merge. |
| `docs/gauntlet-runs/2026-07-09-quiet-workflow-guaranteed-merge.md` | Exceptions-only record of the measured validator evidence and selected tradeoff. |

---

### Task 1: Make packet validation target material hazards

**Files:**

- Modify: `scripts/check-subagent-plan.py`
- Modify: `scripts/check-gauntlet-workflow.py`
- Modify: `docs/subagent-plan-validator.md`

**Interfaces:**

- Consumes: schema `1.2` JSON with a top-level `shared` object and one or more lane objects; invoked for multi-lane or write-heavy child implementation.
- Produces: `validate_plan(data: dict, project_root: Path, max_lane_words: int, max_total_words: int) -> {"rejections": list[dict], "warnings": list[dict]}`; accepted/rejected JSONL records containing both counts; exit code `1` only for rejections.

- [ ] **Step 1: Add failing schema and severity tests**

Add `complete_subagent_plan(project: Path) -> dict` in `scripts/check-gauntlet-workflow.py` and use this exact shape:

```python
def complete_subagent_plan(project):
    return {
        "schemaVersion": "1.2",
        "runId": "workflow-test",
        "shared": {
            "projectRoot": ".",
            "acceptedSource": "docs/accepted-spec.md",
            "constraints": ["Preserve unrelated work."],
            "askUserPolicy": "Return Needs decision to the main task.",
            "expectedReturn": "Verdict, evidence, residual risk, and one next action.",
        },
        "lanes": [
            {
                "id": lane_id,
                "skill": "implementer",
                "objective": f"Implement bounded lane {lane_id}",
                "worktreePath": f".worktrees/{lane_id}",
                "scope": f"Implement {lane_id}",
                "inScope": [f"src/{lane_id}/**"],
                "outOfScope": ["src/shared/**"],
                "filesRead": [f"src/{lane_id}/**"],
                "filesWrite": [f"src/{lane_id}/**"],
                "filesAvoid": ["src/shared/**"],
                "stateScope": lane_id,
                "stateAccess": "mutates",
                "dependencies": [],
                "consumes": ["accepted spec"],
                "produces": [f"{lane_id} patch"],
                "laneConstraints": [],
                "proof": [f"test-{lane_id}"],
                "contextDelta": f"Only change the {lane_id} boundary.",
                "taskPacketRef": f".gauntlet/packets/{lane_id}.md",
            }
            for lane_id in ["C1", "C2"]
        ],
    }
```

Create the referenced spec and packets in the fixture. Add assertions that:

```python
assert accepted.returncode == 0
assert record["status"] == "accepted"
assert record["warningCount"] == 0

repeated = complete_subagent_plan(project)
repeated["lanes"][0]["contextDelta"] = "shared repeated context " * 20
repeated["lanes"][1]["contextDelta"] = "shared repeated context " * 20
assert repeated_result.returncode == 0
assert "duplicated_lane_context" in warning_codes

overlap = complete_subagent_plan(project)
overlap["lanes"][1]["filesWrite"] = overlap["lanes"][0]["filesWrite"]
assert overlap_result.returncode == 1
assert "overlapping_writes" in rejection_codes
```

Also cover shared mutable state, secret-bearing shared context, missing packet/source files, path escape, overbroad writes, duplicate proof warnings, broad read warnings, and oversized context warnings.

Add a one-lane fixture with non-empty `filesWrite` and `stateAccess: "mutates"`; assert it validates successfully. Remove the old `not_enough_lanes` rejection. A single small read-only child is packeted directly and does not invoke this manifest gate.

- [ ] **Step 2: Run the workflow suite and confirm it fails for unsupported schema `1.2`**

Run:

```bash
python3 scripts/check-gauntlet-workflow.py
```

Expected: FAIL in the subagent-plan tests because the validator still accepts only schema `1.1` and returns a flat rejection list.

- [ ] **Step 3: Implement the blocking/advisory split**

Refactor the validator around these exact constants and result contract:

```python
VALID_SCHEMA_VERSION = "1.2"
REQUIRED_SHARED_FIELDS = [
    "projectRoot",
    "acceptedSource",
    "constraints",
    "askUserPolicy",
    "expectedReturn",
]
REQUIRED_LANE_FIELDS = [
    "id", "skill", "objective", "worktreePath", "scope", "inScope",
    "outOfScope", "filesRead", "filesWrite", "filesAvoid", "stateScope",
    "stateAccess", "dependencies", "consumes", "produces",
    "laneConstraints", "proof", "contextDelta", "taskPacketRef",
]

def add_finding(findings, code, message, lane_id=None):
    findings.append({"code": code, "laneId": lane_id, "message": message})

def validate_plan(data, project_root, max_lane_words, max_total_words):
    rejections = []
    warnings = []
    # Populate rejections only for non-executable or unsafe packets.
    # Populate warnings for cost/redundancy findings.
    return {"rejections": rejections, "warnings": warnings}
```

Use `shared.projectRoot`, `shared.acceptedSource`, `shared.constraints`, `shared.askUserPolicy`, and `shared.expectedReturn` once. Validate secrets across serialized `shared` plus each `contextDelta`/`laneConstraints`. Move these existing codes to warnings and rename where needed:

```python
ADVISORY_CODES = {
    "duplicated_lane_context",
    "lane_context_too_large",
    "total_context_too_large",
    "duplicate_proof_target",
    "overbroad_read_scope",
}
```

Keep missing fields/files, invalid roots/references, secrets, overlapping writes, shared mutable state, and overbroad writes as rejections. Remove `title` and `status` validation entirely.

- [ ] **Step 4: Make accepted output quiet and logs complete**

Default stdout behavior:

```text
accepted
```

Use detailed text only for warnings/rejections or `--stats`. Persist:

```python
record.update({
    "status": "rejected" if result["rejections"] else "accepted",
    "warningCount": len(result["warnings"]),
    "warnings": result["warnings"],
    "rejectionCount": len(result["rejections"]),
    "rejections": result["rejections"],
})
```

- [ ] **Step 5: Update the validator reference**

Replace the example manifest in `docs/subagent-plan-validator.md` with schema `1.2`. State explicitly:

```text
Use the manifest for two or more parallel lanes or any write-heavy child implementation lane, including a single write-heavy lane.
Every child implementation lane still receives a bounded packet; a single small read-only child does not need this manifest gate.
Shared constraints and accepted sources live under `shared`; lanes contain only lane-specific deltas.
Warnings do not delay implementation unless they expose a real dependency, ownership conflict, or user decision.
Successful validation is durable internal evidence and is not a chat/final-summary event.
```

- [ ] **Step 6: Run proof and commit the independently reviewable validator change**

Run:

```bash
python3 scripts/check-gauntlet-workflow.py
```

Expected: PASS, including the new blocker/warning cases.

Commit:

```bash
git add scripts/check-subagent-plan.py scripts/check-gauntlet-workflow.py docs/subagent-plan-validator.md
git commit -m "workflow: validate material child hazards"
```

---

### Task 2: Keep workflow mechanics out of the conversation

**Files:**

- Modify: `AGENTS.md`
- Modify: `docs/workflow-etiquette.md`
- Modify: `skills/planner/SKILL.md`
- Modify: `skills/implementer/SKILL.md`
- Modify: `scripts/check-workflow-etiquette.py`
- Modify: `scripts/check-gauntlet-workflow.py`

**Interfaces:**

- Consumes: user asks, accepted scope, internal priority/mode/proof/gate decisions, scope additions, and optional child-lane plans.
- Produces: user-visible messages containing substantive decisions/results only; internal plan markers where consistency requires them.

- [ ] **Step 1: Add failing guidance-contract tests**

Add `test_workflow_guidance_keeps_routine_controls_silent()` with these assertions:

```python
agents = read(AGENTS_MD)
etiquette = read(DOCS / "workflow-etiquette.md")
planner = read(SKILLS / "planner" / "SKILL.md")

for marker in [
    "no later than the third user-assistant exchange",
    "Research is never assigned `p4` merely because it is research",
    "If the priority is unchanged, say nothing",
    "A clean check stays silent in chat",
    "Successful packet validation stays silent",
    "Do not record packetization when no child implementation lanes exist",
    "Native Codex state owns child progress; do not require title/status churn",
]:
    assert_contains(agents + etiquette + planner, marker, "quiet workflow contract")

for forbidden in [
    "Title child chats with the normal priority prefix plus lane/status tags",
    "Subagent packetization: not relevant because",
]:
    if forbidden in agents + etiquette + planner:
        raise AssertionError(f"obsolete ceremony remains: {forbidden}")
```

Adjust `scripts/check-workflow-etiquette.py` fixtures so a substantive response without Mode/Depth/Proof/Edge Cases headings passes, while a real unresolved p0-p2 kickoff label or material changed priority still requires user-visible handling.

- [ ] **Step 2: Run tests and confirm current guidance fails**

Run:

```bash
python3 scripts/check-gauntlet-workflow.py
```

Expected: FAIL because current guidance requires named mode/gate output, child title/status fields, and an explicit no-op packetization record.

- [ ] **Step 3: Rewrite the active workflow contract**

Apply these rules consistently in `AGENTS.md` and `docs/workflow-etiquette.md`:

```text
Internal only by default:
- mode, depth, proof scope, triggered gates
- skill selection
- worktree creation
- clean edge/scope checks
- successful packet validation
- architecture-hygiene transition
- routine review transition

User-visible only when substantive:
- a recommendation that changes the work
- a changed assumption or priority
- a blocker or decision
- a material finding
- meaningful proof/progress
- completion
```

Retain the current consequence-based priority table and third-exchange deadline. Keep `set_thread_title` as the internal app action. Remove mandatory chat confirmation for p0-p2 naming when the title/priority itself does not alter scope, risk appetite, or execution authorization; ask only when the consequence class changes what will be done.

For edge cases, retain exactly:

```text
Run scope-addition delta foresight before every genuine scope addition.
A clean result may be recorded only in the affected plan/task packet as:
`Scope delta checked: no material change.`
Material findings update scope, acceptance criteria, proof, priority, execution mode, or packets before implementation and are called out only when they change the plan or need a decision.
```

For child work, retain bounded packets for every implementation lane, ownership, worktrees, proof, main-task integration, and `Needs decision`. Validate two or more parallel lanes and every write-heavy child lane before implementation. Remove child title/status choreography, provenance/fork additions, clean validation narration, final validation counts, and the no-lanes declaration.

Fold the architecture-hygiene check into the normal final review and only name it when it finds something, is explicitly requested, or changes a release decision.

- [ ] **Step 4: Narrow planner and implementer output contracts**

In `skills/planner/SKILL.md`:

```text
- Omit the subagent manifest field when no child implementation lanes are proposed.
- For two or more parallel lanes or any write-heavy child lane, write schema 1.2 with one shared block and lane deltas, validate before implementation, and surface only blocking/material findings.
- Keep a clean scope-delta marker inside the affected task packet; do not narrate it.
```

In `skills/implementer/SKILL.md`:

```text
- Refuse delegated implementation only for missing/unaccepted packets or blocking validator findings.
- Do not include clean packet, scope-delta, architecture-hygiene, mode, gate, or skill transitions in the implementation report.
- Include warnings only when they changed execution or remain a real risk.
```

- [ ] **Step 5: Run targeted skill checks and workflow proof**

Run:

```bash
python3 scripts/lint-skills.py --only planner,implementer
python3 scripts/run-skill-evals.py --only-skill planner,implementer
python3 scripts/check-gauntlet-workflow.py
```

Expected: all commands PASS.

- [ ] **Step 6: Commit the independently reviewable conversation change**

```bash
git add AGENTS.md docs/workflow-etiquette.md skills/planner/SKILL.md skills/implementer/SKILL.md scripts/check-workflow-etiquette.py scripts/check-gauntlet-workflow.py
git commit -m "workflow: keep routine controls silent"
```

---

### Task 3: Generate high-context PR and changelog handoffs

**Files:**

- Modify: `scripts/gauntlet.py`
- Modify: `scripts/check-gauntlet-workflow.py`
- Modify: `.gitignore` only if `.gauntlet/merge-handoff.json` and `.gauntlet/pr-body.md` are not already ignored

**Interfaces:**

- Consumes: `.gauntlet/merge-handoff.json` with user-goal framing and proof.
- Produces: deterministic PR Markdown, an idempotent `CHANGELOG.md` update, and JSON describing both paths and exact changelog identity.

- [ ] **Step 1: Add a failing merge-handoff renderer test**

Use this exact fixture:

```python
handoff = {
    "schemaVersion": "1.0",
    "title": "workflow: generate contextual merge handoffs",
    "problem": {
        "context": "Gauntlet's useful controls are exposed as conversation ceremony.",
        "impact": "The user has to read process narration and manually reconstruct merge context.",
    },
    "solution": {
        "outcome": "Keep material controls internal and make merge handoffs automatic.",
        "invariants": [
            "Child ownership and proof controls remain enforced.",
            "The PR changelog line exactly matches CHANGELOG.md.",
        ],
        "preserved": ["Quick local prototype development remains the default."],
        "nonGoals": ["No new child thread provenance machinery."],
    },
    "changelog": "Gauntlet now keeps routine workflow controls out of the conversation and automatically creates contextual PR and changelog handoffs when merging work.",
    "testing": [
        {
            "command": "python3 scripts/check-gauntlet-workflow.py",
            "result": "PASS",
            "proves": "Packet, conversation, handoff, and merge contracts pass together.",
        }
    ],
    "prNote": [
        "Child safeguards are retained; duplicate-context findings are advisory because the old blocker did not control actual dispatch prompts."
    ],
    "securityRisk": None,
}
```

Assert the rendered body has sections in this order:

```python
expected = [
    "## Problem",
    "## Solution",
    "## Changelog",
    "## Testing",
    "## PR Note",
]
positions = [body.index(item) for item in expected]
assert positions == sorted(positions)
assert "## Security / Risk" not in body
assert f"- {handoff['changelog']}" in body
assert "Files changed" not in body
```

Run prepare twice and assert exactly one identical `Unreleased` entry exists.

- [ ] **Step 2: Run the test and confirm the merge-handoff command is missing**

Run:

```bash
python3 scripts/check-gauntlet-workflow.py
```

Expected: FAIL because `gauntlet.py merge prepare` and the renderer do not exist.

- [ ] **Step 3: Implement the handoff schema and renderer**

Add these exact interfaces to `scripts/gauntlet.py`:

```python
REQUIRED_HANDOFF_FIELDS = {
    "schemaVersion", "title", "problem", "solution", "changelog",
    "testing", "prNote", "securityRisk",
}

def load_merge_handoff(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def validate_merge_handoff(data: dict) -> list[dict]:
    """Return blocking findings for missing/empty framing, proof, or changelog data."""

def render_pr_body(data: dict) -> str:
    """Render Problem, Solution, Changelog, Testing, PR Note, and optional Security / Risk."""

def ensure_unreleased_changelog(changelog_path: Path, entry: str) -> bool:
    """Create/update CHANGELOG.md idempotently; return True only when the file changed."""
```

Validation requires non-empty `problem.context`, `problem.impact`, `solution.outcome`, `changelog`, `testing`, and `prNote`. It allows empty `invariants`, `preserved`, and `nonGoals`, omitting their prose rather than rendering empty boilerplate. It rejects newlines in the changelog entry so byte-for-byte comparison stays deterministic.

Render Testing as:

```markdown
- `python3 scripts/check-gauntlet-workflow.py` — **PASS** — Packet, conversation, handoff, and merge contracts pass together.
```

Write the PR body to `.gauntlet/pr-body.md` and print JSON containing `title`, `bodyPath`, `changelogPath`, `changelogEntry`, and `changelogChanged`.

- [ ] **Step 4: Add the `merge prepare` parser**

Add:

```text
scripts/gauntlet.py merge prepare \
  --git-root "$PROJECT_ROOT" \
  --handoff .gauntlet/merge-handoff.json \
  --body-output .gauntlet/pr-body.md \
  --json
```

Keep `changelog pr --implementation-memory` backward-compatible, but make the merge path use the new goal-first handoff renderer.

- [ ] **Step 5: Run proof and commit**

Run:

```bash
python3 scripts/check-gauntlet-workflow.py
```

Expected: PASS for handoff validation, conditional risk section, deterministic ordering, and idempotent changelog identity.

Commit:

```bash
git add scripts/gauntlet.py scripts/check-gauntlet-workflow.py .gitignore
git commit -m "workflow: generate contextual PR handoffs"
```

If `.gitignore` does not change, omit it from `git add`.

---

### Task 4: Make “merge this” execute the complete safe lifecycle

**Files:**

- Modify: `scripts/gauntlet.py`
- Modify: `scripts/check-gauntlet-workflow.py`
- Modify: `AGENTS.md`
- Modify: `docs/github-discipline.md`
- Modify: `docs/workflow-etiquette.md`

**Interfaces:**

- Consumes: prepared handoff/body/changelog, current task branch, Git/PR/check state, and a user merge instruction.
- Produces: ordered safe actions for push, PR create/update, check wait, merge, remote deletion, default-branch verification, and local cleanup guidance.

- [ ] **Step 1: Add failing merge-plan and execution tests**

Extend the existing fake `git`/`gh` harness to prove these cases:

```python
expected_new_pr_actions = [
    "git_push",
    "gh_pr_create",
    "gh_pr_checks_watch",
    "gh_pr_merge",
    "verify_default_branch",
]

expected_existing_pr_actions = [
    "git_push",
    "gh_pr_edit",
    "gh_pr_checks_watch",
    "gh_pr_merge",
    "verify_default_branch",
]
```

Also assert:

- Current branch `main` fails with `task_branch_required`.
- Uncommitted `CHANGELOG.md` or source changes fail with `uncommitted_merge_work`.
- Missing/mismatched PR changelog fails before push.
- Failed/pending required checks prevent merge.
- A new commit after the PR proof causes body refresh and another check wait.
- Merge uses the repository-configured method; the fallback command is `gh pr merge "$PR_NUMBER" --merge --delete-branch`, where `PR_NUMBER` comes from the freshly queried PR state.
- An existing PR is edited, never duplicated.
- Local worktree/branch cleanup is not attempted while unique uncommitted work exists.
- Final verification proves the merge commit is reachable from `origin/main`.

- [ ] **Step 2: Run the workflow test and confirm the merge commands are missing**

Run:

```bash
python3 scripts/check-gauntlet-workflow.py
```

Expected: FAIL because `merge plan` and `merge execute` are not registered.

- [ ] **Step 3: Implement plan and execute commands by reusing archive safety primitives**

Add these interfaces:

```python
def collect_merge_state(git_root: Path, handoff: dict, body: str) -> dict:
    """Collect branch, upstream, dirty, PR, checks, review, and merge-method facts."""

def build_merge_plan(state: dict) -> dict:
    """Return pass/review/fail findings plus a deterministic ordered action list."""

def execute_merge_plan(plan: dict, git_root: Path) -> dict:
    """Execute only actions returned by a fresh passing merge plan."""
```

Register:

```text
scripts/gauntlet.py merge plan --git-root /Users/ajsathyan/Documents/CC/Gauntlet-guaranteed-merge-child-workflows --handoff .gauntlet/merge-handoff.json --body .gauntlet/pr-body.md --json
scripts/gauntlet.py merge execute --git-root /Users/ajsathyan/Documents/CC/Gauntlet-guaranteed-merge-child-workflows --handoff .gauntlet/merge-handoff.json --body .gauntlet/pr-body.md --json
```

Execution order is fixed:

1. Push the current task branch.
2. Create or edit one PR using the handoff title and body file.
3. Watch required checks.
4. Re-fetch PR/check/review state and abort on any blocker.
5. Merge using repository policy, defaulting to `--merge` only when multiple methods are allowed and no override exists.
6. Verify the merged commit is reachable from `origin/main`.
7. Delete the remote branch through the merge command.
8. Return the exact local branch/worktree cleanup action; execute cleanup only from outside that worktree and only when no unique work remains.

Do not auto-create commits inside the helper. The main task owns the coherent commit after `merge prepare`; “merge this” instructs the agent to perform that local commit step before calling `merge execute`.

- [ ] **Step 4: Guarantee the phrase-level behavior in workflow guidance**

Add this exact semantic rule to `AGENTS.md` and the two references:

```text
“Merge this,” “land this,” or “merge this to main” authorizes the complete safe closeout for the current scoped work: prepare the contextual handoff, update CHANGELOG.md, commit coherent local changes, push the task branch, create/update the PR, wait for required checks and blocking review state, merge, delete the task branch, and verify the default branch. Ask only when a new material decision or preservation risk appears.
```

Clarify that “push to git” means push the current branch and does not by itself merge or direct-push to `main`.

- [ ] **Step 5: Run proof and commit**

Run:

```bash
python3 scripts/check-gauntlet-workflow.py
```

Expected: PASS for new/existing PRs, check gating, stale proof, merge method, changelog identity, and cleanup safety.

Commit:

```bash
git add scripts/gauntlet.py scripts/check-gauntlet-workflow.py AGENTS.md docs/github-discipline.md docs/workflow-etiquette.md
git commit -m "workflow: land changes through contextual PRs"
```

---

### Task 5: Publish the agreed PR format and durable change record

**Files:**

- Modify: `.github/PULL_REQUEST_TEMPLATE.md`
- Modify: `docs/github-discipline.md`
- Create: `CHANGELOG.md`
- Create: `docs/gauntlet-runs/2026-07-09-quiet-workflow-guaranteed-merge.md`
- Modify: `scripts/check-gauntlet-workflow.py`

**Interfaces:**

- Consumes: the accepted PR body contract and measured trace evidence.
- Produces: reviewer-facing template, release history, and exceptions-only decision record.

- [ ] **Step 1: Add failing static contract tests**

Assert the PR template contains the required headings in order and does not contain empty process sections:

```python
template = read(ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md")
required = ["## Problem", "## Solution", "## Changelog", "## Testing", "## PR Note"]
assert [template.index(item) for item in required] == sorted(template.index(item) for item in required)
for obsolete in ["## Functional Changes", "## User Or Agent Impact", "## Workflow Or Behavior Changes", "## Release Proof (near-launch only)"]:
    if obsolete in template:
        raise AssertionError(f"obsolete PR ceremony remains: {obsolete}")
```

Assert `CHANGELOG.md` contains the exact bullet used by the handoff fixture.

- [ ] **Step 2: Replace the PR template with the approved format**

Use exactly:

```markdown
## Problem

<!-- Who is affected, what was insufficient before, and why it matters. -->

## Solution

<!-- Resulting behavior, important invariants/design choices, preserved behavior, and meaningful non-goals. Do not write a file/function tour. -->

## Changelog

<!-- One release-note bullet copied exactly into CHANGELOG.md under Unreleased. -->

- <!-- Exact changelog entry -->

## Testing

<!-- `command` — PASS/FAIL — what it proves; include limitations or Cannot verify when relevant. -->

- <!-- Exact command, result, and what it proves -->

## PR Note

<!-- Material tradeoff, compatibility/recovery context, meaningful non-goal, or merge rationale. -->
```

The renderer adds `## Security / Risk` only when material; the static template omits it to avoid empty boilerplate.

- [ ] **Step 3: Create the changelog with the exact current entry**

Create:

```markdown
# Changelog

## Unreleased

- Gauntlet now keeps routine workflow controls out of the conversation and automatically creates contextual PR and changelog handoffs when merging work.
```

- [ ] **Step 4: Create the exceptions-only run log**

Record only:

- Nine attempts across seven unique validator runs.
- Two rejections, both duplicate context; no observed material-hazard rejection.
- Combined manifest overhead: +148 tokens, +7.7% relative to accepted manifests.
- Actual dispatched child instructions: 866 repeated exact-sentence tokens out of 2,143 instruction tokens; current validator did not control them.
- Decision: shared references plus material blocking; duplicate/size/proof/read breadth become warnings.
- Limitation: separate children still need their relevant shared constraints; total billed/cached child context was not available in the traces.

Do not list routine successful checks.

- [ ] **Step 5: Run static and full proof, then commit**

Run:

```bash
python3 scripts/check-gauntlet-workflow.py
```

Expected: PASS.

Commit:

```bash
git add .github/PULL_REQUEST_TEMPLATE.md docs/github-discipline.md CHANGELOG.md docs/gauntlet-runs/2026-07-09-quiet-workflow-guaranteed-merge.md scripts/check-gauntlet-workflow.py
git commit -m "docs: frame changes for future maintainers"
```

---

### Task 6: Verify, install, protect `main`, and use the new merge path

**Files:**

- Modify only if verification finds an in-scope defect: files already listed above
- Use as ephemeral inputs: `.gauntlet/merge-handoff.json`, `.gauntlet/pr-body.md`
- Verify installed copy: `/Users/ajsathyan/.codex/AGENTS.md` and `/Users/ajsathyan/.codex/gauntlet/**`

**Interfaces:**

- Consumes: all committed implementation tasks and the accepted merge instruction.
- Produces: passing local proof, installed global behavior, protected `main`, contextual PR, merged commit, deleted task branch/worktree, and verified default branch.

- [ ] **Step 1: Run final changed-surface and skill proof**

Run:

```bash
python3 scripts/lint-skills.py --only planner,implementer
python3 scripts/run-skill-evals.py --only-skill planner,implementer
python3 scripts/check-gauntlet-workflow.py
```

Expected: all commands PASS. If a review fix changes code, rerun the affected targeted command and the full workflow suite.

- [ ] **Step 2: Review the diff for the agreed cut line**

Run:

```bash
git diff --check main...HEAD
git diff --stat main...HEAD
git log --oneline main..HEAD
```

Expected: no whitespace errors; only scoped workflow, validator, merge, PR, changelog, test, and decision-log files; each commit has an independently understandable behavioral subject.

Reject from this PR any child fork/provenance/thread-ID feature, title/status lifecycle, release publishing, generic process checklist, or unrelated cleanup.

- [ ] **Step 3: Install and verify the global Codex copy**

Run:

```bash
./scripts/install.sh --target codex
python3 scripts/gauntlet.py install verify --target codex --agent-home /Users/ajsathyan/.codex --json
```

Expected: installer and verification PASS while preserving the personal house-voice block.

- [ ] **Step 4: Prepare the actual merge handoff**

Write `.gauntlet/merge-handoff.json` with the Task 3 fixture updated to the final verified test results. Run:

```bash
python3 scripts/gauntlet.py merge prepare \
  --git-root /Users/ajsathyan/Documents/CC/Gauntlet-guaranteed-merge-child-workflows \
  --handoff .gauntlet/merge-handoff.json \
  --body-output .gauntlet/pr-body.md \
  --json
```

Expected: `CHANGELOG.md` remains unchanged because its exact entry already exists; the rendered PR body contains the agreed sections and omits `Security / Risk` unless final review found a material risk.

- [ ] **Step 5: Commit any final handoff-driven changelog change and push**

If `merge prepare` changed `CHANGELOG.md`, rerun the full workflow suite and commit that coherent change. Then run:

```bash
git status --short
git push -u origin codex/guarantee-merge-child-workflows
```

Expected: the worktree is clean before push, and the task branch is present on origin.

- [ ] **Step 6: Protect `main` without adding a human-approval ceremony**

Verify that the current default-branch commit has a check named `gauntlet`:

```bash
gh api repos/ajsathyan/Gauntlet/commits/main/check-runs \
  --jq '.check_runs[] | select(.name == "gauntlet") | .name'
```

Expected: at least one exact `gauntlet` result. If it cannot be verified, stop instead of configuring a guessed required context. Then configure branch protection for `ajsathyan/Gauntlet`:

```bash
gh api --method PUT repos/ajsathyan/Gauntlet/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  --input -
```

Supply this JSON on stdin:

```json
{
  "required_status_checks": {"strict": true, "contexts": ["gauntlet"]},
  "enforce_admins": true,
  "required_pull_request_reviews": {"required_approving_review_count": 0},
  "restrictions": null,
  "required_conversation_resolution": true,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "allow_fork_syncing": true
}
```

Then verify:

```bash
gh api repos/ajsathyan/Gauntlet/branches/main/protection
```

Expected: required status check `gauntlet`, strict/current branch requirement, conversation resolution, admin enforcement, no force pushes, and no deletion. If GitHub rejects zero-review PR protection, stop and report the exact API limitation rather than silently requiring a human approval or weakening the PR/check guarantee.

- [ ] **Step 7: Create/update the PR and merge through the helper**

Run:

```bash
python3 scripts/gauntlet.py merge execute \
  --git-root /Users/ajsathyan/Documents/CC/Gauntlet-guaranteed-merge-child-workflows \
  --handoff .gauntlet/merge-handoff.json \
  --body .gauntlet/pr-body.md \
  --json
```

Expected: one PR titled `workflow: generate contextual merge handoffs`; PR body uses the approved high-level format; protected `main` requires the current green `gauntlet` check; the PR merges with a merge commit; the remote task branch is deleted; `origin/main` contains the merge.

- [ ] **Step 8: Clean local state and verify `main`**

From `/Users/ajsathyan/Documents/CC/Gauntlet`, after confirming the worktree has no unique work:

```bash
git fetch origin
git merge --ff-only origin/main
git worktree remove /Users/ajsathyan/Documents/CC/Gauntlet-guaranteed-merge-child-workflows
git branch -d codex/guarantee-merge-child-workflows
git status --short
git log -1 --oneline main
```

Expected: local `main` matches `origin/main`; the task worktree and local branch are removed; unrelated `/Users/ajsathyan/Documents/CC/Gauntlet/house-voice-plans.md` remains untouched; the latest main commit is the PR merge commit.

---

## Planned PR Output For This Change

**Title**

```text
workflow: generate contextual merge handoffs
```

**Body source, before final proof values are inserted**

```markdown
## Problem

Gauntlet’s useful workflow controls are exposed as conversation ceremony, while its merge path does not automatically preserve the higher-level reason for a change. This makes AI-driven local prototyping feel slower in chat and leaves future maintainers with code-detail summaries instead of the framing needed to understand what landed.

## Solution

Keep material controls—child ownership, write isolation, proof, and merge safety—but make clean routine mechanics silent. Replace duplicate-text packet rejection with shared context references and material-risk validation. Treat “merge this” as the complete branch, changelog, contextual PR, checks, merge, cleanup, and verification lifecycle.

Quick local prototype development remains the default. This change does not add child thread provenance, child title/status churn, human approval requirements, or release publishing.

## Changelog

- Gauntlet now keeps routine workflow controls out of the conversation and automatically creates contextual PR and changelog handoffs when merging work.

## Testing

- `python3 scripts/lint-skills.py --only planner,implementer` — **PASS** — Planner and implementer contracts remain valid after the packet/output changes.
- `python3 scripts/run-skill-evals.py --only-skill planner,implementer` — **PASS** — Targeted scenarios preserve bounded planning and implementation behavior.
- `python3 scripts/check-gauntlet-workflow.py` — **PASS** — Packet, conversation, handoff, changelog, and merge contracts pass together.
- `python3 scripts/gauntlet.py install verify --target codex --agent-home /Users/ajsathyan/.codex --json` — **PASS** — The installed global workflow matches the verified repository behavior and preserves the personal layer.

## PR Note

The trace sample found two packet rejections, both for duplicated inline text, and no material-hazard rejection. Duplicate manifest text added 148 tokens (+7.7%) across those cases, while actual dispatch prompts still repeated shared instructions. The design therefore retains blocking validation for executable/safety hazards and makes duplication an advisory signal handled through shared references.
```

If any listed command does not pass during implementation, replace `PASS` with the actual result and describe the limitation; do not merge with a knowingly false PR body.
