#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${GAUNTLET_INSTALL_TARGET:-codex}"
AGENT_HOME="${AGENT_HOME:-${GAUNTLET_AGENT_HOME:-}}"
SKIP_GIT_HOOKS="${GAUNTLET_SKIP_GIT_HOOKS:-0}"
SKILLS_SRC="$ROOT/skills"
if [ ! -d "$SKILLS_SRC" ] && [ -d "$ROOT/../skills" ]; then
  SKILLS_SRC="$ROOT/../skills"
fi

usage() {
  cat <<'USAGE'
Usage: scripts/install.sh [--target codex|claude] [--agent-home PATH] [--skip-git-hooks]

Targets:
  codex   Install Gauntlet as AGENTS.md under the agent home. Default home: ~/.codex
  claude  Install Gauntlet as a managed import block in CLAUDE.md. Default home: ~/.claude

Environment:
  GAUNTLET_INSTALL_TARGET  codex or claude
  AGENT_HOME              install destination override
  GAUNTLET_AGENT_HOME     install destination override when AGENT_HOME is unset
  GAUNTLET_SKIP_GIT_HOOKS set to 1 to skip this repo's pre-commit hook install
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target)
      if [ "$#" -lt 2 ]; then
        echo "Missing value for --target" >&2
        exit 2
      fi
      TARGET="$2"
      shift 2
      ;;
    --target=*)
      TARGET="${1#--target=}"
      shift
      ;;
    --agent-home)
      if [ "$#" -lt 2 ]; then
        echo "Missing value for --agent-home" >&2
        exit 2
      fi
      AGENT_HOME="$2"
      shift 2
      ;;
    --agent-home=*)
      AGENT_HOME="${1#--agent-home=}"
      shift
      ;;
    --skip-git-hooks)
      SKIP_GIT_HOOKS="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$TARGET" in
  codex|claude)
    ;;
  *)
    echo "Unsupported install target: $TARGET" >&2
    usage >&2
    exit 2
    ;;
esac

if [ -z "$AGENT_HOME" ]; then
  case "$TARGET" in
    codex)
      AGENT_HOME="$HOME/.codex"
      ;;
    claude)
      AGENT_HOME="$HOME/.claude"
      ;;
  esac
fi

AGENT_HOME="$(python3 - "$AGENT_HOME" <<'PY'
import os
import sys

print(os.path.abspath(os.path.expanduser(sys.argv[1])))
PY
)"

MANAGED_BEGIN='<!-- BEGIN GAUNTLET MANAGED BLOCK -->'
MANAGED_END='<!-- END GAUNTLET MANAGED BLOCK -->'

validate_managed_file() {
  local target_file="$1"
  [ -f "$target_file" ] || return 0
  python3 - "$target_file" "$MANAGED_BEGIN" "$MANAGED_END" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
begin = sys.argv[2].encode()
end = sys.argv[3].encode()
data = path.read_bytes()
begin_count = data.count(begin)
end_count = data.count(end)
valid = begin_count == end_count and begin_count <= 1
if begin_count == 1 and end_count == 1:
    begin_at = data.find(begin)
    end_at = data.find(end)
    begin_after = begin_at + len(begin)
    end_after = end_at + len(end)
    begin_is_line = (begin_at == 0 or data[begin_at - 1:begin_at] == b"\n") and (
        begin_after == len(data) or data[begin_after:begin_after + 1] == b"\n" or data[begin_after:begin_after + 2] == b"\r\n"
    )
    end_is_line = (end_at == 0 or data[end_at - 1:end_at] == b"\n") and (
        end_after == len(data) or data[end_after:end_after + 1] == b"\n" or data[end_after:end_after + 2] == b"\r\n"
    )
    valid = valid and begin_at < end_at and begin_is_line and end_is_line
if not valid:
    print(f"Malformed Gauntlet managed block in {path}", file=sys.stderr)
    raise SystemExit(1)
PY
}

