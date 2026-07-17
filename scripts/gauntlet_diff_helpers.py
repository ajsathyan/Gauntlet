import json
import re
from pathlib import Path

from gauntletlib.core.processes import git, run_command as _run_command
from gauntletlib.core.security import SECRET_PATTERNS as SECRET_PATTERNS
from gauntletlib.core.security import has_secret, redact_secrets as redact_secrets
from gauntletlib.core.serialization import read_json as _read_json
from gauntletlib.core.timestamps import utc_now_seconds


RISK_ORDER = [
    "auth",
    "permissions",
    "billing",
    "migration",
    "persistence",
    "public-api",
    "data-integrity",
    "security-privacy",
    "durable-workflow",
    "shared-domain",
    "instruction-surface",
    "ui",
    "generated",
    "docs-only",
]

IGNORED_CHANGE_PREFIXES = (
    ".gauntlet/",
    ".review-brief",
    ".gauntlet-review",
    ".gauntlet-notes",
)
IGNORED_CHANGE_NAMES = {
    "review-brief.html",
    "review-brief-data.json",
    "review-brief-data.schema.json",
    "implementation-notes.html",
}

RISK_PATTERNS = [
    ("auth", re.compile(r"\b(auth|session|login|oauth|jwt|token|principal)\b", re.I)),
    ("permissions", re.compile(r"\b(permission|permissions|role|roles|rbac|policy|policies)\b", re.I)),
    ("billing", re.compile(r"\b(billing|payment|payments|stripe|invoice|subscription|credits?|entitlement)\b", re.I)),
    ("migration", re.compile(r"\b(migration|migrations|schema|prisma|drizzle|knex|database|db/|sql)\b", re.I)),
    ("persistence", re.compile(r"\b(repository|repositories|adapter|adapters|store|storage|postgres|sqlite|redis|cache)\b", re.I)),
    ("public-api", re.compile(r"\b(api|sdk|contract|openapi|graphql|trpc|route|routes|endpoint|webhook)\b", re.I)),
    ("data-integrity", re.compile(r"\b(idempot|transaction|dedupe|concurr|lock|race|consistency|integrity)\b", re.I)),
    ("security-privacy", re.compile(r"\b(secret|credential|password|pii|privacy|encrypt|decrypt|redact)\b", re.I)),
    ("durable-workflow", re.compile(r"\b(queue|worker|workflow|retry|retries|compensation|saga)\b", re.I)),
    ("shared-domain", re.compile(r"\b(domain|domains|model|models|entity|entities|value-object|value_objects)\b", re.I)),
]


def now_iso():
    return utc_now_seconds()


def run_command(args, cwd):
    return _run_command(args, cwd=cwd)


def relpath(root, path):
    try:
        return str(Path(path).resolve().relative_to(root))
    except ValueError:
        return str(path)


def read_json(path):
    return _read_json(Path(path))


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def is_git_repo(root):
    return git(["rev-parse", "--is-inside-work-tree"], root).returncode == 0


def is_tracked_file(root, path):
    return git(["ls-files", "--error-unmatch", "--", path], root).returncode == 0


def should_ignore_changed_path(path):
    name = Path(path).name
    return path in IGNORED_CHANGE_NAMES or name in IGNORED_CHANGE_NAMES or any(
        path.startswith(prefix) for prefix in IGNORED_CHANGE_PREFIXES
    )


def discover_changed_files(root, base_ref="HEAD"):
    if not is_git_repo(root):
        return []

    status_by_path = {}
    diff = git(["diff", "--name-status", "--diff-filter=ACMR", base_ref, "--"], root)
    if diff.returncode == 0:
        for line in diff.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                status_by_path[parts[-1]] = parts[0]

    untracked = git(["ls-files", "--others", "--exclude-standard"], root)
    if untracked.returncode == 0:
        for path in untracked.stdout.splitlines():
            if path.strip():
                status_by_path.setdefault(path.strip(), "??")

    return [
        {"path": path, "status": status_by_path[path]}
        for path in sorted(status_by_path)
        if not should_ignore_changed_path(path)
    ]


def path_is_docs(path):
    lower = path.lower()
    return lower.startswith("docs/") or lower.endswith((".md", ".mdx", ".rst", ".txt"))


