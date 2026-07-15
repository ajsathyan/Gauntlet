#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${GAUNTLET_INSTALL_TARGET:-codex}"
AGENT_HOME="${AGENT_HOME:-${GAUNTLET_AGENT_HOME:-}}"
SKIP_GIT_HOOKS="${GAUNTLET_SKIP_GIT_HOOKS:-0}"
INSTRUCTIONS_REVIEWED="${GAUNTLET_INSTRUCTIONS_REVIEWED:-0}"
CODEX_PREFERENCES="${GAUNTLET_CODEX_PREFERENCES:-prompt}"
CHECK_ONLY="${GAUNTLET_INSTALL_CHECK_ONLY:-0}"
RESPONSE_STYLE="${GAUNTLET_RESPONSE_STYLE:-gauntlet}"
SKILLS_SRC="$ROOT/skills"
if [ ! -d "$SKILLS_SRC" ] && [ -d "$ROOT/../skills" ]; then
  SKILLS_SRC="$ROOT/../skills"
fi
AGENTS_SRC="$ROOT/agents/codex"
if [ ! -d "$AGENTS_SRC" ] && [ -d "$ROOT/../agents/codex" ]; then
  AGENTS_SRC="$ROOT/../agents/codex"
fi

usage() {
  cat <<'USAGE'
Usage: scripts/install.sh [--target codex|claude] [--agent-home PATH] [--check] [--instructions-reviewed]
                          [--response-style gauntlet|existing]
                          [--codex-preferences prompt|gauntlet|existing|skip] [--skip-git-hooks]

Targets:
  codex   Install Gauntlet as AGENTS.md under the agent home. Default home: ~/.codex
  claude  Install Gauntlet as a managed import block in CLAUDE.md. Default home: ~/.claude

Environment:
  GAUNTLET_INSTALL_TARGET  codex or claude
  AGENT_HOME              install destination override
  GAUNTLET_AGENT_HOME     install destination override when AGENT_HOME is unset
  GAUNTLET_INSTRUCTIONS_REVIEWED set to 1 after existing instructions were checked for conflicts
  GAUNTLET_CODEX_PREFERENCES prompt, gauntlet, existing, or skip (default: prompt)
  GAUNTLET_INSTALL_CHECK_ONLY set to 1 to run conflict and safety preflight without installing
  GAUNTLET_RESPONSE_STYLE   gauntlet or existing (default: gauntlet)
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
    --instructions-reviewed)
      INSTRUCTIONS_REVIEWED="1"
      shift
      ;;
    --check)
      CHECK_ONLY="1"
      shift
      ;;
    --codex-preferences)
      if [ "$#" -lt 2 ]; then
        echo "Missing value for --codex-preferences" >&2
        exit 2
      fi
      CODEX_PREFERENCES="$2"
      shift 2
      ;;
    --codex-preferences=*)
      CODEX_PREFERENCES="${1#--codex-preferences=}"
      shift
      ;;
    --response-style)
      if [ "$#" -lt 2 ]; then
        echo "Missing value for --response-style" >&2
        exit 2
      fi
      RESPONSE_STYLE="$2"
      shift 2
      ;;
    --response-style=*)
      RESPONSE_STYLE="${1#--response-style=}"
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

case "$INSTRUCTIONS_REVIEWED" in
  0|1)
    ;;
  *)
    echo "GAUNTLET_INSTRUCTIONS_REVIEWED must be 0 or 1" >&2
    exit 2
    ;;
esac

case "$CHECK_ONLY" in
  0|1)
    ;;
  *)
    echo "GAUNTLET_INSTALL_CHECK_ONLY must be 0 or 1" >&2
    exit 2
    ;;
esac

case "$CODEX_PREFERENCES" in
  prompt|gauntlet|existing|skip)
    ;;
  *)
    echo "Unsupported --codex-preferences value: $CODEX_PREFERENCES" >&2
    usage >&2
    exit 2
    ;;
esac