write_managed_file() {
  local target_file="$1"
  local block_file="$2"
  local legacy_reference="${3:-}"
  python3 - "$target_file" "$block_file" "$MANAGED_BEGIN" "$MANAGED_END" "$legacy_reference" <<'PY'
from pathlib import Path
import os
import sys
import tempfile

target = Path(sys.argv[1])
block = Path(sys.argv[2]).read_bytes()
begin = sys.argv[3].encode()
end = sys.argv[4].encode()
legacy_reference = Path(sys.argv[5]) if sys.argv[5] else None
data = target.read_bytes() if target.exists() else b""
begin_count = data.count(begin)
end_count = data.count(end)
valid = begin_count == end_count and begin_count <= 1
if begin_count == 1 and end_count == 1:
    begin_at = data.find(begin)
    end_at = data.find(end)
    begin_after = begin_at + len(begin)
    end_after = end_at + len(end)
    begin_is_line = (begin_at == 0 or data[begin_at - 1:begin_at] == b"\n") and (
        begin_after == len(data) or data[begin_after:begin_after + 1] == b"\n" or data[begin_after:begin_after + 2] == b"\r\n"
    )
    end_is_line = (end_at == 0 or data[end_at - 1:end_at] == b"\n") and (
        end_after == len(data) or data[end_after:end_after + 1] == b"\n" or data[end_after:end_after + 2] == b"\r\n"
    )
    valid = valid and begin_at < end_at and begin_is_line and end_is_line
if not valid:
    print(f"Malformed Gauntlet managed block in {target}", file=sys.stderr)
    raise SystemExit(1)
start = data.find(begin)
if start >= 0:
    finish = data.find(end, start) + len(end)
    output = data[:start] + block + data[finish:]
else:
    preserved = data
    if legacy_reference and legacy_reference.is_file():
        legacy = legacy_reference.read_bytes()
        if data == legacy:
            preserved = b""
        else:
            personal_begin = b"<!-- BEGIN PERSONAL HOUSE VOICE -->"
            personal_end = b"<!-- END PERSONAL HOUSE VOICE -->"
            if data.count(personal_begin) == 1 and data.count(personal_end) == 1:
                personal_at = data.find(personal_begin)
                personal_finish = data.find(personal_end, personal_at) + len(personal_end)
                if data[personal_finish:personal_finish + 2] == b"\r\n":
                    personal_finish += 2
                elif data[personal_finish:personal_finish + 1] == b"\n":
                    personal_finish += 1
                personal = data[personal_at:personal_finish]
                first_line_end = legacy.find(b"\n")
                if first_line_end >= 0:
                    expected = legacy[:first_line_end + 1] + b"\n" + personal + legacy[first_line_end + 1:]
                    if data == expected:
                        preserved = personal
    separator = b"" if not preserved else (b"\n" if preserved.endswith(b"\n") else b"\n\n")
    output = preserved + separator + block

if target.exists() and output == data:
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

render_router() {
  local output_file="$1"
  python3 - "$ROOT/router/AGENTS.md" "$output_file" "$AGENT_HOME" <<'PY'
from pathlib import Path
import re
import sys

source = Path(sys.argv[1]).read_text()
output = Path(sys.argv[2])
agent_home = sys.argv[3]
replacements = {
    "{{AGENT_HOME}}": agent_home,
    "{{GAUNTLET_ROOT}}": str(Path(agent_home) / "gauntlet"),
}
rendered = source
for placeholder, value in replacements.items():
    if placeholder not in rendered:
        print(f"Portable router is missing {placeholder}", file=sys.stderr)
        raise SystemExit(1)
    rendered = rendered.replace(placeholder, value)
if "{{" in rendered or "}}" in rendered:
    print("Portable router contains an unresolved install placeholder", file=sys.stderr)
    raise SystemExit(1)
if len(rendered.encode()) >= 32768:
    print("Rendered portable router exceeds the 32 KiB discovery budget", file=sys.stderr)
    raise SystemExit(1)
for line in rendered.splitlines():
    if re.search(r"(?<!/)(?<![A-Za-z0-9_.-])(docs|scripts)/", line):
        print(f"Portable router contains a downstream-relative Gauntlet path: {line}", file=sys.stderr)
        raise SystemExit(1)
output.write_text(rendered)
PY
}

# Reject malformed target state before installing or removing any payload files.
case "$TARGET" in
  codex)
    validate_managed_file "$AGENT_HOME/AGENTS.md"
    ;;
  claude)
    validate_managed_file "$AGENT_HOME/CLAUDE.md"
    ;;
esac

write_claude_adapter() {
  local claude_file="$AGENT_HOME/CLAUDE.md"
  local block_file
  block_file="$(mktemp)"

  {
    printf '%s\n' "$MANAGED_BEGIN"
    printf '@%s/gauntlet/AGENTS.md\n\n' "$AGENT_HOME"
    printf '%s\n\n' '## Gauntlet Adapter For Claude Code'
    printf '%s\n' '- Imported Gauntlet AGENTS.md is the workflow source of truth.'
    printf '%s\n' "- Gauntlet role skill files are installed in ${AGENT_HOME}/skills. When Gauntlet names a role skill, read that skill's SKILL.md before using it."
    printf '%s\n' '- Codex-specific thread, app, or skill actions should be mapped to available Claude Code, Git, or GitHub equivalents when possible.'
    printf '%s' "$MANAGED_END"
  } > "$block_file"

  write_managed_file "$claude_file" "$block_file"
  rm -f "$block_file"
}

