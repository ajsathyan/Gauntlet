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
else
  if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    while IFS= read -r file; do
      changed_files+=("$file")
    done < <(git -C "$ROOT" diff --cached --name-only --diff-filter=ACMRD)
  fi
fi

skill_change=0
changed_skill_names=()
if [ "${#changed_files[@]}" -gt 0 ]; then
  for file in "${changed_files[@]}"; do
    case "$file" in
      skills/*/*)
        skill_change=1
        skill_name="${file#skills/}"
        skill_name="${skill_name%%/*}"
        changed_skill_names+=("$skill_name")
        ;;
    esac
  done
fi

if [ "$skill_change" -eq 0 ]; then
  echo "No Gauntlet skill changes detected; skipping skill text coverage."
  exit 0
fi

if [ "$detect_only" -eq 1 ]; then
  printf 'Gauntlet skill changes detected: %s\n' "$(printf '%s\n' "${changed_skill_names[@]}" | sort -u | paste -sd, -)"
  exit 0
fi

echo "Gauntlet skill changes detected; running skill evals and linter."

mkdir -p "$ROOT/evals/results"

skill_names="$(
  printf '%s\n' "${changed_skill_names[@]}" | sort -u | paste -sd, -
)"

echo "targeted skill text coverage: $skill_names"

configured_skill_names="$(python3 - "$ROOT/evals/skill-evals.json" "$skill_names" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
requested = set(filter(None, sys.argv[2].split(",")))
configured = {case["skill"] for case in data["cases"]}
print(",".join(sorted(requested & configured)))
PY
)"

if [ -n "$configured_skill_names" ]; then
  "$ROOT/scripts/run-skill-evals.py" \
    --only-skill "$configured_skill_names" \
    --scorer-smoke-responses "$ROOT/evals/scorer-smoke-fixtures.json" \
    --results "$ROOT/evals/results/skill-change-check.json"
else
  echo "No configured text-coverage cases apply; using structural lint and task-appropriate forward testing."
fi

"$ROOT/scripts/run-orchestration-evals.py" \
  --pack "$ROOT/evals/orchestration-trace-fixtures.json" \
  --results "$ROOT/evals/results/orchestration-scorer-check.json"

"$ROOT/scripts/run-orchestration-evals.py" \
  --pack "$ROOT/evals/refactor-skill-trace-fixtures.json" \
  --results "$ROOT/evals/results/refactor-skill-orchestration-check.json"

"$ROOT/scripts/lint-skills.py" \
  --skills-root "$SKILLS_ROOT" \
  --only "$skill_names" \
  --json > "$ROOT/evals/results/skill-change-lint.json"

if printf '%s\n' "${changed_skill_names[@]}" | grep -qx 'refactor-codebase'; then
  env \
    -u GIT_DIR \
    -u GIT_WORK_TREE \
    -u GIT_INDEX_FILE \
    -u GIT_OBJECT_DIRECTORY \
    -u GIT_ALTERNATE_OBJECT_DIRECTORIES \
    -u GIT_COMMON_DIR \
    python3 -m unittest discover \
    -s "$SKILLS_ROOT/refactor-codebase/scripts" \
    -p 'test_*.py'
fi

echo "skill linter: passed"