case "$RESPONSE_STYLE" in
  gauntlet|existing)
    ;;
  *)
    echo "Unsupported --response-style value: $RESPONSE_STYLE" >&2
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

require_instruction_review() {
  local target_file="$1"
  local candidate_block="$2"
  local rendered_router="$3"
  local review_state="$AGENT_HOME/gauntlet/install-review-${TARGET}.json"
  python3 - "$target_file" "$candidate_block" "$review_state" "$INSTRUCTIONS_REVIEWED" "$MANAGED_BEGIN" "$MANAGED_END" "$rendered_router" "$ROOT/router/AGENTS.md" "$ROOT/router/response-style.md" <<'PY'
from pathlib import Path
import hashlib
import json
import sys

target = Path(sys.argv[1])
candidate = Path(sys.argv[2]).read_bytes()
state_path = Path(sys.argv[3])
reviewed = sys.argv[4] == "1"
begin = sys.argv[5].encode()
end = sys.argv[6].encode()
effective_candidate = candidate + b"\0" + Path(sys.argv[7]).read_bytes()
data = target.read_bytes() if target.exists() else b""

start = data.find(begin)
if start >= 0:
    finish = data.find(end, start) + len(end)
    user_content = data[:start] + data[finish:]
else:
    user_content = data

if not user_content.strip():
    raise SystemExit(0)

current = {
    "candidateSha256": hashlib.sha256(effective_candidate).hexdigest(),
    "userInstructionsSha256": hashlib.sha256(user_content).hexdigest(),
}
previous = None
if state_path.is_file():
    try:
        previous = json.loads(state_path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        previous = None
if previous == current or reviewed:
    raise SystemExit(0)

print("Existing user instructions require conflict review before Gauntlet can modify this agent home.", file=sys.stderr)
print(f"\nExisting instructions: {target}", file=sys.stderr)
print(f"Gauntlet candidate: {sys.argv[8]} with response style {sys.argv[9]}", file=sys.stderr)
print(
    "\nAn installing agent must compare the two, preserve unrelated user content, and show both conflicting "
    "passages to the user before asking which instruction should remain active. Gauntlet never removes or "
    "rewrites user-owned instructions during this install.",
    file=sys.stderr,
)
print("\nAfter resolving conflicts or confirming compatibility, rerun with --instructions-reviewed.", file=sys.stderr)
print("No files were changed.", file=sys.stderr)
raise SystemExit(3)
PY
}

record_instruction_review() {
  local target_file="$1"
  local candidate_block="$2"
  local rendered_router="$3"
  local review_state="$AGENT_HOME/gauntlet/install-review-${TARGET}.json"
  python3 - "$target_file" "$candidate_block" "$review_state" "$MANAGED_BEGIN" "$MANAGED_END" "$rendered_router" <<'PY'
from pathlib import Path
import hashlib
import json
import os
import sys
import tempfile

target = Path(sys.argv[1])
candidate = Path(sys.argv[2]).read_bytes()
state_path = Path(sys.argv[3])
begin = sys.argv[4].encode()
end = sys.argv[5].encode()
effective_candidate = candidate + b"\0" + Path(sys.argv[6]).read_bytes()
data = target.read_bytes()
start = data.find(begin)
finish = data.find(end, start) + len(end)
user_content = data[:start] + data[finish:]
state = {
    "candidateSha256": hashlib.sha256(effective_candidate).hexdigest(),
    "userInstructionsSha256": hashlib.sha256(user_content).hexdigest(),
}
rendered = (json.dumps(state, indent=2, sort_keys=True) + "\n").encode()
if state_path.is_file() and state_path.read_bytes() == rendered:
    raise SystemExit(0)
state_path.parent.mkdir(parents=True, exist_ok=True)
fd, temporary = tempfile.mkstemp(prefix=f".{state_path.name}.", dir=state_path.parent)
try:
    with os.fdopen(fd, "wb") as handle:
        handle.write(rendered)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, 0o644)
    os.replace(temporary, state_path)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
}

