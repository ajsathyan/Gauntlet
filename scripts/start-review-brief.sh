#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$PWD}"
ROOT="$(cd "$ROOT" && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INIT="$SCRIPT_DIR/init-review-brief.sh"
SERVE="$SCRIPT_DIR/serve-review-brief.sh"
GAUNTLET_HOME="${GAUNTLET_HOME:-${AGENT_HOME:-$HOME/.codex/gauntlet}}"

if [ ! -x "$INIT" ] && [ -x "$GAUNTLET_HOME/scripts/init-review-brief.sh" ]; then
  INIT="$GAUNTLET_HOME/scripts/init-review-brief.sh"
fi
if [ ! -x "$SERVE" ] && [ -x "$GAUNTLET_HOME/scripts/serve-review-brief.sh" ]; then
  SERVE="$GAUNTLET_HOME/scripts/serve-review-brief.sh"
fi

if [ ! -x "$INIT" ]; then
  echo "missing executable init-review-brief.sh" >&2
  exit 1
fi
if [ ! -x "$SERVE" ]; then
  echo "missing executable serve-review-brief.sh" >&2
  exit 1
fi

"$INIT" "$ROOT" >/dev/null
URL="$("$SERVE" "$ROOT")"

if [ -z "$URL" ]; then
  echo "review brief server did not return a URL" >&2
  exit 1
fi

echo "Review brief: $URL"
