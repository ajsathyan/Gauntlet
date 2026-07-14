# Auditable Custom Agents

## Decisions

- Codex profiles are repository-owned TOML installed under the user agent home; the installer uses a hash manifest and refuses to adopt or overwrite unowned same-name files.
- Ticket routing is an ordered deterministic decision table. The parent supplies the selected profile explicitly and retains integration and release authority.
- Codex native SQLite state is the immediate usage record. Gauntlet creates a durable, privacy-bounded JSONL view by idempotent merge because the documented `SubagentStart` hook did not fire in the local CLI smoke environment. Existing audit rows survive native-state pruning or temporary database unavailability.
- The audit excludes prompts, previews, transcript paths, and message contents. It includes only operational identity, selection, timing, working-directory, and usage fields.

## Proof And Limits

- An early isolated smoke appeared to start the requested profile, but the first merged-revision check exposed Codex's underscore-only agent-name constraint. The profiles were renamed and reinstalled.
- After that correction, this machine's non-interactive `codex exec` runner did not spawn either a custom agent or two explicitly requested built-in agents, even with stable multi-agent support explicitly enabled. The router now forbids waiting or parent fallback until `spawn_agent` returns a child ID. Actual desktop dispatch remains `Cannot verify` until Codex is restarted and a new task exercises the installed profile.
- Repository checks cover profile validation, preservation-safe installation, deterministic guidance, and audit export behavior. The exact merged revision must be installed and rechecked after merge.
- Native state capture is immediate. The JSONL view is current after the router's terminal-state sync or a later manual/backfill sync; it is not an independent event stream.