manage_codex_preferences() {
  local phase="$1"
  local config_file="$AGENT_HOME/config.toml"
  [ "$CODEX_PREFERENCES" != "skip" ] || return 0

  python3 - "$config_file" "$phase" "$CODEX_PREFERENCES" <<'PY'
from pathlib import Path
import ast
import os
import re
import sys
import tempfile

target = Path(sys.argv[1])
phase = sys.argv[2]
choice = sys.argv[3]
desired_top = {"model_verbosity": "low", "personality": "none"}
desired_max_threads = 24
data = target.read_bytes() if target.exists() else b""
try:
    text = data.decode("utf-8")
except UnicodeDecodeError:
    print(f"Cannot safely update non-UTF-8 Codex config: {target}", file=sys.stderr)
    raise SystemExit(1)

lines = text.splitlines(keepends=True)
table_at = len(lines)
for index, line in enumerate(lines):
    stripped = line.lstrip()
    if stripped.startswith("["):
        table_at = index
        break

assignment = re.compile(
    r"^(?P<indent>[ \t]*)(?P<key>model_verbosity|personality)(?P<separator>[ \t]*=[ \t]*)"
    r"(?P<value>\"(?:\\.|[^\"])*\"|'[^']*')(?P<suffix>[ \t]*(?:#.*)?)(?P<newline>\r?\n)?$"
)
found = {}
for index, line in enumerate(lines[:table_at]):
    stripped = line.lstrip()
    if not re.match(r"^(model_verbosity|personality)[ \t]*=", stripped):
        continue
    match = assignment.match(line)
    if not match:
        print(f"Cannot safely update unsupported Codex preference syntax at {target}:{index + 1}", file=sys.stderr)
        raise SystemExit(1)
    key = match.group("key")
    if key in found:
        print(f"Cannot safely update duplicate top-level Codex preference {key} in {target}", file=sys.stderr)
        raise SystemExit(1)
    try:
        value = ast.literal_eval(match.group("value"))
    except (SyntaxError, ValueError):
        print(f"Cannot safely parse Codex preference {key} at {target}:{index + 1}", file=sys.stderr)
        raise SystemExit(1)
    if not isinstance(value, str):
        print(f"Codex preference {key} must be a string at {target}:{index + 1}", file=sys.stderr)
        raise SystemExit(1)
    found[key] = (index, value, match)

agents_header = re.compile(r"^[ \t]*\[agents\][ \t]*(?:#.*)?(?:\r?\n)?$")
agent_headers = [index for index, line in enumerate(lines) if agents_header.match(line)]
if len(agent_headers) > 1:
    print(f"Cannot safely update duplicate [agents] tables in {target}", file=sys.stderr)
    raise SystemExit(1)
for index, line in enumerate(lines[:table_at]):
    if re.match(r"^[ \t]*agents(?:[ \t]*=|\.)", line):
        print(f"Cannot safely update unsupported top-level agents syntax at {target}:{index + 1}", file=sys.stderr)
        raise SystemExit(1)

agent_table = None
agent_found = None
agent_assignment = re.compile(
    r"^(?P<indent>[ \t]*)(?P<key>max_threads)(?P<separator>[ \t]*=[ \t]*)"
    r"(?P<value>[+]?[0-9](?:_?[0-9])*)(?P<suffix>[ \t]*(?:#.*)?)(?P<newline>\r?\n)?$"
)
if agent_headers:
    header_at = agent_headers[0]
    table_end = len(lines)
    for index in range(header_at + 1, len(lines)):
        if lines[index].lstrip().startswith("["):
            table_end = index
            break
    agent_table = (header_at, table_end)
    for index in range(header_at + 1, table_end):
        stripped = lines[index].lstrip()
        if not re.match(r"^max_threads[ \t]*=", stripped):
            continue
        match = agent_assignment.match(lines[index])
        if not match:
            print(f"Cannot safely update unsupported agents.max_threads syntax at {target}:{index + 1}", file=sys.stderr)
            raise SystemExit(1)
        if agent_found is not None:
            print(f"Cannot safely update duplicate agents.max_threads in {target}", file=sys.stderr)
            raise SystemExit(1)
        agent_found = (index, int(match.group("value").replace("_", "")), match)

conflicts = {
    key: value for key, (_, value, _) in found.items() if value != desired_top[key]
}
agent_conflict = agent_found is not None and agent_found[1] != desired_max_threads
if phase == "check":
    if (conflicts or agent_conflict) and choice == "prompt":
        print("Codex preference conflict requires a user choice before Gauntlet can install.", file=sys.stderr)
        for key, current in conflicts.items():
            print(f'Existing: {key} = "{current}"', file=sys.stderr)
            print(f'Gauntlet: {key} = "{desired_top[key]}"', file=sys.stderr)
        if agent_conflict:
            print(f"Existing: agents.max_threads = {agent_found[1]}", file=sys.stderr)
            print(f"Gauntlet: agents.max_threads = {desired_max_threads}", file=sys.stderr)
        print("Rerun with --codex-preferences gauntlet to use Gauntlet defaults,", file=sys.stderr)
        print("or --codex-preferences existing to preserve the existing values.", file=sys.stderr)
        print("Use --codex-preferences skip to leave config.toml entirely unchanged.", file=sys.stderr)
        print("No files were changed.", file=sys.stderr)
        raise SystemExit(3)
    raise SystemExit(0)

if phase != "apply":
    print(f"Unsupported Codex preference phase: {phase}", file=sys.stderr)
    raise SystemExit(2)

output = list(lines)
if choice in {"prompt", "gauntlet"}:
    for key, (index, value, match) in found.items():
        if value == desired_top[key]:
            continue
        newline = match.group("newline") or ""
        output[index] = (
            f'{match.group("indent")}{key}{match.group("separator")}"{desired_top[key]}"'
            f'{match.group("suffix")}{newline}'
        )
    if agent_found is not None and agent_found[1] != desired_max_threads:
        index, _, match = agent_found
        newline = match.group("newline") or ""
        output[index] = (
            f'{match.group("indent")}max_threads{match.group("separator")}{desired_max_threads}'
            f'{match.group("suffix")}{newline}'
        )

newline_style = "\r\n" if any(line.endswith("\r\n") for line in lines) else "\n"
if agent_found is None:
    if agent_table is not None:
        agent_header_at, agent_table_end = agent_table
        agent_insert_at = agent_table_end
        while agent_insert_at > agent_header_at + 1 and not output[agent_insert_at - 1].strip():
            agent_insert_at -= 1
        if agent_insert_at > 0 and output[agent_insert_at - 1] and not output[agent_insert_at - 1].endswith(("\n", "\r")):
            output[agent_insert_at - 1] += newline_style
        output[agent_insert_at:agent_insert_at] = [f"max_threads = {desired_max_threads}{newline_style}"]
    else:
        if output and output[-1] and not output[-1].endswith(("\n", "\r")):
            output[-1] += newline_style
        if output and output[-1].strip():
            output.append(newline_style)
        output.extend([
            f"[agents]{newline_style}",
            f"max_threads = {desired_max_threads}{newline_style}",
        ])

missing = [key for key in desired_top if key not in found]
if missing:
    insertion = [f'{key} = "{desired_top[key]}"{newline_style}' for key in missing]
    if table_at > 0 and output[table_at - 1] and not output[table_at - 1].endswith(("\n", "\r")):
        output[table_at - 1] += newline_style
    if table_at < len(output) and table_at > 0 and output[table_at - 1].strip():
        insertion.insert(0, newline_style)
    if table_at < len(output) and output[table_at].strip():
        insertion.append(newline_style)
    output[table_at:table_at] = insertion

rendered = "".join(output).encode("utf-8")
if rendered == data:
    raise SystemExit(0)

write_target = target.resolve() if target.is_symlink() else target
write_target.parent.mkdir(parents=True, exist_ok=True)
mode = write_target.stat().st_mode & 0o777 if write_target.exists() else 0o644
fd, temporary = tempfile.mkstemp(prefix=f".{write_target.name}.", dir=write_target.parent)
try:
    with os.fdopen(fd, "wb") as handle:
        handle.write(rendered)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, mode)
    os.replace(temporary, write_target)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
}

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
write_target = target.resolve() if target.is_symlink() else target
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

