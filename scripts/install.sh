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
CODEX_BIN_OVERRIDE="${GAUNTLET_CODEX_BIN:-}"
UNINSTALL="0"
CONFIRM_NO_LIVE_CONTROLLER_WORK="0"
CUTOVER_PROJECT_ROOTS=()
SKILLS_SRC="$ROOT/skills"
if [ ! -d "$SKILLS_SRC" ] && [ -d "$ROOT/../skills" ]; then
  SKILLS_SRC="$ROOT/../skills"
fi
usage() {
  cat <<'USAGE'
Usage: scripts/install.sh [--target codex] [--agent-home PATH] [--check] [--instructions-reviewed]
                          [--response-style gauntlet|existing]
                          [--codex-preferences prompt|gauntlet|existing|skip] [--skip-git-hooks]
                          [--cutover-project-root PATH | --confirm-no-live-controller-work]
       scripts/install.sh --target codex [--agent-home PATH] --uninstall

Targets:
  codex   Install Gauntlet as AGENTS.md under the agent home. Default home: ~/.codex

Environment:
  GAUNTLET_INSTALL_TARGET  codex
  AGENT_HOME              install destination override
  GAUNTLET_AGENT_HOME     install destination override when AGENT_HOME is unset
  GAUNTLET_INSTRUCTIONS_REVIEWED set to 1 after existing instructions were checked for conflicts
  GAUNTLET_CODEX_PREFERENCES prompt, gauntlet, existing, or skip (default: prompt)
  GAUNTLET_INSTALL_CHECK_ONLY set to 1 to run conflict and safety preflight without installing
  GAUNTLET_RESPONSE_STYLE   gauntlet or existing (default: gauntlet)
  GAUNTLET_CODEX_BIN       Codex executable override used to install required bundled plugins
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
    --cutover-project-root)
      if [ "$#" -lt 2 ]; then
        echo "Missing value for --cutover-project-root" >&2
        exit 2
      fi
      CUTOVER_PROJECT_ROOTS+=("$2")
      shift 2
      ;;
    --cutover-project-root=*)
      CUTOVER_PROJECT_ROOTS+=("${1#--cutover-project-root=}")
      shift
      ;;
    --confirm-no-live-controller-work)
      CONFIRM_NO_LIVE_CONTROLLER_WORK="1"
      shift
      ;;
    --uninstall)
      UNINSTALL="1"
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
  codex)
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

case "$UNINSTALL" in
  0|1)
    ;;
  *)
    echo "Uninstall mode must be 0 or 1" >&2
    exit 2
    ;;
esac

case "$CONFIRM_NO_LIVE_CONTROLLER_WORK" in
  0|1)
    ;;
  *)
    echo "Cutover confirmation must be 0 or 1" >&2
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
  AGENT_HOME="$HOME/.codex"
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
desired_top = {
    "model_verbosity": "low",
    "personality": "none",
    "model_reasoning_summary": "concise",
}
desired_max_threads = 24
desired_context_usage = True
desired_plugins = ["browser@openai-bundled", "computer-use@openai-bundled"]
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
    r"^(?P<indent>[ \t]*)(?P<key>model_verbosity|personality|model_reasoning_summary)(?P<separator>[ \t]*=[ \t]*)"
    r"(?P<value>\"(?:\\.|[^\"])*\"|'[^']*')(?P<suffix>[ \t]*(?:#.*)?)(?P<newline>\r?\n)?$"
)
found = {}
for index, line in enumerate(lines[:table_at]):
    stripped = line.lstrip()
    if not re.match(r"^(model_verbosity|personality|model_reasoning_summary)[ \t]*=", stripped):
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

def find_table(header, label):
    pattern = re.compile(rf"^[ \t]*{re.escape(header)}[ \t]*(?:#.*)?(?:\r?\n)?$")
    headers = [index for index, line in enumerate(lines) if pattern.match(line)]
    if len(headers) > 1:
        print(f"Cannot safely update duplicate {label} tables in {target}", file=sys.stderr)
        raise SystemExit(1)
    if not headers:
        return None
    header_at = headers[0]
    table_end = len(lines)
    for index in range(header_at + 1, len(lines)):
        if lines[index].lstrip().startswith("["):
            table_end = index
            break
    return (header_at, table_end)

