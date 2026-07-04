# Claude Install Target

Date: 2026-07-04
Scope: Add first-class Codex and Claude Code install targets and verify both in clean temporary agent homes.
Proof scope: delta.

## Assumptions

- Claude Code should consume Gauntlet through `CLAUDE.md`, with Gauntlet's `AGENTS.md` kept as the shared source of truth.
- Existing user-level Claude instructions are personal memory and must be preserved.

## Decisions

- `scripts/install.sh` keeps `codex` as the default target for backward compatibility.
- `--target claude` writes a managed Gauntlet block into `CLAUDE.md` instead of replacing the file.
- Both targets install `AGENTS.md` under `$AGENT_HOME/gauntlet/AGENTS.md` so installed workflow checks can run from the installed layout.
- Claude-specific adaptation is intentionally thin: import Gauntlet, point at installed role skills, and map Codex-specific actions to Claude Code/Git/GitHub equivalents when possible.

## Exceptions

- Did not globally install into `/Users/ajsathyan/.codex` or `/Users/ajsathyan/.claude`; proof used temporary clean homes to avoid mutating personal state.
- Did not implement broader archive/git deterministic execution or workflow speedup CLI promotion in this run; those remain discussion items.

## Proof

- `python3 scripts/check-gauntlet-workflow.py`
- `python3 -m py_compile scripts/check-gauntlet-workflow.py`
- `bash -n scripts/install.sh`
- `./scripts/install.sh --help`

## Production Quality Bar

Not relevant because this is installer workflow guidance, not an app or production launch surface. Release-style proof was limited to clean install behavior and regression checks.

## Coverage Gap Candidates

None.
