#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_ROOT="$ROOT/skills"
if [ ! -d "$SKILLS_ROOT" ] && [ -d "$ROOT/../skills" ]; then
  SKILLS_ROOT="$ROOT/../skills"
fi

changed_files=()
if [ "${1:-}" = "--changed-files" ]; then
  shift
  changed_files=("$@")
else
  if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    while IFS= read -r file; do
      changed_files+=("$file")
    done < <(git -C "$ROOT" diff --cached --name-only --diff-filter=ACMR)
  fi
fi

skill_change=0
changed_skill_names=()
if [ "${#changed_files[@]}" -gt 0 ]; then
  for file in "${changed_files[@]}"; do
    case "$file" in
      skills/*/SKILL.md|skills/*/examples/*)
        skill_change=1
        skill_name="${file#skills/}"
        skill_name="${skill_name%%/*}"
        changed_skill_names+=("$skill_name")
        ;;
    esac
  done
fi

if [ "$skill_change" -eq 0 ]; then
  echo "No Gauntlet skill changes detected; skipping skill evals."
  exit 0
fi

echo "Gauntlet skill changes detected; running skill evals and linter."

mkdir -p "$ROOT/evals/results"

skill_names="$(
  printf '%s\n' "${changed_skill_names[@]}" | sort -u | paste -sd, -
)"

echo "targeted skill evals: $skill_names"

"$ROOT/scripts/run-skill-evals.py" \
  --only-skill "$skill_names" \
  --behavior-responses "$ROOT/evals/behavior-fixtures.json" \
  --results "$ROOT/evals/results/skill-change-check.json"

"$ROOT/scripts/lint-skills.py" \
  --skills-root "$SKILLS_ROOT" \
  --only "$skill_names" \
  --json > "$ROOT/evals/results/skill-change-lint.json"

echo "skill linter: passed"