def find_boolean(table, key, label):
    if table is None:
        return None
    assignment = re.compile(
        rf"^(?P<indent>[ \t]*){re.escape(key)}(?P<separator>[ \t]*=[ \t]*)"
        r"(?P<value>true|false)(?P<suffix>[ \t]*(?:#.*)?)(?P<newline>\r?\n)?$"
    )
    found_value = None
    for index in range(table[0] + 1, table[1]):
        stripped = lines[index].lstrip()
        if not re.match(rf"^{re.escape(key)}[ \t]*=", stripped):
            continue
        match = assignment.match(lines[index])
        if not match:
            print(f"Cannot safely update unsupported {label} syntax at {target}:{index + 1}", file=sys.stderr)
            raise SystemExit(1)
        if found_value is not None:
            print(f"Cannot safely update duplicate {label} in {target}", file=sys.stderr)
            raise SystemExit(1)
        found_value = (index, match.group("value") == "true", match)
    return found_value

for index, line in enumerate(lines[:table_at]):
    if re.match(r"^[ \t]*(desktop|plugins)(?:[ \t]*=|\.)", line):
        print(f"Cannot safely update unsupported top-level desktop or plugins syntax at {target}:{index + 1}", file=sys.stderr)
        raise SystemExit(1)

desktop_table = find_table("[desktop]", "[desktop]")
desktop_found = find_boolean(
    desktop_table, "show-context-window-usage", "desktop.show-context-window-usage"
)
plugin_tables = {}
plugin_found = {}
for plugin in desired_plugins:
    header = f'[plugins."{plugin}"]'
    plugin_tables[plugin] = find_table(header, header)
    plugin_found[plugin] = find_boolean(
        plugin_tables[plugin], "enabled", f'plugins."{plugin}".enabled'
    )

