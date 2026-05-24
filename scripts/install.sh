#!/usr/bin/env bash
set -euo pipefail

CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

mkdir -p "$CODEX_HOME/skills"
cp "$ROOT/AGENTS.md" "$CODEX_HOME/AGENTS.md"
cp -R "$ROOT/skills/." "$CODEX_HOME/skills/"

echo "Installed Gauntlet to $CODEX_HOME"
echo "Restart Codex to pick up new skills."