write_target.parent.mkdir(parents=True, exist_ok=True)
mode = write_target.stat().st_mode & 0o777 if write_target.exists() else 0o644
fd, temporary = tempfile.mkstemp(prefix=f".{write_target.name}.", dir=write_target.parent)
try:
    with os.fdopen(fd, "wb") as handle:
        handle.write(output)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, mode)
    os.replace(temporary, write_target)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
}

render_router() {
  local output_file="$1"
  python3 - "$ROOT/router/AGENTS.md" "$ROOT/router/response-style.md" "$output_file" "$AGENT_HOME" "$RESPONSE_STYLE" <<'PY'
from pathlib import Path
import re
import sys

source = Path(sys.argv[1]).read_text()
response_style = Path(sys.argv[2]).read_text().strip()
output = Path(sys.argv[3])
agent_home = sys.argv[4]
response_choice = sys.argv[5]
replacements = {
    "{{AGENT_HOME}}": agent_home,
    "{{GAUNTLET_ROOT}}": str(Path(agent_home) / "gauntlet"),
    "{{RESPONSE_STYLE}}": response_style if response_choice == "gauntlet" else "",
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

render_claude_adapter_block() {
  local block_file="$1"
  {
    printf '%s\n' "$MANAGED_BEGIN"
    printf '@%s/gauntlet/AGENTS.md\n\n' "$AGENT_HOME"
    printf '%s\n\n' '## Gauntlet Adapter For Claude Code'
    printf '%s\n' '- Imported Gauntlet AGENTS.md is the workflow source of truth.'
    printf '%s\n' "- Gauntlet role skill files are installed in ${AGENT_HOME}/skills. When Gauntlet names a role skill, read that skill's SKILL.md before using it."
    printf '%s\n' '- Codex-specific thread, app, or skill actions should be mapped to available Claude Code, Git, or GitHub equivalents when possible.'
    printf '%s' "$MANAGED_END"
  } > "$block_file"
}

render_codex_agents_block() {
  local block_file="$1"
  local router_file="$2"
  {
    printf '%s\n' "$MANAGED_BEGIN"
    cat "$router_file"
    printf '%s' "$MANAGED_END"
  } > "$block_file"
}

rendered_router="$(mktemp)"
candidate_block="$(mktemp)"
instruction_review_log="$(mktemp)"
codex_preference_log="$(mktemp)"
legacy_installed_router=""
if [ "$TARGET" = "codex" ] && [ -f "$AGENT_HOME/gauntlet/AGENTS.md" ]; then
  legacy_installed_router="$(mktemp)"
  cp "$AGENT_HOME/gauntlet/AGENTS.md" "$legacy_installed_router"
fi
cleanup_install() {
  rm -f "$rendered_router" "$candidate_block" "$instruction_review_log" "$codex_preference_log"
  if [ -n "$legacy_installed_router" ]; then
    rm -f "$legacy_installed_router"
  fi
}
trap cleanup_install EXIT
render_router "$rendered_router"

case "$TARGET" in
  codex)
    render_codex_agents_block "$candidate_block" "$rendered_router"
    ;;
  claude)
    render_claude_adapter_block "$candidate_block"
    ;;