conflicts = {
    key: value for key, (_, value, _) in found.items() if value != desired_top[key]
}
agent_conflict = agent_found is not None and agent_found[1] != desired_max_threads
desktop_conflict = desktop_found is not None and desktop_found[1] != desired_context_usage
plugin_conflicts = {
    plugin: value[1]
    for plugin, value in plugin_found.items()
    if value is not None and value[1] is not True
}
if phase == "check":
    if (conflicts or agent_conflict or desktop_conflict or plugin_conflicts) and choice == "prompt":
        print("Codex preference conflict requires a user choice before Gauntlet can install.", file=sys.stderr)
        for key, current in conflicts.items():
            print(f'Existing: {key} = "{current}"', file=sys.stderr)
            print(f'Gauntlet: {key} = "{desired_top[key]}"', file=sys.stderr)
        if agent_conflict:
            print(f"Existing: agents.max_threads = {agent_found[1]}", file=sys.stderr)
            print(f"Gauntlet: agents.max_threads = {desired_max_threads}", file=sys.stderr)
        if desktop_conflict:
            print(f"Existing: desktop.show-context-window-usage = {str(desktop_found[1]).lower()}", file=sys.stderr)
            print("Gauntlet: desktop.show-context-window-usage = true", file=sys.stderr)
        for plugin in plugin_conflicts:
            print(f'Existing: plugins."{plugin}".enabled = false', file=sys.stderr)
            print(f'Gauntlet: plugins."{plugin}".enabled = true', file=sys.stderr)
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
    if desktop_found is not None and desktop_found[1] != desired_context_usage:
        index, _, match = desktop_found
        newline = match.group("newline") or ""
        output[index] = (
            f'{match.group("indent")}show-context-window-usage{match.group("separator")}true'
            f'{match.group("suffix")}{newline}'
        )
    for plugin, value in plugin_found.items():
        if value is None or value[1] is True:
            continue
        index, _, match = value
        newline = match.group("newline") or ""
        output[index] = (
            f'{match.group("indent")}enabled{match.group("separator")}true'
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

def ensure_table_value(header, found_value, rendered_value):
    if found_value is not None:
        return
    pattern = re.compile(rf"^[ \t]*{re.escape(header)}[ \t]*(?:#.*)?(?:\r?\n)?$")
    current_header = next((index for index, line in enumerate(output) if pattern.match(line)), None)
    if current_header is not None:
        insert_at = len(output)
        for index in range(current_header + 1, len(output)):
            if output[index].lstrip().startswith("["):
                insert_at = index
                break
        while insert_at > current_header + 1 and not output[insert_at - 1].strip():
            insert_at -= 1
        if insert_at > 0 and output[insert_at - 1] and not output[insert_at - 1].endswith(("\n", "\r")):
            output[insert_at - 1] += newline_style
        output[insert_at:insert_at] = [f"{rendered_value}{newline_style}"]
        return
    if output and output[-1] and not output[-1].endswith(("\n", "\r")):
        output[-1] += newline_style
    if output and output[-1].strip():
        output.append(newline_style)
    output.extend([f"{header}{newline_style}", f"{rendered_value}{newline_style}"])

ensure_table_value(
    "[desktop]", desktop_found, "show-context-window-usage = true"
)
for plugin in desired_plugins:
    ensure_table_value(
        f'[plugins."{plugin}"]', plugin_found[plugin], "enabled = true"
    )

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

RESOLVED_CODEX_BIN=""

resolve_codex_bin() {
  local candidate=""
  if [ -n "$CODEX_BIN_OVERRIDE" ]; then
    if [ ! -x "$CODEX_BIN_OVERRIDE" ] || ! "$CODEX_BIN_OVERRIDE" plugin add --help >/dev/null 2>&1; then
      echo "GAUNTLET_CODEX_BIN is not an executable Codex CLI with plugin support: $CODEX_BIN_OVERRIDE" >&2
      return 1
    fi
    RESOLVED_CODEX_BIN="$CODEX_BIN_OVERRIDE"
    return 0
  fi

  for candidate in \
    "$AGENT_HOME/plugins/.plugin-appserver/codex" \
    "/Applications/ChatGPT.app/Contents/Resources/codex" \
    "$(command -v codex 2>/dev/null || true)"
  do
    [ -n "$candidate" ] || continue
    if [ -x "$candidate" ] && "$candidate" plugin add --help >/dev/null 2>&1; then
      RESOLVED_CODEX_BIN="$candidate"
      return 0
    fi
  done

  echo "Gauntlet requires a Codex CLI with plugin support to install Browser and Computer Use." >&2
  echo "Set GAUNTLET_CODEX_BIN to a working Codex executable and rerun." >&2
  return 1
}

planned_codex_plugins() {
  [ "$CODEX_PREFERENCES" != "skip" ] || return 0
  python3 - "$AGENT_HOME/config.toml" "$CODEX_PREFERENCES" <<'PY'
from pathlib import Path
import re
import sys

target = Path(sys.argv[1])
choice = sys.argv[2]
plugins = ["browser@openai-bundled", "computer-use@openai-bundled"]
text = target.read_text(encoding="utf-8") if target.exists() else ""
lines = text.splitlines()

for plugin in plugins:
    header = f'[plugins."{plugin}"]'
    header_pattern = re.compile(rf"^[ \t]*{re.escape(header)}[ \t]*(?:#.*)?$")
    header_at = next((i for i, line in enumerate(lines) if header_pattern.match(line)), None)
    enabled = None
    if header_at is not None:
        for line in lines[header_at + 1:]:
            if line.lstrip().startswith("["):
                break
            match = re.match(r"^[ \t]*enabled[ \t]*=[ \t]*(true|false)(?:[ \t]*(?:#.*)?)?$", line)
            if match:
                enabled = match.group(1) == "true"
                break
    if choice != "existing" or enabled is not False:
        print(plugin)
PY
}

preflight_codex_plugins() {
  local planned=()
  local listing=""
  local preflight_home=""
  while IFS= read -r plugin; do
    [ -n "$plugin" ] && planned+=("$plugin")
  done < <(planned_codex_plugins)
  [ "${#planned[@]}" -gt 0 ] || return 0

  resolve_codex_bin
  listing="$(mktemp)"
  preflight_home="$(mktemp -d)"
  if [ -f "$AGENT_HOME/config.toml" ]; then
    python3 - "$AGENT_HOME/config.toml" "$preflight_home/config.toml" <<'PY'
from pathlib import Path
import re
import sys

source = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines(keepends=True)
output = []
capture = False
for line in source:
    stripped = line.lstrip()
    if stripped.startswith("["):
        capture = re.match(r'^\[marketplaces(?:\.|\])', stripped) is not None
    if capture:
        output.append(line)
if output:
    Path(sys.argv[2]).write_text("".join(output), encoding="utf-8")
PY
  fi
  if ! CODEX_HOME="$preflight_home" "$RESOLVED_CODEX_BIN" plugin list --available --json >"$listing"; then
    rm -f "$listing"
    rm -rf "$preflight_home"
    echo "Gauntlet could not inspect Codex plugin availability." >&2
    return 1
  fi
  if ! python3 - "$listing" "${planned[@]}" <<'PY'
import json
from pathlib import Path
import sys

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
rows = []
if isinstance(data, dict):
    rows.extend(data.get("installed", []))
    rows.extend(data.get("available", []))
available = {row.get("pluginId") for row in rows if isinstance(row, dict)}
missing = [plugin for plugin in sys.argv[2:] if plugin not in available]
if missing:
    for plugin in missing:
        print(f"Required Codex plugin is unavailable: {plugin}", file=sys.stderr)
    raise SystemExit(1)
PY
  then
    rm -f "$listing"
    rm -rf "$preflight_home"
    echo "A required Codex plugin is unavailable; no files were changed." >&2
    return 1
  fi
  rm -f "$listing"
  rm -rf "$preflight_home"
}

install_codex_plugins() {
  local plugin=""
  while IFS= read -r plugin; do
    [ -n "$plugin" ] || continue
    CODEX_HOME="$AGENT_HOME" "$RESOLVED_CODEX_BIN" plugin add "$plugin" --json >/dev/null
  done < <(planned_codex_plugins)
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
        if data.count(legacy) == 1:
            preserved = data.replace(legacy, b"", 1)
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

# Remove only exact obsolete runtime logs/state and directories that are empty.
# This is intentionally small: retired subsystems are not part of Lite.
retire_legacy_artifacts() {
  local phase="$1"
  python3 - "$AGENT_HOME" "$phase" <<'PY'
from pathlib import Path
import sys

agent_home = Path(sys.argv[1])
phase = sys.argv[2]
if phase not in {"check", "remove"}:
    raise SystemExit("invalid legacy-artifact cleanup phase")

targets = (
    agent_home / "gauntlet" / "logs" / "subagent-model-requests.jsonl",
    agent_home / "gauntlet" / "logs" / "subagent-quarantine.jsonl",
    agent_home / "gauntlet" / "logs" / "subagents.jsonl",
    agent_home / "gauntlet" / "state" / "routing-circuit.json",
    agent_home / "gauntlet" / "state" / "routing-circuit.json.lock",
    agent_home / "gauntlet" / "state" / "subagent-request-cursors.json",
)
parents = {path.parent for path in targets}
for parent in parents:
    if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
        print(f"Refusing unsafe retired Gauntlet artifact directory: {parent}", file=sys.stderr)
        raise SystemExit(1)
if phase == "check":
    profile_root = agent_home / "agents"
    if profile_root.is_symlink() or (
        profile_root.exists() and not profile_root.is_dir()
    ):
        print(
            f"Refusing unsafe retired profile directory: {profile_root}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    profile_names = (
        "gauntlet_deep_expert_researcher.toml",
        "gauntlet_deep_worker.toml",
        "gauntlet_fast_reader.toml",
        "gauntlet_independent_verifier.toml",
        "gauntlet_release_integrator.toml",
        "gauntlet_security_reviewer.toml",
        "gauntlet_standard_worker.toml",
    )
    blockers = [profile_root / name for name in profile_names if (profile_root / name).exists()]
    blockers.extend(
        path
        for path in (
            agent_home / "gauntlet" / "install-agents-codex.json",
            agent_home / "gauntlet" / "install-agents-codex.pending.json",
        )
        if path.exists()
    )
    tool_root = agent_home / "gauntlet-tools"
    if tool_root.is_symlink() or (tool_root.exists() and not tool_root.is_dir()):
        blockers.append(tool_root)
    elif tool_root.exists() and any(tool_root.iterdir()):
        blockers.append(tool_root)
    if blockers:
        rendered = ", ".join(str(path) for path in blockers)
        print(
            "Gauntlet Lite requires a clean replacement. Use the currently "
            "installed Gauntlet's preservation-safe --uninstall first; "
            f"retired runtime artifacts remain: {rendered}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    raise SystemExit(0)

for path in targets:
    if not path.exists() and not path.is_symlink():
        continue
    if path.is_dir() and not path.is_symlink():
        print(
            f"Gauntlet installer finding: preserved non-file at retired artifact path: {path}",
            file=sys.stderr,
        )
        continue
    path.unlink()

empty_directories = (
    *parents,
    agent_home / "agents",
    agent_home / "gauntlet-tools" / "generations",
    agent_home / "gauntlet-tools" / "preserved-generations",
    agent_home / "gauntlet-tools",
)
for directory in empty_directories:
    if directory.is_symlink():
        continue
    try:
        directory.rmdir()
    except OSError:
        pass
PY
}
# Reject malformed target state before installing or removing any payload files.
validate_managed_file "$AGENT_HOME/AGENTS.md"

if [ "$UNINSTALL" = "1" ]; then
  if [ "$CHECK_ONLY" = "1" ] || [ "${#CUTOVER_PROJECT_ROOTS[@]}" -gt 0 ] || [ "$CONFIRM_NO_LIVE_CONTROLLER_WORK" = "1" ]; then
    echo "--uninstall cannot be combined with install preflight or cutover options" >&2
    exit 2
  fi

  PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}" python3 - "$AGENT_HOME" <<'PY'
from pathlib import Path
import sys

from gauntletlib.install.manifest import preflight_uninstall_payload

preflight_uninstall_payload(Path(sys.argv[1]))
PY
  retire_legacy_artifacts check

  python3 "$ROOT/scripts/install-codex-hooks.py" check-remove \
    --agent-home "$AGENT_HOME" \
    --runtime "$AGENT_HOME/gauntlet/scripts/workflow-mode.py"

  python3 "$ROOT/scripts/install-codex-hooks.py" remove \
    --agent-home "$AGENT_HOME" \
    --runtime "$AGENT_HOME/gauntlet/scripts/workflow-mode.py"
  retire_legacy_artifacts remove

  python3 - "$AGENT_HOME/AGENTS.md" "$MANAGED_BEGIN" "$MANAGED_END" <<'PY'
from pathlib import Path
import os
import sys
import tempfile

path = Path(sys.argv[1])
begin = sys.argv[2].encode()
end = sys.argv[3].encode()
if not path.exists():
    raise SystemExit(0)
data = path.read_bytes()
start = data.find(begin)
if start < 0:
    raise SystemExit(0)
finish = data.find(end, start) + len(end)
output = data[:start] + data[finish:]
write_target = path.resolve() if path.is_symlink() else path
mode = write_target.stat().st_mode & 0o777
descriptor, temporary = tempfile.mkstemp(prefix=f".{write_target.name}.", dir=write_target.parent)
try:
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(output)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, mode)
    os.replace(temporary, write_target)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY

  PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}" python3 - "$AGENT_HOME" <<'PY'
