#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$PWD}"
ROOT="$(cd "$ROOT" && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
START="$SCRIPT_DIR/start-review-brief.sh"
GAUNTLET_HOME="${GAUNTLET_HOME:-${AGENT_HOME:-$HOME/.codex/gauntlet}}"
OPEN_MODE="${GAUNTLET_REVIEW_OPEN:-default}"
SENTINEL="$ROOT/.gauntlet-review-brief-started.json"

if [ ! -x "$START" ] && [ -x "$GAUNTLET_HOME/scripts/start-review-brief.sh" ]; then
  START="$GAUNTLET_HOME/scripts/start-review-brief.sh"
fi
if [ ! -x "$START" ]; then
  echo "missing executable start-review-brief.sh" >&2
  exit 1
fi

verify_review_url() {
  local url="$1"
  URL="$url" ROOT="$ROOT" python3 - <<'PY' >/dev/null 2>&1
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

url = os.environ["URL"]
root = Path(os.environ["ROOT"])
parsed = urllib.parse.urlparse(url)
if parsed.scheme != "http" or parsed.path != "/review-brief.html":
    raise SystemExit(1)

pid_file = root / ".gauntlet-review-server.pid"
if not pid_file.exists():
    raise SystemExit(1)
pid = int(pid_file.read_text().strip())
if hasattr(os, "getsid") and os.getsid(pid) == os.getsid(0):
    raise SystemExit(1)

time.sleep(0.4)

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

open_review_url() {
  local url="$1"
  case "$OPEN_MODE" in
    none)
      return 0
      ;;
    default)
      if [ -n "${GAUNTLET_REVIEW_OPEN_COMMAND:-}" ]; then
        "$GAUNTLET_REVIEW_OPEN_COMMAND" "$url"
      elif command -v open >/dev/null 2>&1; then
        open "$url" >/dev/null
      elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" >/dev/null
      else
        echo "no default browser opener found; set GAUNTLET_REVIEW_OPEN=none to skip opening" >&2
        return 1
      fi
      ;;
    chrome)
      if [ -n "${GAUNTLET_REVIEW_OPEN_COMMAND:-}" ]; then
        "$GAUNTLET_REVIEW_OPEN_COMMAND" "$url"
      elif command -v open >/dev/null 2>&1; then
        open -a "Google Chrome" "$url" >/dev/null
      elif command -v google-chrome >/dev/null 2>&1; then
        google-chrome "$url" >/dev/null
      elif command -v chromium >/dev/null 2>&1; then
        chromium "$url" >/dev/null
      else
        echo "no Chrome opener found; set GAUNTLET_REVIEW_OPEN=default or GAUNTLET_REVIEW_OPEN=none" >&2
        return 1
      fi
      ;;
    *)
      echo "invalid GAUNTLET_REVIEW_OPEN mode: $OPEN_MODE" >&2
      echo "expected one of: default, chrome, none" >&2
      return 1
      ;;
  esac
}

write_sentinel() {
  local url="$1"
  URL="$url" ROOT="$ROOT" OPEN_MODE="$OPEN_MODE" SENTINEL="$SENTINEL" python3 - <<'PY'
import datetime
import json
import os
import urllib.parse
from pathlib import Path

root = Path(os.environ["ROOT"])
url = os.environ["URL"]
parsed = urllib.parse.urlparse(url)
data_url = urllib.parse.urlunparse(parsed._replace(path="/review-brief-data.json"))
pid = int((root / ".gauntlet-review-server.pid").read_text().strip())
payload = {
    "schemaVersion": "1.0",
    "startedAt": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "projectRoot": str(root),
    "url": url,
    "dataUrl": data_url,
    "serverPid": pid,
    "serverPort": parsed.port,
    "openMode": os.environ["OPEN_MODE"],
    "opened": os.environ["OPEN_MODE"] != "none",
}
Path(os.environ["SENTINEL"]).write_text(json.dumps(payload, indent=2) + "\n")
PY
}

START_OUTPUT="$("$START" "$ROOT")"
URL="$(printf '%s\n' "$START_OUTPUT" | awk '/^Review brief: http:\/\// { print $3; exit }')"
if [ -z "$URL" ]; then
  echo "review brief starter did not return a usable URL" >&2
  printf '%s\n' "$START_OUTPUT" >&2
  exit 1
fi

if ! verify_review_url "$URL"; then
  echo "review brief URL failed gate verification: $URL" >&2
  exit 1
fi
if ! open_review_url "$URL"; then
  echo "review brief was healthy but could not be opened: $URL" >&2
  exit 1
fi
if ! verify_review_url "$URL"; then
  echo "review brief URL failed post-open verification: $URL" >&2
  exit 1
fi

write_sentinel "$URL"
echo "Review brief: $URL"
