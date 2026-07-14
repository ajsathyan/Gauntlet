# Auditable Custom Agents

## Decisions

- Codex profiles are repository-owned TOML installed under the user agent home; the installer uses a hash manifest and refuses to adopt or overwrite unowned same-name files.
- Ticket routing is an ordered deterministic decision table. The parent supplies the selected profile explicitly and retains integration and release authority.
- Codex native SQLite state is the immediate usage record. Gauntlet creates a durable, privacy-bounded JSONL view by idempotent merge because the documented `SubagentStart` hook did not fire in the local CLI smoke environment. Existing audit rows survive native-state pruning or temporary database unavailability.
- The audit excludes prompts, previews, transcript paths, and message contents. It includes only operational identity, selection, timing, working-directory, and usage fields.

## Proof And Limits

- A pre-implementation local smoke proved that an explicitly requested `gauntlet-fast-reader` started with its configured Luna model and medium reasoning effort in native state.
- Repository checks cover profile validation, preservation-safe installation, deterministic guidance, and audit export behavior. The exact merged revision must be installed and rechecked after merge.
- Native state capture is immediate. The JSONL view is current after the router's terminal-state sync or a later manual/backfill sync; it is not an independent event stream.
