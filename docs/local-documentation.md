# Local Design Documentation

Durable local documents are optional. Use them only when product meaning,
authority, or decisions need to survive the conversation. Research notes and
ordinary implementation plans remain ephemeral unless the task needs durable
meaning.

When the profile is active:

```sh
python3 scripts/gauntlet.py docs ensure --project-root "$PROJECT_ROOT"
python3 scripts/gauntlet.py docs design create --project-root "$PROJECT_ROOT" --title "Title"
python3 scripts/gauntlet.py docs design accept --project-root "$PROJECT_ROOT" --design PROJECT-001
```

Canonical private documents stay under ignored `local-docs/` in the primary
worktree. The accepted record binds the exact source and Acceptance section.
Unsupported old Epic and PRD schemas are not migrated or interpreted.