def path_is_instruction_surface(path, text=""):
    """Return whether a changed file can directly steer an agent or harness."""
    lower = path.lower()
    if lower.startswith("./"):
        lower = lower[2:]
    name = Path(lower).name
    parts = Path(lower).parts
    if name in {"agents.md", "claude.md", "gemini.md"}:
        return True
    if parts and parts[0] == "router" and Path(name).suffix in {".md", ".mdx", ".txt"}:
        return True
    if len(parts) >= 3 and parts[0] == "skills" and parts[-1] == "skill.md":
        return True
    if len(parts) >= 4 and parts[0] == "skills" and "examples" in parts[2:-1] and Path(name).suffix in {".md", ".mdx", ".txt"}:
        return True
    if lower in {
        "docs/github-discipline.md",
        "docs/meaningful-proof.md",
        "docs/production-quality-bar.md",
        "docs/skill-quality-bar.md",
        "docs/ui-constitution.md",
        "docs/workflow-etiquette.md",
        "docs/workflow-speedups.md",
    }:
        return True
    if any(part in {"prompts", "prompt", "templates", "template", "instructions"} for part in parts[:-1]):
        return True
    if parts and parts[0] in {".codex-plugin", ".claude-plugin"}:
        return True
    instruction_tokens = {
        "agent",
        "agents",
        "instruction",
        "instructions",
        "prompt",
        "prompts",
        "system-prompt",
    }
    stem_tokens = set(re.split(r"[^a-z0-9]+", Path(name).stem))
    suffix = Path(name).suffix
    if bool(stem_tokens & instruction_tokens) and suffix in {
        ".md",
        ".mdx",
        ".txt",
        ".json",
        ".jsonl",
        ".yaml",
        ".yml",
        ".toml",
    }:
        return True
    return suffix in {".json", ".jsonl", ".yaml", ".yml", ".toml"} and bool(
        re.search(r"(?i)\b(system_?prompt|developer_?prompt|agent_?prompt|instructions?)\b", text)
        or re.search(r"(?im)^\+?\s*[\"']?prompt[\"']?\s*[:=]", text)
    )


def path_is_generated(path):
    lower = path.lower()
    name = Path(lower).name
    return (
        "/generated/" in f"/{lower}"
        or lower.startswith("generated/")
        or ".generated." in name
        or name in {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock"}
    )


def path_is_test(path):
    lower = path.lower()
    name = Path(lower).name
    return bool(re.search(r"(\.test|\.spec)\.(ts|tsx|js|jsx|mjs|cjs)$", name)) or name.startswith("test_") or name.endswith("_test.py")


def path_is_ui(path):
    lower = path.lower()
    if lower.endswith((".css", ".scss", ".sass", ".less")):
        return True
    if lower.endswith((".tsx", ".jsx")) and re.search(r"(^|/)(components?|ui|views?|screens?|pages|app)(/|$)", lower):
        return True
    return False


def diff_for_file(root, path, base_ref="HEAD"):
    if is_git_repo(root):
        result = git(["diff", base_ref, "--", path], root)
        if result.returncode == 0 and result.stdout:
            return result.stdout
        if is_tracked_file(root, path):
            return ""
    return read_text(root / path)


def risk_triggers_for(path, diff_text):
    blob = f"{path}\n{diff_text}".lower()
    triggers = set()
    if path_is_instruction_surface(path, diff_text):
        triggers.add("instruction-surface")
    if path_is_generated(path):
        triggers.add("generated")
    if path_is_ui(path):
        triggers.add("ui")
    if has_secret(diff_text):
        triggers.add("security-privacy")
    for trigger, pattern in RISK_PATTERNS:
        if pattern.search(blob):
            triggers.add(trigger)
    return triggers


def order_risks(triggers):
    return [trigger for trigger in RISK_ORDER if trigger in triggers] + sorted(set(triggers) - set(RISK_ORDER))


def nearest_package_root(root, relative_path):
    current = (root / relative_path).parent
    while current != root.parent:
        for marker in ["package.json", "pyproject.toml", "requirements.txt", "go.mod", "Cargo.toml"]:
            if (current / marker).exists():
                return "." if current == root else relpath(root, current)
        if current == root:
            break
        current = current.parent
    return "."


def test_candidates_for(root, relative_path):
    path = root / relative_path
    if path_is_test(relative_path) or path_is_docs(relative_path) or path_is_generated(relative_path):
        return []
    stem = path.stem
    suffix = path.suffix
    candidates = []
    if suffix in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}:
        for test_suffix in [".test", ".spec"]:
            candidate = path.with_name(f"{stem}{test_suffix}{suffix}")
            if candidate.exists():
                candidates.append(relpath(root, candidate))
    if suffix == ".py":
        for candidate in [path.with_name(f"test_{path.name}"), path.with_name(f"{stem}_test.py")]:
            if candidate.exists():
                candidates.append(relpath(root, candidate))
        tests_dir = root / "tests"
        if tests_dir.exists():
            wanted_names = {f"test_{stem}.py", f"{stem}_test.py"}
            parts = Path(relative_path).parts
            if parts and parts[0] == "src" and len(parts) > 2:
                flattened = "_".join(parts[1:-1] + (stem,))
                wanted_names.add(f"test_{flattened}.py")
            for candidate in sorted(tests_dir.rglob("*.py")):
                name = candidate.name
                if name in wanted_names or (name.startswith("test_") and stem in name):
                    relative = relpath(root, candidate)
                    if relative not in candidates:
                        candidates.append(relative)
    return candidates


