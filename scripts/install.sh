#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="codex"
AGENT_HOME="${AGENT_HOME:-${GAUNTLET_AGENT_HOME:-}}"
CHECK_ONLY=0
UNINSTALL=0
INSTRUCTIONS_REVIEWED=0
RESPONSE_STYLE="gauntlet"
SKIP_GIT_HOOKS=0

usage() {
  cat <<'USAGE'
Usage: scripts/install.sh [--target codex] [--agent-home PATH] [--check]
                          [--instructions-reviewed]
                          [--response-style gauntlet|existing] [--skip-git-hooks]
       scripts/install.sh [--target codex] [--agent-home PATH] --uninstall
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --target=*) TARGET="${1#--target=}"; shift ;;
    --agent-home) AGENT_HOME="$2"; shift 2 ;;
    --agent-home=*) AGENT_HOME="${1#--agent-home=}"; shift ;;
    --check) CHECK_ONLY=1; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    --instructions-reviewed) INSTRUCTIONS_REVIEWED=1; shift ;;
    --response-style) RESPONSE_STYLE="$2"; shift 2 ;;
    --response-style=*) RESPONSE_STYLE="${1#--response-style=}"; shift ;;
    --skip-git-hooks) SKIP_GIT_HOOKS=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[ "$TARGET" = "codex" ] || { echo "Unsupported install target: $TARGET" >&2; exit 2; }
case "$RESPONSE_STYLE" in gauntlet|existing) ;; *) echo "Unsupported response style" >&2; exit 2 ;; esac
if [ -z "$AGENT_HOME" ]; then AGENT_HOME="$HOME/.codex"; fi
AGENT_HOME="$(python3 -c 'import os,sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))' "$AGENT_HOME")"

BEGIN='<!-- BEGIN GAUNTLET MANAGED BLOCK -->'
END='<!-- END GAUNTLET MANAGED BLOCK -->'
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT
ROUTER="$TEMP_DIR/AGENTS.md"
BLOCK="$TEMP_DIR/block.md"

python3 - "$ROOT/router/AGENTS.md" "$ROOT/router/response-style.md" "$ROUTER" "$AGENT_HOME" "$RESPONSE_STYLE" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1]).read_text(encoding="utf-8")
style = Path(sys.argv[2]).read_text(encoding="utf-8").strip()
agent_home = Path(sys.argv[4])
rendered = source
replacements = {
    "{{AGENT_HOME}}": str(agent_home),
    "{{GAUNTLET_ROOT}}": str(agent_home / "gauntlet"),
    "{{RESPONSE_STYLE}}": style if sys.argv[5] == "gauntlet" else "",
}
for marker, value in replacements.items():
    if marker not in rendered:
        raise SystemExit(f"Portable router is missing {marker}")
    rendered = rendered.replace(marker, value)
if "{{" in rendered or "}}" in rendered:
    raise SystemExit("Portable router contains an unresolved placeholder")
if len(rendered.encode()) >= 32768:
    raise SystemExit("Rendered router exceeds the 32 KiB instruction budget")
Path(sys.argv[3]).write_text(rendered, encoding="utf-8")
PY

{
  printf '%s\n' "$BEGIN"
  cat "$ROUTER"
  printf '%s\n' "$END"
} > "$BLOCK"

validate_agents() {
  python3 - "$1" "$BEGIN" "$END" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit(0)
data = path.read_text(encoding="utf-8")
begin, end = sys.argv[2:]
if data.count(begin) != data.count(end) or data.count(begin) > 1:
    raise SystemExit(f"Malformed Gauntlet managed block in {path}")
if begin in data and data.index(begin) > data.index(end):
    raise SystemExit(f"Malformed Gauntlet managed block in {path}")
PY
}

write_agents() {
  python3 - "$1" "$2" "$BEGIN" "$END" <<'PY'
from pathlib import Path
import os
import sys
import tempfile

target = Path(sys.argv[1])
block = Path(sys.argv[2]).read_bytes()
begin, end = (value.encode() for value in sys.argv[3:])
data = target.read_bytes() if target.exists() else b""
start = data.find(begin)
if start >= 0:
    finish = data.find(end, start) + len(end)
    output = data[:start] + block.rstrip(b"\n") + data[finish:]
else:
    separator = b"" if not data else (b"" if data.endswith(b"\n") else b"\n")
    output = data + separator + block
if output == data:
    raise SystemExit(0)
target.parent.mkdir(parents=True, exist_ok=True)
mode = target.stat().st_mode & 0o777 if target.exists() else 0o644
fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
try:
    with os.fdopen(fd, "wb") as handle:
        handle.write(output)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, mode)
    os.replace(temporary, target)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
}

