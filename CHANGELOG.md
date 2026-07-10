# Changelog

## Unreleased

- Gauntlet remote-branch cleanup now treats concurrent GitHub auto-deletion as a successful postcondition.
- Gauntlet merge cleanup now deletes remote branches without asking GitHub CLI to manipulate linked local worktrees.
- Gauntlet now keeps routine workflow controls out of the conversation and automatically creates contextual PR and changelog handoffs when merging work.
