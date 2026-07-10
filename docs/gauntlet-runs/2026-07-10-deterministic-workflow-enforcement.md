# Deterministic Workflow Enforcement Audit

Task: `p1-auto: harden deterministic workflow enforcement`

## Research contract

- Question: Which Gauntlet workflow rules are actually enforced, where does thread-title enforcement first become reliable, and what should move from model instructions into code?
- Downstream consequence: prompt-only safety and naming rules can be skipped while still consuming context; over-mechanizing judgment would create brittle ceremony.
- Scope: source and installed Gauntlet, current checker/tests/call sites, title mutation paths, hooks/CI/evals, and current primary-source implementations in OMP, Claude Code, Codex, and OpenHands.
- Non-goals: modifying Codex host APIs, installing hooks globally, changing production systems, or making subjective product decisions deterministic.
- Freshness: source repositories inspected on 2026-07-10. OMP commit `395e4a5fcfceb0802e130370e358573636c2aad8`; OpenHands commit `d3b43ff34c533c8d7d03918cd1a953c79a7f6d9e`.

## Observed facts

The recent miss had three independent causes:

1. `docs/workflow-etiquette.md` stated the four-word convention, but the always-loaded router did not contain it and no lifecycle hook invoked the checker when a title changed.
2. `scripts/check-workflow-etiquette.py` parsed the prefix deterministically but accepted any non-empty goal after the colon.
3. `scripts/gauntlet.py followup thread` duplicated that permissive regex. Direct `set_thread_title` host calls bypass both CLIs.

The installed copies of the router, etiquette reference, checker, CLI, and workflow regression suite were byte-identical to source before this change. The intentionally untracked `house-voice-plans.md` was not read or changed.

## Enforcement inventory

| Surface | Present mechanism | Classification | Actual boundary or gap |
| --- | --- | --- | --- |
| Thread title prefix and execution suffix | Etiquette checker parser | Deterministic when invoked | No automatic invocation on raw host rename |
| Exactly four title words | Documentation only; permissive parsers | Unenforced before this slice | Both three- and five-word goals passed |
| Archive title rename/create-thread packets | Checker/CLI action plans | Deterministic | Safe place Gauntlet controls before app actions |
| Path/depth/proof/execution classification | Router and role instructions | Prompt-only | Requires agent judgment; should stay judgment-led |
| Deprecated kickoff fields | Parser emits warnings | Advisory | Invalid supplied enum values fail; missing narration does not block |
| Autonomous closeout assumptions | Checker flag | Deterministic when explicitly requested | Not a universal lifecycle gate |
| Strong follow-up/archive state | Checker plus `archive plan` | Deterministic state check with explicit review outcome | Agent must use the archive CLI |
| Dirty/ahead/behind Git archive state | Git inspection and action planner | Deterministic | Unknown/unavailable state becomes review or no action |
| Merge handoff shape, branch/PR/check state, action order | `gauntlet.py merge prepare|plan|execute` | Deterministic state machine | External GitHub state can change after planning |
| Installer managed blocks and installed layout | Installer parser plus `install verify` fixtures | Deterministic | Applies only when installer/verify runs |
| Skill contract shape and word budget | `lint-skills.py` | Deterministic | Soft-language findings are warnings |
| Skill-change pre-commit hook | Generated Git hook | Deterministic but opt-in | Covers staged skill files only; hook installation is not automatic |
| Pull-request/main regression suite | GitHub Actions | Deterministic | Enforces repository changes after push/PR, not live agent behavior |
| Skill text coverage and scorer smoke | Fixture phrase matching | Deterministic scorer plumbing | Explicitly not behavioral proof |
| Orchestration trace actions, authority, proof, and budgets | Schema plus deterministic trace scorer | Deterministic for observable fields | Subjective criteria return `cannot_verify` |
| Role reviews and product-quality decisions | Role skills/model reasoning | LLM-judged | Useful judgment; no calibrated automatic gate exists |
| Diff intel, test-plan suggestions, review packets, TypeScript durability classification | Heuristic scripts | Advisory | Inputs for judgment, not completion proof |
| UI, production, architecture, delegation, quiet-execution guidance | Router/docs/skills | Prompt-only | Triggered judgment remains necessary; not all prose has a host event to intercept |

No current Gauntlet script calls an LLM or the network to judge workflow compliance. `run-skill-evals.py` and `run-orchestration-evals.py` score local fixtures; live-model behavior and calibrated subjective judgment remain unavailable.

