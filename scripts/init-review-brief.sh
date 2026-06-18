#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$PWD}"
ROOT="$(cd "$ROOT" && pwd)"
PROJECT_NAME="${GAUNTLET_REVIEW_PROJECT:-$(basename "$ROOT")}"
BRIEF="$ROOT/review-brief.html"
DATA="$ROOT/review-brief-data.json"
SCHEMA_TARGET="$ROOT/review-brief-data.schema.json"
ASSETS="$ROOT/review-brief-assets"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GAUNTLET_HOME="${GAUNTLET_HOME:-${AGENT_HOME:-$HOME/.codex/gauntlet}}"
REFRESH_TEMPLATE="${GAUNTLET_REVIEW_REFRESH_TEMPLATE:-0}"

copy_if_missing_or_refresh() {
  local source="$1"
  local target="$2"
  if [ -f "$source" ] && { [ ! -f "$target" ] || [ "$REFRESH_TEMPLATE" = "1" ]; }; then
    cp "$source" "$target"
  fi
}

TEMPLATE="$SCRIPT_DIR/../templates/review-brief.html"
SCHEMA="$SCRIPT_DIR/../templates/review-brief-data.schema.json"
VALIDATOR="$SCRIPT_DIR/validate-review-brief-data.py"
EMBEDDER="$SCRIPT_DIR/embed-review-brief-data.py"

if [ ! -f "$TEMPLATE" ] && [ -f "$GAUNTLET_HOME/templates/review-brief.html" ]; then
  TEMPLATE="$GAUNTLET_HOME/templates/review-brief.html"
fi
if [ ! -f "$SCHEMA" ] && [ -f "$GAUNTLET_HOME/templates/review-brief-data.schema.json" ]; then
  SCHEMA="$GAUNTLET_HOME/templates/review-brief-data.schema.json"
fi
if [ ! -f "$VALIDATOR" ] && [ -f "$GAUNTLET_HOME/scripts/validate-review-brief-data.py" ]; then
  VALIDATOR="$GAUNTLET_HOME/scripts/validate-review-brief-data.py"
fi
if [ ! -f "$EMBEDDER" ] && [ -f "$GAUNTLET_HOME/scripts/embed-review-brief-data.py" ]; then
  EMBEDDER="$GAUNTLET_HOME/scripts/embed-review-brief-data.py"
fi

copy_if_missing_or_refresh "$TEMPLATE" "$BRIEF"
copy_if_missing_or_refresh "$SCHEMA" "$SCHEMA_TARGET"
mkdir -p "$ASSETS"

if [ ! -f "$DATA" ]; then
  PROJECT_NAME="$PROJECT_NAME" python3 - <<'PY' > "$DATA"
import datetime
import json
import os

now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
project = os.environ["PROJECT_NAME"]
json.dump({
    "schemaVersion": "1.0",
    "generatedAt": now,
    "brief": {
        "title": f"{project} review brief",
        "summary": "Live review surface for the current Gauntlet run. Add RB/CU/N/P records as meaningful review data emerges.",
        "status": "In Progress",
        "project": project,
        "mode": "Unclassified",
        "artifactPath": "review-brief.html",
        "sinceLastReview": "Initial brief"
    },
    "reviewItems": [],
    "changeUnits": [],
    "notes": [],
    "proof": []
}, fp=os.sys.stdout, indent=2)
os.sys.stdout.write("\n")
PY
fi

if [ -f "$VALIDATOR" ]; then
  python3 "$VALIDATOR" "$DATA" >/dev/null
fi
if [ ! -f "$EMBEDDER" ]; then
  echo "missing embed-review-brief-data.py" >&2
  exit 1
fi
python3 "$EMBEDDER" "$ROOT" >/dev/null

echo "Initialized review brief files in $ROOT"
echo "Serve with: ${SCRIPT_DIR}/serve-review-brief.sh \"$ROOT\""
