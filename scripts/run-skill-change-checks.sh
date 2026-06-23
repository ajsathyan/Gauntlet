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
if [ "${#changed_files[@]}" -gt 0 ]; then
  for file in "${changed_files[@]}"; do
    case "$file" in
      skills/*/SKILL.md|skills/*/examples/*)
        skill_change=1
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

"$ROOT/scripts/run-skill-evals.py" \
  --behavior-responses "$ROOT/evals/behavior-fixtures.json" \
  --results "$ROOT/evals/results/skill-change-check.json"

skill_names="$(
  python3 - "$ROOT/evals/skill-evals.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text())
print(",".join(sorted({case["skill"] for case in data["cases"]})))
PY
)"

"$ROOT/scripts/lint-skills.py" \
  --skills-root "$SKILLS_ROOT" \
  --only "$skill_names" \
  --json > "$ROOT/evals/results/skill-change-lint.json"

echo "skill linter: passed"
