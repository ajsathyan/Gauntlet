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

write_claude_adapter() {
  local claude_file="$AGENT_HOME/CLAUDE.md"
  local block_file
  local output_file
  block_file="$(mktemp)"
  output_file="$(mktemp)"

  cat > "$block_file" <<EOF
<!-- BEGIN GAUNTLET MANAGED BLOCK -->
@${AGENT_HOME}/gauntlet/AGENTS.md

## Gauntlet Adapter For Claude Code

- Imported Gauntlet AGENTS.md is the workflow source of truth.
- Gauntlet role skill files are installed in ${AGENT_HOME}/skills. When Gauntlet names a role skill, read that skill's SKILL.md before using it.
- Codex-specific thread, app, or skill actions should be mapped to available Claude Code, Git, or GitHub equivalents when possible.
<!-- END GAUNTLET MANAGED BLOCK -->
EOF

  if [ -f "$claude_file" ]; then
    local begin_count
    local end_count
    begin_count="$(grep -c '<!-- BEGIN GAUNTLET MANAGED BLOCK -->' "$claude_file" || true)"
    end_count="$(grep -c '<!-- END GAUNTLET MANAGED BLOCK -->' "$claude_file" || true)"
    if [ "$begin_count" -ne "$end_count" ] || [ "$begin_count" -gt 1 ]; then
      echo "Malformed Gauntlet managed block in $claude_file" >&2
      rm -f "$block_file" "$output_file"
      return 1
    fi
    if [ "$begin_count" -eq 1 ]; then
      local begin_line
      local end_line
      begin_line="$(grep -n '<!-- BEGIN GAUNTLET MANAGED BLOCK -->' "$claude_file" | cut -d: -f1)"
      end_line="$(grep -n '<!-- END GAUNTLET MANAGED BLOCK -->' "$claude_file" | cut -d: -f1)"
      if [ "$begin_line" -ge "$end_line" ]; then
        echo "Malformed Gauntlet managed block in $claude_file" >&2
        rm -f "$block_file" "$output_file"
        return 1
      fi
    fi

    awk -v block_file="$block_file" '
      BEGIN {
        while ((getline line < block_file) > 0) {
          block = block line ORS
        }
        in_block = 0
        replaced = 0
      }
      /<!-- BEGIN GAUNTLET MANAGED BLOCK -->/ {
        if (!replaced) {
          printf "%s", block
          replaced = 1
        }
        in_block = 1
        next
      }
      /<!-- END GAUNTLET MANAGED BLOCK -->/ {
        if (in_block) {
          in_block = 0
          next
        }
      }
      !in_block {
        print
      }
      END {
        if (!replaced) {
          if (NR > 0) {
            print ""
          }
          printf "%s", block
        }
      }
    ' "$claude_file" > "$output_file"
    mv "$output_file" "$claude_file"
  else
    {
      printf "# Claude Code Global Instructions\n\n"
      cat "$block_file"
    } > "$claude_file"
    rm -f "$output_file"
  fi

  rm -f "$block_file"
}

