#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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
for file in "${changed_files[@]}"; do
  case "$file" in
    skills/*/*)
      skill_name="${file#skills/}"
      changed_skill_names+=("${skill_name%%/*}")
      ;;
  esac
done

if [ "${#changed_skill_names[@]}" -eq 0 ]; then
  echo "No Gauntlet skill changes detected; skipping skill checks."
  exit 0
fi

skill_names="$(printf '%s\n' "${changed_skill_names[@]}" | sort -u | paste -sd, -)"
if [ "$detect_only" -eq 1 ]; then
  echo "Gauntlet skill changes detected: $skill_names"
  exit 0
fi

echo "Gauntlet skill changes detected; running structural lint: $skill_names"
"$ROOT/scripts/lint-skills.py" --skills-root "$SKILLS_ROOT" --only "$skill_names" --json >/dev/null
echo "skill structural lint: passed"