from pathlib import Path
import sys

from gauntletlib.install.manifest import uninstall_payload

for finding in uninstall_payload(Path(sys.argv[1])):
    print(f"Gauntlet installer finding: {finding}", file=sys.stderr)
PY
  echo "Uninstalled receipt-owned Gauntlet files from $AGENT_HOME"
  echo "Codex config preferences and all unowned or modified files were preserved."
  exit 0
fi

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
if [ -f "$AGENT_HOME/gauntlet/AGENTS.md" ]; then
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

render_codex_agents_block "$candidate_block" "$rendered_router"

# Hook validation is part of preflight because a rejected hooks.json must not
# leave a partially updated Gauntlet payload behind.
python3 "$ROOT/scripts/install-codex-hooks.py" check \
  --agent-home "$AGENT_HOME" \
  --runtime "$AGENT_HOME/gauntlet/scripts/workflow-mode.py"
retire_legacy_artifacts check

set +e
require_instruction_review "$AGENT_HOME/AGENTS.md" "$candidate_block" "$rendered_router" 2>"$instruction_review_log"
instruction_review_status=$?
manage_codex_preferences check 2>"$codex_preference_log"
codex_preference_status=$?
set -e

if [ "$instruction_review_status" -ne 0 ] || [ "$codex_preference_status" -ne 0 ]; then
  cat "$instruction_review_log" "$codex_preference_log" >&2
  if [ "$instruction_review_status" -eq 1 ] || [ "$codex_preference_status" -eq 1 ]; then
    exit 1
  fi
  exit 3
