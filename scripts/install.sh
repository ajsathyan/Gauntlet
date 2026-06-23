#!/usr/bin/env bash
set -euo pipefail

AGENT_HOME="${AGENT_HOME:-${GAUNTLET_AGENT_HOME:-$HOME/.codex}}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

mkdir -p "$AGENT_HOME/skills" "$AGENT_HOME/gauntlet"
cp "$ROOT/AGENTS.md" "$AGENT_HOME/AGENTS.md"
cp "$ROOT/README.md" "$AGENT_HOME/gauntlet/README.md"
cp -R "$ROOT/skills/." "$AGENT_HOME/skills/"
cp -R "$ROOT/templates" "$AGENT_HOME/gauntlet/"
cp -R "$ROOT/scripts" "$AGENT_HOME/gauntlet/"
mkdir -p "$AGENT_HOME/gauntlet/evals"
rsync -a --delete \
  --exclude '/generated-prompts/' \
  --exclude '/results/' \
  "$ROOT/evals/" "$AGENT_HOME/gauntlet/evals/"
if [ "${GAUNTLET_SKIP_GIT_HOOKS:-0}" != "1" ] && [ -d "$ROOT/.git" ]; then
  "$ROOT/scripts/install-git-hooks.sh" --repo "$ROOT" --gauntlet-root "$ROOT" >/dev/null
fi
rm -f "$AGENT_HOME/gauntlet/templates/implementation-notes.html"
rm -f "$AGENT_HOME/gauntlet/scripts/serve-notes.sh"

echo "Installed Gauntlet to $AGENT_HOME"
echo "Restart your coding agent to pick up the new workflow."