def line_change_count(diff_text):
    count = 0
    for line in diff_text.splitlines():
        if line.startswith(("+++", "---")):
            continue
        if line.startswith(("+", "-")):
            count += 1
    return count


def build_diff_intel(project_root, changed_files=None, base_ref="HEAD"):
    root = Path(project_root).resolve()
    discovered = [{"path": path, "status": "M"} for path in changed_files] if changed_files else discover_changed_files(root, base_ref)
    all_triggers = set()
    changed = []
    package_roots = set()
    total_line_changes = 0
    cannot_verify = []

    for item in discovered:
        path = item["path"]
        diff_text = diff_for_file(root, path, base_ref)
        triggers = risk_triggers_for(path, diff_text)
        total_line_changes += line_change_count(diff_text)
        all_triggers.update(triggers)
        package_roots.add(nearest_package_root(root, path))
        changed.append({
            "path": path,
            "status": item.get("status", "M"),
            "flags": sorted({
                flag
                for flag, present in {
                    "docs": path_is_docs(path),
                    "instruction": path_is_instruction_surface(path, diff_text),
                    "generated": path_is_generated(path),
                    "test": path_is_test(path),
                    "ui": path_is_ui(path),
                    "secret-like-diff": has_secret(diff_text),
                }.items()
                if present
            }),
            "riskTriggers": order_risks(triggers),
            "packageRoot": nearest_package_root(root, path),
            "testCandidates": test_candidates_for(root, path),
            "lineChanges": line_change_count(diff_text),
        })

    if changed and all(path_is_docs(item["path"]) for item in changed) and "instruction-surface" not in all_triggers:
        all_triggers = {"docs-only"}

    if not changed:
        confidence = "low"
        cannot_verify.append("No changed files detected; pass explicit files or check git base ref.")
    elif all_triggers == {"docs-only"}:
        confidence = "high"
    elif "generated" in all_triggers or total_line_changes > 700 or len(package_roots) > 2:
        confidence = "medium"
        if "generated" in all_triggers:
            cannot_verify.append("Generated files changed; verify the source generator or regeneration command.")
    else:
        confidence = "medium" if any(trigger in all_triggers for trigger in {"security-privacy", "auth", "billing"}) else "high"

    if any(item["lineChanges"] > 500 for item in changed):
        cannot_verify.append("A large changed file may contain multiple unrelated surfaces; inspect manually.")

    dirty = bool(changed)
    if is_git_repo(root):
        status = git(["status", "--porcelain"], root)
        dirty = bool(status.stdout.strip()) if status.returncode == 0 else dirty

    return {
        "schemaVersion": "1.0",
        "generatedAt": now_iso(),
        "projectRoot": str(root),
        "baseRef": base_ref,
        "dirtyWorktree": dirty,
        "changedFiles": changed,
        "packageRoots": sorted(package_roots),
        "riskTriggers": order_risks(all_triggers),
        "confidence": confidence,
        "cannotVerify": cannot_verify,
    }