fi

cutover_arguments=("$AGENT_HOME" "$CONFIRM_NO_LIVE_CONTROLLER_WORK")
for cutover_root in "${CUTOVER_PROJECT_ROOTS[@]+"${CUTOVER_PROJECT_ROOTS[@]}"}"; do
  cutover_arguments+=("$cutover_root")
done
PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}" python3 - \
  "${cutover_arguments[@]}" <<'PY'
from pathlib import Path
import sys

from gauntletlib.install.manifest import preflight_product_cutover

agent_home = Path(sys.argv[1])
confirmed = sys.argv[2] == "1"
roots = [Path(value) for value in sys.argv[3:]]
try:
    findings = preflight_product_cutover(
        agent_home,
        roots,
        confirmed_no_unscanned_live_work=confirmed,
    )
except ValueError as error:
    print(str(error), file=sys.stderr)
    raise SystemExit(1)
for finding in findings:
    print(f"Gauntlet installer finding: {finding}", file=sys.stderr)
PY

preflight_codex_plugins

PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}" python3 - \
  "$AGENT_HOME" "$rendered_router" "$AGENT_HOME/AGENTS.md" <<'PY'
from pathlib import Path
import sys

from gauntletlib.install.manifest import preflight_generated_payload

try:
    preflight_generated_payload(
        Path(sys.argv[1]),
        "gauntlet/AGENTS.md",
        Path(sys.argv[2]),
        legacy_container=Path(sys.argv[3]),
    )