esac

set +e
case "$TARGET" in
  codex)
    require_instruction_review "$AGENT_HOME/AGENTS.md" "$candidate_block" "$rendered_router" 2>"$instruction_review_log"
    instruction_review_status=$?
    manage_codex_preferences check 2>"$codex_preference_log"
    codex_preference_status=$?
    ;;
  claude)
    require_instruction_review "$AGENT_HOME/CLAUDE.md" "$candidate_block" "$rendered_router" 2>"$instruction_review_log"
    instruction_review_status=$?
    codex_preference_status=0
    ;;
esac
set -e

if [ "$TARGET" = "codex" ]; then
  python3 "$ROOT/scripts/install-codex-agents.py" check \
    --source "$AGENTS_SRC" --agent-home "$AGENT_HOME"
fi

if [ "$instruction_review_status" -ne 0 ] || [ "$codex_preference_status" -ne 0 ]; then
  cat "$instruction_review_log" "$codex_preference_log" >&2
  if [ "$instruction_review_status" -eq 1 ] || [ "$codex_preference_status" -eq 1 ]; then
    exit 1
  fi
  exit 3
fi

if [ "$CHECK_ONLY" = "1" ]; then
  exit 0
fi

mkdir -p "$AGENT_HOME/skills" "$AGENT_HOME/gauntlet"
source_is_installed_payload="$(python3 - "$ROOT" "$AGENT_HOME/gauntlet" <<'PY'
import os
import sys