## External implementation findings

- OMP wraps tool execution at the harness boundary: typed `tool_call` events run before execution, can block, and fail closed on hook errors. Its session-title setter is also a single mutation point, although its built-in cleaner normalizes rather than validates title policy. This supports intercepting mutations at the owner boundary, not asking the model to remember a rule.
- Claude Code exposes blocking lifecycle hooks, including `PreToolUse`, `TaskCreated`, and `TaskCompleted`. Its documentation also identifies bypasses when a rule is attached to the wrong event, reinforcing the need to enumerate every mutation path.
- Codex's command policy is parsed and checked in runtime code and has a standalone checker, but current issue reports show that wrapper normalization and runtime-policy integration still matter. A deterministic parser is only reliable when every execution path consumes the same decision.
- OpenHands separates confirmation policy from its optional LLM security analyzer: never confirm, always confirm, or confirm risky when an LLM analyzer is selected. That is a useful boundary—objective state transitions can be deterministic while semantic risk classification remains judgment-based.

Primary sources: [OMP hook wrapper](https://github.com/can1357/oh-my-pi/blob/395e4a5fcfceb0802e130370e358573636c2aad8/packages/coding-agent/src/extensibility/hooks/tool-wrapper.ts), [OMP session title mutation](https://github.com/can1357/oh-my-pi/blob/395e4a5fcfceb0802e130370e358573636c2aad8/packages/coding-agent/src/session/session-manager.ts), [Claude Code hooks reference](https://code.claude.com/docs/en/hooks), [Codex repository and runtime policy code](https://github.com/openai/codex), and [OpenHands confirmation-policy selection](https://github.com/OpenHands/OpenHands/blob/d3b43ff34c533c8d7d03918cd1a953c79a7f6d9e/openhands/app_server/app_conversation/app_conversation_service_base.py).

## Recommendation and first slice

The earliest fully reliable enforcement point is the host's title mutation boundary. Gauntlet cannot modify that Codex app boundary from this repository. The earliest reliable point Gauntlet owns is immediately before emitting any title app action. Use one stdlib parser there and in the standalone checker, fail closed for current-format titles whose goals are not exactly four whitespace-delimited words, and retain the legacy format as warning-only migration behavior.

Do not add TypeScript. Gauntlet's active workflow CLI, installer, fixtures, and CI are Python/stdlib; TypeScript would add a runtime and distribution boundary without improving this parser's type safety, speed, or integration.

Token impact:

- Realized by this slice: zero always-loaded prompt growth and zero added LLM calls.
- Runtime cost: one local parser call; no subprocess or network is added to the follow-up path.
- Avoided alternative: adding another always-loaded reminder would cost roughly 25–40 tokens per task invocation using Gauntlet's word-count proxy, while still allowing bypass.
- Future savings: remove hard-rule prose only after a host-level interceptor covers raw title mutations; today that prose still explains the contract and the remaining boundary.

## Hardening cap and exit

Cap: title parsing, Gauntlet-owned title action emission, negative fixtures, broad workflow regression, and source/install drift inspection. Durable storage, UI, release automation, and unrelated workflow rules are out of scope. Exit when three- and five-word current titles fail, exact four-word titles pass, invalid action packets contain no actions, the broad suite passes, and the raw-host bypass is documented rather than hidden.

## Implementation and proof

- Added `scripts/thread_titles.py` as the single stdlib parser used by the etiquette checker and follow-up action builder.
- Current-format goals require exactly four words and reject multiline titles. Legacy titles remain readable with a warning but cannot create new thread actions.
- Red-green proof observed the prior checker accepting `p2-auto: fix archive closeout`, then passed the new three-word, five-word, multiline, legacy-create, archive-suggestion, and exact-four fixtures.
- Black-box CLI matrix: exact-four checker and create-thread packet pass; three/five/multiline titles fail; invalid or legacy create/archive inputs emit zero actions.
- `python3 scripts/check-gauntlet-workflow.py`: all 41 repository workflow checks passed, including temporary-home Codex/Claude installs.
- `git diff --check` and Python byte-compilation passed.

## Cannot verify

- Gauntlet cannot intercept or reject a direct Codex app `set_thread_title` call from this repository. A host hook/plugin or API-level validator is the next check before claiming universal enforcement.
- No representative corpus quantifies how often title drift occurs, so reliability and token savings beyond the deterministic boundary are estimates, not measured adoption impact.