except ValueError as error:
    print(str(error), file=sys.stderr)
    raise SystemExit(1)
PY

if [ "$CHECK_ONLY" = "1" ]; then
  exit 0
fi

mkdir -p "$AGENT_HOME/skills" "$AGENT_HOME/gauntlet"
PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}" python3 - "$ROOT" "$AGENT_HOME" <<'PY'
from pathlib import Path
import sys

from gauntletlib.install.manifest import sync_payload

for finding in sync_payload(Path(sys.argv[1]), Path(sys.argv[2])):
    print(f"Gauntlet installer finding: {finding}", file=sys.stderr)
PY
retire_legacy_artifacts remove

cp "$rendered_router" "$AGENT_HOME/gauntlet/AGENTS.md"
chmod 0644 "$AGENT_HOME/gauntlet/AGENTS.md"
PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}" python3 - "$AGENT_HOME" <<'PY'
from pathlib import Path
import sys

from gauntletlib.install.manifest import record_generated_payload

record_generated_payload(Path(sys.argv[1]), "gauntlet/AGENTS.md")
PY

python3 "$AGENT_HOME/gauntlet/scripts/install-codex-hooks.py" apply \
  --agent-home "$AGENT_HOME" \
  --runtime "$AGENT_HOME/gauntlet/scripts/workflow-mode.py"

# Activate the router only after the installed payload is complete.
manage_codex_preferences apply
install_codex_plugins
write_managed_file "$AGENT_HOME/AGENTS.md" "$candidate_block" "$legacy_installed_router"
record_instruction_review "$AGENT_HOME/AGENTS.md" "$candidate_block" "$rendered_router"

python3 "$AGENT_HOME/gauntlet/scripts/gauntlet.py" install verify \
  --target "$TARGET" --agent-home "$AGENT_HOME"

if [ "$SKIP_GIT_HOOKS" != "1" ] && [ -d "$ROOT/.git" ]; then
  "$ROOT/scripts/install-git-hooks.sh" --repo "$ROOT" --gauntlet-root "$ROOT" >/dev/null
fi

echo "Installed Gauntlet Lite for $TARGET to $AGENT_HOME"
echo "Restart or reload your coding agent to pick up the new workflow."