write_codex_agents() {
  local codex_file="$AGENT_HOME/AGENTS.md"
  local router_file="$1"
  local legacy_reference="$2"
  local block_file
  block_file="$(mktemp)"

  {
    printf '%s\n' "$MANAGED_BEGIN"
    cat "$router_file"
    printf '%s' "$MANAGED_END"
  } > "$block_file"

  write_managed_file "$codex_file" "$block_file" "$legacy_reference"
  chmod 0644 "$codex_file"
  rm -f "$block_file"
}

rendered_router="$(mktemp)"
legacy_installed_router=""
if [ "$TARGET" = "codex" ] && [ -f "$AGENT_HOME/gauntlet/AGENTS.md" ]; then
  legacy_installed_router="$(mktemp)"
  cp "$AGENT_HOME/gauntlet/AGENTS.md" "$legacy_installed_router"
fi
cleanup_install() {
  rm -f "$rendered_router"
  if [ -n "$legacy_installed_router" ]; then
    rm -f "$legacy_installed_router"
  fi
}
trap cleanup_install EXIT
render_router "$rendered_router"

mkdir -p "$AGENT_HOME/skills" "$AGENT_HOME/gauntlet"
cp "$ROOT/README.md" "$AGENT_HOME/gauntlet/README.md"
cp "$rendered_router" "$AGENT_HOME/gauntlet/AGENTS.md"
chmod 0644 "$AGENT_HOME/gauntlet/AGENTS.md"
rm -rf "$AGENT_HOME/skills/review-brief-builder"
cp -R "$SKILLS_SRC/." "$AGENT_HOME/skills/"
rm -rf "$AGENT_HOME/gauntlet/docs"
cp -R "$ROOT/docs" "$AGENT_HOME/gauntlet/"
cp -R "$ROOT/scripts" "$AGENT_HOME/gauntlet/"
mkdir -p "$AGENT_HOME/gauntlet/evals"
rsync -a --delete \
  --exclude '/generated-prompts/' \
  --exclude '/results/' \
  "$ROOT/evals/" "$AGENT_HOME/gauntlet/evals/"
rm -rf "$AGENT_HOME/gauntlet/templates"
rm -f "$AGENT_HOME/gauntlet/review-brief.html"
rm -f "$AGENT_HOME/gauntlet/review-brief-data.json"
rm -f "$AGENT_HOME/gauntlet/review-brief-data.schema.json"
rm -f "$AGENT_HOME/gauntlet/scripts/serve-notes.sh"
rm -f "$AGENT_HOME/gauntlet/scripts/check-review-brief.py"
rm -f "$AGENT_HOME/gauntlet/scripts/embed-review-brief-data.py"
rm -f "$AGENT_HOME/gauntlet/scripts/init-review-brief.sh"
rm -f "$AGENT_HOME/gauntlet/scripts/require-review-brief-started.sh"
rm -f "$AGENT_HOME/gauntlet/scripts/serve-review-brief.sh"
rm -f "$AGENT_HOME/gauntlet/scripts/start-review-brief.sh"
rm -f "$AGENT_HOME/gauntlet/scripts/validate-review-brief-data.py"

for required_path in \
  "$AGENT_HOME/gauntlet/AGENTS.md" \
  "$AGENT_HOME/gauntlet/docs/workflow-etiquette.md" \
  "$AGENT_HOME/gauntlet/scripts/gauntlet.py" \
  "$AGENT_HOME/gauntlet/scripts/check-subagent-plan.py" \
  "$AGENT_HOME/skills/intake/SKILL.md" \
  "$AGENT_HOME/skills/planner/SKILL.md" \
  "$AGENT_HOME/skills/implementer/SKILL.md"
do
  if [ ! -s "$required_path" ]; then
    echo "Gauntlet install payload is incomplete: $required_path" >&2
    exit 1
  fi
done

# Activate the router only after the installed payload is complete.
case "$TARGET" in
  codex)
    write_codex_agents "$rendered_router" "$legacy_installed_router"
    ;;
  claude)
    write_claude_adapter
    ;;
esac

if [ "$SKIP_GIT_HOOKS" != "1" ] && [ -d "$ROOT/.git" ]; then
  "$ROOT/scripts/install-git-hooks.sh" --repo "$ROOT" --gauntlet-root "$ROOT" >/dev/null
fi

echo "Installed Gauntlet for $TARGET to $AGENT_HOME"
echo "Restart or reload your coding agent to pick up the new workflow."
