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

verify_review_url() {
  local url="$1"
  URL="$url" ROOT="$ROOT" python3 - <<'PY' >/dev/null 2>&1
import hashlib
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

url = os.environ["URL"]
root = Path(os.environ["ROOT"])
parsed = urllib.parse.urlparse(url)
if parsed.scheme != "http" or parsed.path != "/review-brief.html":
    raise SystemExit(1)

def fetch(target):
    with urllib.request.urlopen(target, timeout=2) as response:
        if response.status != 200:
            raise SystemExit(1)
        return response.read()

html = fetch(url)
data_url = urllib.parse.urlunparse(parsed._replace(path="/review-brief-data.json"))
data = fetch(data_url)
if hashlib.sha256(html).digest() != hashlib.sha256((root / "review-brief.html").read_bytes()).digest():
    raise SystemExit(1)
if hashlib.sha256(data).digest() != hashlib.sha256((root / "review-brief-data.json").read_bytes()).digest():
    raise SystemExit(1)
if json.loads(data).get("schemaVersion") != "1.0":
    raise SystemExit(1)
PY
}

"$INIT" "$ROOT" >/dev/null
URL="$("$SERVE" "$ROOT")"

if [ -z "$URL" ]; then
  echo "review brief server did not return a URL" >&2
  exit 1
fi
if ! verify_review_url "$URL"; then
  echo "review brief server returned an unhealthy URL: $URL" >&2
  exit 1
fi

echo "Review brief: $URL"