print("1" if os.path.realpath(sys.argv[1]) == os.path.realpath(sys.argv[2]) else "0")
PY
)"

if [ "$source_is_installed_payload" != "1" ]; then
  cp "$ROOT/README.md" "$AGENT_HOME/gauntlet/README.md"
  mkdir -p "$AGENT_HOME/gauntlet/router"
  cp -R "$ROOT/router/." "$AGENT_HOME/gauntlet/router/"
  rm -rf \
    "$AGENT_HOME/skills/review-brief-builder" \
    "$AGENT_HOME/skills/build-review-interface" \
    "$AGENT_HOME/skills/error-analysis" \
    "$AGENT_HOME/skills/evaluate-rag" \
    "$AGENT_HOME/skills/generate-synthetic-data" \
    "$AGENT_HOME/skills/validate-evaluator" \
    "$AGENT_HOME/skills/write-judge-prompt"
  cp -R "$SKILLS_SRC/." "$AGENT_HOME/skills/"
  rm -rf "$AGENT_HOME/gauntlet/docs"
  cp -R "$ROOT/docs" "$AGENT_HOME/gauntlet/"
  rm -rf "$AGENT_HOME/gauntlet/scripts"
  cp -R "$ROOT/scripts" "$AGENT_HOME/gauntlet/"
  rm -rf "$AGENT_HOME/gauntlet/templates"
  cp -R "$ROOT/templates" "$AGENT_HOME/gauntlet/"
  rm -rf "$AGENT_HOME/gauntlet/agents"
  mkdir -p "$AGENT_HOME/gauntlet/agents"
  cp -R "$ROOT/agents/codex" "$AGENT_HOME/gauntlet/agents/"
  mkdir -p "$AGENT_HOME/gauntlet/evals"
  rsync -a --delete \
    --exclude '/generated-prompts/' \
    --exclude '/results/' \
    "$ROOT/evals/" "$AGENT_HOME/gauntlet/evals/"
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
fi

# Retire payloads removed by the single-Epic cutover even when the installer is
# running from the already-installed Gauntlet directory.
rm -f "$AGENT_HOME/gauntlet/templates/local-docs/IMPLEMENTATION_PLAN.md.tmpl"

cp "$rendered_router" "$AGENT_HOME/gauntlet/AGENTS.md"
chmod 0644 "$AGENT_HOME/gauntlet/AGENTS.md"

