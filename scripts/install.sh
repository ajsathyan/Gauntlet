#!/usr/bin/env bash
set -euo pipefail

AGENT_HOME="${AGENT_HOME:-${GAUNTLET_AGENT_HOME:-$HOME/.codex}}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

mkdir -p "$AGENT_HOME/skills" "$AGENT_HOME/gauntlet"
cp "$ROOT/AGENTS.md" "$AGENT_HOME/AGENTS.md"
cp -R "$ROOT/skills/." "$AGENT_HOME/skills/"
cp -R "$ROOT/templates" "$AGENT_HOME/gauntlet/"
cp -R "$ROOT/scripts" "$AGENT_HOME/gauntlet/"

echo "Installed Gauntlet to $AGENT_HOME"
echo "Restart your coding agent to pick up the new workflow."