remove_agents_block() {
  python3 - "$1" "$BEGIN" "$END" <<'PY'
from pathlib import Path
import os
import sys
import tempfile

path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit(0)
data = path.read_bytes()
begin, end = (value.encode() for value in sys.argv[2:])
start = data.find(begin)
if start < 0:
    raise SystemExit(0)
finish = data.find(end, start) + len(end)
output = data[:start] + data[finish:]
mode = path.stat().st_mode & 0o777
fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
try:
    with os.fdopen(fd, "wb") as handle:
        handle.write(output)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, mode)
    os.replace(temporary, path)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
}

validate_agents "$AGENT_HOME/AGENTS.md"

if [ "$UNINSTALL" = "1" ]; then
  [ "$CHECK_ONLY" = "0" ] || { echo "--check cannot be combined with --uninstall" >&2; exit 2; }
  PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}" python3 - "$AGENT_HOME" <<'PY'
from pathlib import Path
import sys
from gauntletlib.install.manifest import preflight_uninstall_payload
preflight_uninstall_payload(Path(sys.argv[1]))
PY
  remove_agents_block "$AGENT_HOME/AGENTS.md"
  PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}" python3 - "$AGENT_HOME" <<'PY'
from pathlib import Path
import sys
from gauntletlib.install.manifest import uninstall_payload
for finding in uninstall_payload(Path(sys.argv[1])):
    print(f"Gauntlet installer finding: {finding}", file=sys.stderr)
PY
  echo "Uninstalled receipt-owned Gauntlet files from $AGENT_HOME"
  exit 0
fi

if [ -f "$AGENT_HOME/AGENTS.md" ] && ! grep -qF "$BEGIN" "$AGENT_HOME/AGENTS.md"    && [ "$INSTRUCTIONS_REVIEWED" = "0" ] && [ -s "$AGENT_HOME/AGENTS.md" ]; then
  echo "Existing user instructions require review before first install." >&2
  echo "Rerun with --instructions-reviewed after confirming compatibility." >&2
  exit 3
fi

PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}" python3 - "$ROOT" "$AGENT_HOME" "$ROUTER" <<'PY'
from pathlib import Path
import sys
from gauntletlib.install.manifest import preflight_generated_payload, preflight_payload

root, home, router = map(Path, sys.argv[1:])
for finding in preflight_payload(root, home):
    print(f"Gauntlet installer finding: {finding}", file=sys.stderr)
preflight_generated_payload(home, "gauntlet/AGENTS.md", router)
PY

if [ "$CHECK_ONLY" = "1" ]; then exit 0; fi

mkdir -p "$AGENT_HOME/gauntlet" "$AGENT_HOME/skills"
PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}" python3 - "$ROOT" "$AGENT_HOME" <<'PY'
from pathlib import Path
import sys
from gauntletlib.install.manifest import sync_payload
for finding in sync_payload(Path(sys.argv[1]), Path(sys.argv[2])):
    print(f"Gauntlet installer finding: {finding}", file=sys.stderr)
PY
cp "$ROUTER" "$AGENT_HOME/gauntlet/AGENTS.md"
chmod 0644 "$AGENT_HOME/gauntlet/AGENTS.md"
PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}" python3 - "$AGENT_HOME" <<'PY'
from pathlib import Path
import sys
from gauntletlib.install.manifest import record_generated_payload
record_generated_payload(Path(sys.argv[1]), "gauntlet/AGENTS.md")
PY
write_agents "$AGENT_HOME/AGENTS.md" "$BLOCK"

python3 "$AGENT_HOME/gauntlet/scripts/gauntlet.py" install verify   --target codex --agent-home "$AGENT_HOME"

if [ "$SKIP_GIT_HOOKS" = "0" ] && [ -d "$ROOT/.git" ]; then
  "$ROOT/scripts/install-git-hooks.sh" --repo "$ROOT" --gauntlet-root "$ROOT" >/dev/null
fi

echo "Installed Gauntlet Lite for Codex to $AGENT_HOME"
echo "Restart or reload Codex to use the new workflow."