for required_path in \
  "$AGENT_HOME/gauntlet/AGENTS.md" \
  "$AGENT_HOME/gauntlet/docs/workflow-etiquette.md" \
  "$AGENT_HOME/gauntlet/docs/workflow-speedups.md" \
  "$AGENT_HOME/gauntlet/docs/local-documentation.md" \
  "$AGENT_HOME/gauntlet/docs/prd-execution.md" \
  "$AGENT_HOME/gauntlet/docs/generated-context.md" \
  "$AGENT_HOME/gauntlet/docs/evaluation-tasks.md" \
  "$AGENT_HOME/gauntlet/docs/evaluation-protocol.md" \
  "$AGENT_HOME/gauntlet/docs/evaluation-harnesses.md" \
  "$AGENT_HOME/gauntlet/scripts/gauntlet.py" \
  "$AGENT_HOME/gauntlet/scripts/prd-run.py" \
  "$AGENT_HOME/gauntlet/scripts/generated_context.py" \
  "$AGENT_HOME/gauntlet/scripts/eval-task.py" \
  "$AGENT_HOME/gauntlet/scripts/eval-run.py" \
  "$AGENT_HOME/gauntlet/scripts/eval-harness.py" \
  "$AGENT_HOME/gauntlet/scripts/install-codex-agents.py" \
  "$AGENT_HOME/gauntlet/scripts/subagent-audit.py" \
  "$AGENT_HOME/gauntlet/scripts/route-codex-agent.py" \
  "$AGENT_HOME/gauntlet/templates/epic-execution-copy.json" \
  "$AGENT_HOME/gauntlet/templates/local-docs/doc_org.md.tmpl" \
  "$AGENT_HOME/gauntlet/templates/local-docs/EPIC_SECTION.md.tmpl" \
  "$AGENT_HOME/gauntlet/templates/generated-context/implementation-v1.md" \
  "$AGENT_HOME/gauntlet/templates/evaluation/core-slots.json" \
  "$AGENT_HOME/gauntlet/templates/evaluation/core-registry.json" \
  "$AGENT_HOME/gauntlet/templates/evaluation/harnesses/trusted-tasks.json" \
  "$AGENT_HOME/gauntlet/templates/evaluation/harnesses/adapter-registry.json.tmpl" \
  "$AGENT_HOME/gauntlet/templates/evaluation/harnesses/codex-cli.json.tmpl" \
  "$AGENT_HOME/gauntlet/templates/evaluation/harnesses/claude-code.json.tmpl" \
  "$AGENT_HOME/skills/intake/SKILL.md" \
  "$AGENT_HOME/skills/planner/SKILL.md" \
  "$AGENT_HOME/skills/implementer/SKILL.md" \
  "$AGENT_HOME/skills/maintain-prd/SKILL.md" \
  "$AGENT_HOME/skills/implement-prd/SKILL.md"
do
  if [ ! -s "$required_path" ]; then
    echo "Gauntlet install payload is incomplete: $required_path" >&2
    exit 1
  fi
done

if [ -e "$AGENT_HOME/gauntlet/templates/local-docs/IMPLEMENTATION_PLAN.md.tmpl" ]; then
  echo "Gauntlet install retained retired implementation-plan template" >&2
  exit 1
fi

if [ "$TARGET" = "codex" ]; then
  python3 "$ROOT/scripts/install-codex-agents.py" apply \
    --source "$AGENTS_SRC" --agent-home "$AGENT_HOME"
  python3 "$ROOT/scripts/install-codex-agents.py" verify \
    --source "$AGENTS_SRC" --agent-home "$AGENT_HOME"
fi

# Activate the router only after the installed payload is complete.
case "$TARGET" in
  codex)
    manage_codex_preferences apply
    write_managed_file "$AGENT_HOME/AGENTS.md" "$candidate_block" "$legacy_installed_router"
    record_instruction_review "$AGENT_HOME/AGENTS.md" "$candidate_block" "$rendered_router"
    ;;
  claude)
    write_managed_file "$AGENT_HOME/CLAUDE.md" "$candidate_block"
    record_instruction_review "$AGENT_HOME/CLAUDE.md" "$candidate_block" "$rendered_router"
    ;;
esac

if [ "$SKIP_GIT_HOOKS" != "1" ] && [ -d "$ROOT/.git" ]; then
  "$ROOT/scripts/install-git-hooks.sh" --repo "$ROOT" --gauntlet-root "$ROOT" >/dev/null
fi

echo "Installed Gauntlet for $TARGET to $AGENT_HOME"
echo "Restart or reload your coding agent to pick up the new workflow."
