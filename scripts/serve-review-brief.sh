#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$PWD}"
ROOT="$(cd "$ROOT" && pwd)"
BRIEF="$ROOT/review-brief.html"
DATA="$ROOT/review-brief-data.json"
HOST="${GAUNTLET_REVIEW_HOST:-127.0.0.1}"
START_PORT="${GAUNTLET_REVIEW_PORT:-0}"
PORT_MAX="${GAUNTLET_REVIEW_PORT_MAX:-8999}"
PID_FILE="$ROOT/.gauntlet-review-server.pid"
PORT_FILE="$ROOT/.gauntlet-review-server.port"
LOG_FILE="$ROOT/.gauntlet-review-server.log"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GAUNTLET_HOME="${GAUNTLET_HOME:-${AGENT_HOME:-$HOME/.codex/gauntlet}}"
REFRESH_TEMPLATE="${GAUNTLET_REVIEW_REFRESH_TEMPLATE:-0}"

server_matches_project() {
  local port="$1"
  HOST="$HOST" PORT="$port" ROOT="$ROOT" python3 - <<'PY' >/dev/null 2>&1
import hashlib
import http.client
import json
import os
from pathlib import Path

host = os.environ["HOST"]
port = int(os.environ["PORT"])
root = Path(os.environ["ROOT"])

def fetch(path):
    conn = http.client.HTTPConnection(host, port, timeout=0.8)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        body = response.read()
        if response.status != 200:
            raise RuntimeError(f"{path} returned HTTP {response.status}")
        return body
    finally:
        conn.close()

html = fetch("/review-brief.html")
data = fetch("/review-brief-data.json")
local_html = (root / "review-brief.html").read_bytes()
local_data = (root / "review-brief-data.json").read_bytes()
if hashlib.sha256(html).digest() != hashlib.sha256(local_html).digest():
    raise SystemExit(1)
if hashlib.sha256(data).digest() != hashlib.sha256(local_data).digest():
    raise SystemExit(1)
parsed = json.loads(data)
if parsed.get("schemaVersion") != "1.0":
    raise SystemExit(1)
PY
}

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
copy_if_missing_or_refresh "$SCHEMA" "$ROOT/review-brief-data.schema.json"

if [ ! -f "$DATA" ]; then
  echo "review-brief-data.json is missing. Generate real review data before serving the brief." >&2
  echo "For a new live review surface, run scripts/init-review-brief.sh from the project root." >&2
  echo "For local template testing only, copy templates/review-brief-data.example.json manually." >&2
  exit 1
fi
if [ ! -f "$VALIDATOR" ]; then
  echo "missing validate-review-brief-data.py" >&2
  exit 1
fi
if [ ! -f "$EMBEDDER" ]; then
  echo "missing embed-review-brief-data.py" >&2
  exit 1
fi
python3 "$VALIDATOR" "$DATA" >/dev/null
python3 "$EMBEDDER" "$ROOT" >/dev/null

if [ -f "$PID_FILE" ] && [ -f "$PORT_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  PORT="$(cat "$PORT_FILE")"
  if server_matches_project "$PORT"; then
    echo "http://$HOST:$PORT/review-brief.html"
    exit 0
  fi
  rm -f "$PID_FILE" "$PORT_FILE"
fi

rm -f "$PID_FILE" "$PORT_FILE"

PORT="$(HOST="$HOST" START_PORT="$START_PORT" PORT_MAX="$PORT_MAX" python3 - <<'PY'
import os
import socket

host = os.environ["HOST"]
port = int(os.environ["START_PORT"])
port_max = int(os.environ["PORT_MAX"])
if port == 0:
    sock = socket.socket()
    try:
        sock.bind((host, 0))
        print(sock.getsockname()[1])
    finally:
        sock.close()
    raise SystemExit(0)

while port <= port_max:
    sock = socket.socket()
    try:
        sock.bind((host, port))
    except OSError:
        port += 1
    else:
        print(port)
        break
    finally:
        sock.close()
else:
    raise SystemExit(f"No available port in {os.environ['START_PORT']}-{os.environ['PORT_MAX']}")
PY
)"

PID="$(HOST="$HOST" PORT="$PORT" ROOT="$ROOT" LOG_FILE="$LOG_FILE" python3 - <<'PY'
import os
import subprocess
import sys

host = os.environ["HOST"]
port = os.environ["PORT"]
root = os.environ["ROOT"]
log_file = os.environ["LOG_FILE"]

log = open(log_file, "ab", buffering=0)
process = subprocess.Popen(
    [sys.executable, "-m", "http.server", port, "--bind", host, "--directory", root],
    stdin=subprocess.DEVNULL,
    stdout=log,
    stderr=subprocess.STDOUT,
    close_fds=True,
    start_new_session=True,
)
print(process.pid)
PY
)"
printf '%s\n' "$PID" > "$PID_FILE"
printf '%s\n' "$PORT" > "$PORT_FILE"

for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  if server_matches_project "$PORT"; then
    echo "http://$HOST:$PORT/review-brief.html"
    exit 0
  fi
  sleep 0.1
done

rm -f "$PID_FILE" "$PORT_FILE"
echo "failed to start healthy review brief server; see $LOG_FILE" >&2
exit 1
