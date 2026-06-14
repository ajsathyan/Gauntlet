#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$PWD}"
ROOT="$(cd "$ROOT" && pwd)"
BRIEF="$ROOT/review-brief.html"
DATA="$ROOT/review-brief-data.json"
START_PORT="${GAUNTLET_REVIEW_PORT:-8770}"
PID_FILE="$ROOT/.gauntlet-review-server.pid"
PORT_FILE="$ROOT/.gauntlet-review-server.port"
LOG_FILE="$ROOT/.gauntlet-review-server.log"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GAUNTLET_HOME="${GAUNTLET_HOME:-${AGENT_HOME:-$HOME/.codex/gauntlet}}"

url_responds() {
  local port="$1"
  PORT="$port" python3 - <<'PY' >/dev/null 2>&1
import http.client
import os

conn = http.client.HTTPConnection("127.0.0.1", int(os.environ["PORT"]), timeout=0.4)
try:
    conn.request("GET", "/review-brief.html")
    response = conn.getresponse()
    raise SystemExit(0 if response.status < 500 else 1)
except Exception:
    raise SystemExit(1)
finally:
    conn.close()
PY
}

copy_if_missing() {
  local source="$1"
  local target="$2"
  if [ ! -f "$target" ] && [ -f "$source" ]; then
    cp "$source" "$target"
  fi
}

TEMPLATE="$SCRIPT_DIR/../templates/review-brief.html"
SCHEMA="$SCRIPT_DIR/../templates/review-brief-data.schema.json"

if [ ! -f "$TEMPLATE" ] && [ -f "$GAUNTLET_HOME/templates/review-brief.html" ]; then
  TEMPLATE="$GAUNTLET_HOME/templates/review-brief.html"
fi
if [ ! -f "$SCHEMA" ] && [ -f "$GAUNTLET_HOME/templates/review-brief-data.schema.json" ]; then
  SCHEMA="$GAUNTLET_HOME/templates/review-brief-data.schema.json"
fi
copy_if_missing "$TEMPLATE" "$BRIEF"
copy_if_missing "$SCHEMA" "$ROOT/review-brief-data.schema.json"

if [ ! -f "$DATA" ]; then
  echo "review-brief-data.json is missing. Generate real review data before serving the brief." >&2
  echo "For a new live review surface, run scripts/init-review-brief.sh from the project root." >&2
  echo "For local template testing only, copy templates/review-brief-data.example.json manually." >&2
  exit 1
fi

if [ -f "$PID_FILE" ] && [ -f "$PORT_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  PORT="$(cat "$PORT_FILE")"
  if url_responds "$PORT"; then
    echo "http://127.0.0.1:$PORT/review-brief.html"
    exit 0
  fi
  rm -f "$PID_FILE" "$PORT_FILE"
fi

rm -f "$PID_FILE" "$PORT_FILE"

PORT="$(START_PORT="$START_PORT" python3 - <<'PY'
import os
import socket

port = int(os.environ["START_PORT"])
while port < 9000:
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        port += 1
    else:
        print(port)
        break
    finally:
        sock.close()
else:
    raise SystemExit("No available port in 8770-8999")
PY
)"

nohup python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$ROOT" > "$LOG_FILE" 2>&1 &
PID="$!"
printf '%s\n' "$PID" > "$PID_FILE"
printf '%s\n' "$PORT" > "$PORT_FILE"
sleep 0.2

if ! url_responds "$PORT"; then
  rm -f "$PID_FILE" "$PORT_FILE"
  echo "failed to start review brief server; see $LOG_FILE" >&2
  exit 1
fi

echo "http://127.0.0.1:$PORT/review-brief.html"
