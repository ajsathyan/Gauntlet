#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$PWD}"
ROOT="$(cd "$ROOT" && pwd)"
NOTES="$ROOT/implementation-notes.html"
START_PORT="${GAUNTLET_NOTES_PORT:-8765}"
PID_FILE="$ROOT/.gauntlet-notes-server.pid"
PORT_FILE="$ROOT/.gauntlet-notes-server.port"
LOG_FILE="$ROOT/.gauntlet-notes-server.log"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GAUNTLET_HOME="${GAUNTLET_HOME:-${AGENT_HOME:-$HOME/.codex/gauntlet}}"

url_responds() {
  local port="$1"
  PORT="$port" python3 - <<'PY' >/dev/null 2>&1
import http.client
import os

conn = http.client.HTTPConnection("127.0.0.1", int(os.environ["PORT"]), timeout=0.4)
try:
    conn.request("GET", "/implementation-notes.html")
    response = conn.getresponse()
    raise SystemExit(0 if response.status < 500 else 1)
except Exception:
    raise SystemExit(1)
finally:
    conn.close()
PY
}

TEMPLATE="$SCRIPT_DIR/../templates/implementation-notes.html"
if [ ! -f "$TEMPLATE" ] && [ -f "$GAUNTLET_HOME/templates/implementation-notes.html" ]; then
  TEMPLATE="$GAUNTLET_HOME/templates/implementation-notes.html"
fi

if [ ! -f "$NOTES" ]; then
  if [ -f "$TEMPLATE" ]; then
    cp "$TEMPLATE" "$NOTES"
  else
    printf '%s\n' '<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="3"><title>Implementation Notes</title><h1>Implementation Notes</h1>' > "$NOTES"
  fi
fi

if [ -f "$PID_FILE" ] && [ -f "$PORT_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  PORT="$(cat "$PORT_FILE")"
  if url_responds "$PORT"; then
    echo "http://127.0.0.1:$PORT/implementation-notes.html"
    exit 0
  fi
  rm -f "$PID_FILE" "$PORT_FILE"
fi

if [ -f "$PORT_FILE" ]; then
  PORT="$(cat "$PORT_FILE")"
  if url_responds "$PORT"; then
    rm -f "$PID_FILE"
    printf '%s\n' "$PORT" > "$PORT_FILE"
    echo "http://127.0.0.1:$PORT/implementation-notes.html"
    exit 0
  fi
fi

if [ -f "$PID_FILE" ]; then
  rm -f "$PID_FILE"
fi
rm -f "$PORT_FILE"

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
    raise SystemExit("No available port in 8765-8999")
PY
)"

nohup python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$ROOT" > "$LOG_FILE" 2>&1 &
PID="$!"
printf '%s\n' "$PID" > "$PID_FILE"
printf '%s\n' "$PORT" > "$PORT_FILE"
sleep 0.2

if ! url_responds "$PORT"; then
  rm -f "$PID_FILE" "$PORT_FILE"
  echo "failed to start notes server; see $LOG_FILE" >&2
  exit 1
fi

echo "http://127.0.0.1:$PORT/implementation-notes.html"
