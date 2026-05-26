#!/usr/bin/env bash
set -euo pipefail

CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

mkdir -p "$CODEX_HOME/skills" "$CODEX_HOME/gauntlet"
cp "$ROOT/AGENTS.md" "$CODEX_HOME/AGENTS.md"
cp -R "$ROOT/skills/." "$CODEX_HOME/skills/"
cp -R "$ROOT/templates" "$CODEX_HOME/gauntlet/"
cp -R "$ROOT/scripts" "$CODEX_HOME/gauntlet/"

echo "Installed Gauntlet to $CODEX_HOME"
echo "Restart Codex to pick up new skills."
