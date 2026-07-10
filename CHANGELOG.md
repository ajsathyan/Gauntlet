# Changelog

## Unreleased

- Gauntlet now uses one lean Research/Patch/Feature/Release workflow, folds selected Superpowers techniques into attributed native skills, and safely retires overlapping runtime skills.

- Gauntlet remote-branch cleanup now treats concurrent GitHub auto-deletion as a successful postcondition.
- Gauntlet merge cleanup now deletes remote branches without asking GitHub CLI to manipulate linked local worktrees.
- Gauntlet now keeps routine workflow controls out of the conversation and automatically creates contextual PR and changelog handoffs when merging work.
