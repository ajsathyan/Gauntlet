#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$PWD}"
ROOT="$(cd "$ROOT" && pwd)"
shift || true

ROOT="$ROOT" CHANGED_FILES="$*" python3 - <<'PY'
import datetime
import json
import os
import re
from pathlib import Path

root = Path(os.environ["ROOT"])
changed_files = [item for item in os.environ.get("CHANGED_FILES", "").split() if item]

artifact = root / ".gauntlet-ts-durability.json"

def rel(path):
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)

def read_text(path):
    try:
        return path.read_text(errors="ignore")
    except OSError:
        return ""

def first_existing(names):
    found = []
    for name in names:
        path = root / name
        if path.exists():
            found.append(path)
    return found

def has_ts_project():
    if first_existing(["tsconfig.json", "tsconfig.base.json"]):
        return True
    package = root / "package.json"
    if package.exists():
        text = read_text(package)
        return any(token in text for token in ['"typescript"', '"tsx"', '"ts-node"', '"vite"', '"next"'])
    return any(root.glob("**/*.ts")) or any(root.glob("**/*.tsx"))

def repo_files_to_scan():
    paths = first_existing([
        "package.json",
        "tsconfig.json",
        "tsconfig.base.json",
        "src",
        "app",
        "pages",
    ])
    return [rel(path) for path in paths]

def path_blob():
    values = changed_files[:]
    if not values:
        for pattern in ("src/**/*.ts", "src/**/*.tsx", "app/**/*.ts", "app/**/*.tsx", "pages/**/*.ts", "pages/**/*.tsx"):
            values.extend(rel(path) for path in root.glob(pattern))
    return "\n".join(values).lower()

def package_blob():
    return "\n".join(read_text(path) for path in first_existing(["package.json", "tsconfig.json", "tsconfig.base.json"])).lower()

triggers = []
reasons = []
files_scanned = repo_files_to_scan()

if not has_ts_project():
    payload = {
        "schemaVersion": "1.0",
        "durabilityRequired": False,
        "reason": "TypeScript not in scope.",
        "filesScanned": files_scanned,
        "triggers": [],
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    artifact.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    raise SystemExit(0)

paths = path_blob()
config = package_blob()

def is_ui_only_path(value):
    path = value.lower()
    if re.search(r"(^|/)(api|routes|server|servers|service|services|domain|domains|model|models|repository|repositories|adapter|adapters)(/|$)", path):
        return False
    if re.search(r"\.(css|scss|sass|less|pcss|stories\.(ts|tsx|js|jsx))$", path):
        return True
    if re.search(r"(^|/)(app|index|page|layout|template|loading|error|not-found)\.(tsx|jsx)$", path):
        return True
    if re.search(r"(^|/)(components|component|ui|views|view|screens|screen|styles|style|assets)(/|$)", path):
        return True
    if re.search(r"(^|/)(pages|app)/[^/]+\.(tsx|jsx)$", path):
        return True
    return False

ui_only_changed = bool(changed_files) and all(is_ui_only_path(item) for item in changed_files)

trigger_patterns = [
    ("auth", r"\b(auth|session|permission|permissions|role|roles|rbac|login|oauth|jwt|token|principal)\b"),
    ("billing", r"\b(billing|payment|payments|stripe|invoice|invoices|subscription|credits?|entitlement|entitlements)\b"),
    ("migration", r"\b(migration|migrations|schema|prisma|drizzle|knex|supabase|database|db/|sql)\b"),
    ("persistence", r"\b(repository|repositories|adapter|adapters|store|storage|persistence|postgres|sqlite|redis|cache)\b"),
    ("public-api", r"\b(api|sdk|contract|openapi|graphql|trpc|route|routes|endpoint|endpoints|webhook|webhooks)\b"),
    ("data-integrity", r"\b(idempot|transaction|outbox|inbox|dedupe|concurr|lock|race|consistency|integrity)\b"),
    ("security-privacy", r"\b(secret|secrets|credential|credentials|password|pii|privacy|encrypt|decrypt|redact|redacted)\b"),
    ("durable-workflow", r"\b(queue|queues|worker|workers|workflow|workflows|retry|retries|compensation|saga)\b"),
    ("shared-domain", r"\b(domain|domains|model|models|entity|entities|policy|policies|value-object|value_objects)\b"),
]

for trigger, pattern in trigger_patterns:
    if re.search(pattern, paths):
        triggers.append(trigger)
        reasons.append(f"changed paths match {trigger} durability trigger")

has_existing_durable_patterns = bool(re.search(r'"(effect|better-result|neverthrow|fp-ts|zod|@effect/schema)"', config))
if has_existing_durable_patterns and not (ui_only_changed and not triggers):
    triggers.append("existing-durable-patterns")
    reasons.append("project config shows existing durable TypeScript patterns")

if os.environ.get("GAUNTLET_MODE", "").lower() == "release":
    triggers.append("release-mode")
    reasons.append("GAUNTLET_MODE=Release")

if os.environ.get("GAUNTLET_TS_DURABILITY", "").lower() in {"1", "true", "yes", "required"}:
    triggers.append("explicit-request")
    reasons.append("GAUNTLET_TS_DURABILITY explicitly requested")

deduped = []
for trigger in triggers:
    if trigger not in deduped:
        deduped.append(trigger)
triggers = deduped

durability_required = bool(triggers)
if durability_required:
    reason = "; ".join(reasons) or "Concrete TypeScript durability trigger found."
else:
    if changed_files:
        if ui_only_changed and has_existing_durable_patterns:
            reason = "UI-only TypeScript changed files; existing durable patterns are present but the touched surface has no durability trigger."
        else:
            reason = "TypeScript in scope, but changed files do not match auth, billing, persistence, public API, data integrity, security/privacy, concurrency, durable workflow, shared domain, Release, or existing durable-pattern triggers."
    else:
        reason = "TypeScript project detected, but no concrete durability trigger was found."

payload = {
    "schemaVersion": "1.0",
    "durabilityRequired": durability_required,
    "reason": reason,
    "filesScanned": files_scanned,
    "triggers": triggers,
    "generatedAt": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
}
artifact.write_text(json.dumps(payload, indent=2) + "\n")
print(json.dumps(payload, indent=2))
PY
