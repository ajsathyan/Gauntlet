#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -f "$ROOT/scripts/generate-install-manifest.py" ]; then
  python3 "$ROOT/scripts/generate-install-manifest.py" --check
fi
SKILLS_ROOT="$ROOT/skills"
if [ ! -d "$SKILLS_ROOT" ] && [ -d "$ROOT/../skills" ]; then
  SKILLS_ROOT="$ROOT/../skills"
fi

changed_files=()
detect_only=0
if [ "${1:-}" = "--detect-only" ]; then
  detect_only=1
  shift
fi
if [ "${1:-}" = "--changed-files" ]; then
  shift
  changed_files=("$@")
elif git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  while IFS= read -r file; do
    changed_files+=("$file")
  done < <(git -C "$ROOT" diff --cached --name-only --diff-filter=ACMRD)
fi

changed_skill_names=()
lint_skill_names=()
changed_python_files=()
if [ "${#changed_files[@]}" -gt 0 ]; then
  for file in "${changed_files[@]}"; do
    case "$file" in
      skills/*/*)
        skill_name="${file#skills/}"
        skill_name="${skill_name%%/*}"
        changed_skill_names+=("$skill_name")
        if [ -f "$SKILLS_ROOT/$skill_name/SKILL.md" ]; then
          lint_skill_names+=("$skill_name")
        fi
        ;;
    esac
    case "$file" in
      *.py)
        if [ -f "$ROOT/$file" ]; then
          changed_python_files+=("$file")
        fi
        ;;
    esac
  done
fi

if [ "$detect_only" -eq 0 ] && [ "${#changed_python_files[@]}" -gt 0 ]; then
  if command -v ruff >/dev/null 2>&1; then
    ruff_command=(ruff)
  elif python3 -m ruff --version >/dev/null 2>&1; then
    ruff_command=(python3 -m ruff)
  else
    echo "Changed Python files require Ruff. Install the dev tools with: python3 -m pip install '.[dev]'" >&2
    exit 1
  fi
  echo "Changed Python files detected; running Ruff."
  (
    cd "$ROOT"
    "${ruff_command[@]}" check --config "$ROOT/pyproject.toml" -- "${changed_python_files[@]}"
  )
  if command -v pyright >/dev/null 2>&1; then
    pyright_command=(pyright)
  elif python3 -m pyright --version >/dev/null 2>&1; then
    pyright_command=(python3 -m pyright)
  else
    echo "Changed Python files require Pyright. Install the dev tools with: python3 -m pip install '.[dev]'" >&2
    exit 1
  fi
  echo "Changed Python files detected; running Pyright."
  (
    cd "$ROOT"
    "${pyright_command[@]}"
  )
fi

if [ "${#changed_skill_names[@]}" -eq 0 ]; then
  echo "No Gauntlet skill changes detected; skipping skill checks."
  exit 0
fi

skill_names="$(printf '%s\n' "${changed_skill_names[@]}" | sort -u | paste -sd, -)"
if [ "$detect_only" -eq 1 ]; then
  echo "Gauntlet skill changes detected: $skill_names"
  exit 0
fi

if [ "${#lint_skill_names[@]}" -eq 0 ]; then
  echo "Gauntlet skill deletions detected; no remaining skill files require structural lint."
  exit 0
fi

lint_skill_names_csv="$(printf '%s\n' "${lint_skill_names[@]}" | sort -u | paste -sd, -)"
echo "Gauntlet skill changes detected; running structural lint: $lint_skill_names_csv"
"$ROOT/scripts/lint-skills.py" --skills-root "$SKILLS_ROOT" --only "$lint_skill_names_csv" --json >/dev/null
echo "skill structural lint: passed"