write_codex_agents() {
  local codex_file="$AGENT_HOME/AGENTS.md"
  local block_file
  local personal_file
  local legacy_base_file
  local legacy_normalized_file
  local installed_normalized_file
  local legacy_reference
  local output_file
  block_file="$(mktemp)"
  personal_file="$(mktemp)"
  legacy_base_file="$(mktemp)"
  legacy_normalized_file="$(mktemp)"
  installed_normalized_file="$(mktemp)"
  output_file="$(mktemp)"
  legacy_reference="${LEGACY_INSTALLED_AGENTS:-}"

  {
    printf '%s\n' '<!-- BEGIN GAUNTLET MANAGED BLOCK -->'
    cat "$ROOT/AGENTS.md"
    printf '%s\n' '<!-- END GAUNTLET MANAGED BLOCK -->'
  } > "$block_file"

  if [ -f "$codex_file" ]; then
    local begin_count
    local end_count
    begin_count="$(grep -c '<!-- BEGIN GAUNTLET MANAGED BLOCK -->' "$codex_file" || true)"
    end_count="$(grep -c '<!-- END GAUNTLET MANAGED BLOCK -->' "$codex_file" || true)"
    if [ "$begin_count" -ne "$end_count" ] || [ "$begin_count" -gt 1 ]; then
      echo "Malformed Gauntlet managed block in $codex_file" >&2
      rm -f "$block_file" "$personal_file" "$legacy_base_file" "$legacy_normalized_file" "$installed_normalized_file" "$output_file"
      return 1
    fi
    if [ "$begin_count" -eq 1 ]; then
      local begin_line
      local end_line
      begin_line="$(grep -n '<!-- BEGIN GAUNTLET MANAGED BLOCK -->' "$codex_file" | cut -d: -f1)"
      end_line="$(grep -n '<!-- END GAUNTLET MANAGED BLOCK -->' "$codex_file" | cut -d: -f1)"
      if [ "$begin_line" -ge "$end_line" ]; then
        echo "Malformed Gauntlet managed block in $codex_file" >&2
        rm -f "$block_file" "$personal_file" "$legacy_base_file" "$legacy_normalized_file" "$installed_normalized_file" "$output_file"
        return 1
      fi
    fi

    awk '
      /<!-- BEGIN PERSONAL HOUSE VOICE -->/ { in_block = 1 }
      in_block { print }
      /<!-- END PERSONAL HOUSE VOICE -->/ { if (in_block) exit }
    ' "$codex_file" > "$personal_file"

    if [ "$begin_count" -eq 1 ]; then
      awk -v block_file="$block_file" '
      BEGIN {
        while ((getline line < block_file) > 0) {
          block = block line ORS
        }
        in_block = 0
        replaced = 0
      }
      /<!-- BEGIN GAUNTLET MANAGED BLOCK -->/ {
        if (!replaced) {
          printf "%s", block
          replaced = 1
        }
        in_block = 1
        next
      }
      /<!-- END GAUNTLET MANAGED BLOCK -->/ {
        if (in_block) {
          in_block = 0
          next
        }
      }
      !in_block { print }
      END {
        if (!replaced) {
          print ""
          printf "%s", block
        }
      }
      ' "$codex_file" > "$output_file"
    else
      awk '
        /<!-- BEGIN PERSONAL HOUSE VOICE -->/ { in_personal = 1; next }
        /<!-- END PERSONAL HOUSE VOICE -->/ { in_personal = 0; next }
        !in_personal { print }
      ' "$codex_file" > "$legacy_base_file"

      # In the legacy layout the personal block could leave one extra blank line
      # inside otherwise identical Gauntlet text. Normalize blank runs only for
      # comparison; never normalize user-owned output.
      awk '
        /^[[:space:]]*$/ { if (!blank) print ""; blank = 1; next }
        { sub(/[[:space:]]+$/, ""); print; blank = 0 }
      ' "$legacy_base_file" > "$legacy_normalized_file"
      if [ -n "$legacy_reference" ] && [ -f "$legacy_reference" ]; then
        awk '
          /^[[:space:]]*$/ { if (!blank) print ""; blank = 1; next }
          { sub(/[[:space:]]+$/, ""); print; blank = 0 }
        ' "$legacy_reference" > "$installed_normalized_file"
      fi

      if [ -n "$legacy_reference" ] && [ -f "$legacy_reference" ] && cmp -s "$legacy_normalized_file" "$installed_normalized_file"; then
        {
          if [ -s "$personal_file" ]; then
            cat "$personal_file"
            printf '\n'
          fi
          cat "$block_file"
        } > "$output_file"
      else
        {
          cat "$codex_file"
          printf '\n'
          cat "$block_file"
        } > "$output_file"
      fi
    fi
  else
    cp "$block_file" "$output_file"
  fi

  mv "$output_file" "$codex_file"
  chmod 0644 "$codex_file"
  rm -f "$block_file" "$personal_file" "$legacy_base_file" "$legacy_normalized_file" "$installed_normalized_file" "$output_file"
}

LEGACY_INSTALLED_AGENTS=""
if [ "$TARGET" = "codex" ] && [ -f "$AGENT_HOME/gauntlet/AGENTS.md" ]; then
  LEGACY_INSTALLED_AGENTS="$(mktemp)"
  cp "$AGENT_HOME/gauntlet/AGENTS.md" "$LEGACY_INSTALLED_AGENTS"
fi

cleanup_install_snapshot() {
  if [ -n "$LEGACY_INSTALLED_AGENTS" ]; then
    rm -f "$LEGACY_INSTALLED_AGENTS"
  fi
}
trap cleanup_install_snapshot EXIT

mkdir -p "$AGENT_HOME/skills" "$AGENT_HOME/gauntlet"
cp "$ROOT/README.md" "$AGENT_HOME/gauntlet/README.md"
cp "$ROOT/AGENTS.md" "$AGENT_HOME/gauntlet/AGENTS.md"
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
  "$AGENT_HOME/gauntlet/docs/upstream-superpowers.json" \
  "$AGENT_HOME/gauntlet/scripts/check-gauntlet-workflow.py" \
  "$AGENT_HOME/gauntlet/evals/skill-evals.json" \
  "$AGENT_HOME/gauntlet/evals/behavior-fixtures.json" \
  "$AGENT_HOME/skills/intake/SKILL.md" \
  "$AGENT_HOME/skills/planner/SKILL.md" \
  "$AGENT_HOME/skills/researcher/SKILL.md" \
  "$AGENT_HOME/skills/debugger/SKILL.md"
do
  if [ ! -s "$required_path" ]; then
    echo "Gauntlet install payload is incomplete: $required_path" >&2
    exit 1
  fi
done

# Activate the new workflow only after the payload is complete.
case "$TARGET" in
  codex)
    write_codex_agents
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
