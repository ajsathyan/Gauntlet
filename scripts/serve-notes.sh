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

TEMPLATE="$SCRIPT_DIR/../templates/implementation-notes.html"
if [ ! -f "$TEMPLATE" ] && [ -f "$HOME/.codex/gauntlet/templates/implementation-notes.html" ]; then
  TEMPLATE="$HOME/.codex/gauntlet/templates/implementation-notes.html"
fi

if [ ! -f "$NOTES" ]; then
  if [ -f "$TEMPLATE" ]; then
    cp "$TEMPLATE" "$NOTES"
  else
    printf '%s\n' '<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="3"><title>Implementation Notes</title><h1>Implementation Notes</h1>' > "$NOTES"
  fi
fi

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  PORT="$(cat "$PORT_FILE")"
  echo "http://127.0.0.1:$PORT/implementation-notes.html"
  exit 0
fi

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

echo "http://127.0.0.1:$PORT/implementation-notes.html"
