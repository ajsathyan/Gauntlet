#!/usr/bin/env bash
set -euo pipefail

REPO=""
GAUNTLET_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo)
      REPO="$2"
      shift 2
      ;;
    --gauntlet-root)
      GAUNTLET_ROOT="$2"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [ -z "$REPO" ]; then
  REPO="$(git -C "$GAUNTLET_ROOT" rev-parse --show-toplevel)"
fi

GIT_DIR="$(git -C "$REPO" rev-parse --git-dir)"
case "$GIT_DIR" in
  /*) ;;
  *) GIT_DIR="$REPO/$GIT_DIR" ;;
esac

HOOK_DIR="$GIT_DIR/hooks"
HOOK="$HOOK_DIR/pre-commit"
mkdir -p "$HOOK_DIR"

USER_HOOK=""
if [ -f "$HOOK" ] && ! grep -q "GAUNTLET SKILL CHECKS" "$HOOK"; then
  USER_HOOK="$HOOK.gauntlet-backup"
  cp "$HOOK" "$USER_HOOK"
  chmod +x "$USER_HOOK"
elif [ -f "$HOOK.gauntlet-backup" ]; then
  USER_HOOK="$HOOK.gauntlet-backup"
fi

cat > "$HOOK" <<EOF
#!/usr/bin/env bash
set -euo pipefail

# GAUNTLET SKILL CHECKS
USER_HOOK="$USER_HOOK"
if [ -n "\$USER_HOOK" ] && [ -f "\$USER_HOOK" ]; then
  "\$USER_HOOK"
fi

REPO_ROOT="\$(git rev-parse --show-toplevel)"
if [ -x "\$REPO_ROOT/scripts/run-skill-change-checks.sh" ]; then
  "\$REPO_ROOT/scripts/run-skill-change-checks.sh"
else
  "$GAUNTLET_ROOT/scripts/run-skill-change-checks.sh"
fi
EOF

chmod +x "$HOOK"
echo "Installed Gauntlet pre-commit hook to $HOOK"
