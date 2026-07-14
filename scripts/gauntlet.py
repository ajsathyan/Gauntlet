#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from thread_titles import parse_thread_title


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
CHECKER = SCRIPTS / "check-workflow-etiquette.py"
LOCAL_DOC_TEMPLATES = ROOT / "templates" / "local-docs"
LOCAL_DOC_OPT_OUT = Path(".gauntlet") / "doc-org.disabled"
STATUS_ORDER = {"pass": 0, "warn": 1, "review": 2, "fail": 3}
EXIT_CODES = {"pass": 0, "warn": 0, "review": 2, "fail": 1}
DEFERRED_AGENT_ACTIONS = {
    "set_thread_title",
    "present_archive_summary",
    "archive_thread",
    "create_thread",
}
PASSING_CHECK_CONCLUSIONS = {"SUCCESS", "SKIPPED", "NEUTRAL"}
PASSING_STATUS_STATES = {"SUCCESS", "SKIPPED", "NEUTRAL"}
REQUIRED_HANDOFF_FIELDS = {
    "schemaVersion",
    "title",
    "problem",
    "solution",
    "changelog",
    "testing",
    "securityRisk",
}
SECTION_REQUIRED = [
    ("goal", ["goal"]),
    ("scope", ["scope"]),
    ("non_goals", ["non-goals", "non goals", "non-goal", "non goal"]),
    ("scan_index", ["scan index"]),
    ("source_of_truth_files", ["source-of-truth files", "source of truth files", "source files", "read first"]),
    ("edge_cases_and_invariants", ["edge cases and invariants", "edge cases", "invariants"]),
    ("verification", ["verification", "proof"]),
    ("follow_ups", ["follow-ups", "follow ups", "followup", "followups"]),
    ("stale_context_warning", ["stale context warning", "stale-context warning", "stale context"]),
    ("redaction_notes", ["redaction notes", "redaction", "secrets"]),
]
SECRET_PATTERNS = [
    re.compile(r"(?i)\b[A-Z0-9_]*(SECRET|TOKEN|PASSWORD|API_KEY|PRIVATE_KEY)[A-Z0-9_]*\s*=\s*['\"]?[^\s'\"`]+"),
    re.compile(r"(?i)\b(sk|pk|rk)-(live|test)-[A-Za-z0-9_-]{8,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
ARCHIVE_SUMMARY_ALIASES = ["archive summary", "what changed", "change summary"]
ANALYTICS_SCHEMA_VERSION = "gauntlet.analytics.v1"
ANALYTICS_EVENT_TYPES = {
    "run_started",
    "mode_selected",
    "plan_created",
    "plan_revised",
    "implementation_started",
    "proof_started",
    "proof_completed",
    "role_review_completed",
    "human_review_requested",
    "human_review_completed",
    "plan_invalidated",
    "attempt_memory_read",
    "attempt_memory_written",
    "commit_created",
    "changelog_updated",
    "pr_opened",
    "closeout_completed",
    "run_completed",
    "annotation_added",
}
SAFE_COMMAND_LABELS = {
    "npm test",
    "npm run test",
    "pytest",
    "python -m pytest",
    "python3 -m pytest",
    "npm run lint",
    "lint",
    "npm run typecheck",
    "typecheck",
}
SENSITIVE_PAYLOAD_KEYS = {
    "command",
    "command_string",
    "repo",
    "repo_name",
    "repository",
    "repository_name",
    "branch",
    "branch_name",
    "file",
    "file_name",
    "path",
    "source",
    "raw_diff",
    "diff",
    "prompt",
    "stack",
    "stack_trace",
    "trace",
    "issue_body",
    "pr_body",
    "customer_data",
    "fingerprint",
    "proof_completed",
    "proof_commands",
    "unresolved_risks",
    "risk_notes",
}
SENSITIVE_PAYLOAD_FRAGMENTS = [
    "repo",
    "branch",
    "command",
    "file",
    "path",
    "diff",
    "prompt",
    "stack",
    "trace",
    "issue_body",
    "pr_body",
    "customer",
]


def run_cmd(args, cwd=None, env=None, check=False):
    result = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"{args} failed with {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
    return result


def git(args, cwd):
    return run_cmd(["git", *args], cwd=cwd)


def gh_binary():
    return os.environ.get("GAUNTLET_GH", "gh")


def gh(args, cwd):
    return run_cmd([gh_binary(), *args], cwd=cwd, env=os.environ.copy())


def read_text(path):
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def redact_secrets(text):
    redacted = text or ""
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    return redacted


def has_secret(text):
    return any(pattern.search(text or "") for pattern in SECRET_PATTERNS)


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def local_hash(value, salt):
    digest = hashlib.sha256()
    digest.update(salt.encode("utf-8"))
    digest.update(b"\0")
    digest.update(str(value).encode("utf-8", errors="ignore"))
    return digest.hexdigest()[:24]


def analytics_dir(project_root):
    return Path(project_root) / ".gauntlet" / "analytics"


def analytics_events_path(project_root, path=None):
    return Path(path) if path else analytics_dir(project_root) / "events.ndjson"


def attempt_memory_path(project_root, path=None):
    return Path(path) if path else Path(project_root) / ".gauntlet" / "attempt-memory.jsonl"


def local_salt(project_root):
    directory = analytics_dir(project_root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "local-salt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    salt = uuid.uuid4().hex
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(salt + "\n")
    return salt


def git_root(repo):
    result = git(["rev-parse", "--show-toplevel"], repo)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def parse_worktree_roots(project_root):
    result = git(["worktree", "list", "--porcelain"], project_root)
    if result.returncode != 0:
        raise RuntimeError(f"Cannot list repository worktrees:\n{result.stderr.strip()}")
    roots = []
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            roots.append(Path(line.removeprefix("worktree ")).resolve())
    if not roots:
        raise RuntimeError("Git did not report a primary worktree.")
    return roots


def local_docs_context(project_root):
    supplied = Path(project_root).expanduser().resolve()
    repository = git_root(supplied)
    if not repository:
        raise RuntimeError(f"Not a Git worktree: {supplied}")
    worktrees = parse_worktree_roots(repository)
    primary = worktrees[0]
    exclude_result = git(["rev-parse", "--git-path", "info/exclude"], primary)
    if exclude_result.returncode != 0:
        raise RuntimeError(f"Cannot resolve the local Git exclude file:\n{exclude_result.stderr.strip()}")
    exclude = Path(exclude_result.stdout.strip())
    if not exclude.is_absolute():
        exclude = (primary / exclude).resolve()
    return {
        "requestedRoot": supplied,
        "primaryRoot": primary,
        "worktrees": worktrees,
        "policyPath": primary / "doc_org.md",
        "docsRoot": primary / "local-docs",
        "indexPath": primary / "local-docs" / "INDEX.md",
        "optOutPath": primary / LOCAL_DOC_OPT_OUT,
        "excludePath": exclude,
    }


def tracked_local_doc_paths(primary):
    result = git(["ls-files", "--", "doc_org.md", "local-docs"], primary)
    if result.returncode != 0:
        raise RuntimeError(f"Cannot inspect tracked local-document paths:\n{result.stderr.strip()}")
    return [line for line in result.stdout.splitlines() if line.strip()]


def local_docs_path_findings(context):
    findings = []
    for path in [context["policyPath"], context["docsRoot"], context["indexPath"]]:
        if path.is_symlink():
            findings.append({
                "code": "local_document_symlink",
                "severity": "fail",
                "message": f"Canonical local-document paths must not be symlinks: {path}",
            })
    if context["policyPath"].exists() and not context["policyPath"].is_file():
        findings.append({"code": "invalid_doc_org_path", "severity": "fail", "message": f"Policy path is not a file: {context['policyPath']}"})
    if context["docsRoot"].exists() and not context["docsRoot"].is_dir():
        findings.append({"code": "invalid_local_docs_path", "severity": "fail", "message": f"Local document root is not a directory: {context['docsRoot']}"})
    if context["indexPath"].exists() and not context["indexPath"].is_file():
        findings.append({"code": "invalid_local_docs_index", "severity": "fail", "message": f"Local document index is not a file: {context['indexPath']}"})
    if context["optOutPath"].is_symlink():
        findings.append({
            "code": "local_document_opt_out_symlink",
            "severity": "fail",
            "message": f"Local-document opt-out marker must not be a symlink: {context['optOutPath']}",
        })
    if context["optOutPath"].exists() and not context["optOutPath"].is_file():
        findings.append({
            "code": "invalid_local_document_opt_out",
            "severity": "fail",
            "message": f"Local-document opt-out marker is not a file: {context['optOutPath']}",
        })
    return findings


def local_docs_opted_out(context):
    return context["optOutPath"].is_file()


def inferred_epic_prefix(context):
    """Return a stable prefix for lazy initialization without asking the user."""
    raw = re.sub(r"[^A-Z0-9]", "", context["primaryRoot"].name.upper())
    if not raw or not raw[0].isalpha():
        raw = "PROJECT"
    if len(raw) == 1:
        raw += "P"
    return raw[:12]


def local_docs_validation_findings(context, require_profile=False):
    findings = local_docs_path_findings(context)
    tracked = tracked_local_doc_paths(context["primaryRoot"])
    if tracked:
        findings.append({
            "code": "tracked_local_document_collision",
            "severity": "fail",
            "message": "Local-document paths must not be tracked.",
            "paths": tracked,
        })
    if local_docs_opted_out(context):
        return findings
    materialized = any(path.exists() for path in [context["policyPath"], context["docsRoot"], context["indexPath"]])
    if require_profile or materialized:
        for key, code in [("policyPath", "missing_doc_org"), ("indexPath", "missing_local_docs_index")]:
            if not context[key].is_file():
                findings.append({"code": code, "severity": "fail", "message": f"Missing {context[key]}"})
        for relative in ["doc_org.md", "local-docs/INDEX.md"]:
            ignored = git(["check-ignore", "-q", "--", relative], context["primaryRoot"])
            if ignored.returncode != 0:
                findings.append({
                    "code": "local_document_not_ignored",
                    "severity": "fail",
                    "message": f"Canonical local path is not ignored: {relative}",
                })
    return findings


def render_local_doc_template(name, replacements):
    path = LOCAL_DOC_TEMPLATES / name
    if not path.exists():
        raise RuntimeError(f"Gauntlet local-document template is missing: {path}")
    rendered = path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    unresolved = re.findall(r"\{\{[A-Z0-9_]+\}\}", rendered)
    if unresolved:
        raise RuntimeError(f"Template {name} has unresolved placeholders: {', '.join(sorted(set(unresolved)))}")
    return rendered


def write_new_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(content)


def atomic_write_text(path, content, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_mode = path.stat().st_mode & 0o777 if path.exists() else mode
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.chmod(temporary_path, existing_mode)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def ensure_local_excludes(exclude_path, dry_run=False):
    required = ["/doc_org.md", "/local-docs/"]
    existing = exclude_path.read_text(encoding="utf-8") if exclude_path.exists() else ""
    lines = {line.strip() for line in existing.splitlines()}
    missing = [entry for entry in required if entry not in lines]
    if missing and not dry_run:
        exclude_path.parent.mkdir(parents=True, exist_ok=True)
        prefix = existing
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        atomic_write_text(exclude_path, prefix + "\n".join(missing) + "\n", mode=0o644)
    return missing


def local_docs_payload(args, context, findings, **extra):
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "primaryRoot": str(context["primaryRoot"]),
        "policyPath": str(context["policyPath"]),
        "localDocsRoot": str(context["docsRoot"]),
        "findings": findings,
        **extra,
    }
    payload["status"] = status_for(payload)
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def initialize_local_docs(args, context, prefix):
    dry_run = getattr(args, "dry_run", False)
    findings = local_docs_path_findings(context)
    tracked = tracked_local_doc_paths(context["primaryRoot"])
    if tracked:
        findings.append({
            "code": "tracked_local_document_collision",
            "severity": "fail",
            "message": "Refusing to initialize because local-document paths are already tracked.",
            "paths": tracked,
        })
    if local_docs_opted_out(context):
        findings.append({
            "code": "local_document_profile_opted_out",
            "severity": "fail",
            "message": f"Project opted out of default local documents through {context['optOutPath']}; run docs enable before initialization.",
        })
    if findings:
        return findings, [], []

    prefix = prefix.upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9]{1,11}", prefix):
        findings.append({
            "code": "invalid_epic_prefix",
            "severity": "fail",
            "message": "Epic prefix must be 2-12 uppercase letters or digits and begin with a letter.",
        })
        return findings, [], []

    created = []
    preserved = []
    candidates = [
        (context["policyPath"], "doc_org.md.tmpl"),
        (context["indexPath"], "INDEX.md.tmpl"),
    ]
    rendered = {
        path: render_local_doc_template(template, {"EPIC_PREFIX": prefix})
        for path, template in candidates if not path.exists()
    }
    if context["indexPath"].exists():
        existing_prefix = local_epic_prefix(context["indexPath"])
        if existing_prefix != prefix:
            findings.append({
                "code": "epic_prefix_mismatch",
                "severity": "fail",
                "message": f"Existing local document index uses epic prefix {existing_prefix}, not {prefix}.",
            })
            return findings, [], []

    missing_excludes = ensure_local_excludes(context["excludePath"], dry_run=dry_run)
    for path, template in candidates:
        if path.exists():
            preserved.append(str(path))
            continue
        created.append(str(path))
        if not dry_run:
            write_new_file(path, rendered[path])
    for directory in [context["docsRoot"] / "epics", context["docsRoot"] / "research"]:
        if directory.exists():
            preserved.append(str(directory))
        else:
            created.append(str(directory))
            if not dry_run:
                directory.mkdir(parents=True, exist_ok=False)

    if missing_excludes:
        findings.append({
            "code": "local_excludes_added" if not dry_run else "local_excludes_planned",
            "severity": "pass",
            "message": "Local Git exclusions protect the canonical local-document paths.",
            "patterns": missing_excludes,
        })
    return findings, created, preserved


def command_docs_init(args):
    context = local_docs_context(args.project_root)
    findings, created, preserved = initialize_local_docs(args, context, args.epic_prefix)
    return local_docs_payload(
        args,
        context,
        findings,
        epicPrefix=args.epic_prefix.upper(),
        dryRun=args.dry_run,
        created=created,
        preserved=preserved,
        excludePath=str(context["excludePath"]),
    )


def command_docs_ensure(args):
    context = local_docs_context(args.project_root)
    path_findings = local_docs_path_findings(context)
    if any(finding.get("severity") == "fail" for finding in path_findings):
        return local_docs_payload(args, context, path_findings, mode="default-on", materialized=False, created=[], preserved=[])
    if local_docs_opted_out(context):
        return local_docs_payload(
            args,
            context,
            [{
                "code": "local_document_profile_opted_out",
                "severity": "pass",
                "message": f"Project opted out of default local documents through {context['optOutPath']}; no files were created.",
            }],
            mode="opted-out",
            materialized=False,
            created=[],
            preserved=[],
        )

    all_paths_exist = all(path.exists() for path in [context["policyPath"], context["docsRoot"], context["indexPath"]])
    if all_paths_exist:
        findings = local_docs_validation_findings(context, require_profile=True)
        return local_docs_payload(
            args,
            context,
            findings,
            mode="default-on",
            materialized=True,
            created=[],
            preserved=[],
        )

    prefix = args.epic_prefix or (local_epic_prefix(context["indexPath"]) if context["indexPath"].is_file() else inferred_epic_prefix(context))
    findings, created, preserved = initialize_local_docs(args, context, prefix)
    if not args.dry_run and not any(finding.get("severity") == "fail" for finding in findings):
        findings.extend(local_docs_validation_findings(context, require_profile=True))
    return local_docs_payload(
        args,
        context,
        findings,
        mode="default-on",
        materialized=not args.dry_run,
        epicPrefix=prefix.upper(),
        dryRun=args.dry_run,
        created=created,
        preserved=preserved,
        excludePath=str(context["excludePath"]),
    )


def command_docs_disable(args):
    context = local_docs_context(args.project_root)
    findings = local_docs_path_findings(context)
    changed = False
    tracked = tracked_local_doc_paths(context["primaryRoot"])
    if tracked:
        findings.append({
            "code": "tracked_local_document_collision",
            "severity": "fail",
            "message": "Refusing to change the local-document mode because local-document paths are already tracked.",
            "paths": tracked,
        })
    if not findings and not context["optOutPath"].exists():
        write_new_file(context["optOutPath"], "# Gauntlet local-document profile disabled.\n")
        changed = True
    if context["optOutPath"].exists() and not context["optOutPath"].is_symlink() and context["optOutPath"].is_file():
        findings.append({
            "code": "local_document_profile_disabled",
            "severity": "pass",
            "message": f"Default local documents are disabled for this project through {context['optOutPath']}.",
        })
    return local_docs_payload(args, context, findings, mode="opted-out", changed=changed)


def command_docs_enable(args):
    context = local_docs_context(args.project_root)
    findings = local_docs_path_findings(context)
    changed = False
    if not any(finding.get("severity") == "fail" for finding in findings) and context["optOutPath"].is_file():
        context["optOutPath"].unlink()
        changed = True
    if not any(finding.get("severity") == "fail" for finding in findings):
        findings.append({
            "code": "local_document_profile_enabled",
            "severity": "pass",
            "message": "Default local documents are enabled for this project; files will be materialized on first covered document task.",
        })
    return local_docs_payload(args, context, findings, mode="default-on", changed=changed)


def command_docs_check(args):
    context = local_docs_context(args.project_root)
    opted_out = local_docs_opted_out(context)
    findings = local_docs_validation_findings(context)
    materialized = any(path.exists() for path in [context["policyPath"], context["docsRoot"], context["indexPath"]])
    if opted_out:
        findings.append({
            "code": "local_document_profile_opted_out",
            "severity": "pass",
            "message": f"Project opted out of default local documents through {context['optOutPath']}.",
        })
    elif materialized:
        findings.append({
            "code": "local_document_profile_materialized",
            "severity": "pass",
            "message": "Default local documents are materialized in the primary worktree.",
        })
    else:
        findings.append({
            "code": "local_document_profile_default_active",
            "severity": "pass",
            "message": "Default local documents are active and will be materialized lazily on the first covered document task.",
        })
    duplicates = []
    if not opted_out and materialized:
        for worktree in context["worktrees"][1:]:
            for relative in ["doc_org.md", "local-docs"]:
                candidate = worktree / relative
                if candidate.exists():
                    duplicates.append(str(candidate))
    if duplicates:
        findings.append({
            "code": "linked_worktree_canonical_copy",
            "severity": "fail",
            "message": "Linked worktrees contain alternate canonical local-document paths.",
            "paths": duplicates,
        })
    return local_docs_payload(args, context, findings, checked=True, mode="opted-out" if opted_out else "default-on", materialized=materialized)


def local_epic_prefix(index_path):
    if not index_path.is_file():
        raise RuntimeError(f"Local document index does not exist: {index_path}")
    match = re.search(r"^Epic prefix:\s*`([^`]+)`\s*$", index_path.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise RuntimeError(f"Local document index does not declare an epic prefix: {index_path}")
    return match.group(1)


def epic_title_slug(title):
    slug = re.sub(r"[^A-Z0-9]+", "_", title.upper()).strip("_")
    return slug[:64] or "UNTITLED"


def valid_epic_title(title):
    return (
        bool(title.strip()) and len(title) <= 120
        and not any(character in title for character in "\n\r|[]()<>`\\")
    )


def allocated_epic_numbers(context, prefix):
    pattern = re.compile(rf"\b{re.escape(prefix)}-(\d{{3}})\b")
    numbers = {int(match) for match in pattern.findall(context["indexPath"].read_text(encoding="utf-8"))}
    epics_root = context["docsRoot"] / "epics"
    if epics_root.exists():
        for path in epics_root.rglob("*.md"):
            if path.is_file() and not path.is_symlink():
                numbers.update(int(match) for match in pattern.findall(path.read_text(encoding="utf-8")))
    return numbers


def existing_prd_path(context, supplied):
    candidate = Path(supplied).expanduser()
    if not candidate.is_absolute():
        candidate = context["docsRoot"] / candidate
    candidate = candidate.absolute()
    epics_root = (context["docsRoot"] / "epics").resolve()
    resolved = candidate.resolve()
    try:
        resolved.relative_to(epics_root)
    except ValueError as exc:
        raise RuntimeError("An appended PRD must be inside local-docs/epics.") from exc
    current = candidate
    while current != context["docsRoot"]:
        if current.is_symlink():
            raise RuntimeError(f"An appended PRD path must not use symlinks: {candidate}")
        current = current.parent
    if not candidate.is_file():
        raise RuntimeError(f"An appended PRD must already exist: {candidate}")
    return candidate


def command_docs_epic_create(args):
    context = local_docs_context(args.project_root)
    if local_docs_opted_out(context):
        findings = local_docs_path_findings(context) + [{
            "code": "local_document_profile_opted_out",
            "severity": "fail",
            "message": f"Project opted out of default local documents through {context['optOutPath']}; run docs enable before creating an Epic.",
        }]
    elif all(path.exists() for path in [context["policyPath"], context["docsRoot"], context["indexPath"]]):
        findings = local_docs_validation_findings(context, require_profile=True)
    else:
        findings, _, _ = initialize_local_docs(args, context, inferred_epic_prefix(context))
        if not any(finding.get("severity") == "fail" for finding in findings):
            findings.extend(local_docs_validation_findings(context, require_profile=True))
    if findings:
        return local_docs_payload(args, context, findings)
    if not valid_epic_title(args.title):
        findings.append({
            "code": "invalid_epic_title",
            "severity": "fail",
            "message": "Epic title must be one non-empty line, at most 120 characters, without Markdown link or control delimiters.",
        })
        return local_docs_payload(args, context, findings)
    prefix = local_epic_prefix(context["indexPath"])
    if not re.fullmatch(r"[A-Z][A-Z0-9]{1,11}", prefix):
        raise RuntimeError(f"Local document index has an invalid epic prefix: {prefix}")
    epics_root = context["docsRoot"] / "epics"
    existing = allocated_epic_numbers(context, prefix)
    number = args.number if args.number is not None else ((max(existing) + 1) if existing else 1)
    if number < 1 or number > 999:
        findings.append({"code": "invalid_epic_number", "severity": "fail", "message": "Epic number must be between 001 and 999."})
        return local_docs_payload(args, context, findings)
    sequence = f"{number:03d}"
    if number in existing:
        findings.append({"code": "epic_id_exists", "severity": "fail", "message": f"Epic ID already exists: {prefix}-{sequence}"})
        return local_docs_payload(args, context, findings)
    epic_root = epics_root / sequence
    if not args.prd and epic_root.exists():
        findings.append({"code": "epic_exists", "severity": "fail", "message": f"Epic folder already exists: {epic_root}"})
        return local_docs_payload(args, context, findings)

    index_text = context["indexPath"].read_text(encoding="utf-8")
    marker = "<!-- EPICS -->"
    if marker not in index_text:
        raise RuntimeError(f"Local document index is missing its epic insertion marker: {context['indexPath']}")
    date = datetime.now().astimezone().date().isoformat()
    epic_id = f"{prefix}-{sequence}"
    section = render_local_doc_template("EPIC_SECTION.md.tmpl", {
        "EPIC_ID": epic_id,
        "TITLE": args.title,
    })
    prd_path = existing_prd_path(context, args.prd) if args.prd else epic_root / f"{sequence}_{epic_title_slug(args.title)}_PRD.md"
    prd_before = prd_path.read_text(encoding="utf-8") if args.prd else None
    try:
        if args.prd:
            separator = "" if prd_before.endswith("\n\n") else ("\n" if prd_before.endswith("\n") else "\n\n")
            atomic_write_text(prd_path, prd_before + separator + section.rstrip() + "\n")
        else:
            epic_root.mkdir(parents=True)
            for child in ["prompts", "research", "decisions", "runs"]:
                (epic_root / child).mkdir()
            write_new_file(prd_path, render_local_doc_template("EPIC_PRD.md.tmpl", {
                "TITLE": args.title,
                "DATE": date,
                "EPIC_SECTION": section.rstrip(),
            }))
        relative = prd_path.relative_to(context["docsRoot"])
        row = f"| `{epic_id}` | [{args.title}]({relative.as_posix()}) | PRD | Proposed | {date} | None | None | Not implemented | Not verified |\n"
        atomic_write_text(context["indexPath"], index_text.replace(marker, row + marker, 1))
    except Exception:
        if args.prd and prd_before is not None:
            atomic_write_text(prd_path, prd_before)
        elif epic_root.exists():
            shutil.rmtree(epic_root)
        raise
    return local_docs_payload(args, context, findings, epicId=epic_id, epicRoot=str(prd_path.parent), prdPath=str(prd_path), appended=bool(args.prd))


def payload_key_is_sensitive(key):
    normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
    return normalized in SENSITIVE_PAYLOAD_KEYS or any(fragment in normalized for fragment in SENSITIVE_PAYLOAD_FRAGMENTS)


def hash_payload_value(value, salt):
    if isinstance(value, list):
        return [hash_payload_value(item, salt) for item in value]
    if isinstance(value, dict):
        return local_hash(json.dumps(value, sort_keys=True), salt)
    return local_hash(value, salt)


def sanitize_payload(payload, salt):
    if not isinstance(payload, dict):
        return {}
    sanitized = {}
    for key, value in payload.items():
        normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
        if normalized == "command_label":
            if isinstance(value, str) and value in SAFE_COMMAND_LABELS:
                sanitized[key] = value
            else:
                sanitized[f"{key}_hash"] = local_hash(value, salt)
            continue
        if payload_key_is_sensitive(key) and isinstance(value, (int, float, bool)):
            sanitized[key] = value
            continue
        if payload_key_is_sensitive(key) or (isinstance(value, str) and has_secret(value)):
            suffix = "hashes" if isinstance(value, list) else "hash"
            sanitized[f"{key}_{suffix}"] = hash_payload_value(value, salt)
            continue
        if isinstance(value, dict):
            sanitized[key] = sanitize_payload(value, salt)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_payload(item, salt) if isinstance(item, dict)
                else ("[REDACTED_SECRET]" if isinstance(item, str) and has_secret(item) else item)
                for item in value
            ]
        elif isinstance(value, str):
            sanitized[key] = redact_secrets(value)
        else:
            sanitized[key] = value
    return sanitized


def analytics_event(project_root, event_type, run_id, payload=None, agent="codex", gauntlet_version="2.0.2", created_at=None):
    root = Path(project_root).resolve()
    salt = local_salt(root)
    repo_root = git_root(root) or str(root)
    branch = branch_name(root) or "detached"
    return {
        "schema_version": ANALYTICS_SCHEMA_VERSION,
        "event_id": uuid.uuid4().hex,
        "run_id": run_id or uuid.uuid4().hex,
        "event_type": event_type,
        "created_at": created_at or utc_timestamp(),
        "project_hash": local_hash(str(root), salt),
        "repo_hash": local_hash(repo_root, salt),
        "branch_hash": local_hash(branch, salt),
        "agent": agent,
        "gauntlet_version": gauntlet_version,
        "payload": sanitize_payload(payload or {}, salt),
    }


def append_analytics_event(project_root, event_type, run_id, payload=None, agent="codex", gauntlet_version="2.0.2", path=None, dry_run=False, created_at=None):
    root = Path(project_root).resolve()
    event = analytics_event(root, event_type, run_id, payload, agent, gauntlet_version, created_at=created_at)
    output_path = analytics_events_path(root, path)
    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
    return event, output_path


def read_analytics_events(path):
    path = Path(path)
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def confidence_label(baseline_runs, candidate_runs):
    sample = min(baseline_runs, candidate_runs)
    if sample == 0:
        return "no claim"
    if sample < 6:
        return "anecdotal"
    if sample < 20:
        return "directional"
    return "strong signal"


def event_cohort(event):
    payload = event.get("payload") or {}
    return payload.get("cohort") or event.get("gauntlet_version")


def event_segment_key(event):
    payload = event.get("payload") or {}
    return (
        payload.get("mode", "unknown"),
        payload.get("depth", "unknown"),
        payload.get("proof_scope", "unknown"),
        payload.get("task_type", "unknown"),
    )


def parse_event_time(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def seconds_between(start, end):
    if not start or not end:
        return None
    return int((end - start).total_seconds())


def duration_summary(values):
    clean = [value for value in values if value is not None and value >= 0]
    total = sum(clean)
    return {
        "count": len(clean),
        "total": total,
        "average": round(total / len(clean), 2) if clean else 0,
    }


def first_event_time(events, event_type):
    for event in events:
        if event.get("event_type") == event_type:
            return parse_event_time(event.get("created_at"))
    return None


def cohort_timing_summary(events, stale_wait_seconds=86400):
    by_run = {}
    for event in events:
        by_run.setdefault(event.get("run_id") or "unknown", []).append(event)

    calendar_spans = []
    active_planning = []
    human_review_latencies = []
    long_review_gaps = 0
    autonomous_eligible = 0
    autonomous_completed = 0

    for run_events in by_run.values():
        ordered = sorted(run_events, key=lambda event: event.get("created_at", ""))
        run_start = first_event_time(ordered, "run_started")
        implementation_start = first_event_time(ordered, "implementation_started")
        calendar_spans.append(seconds_between(run_start, implementation_start))

        active_seconds = 0
        for event in ordered:
            event_time = parse_event_time(event.get("created_at"))
            if implementation_start and event_time and event_time > implementation_start:
                continue
            if event.get("event_type") not in {"mode_selected", "plan_created", "plan_revised"}:
                continue
            value = (event.get("payload") or {}).get("active_agent_seconds")
            if isinstance(value, (int, float)):
                active_seconds += int(value)
        if active_seconds:
            active_planning.append(active_seconds)

        pending_reviews = []
        for event in ordered:
            if event.get("event_type") == "human_review_requested":
                pending_reviews.append(parse_event_time(event.get("created_at")))
            elif event.get("event_type") == "human_review_completed" and pending_reviews:
                requested_at = pending_reviews.pop(0)
                latency = seconds_between(requested_at, parse_event_time(event.get("created_at")))
                if latency is not None and latency >= 0:
                    human_review_latencies.append(latency)
                    if latency > stale_wait_seconds:
                        long_review_gaps += 1

        if any(
            event.get("event_type") == "annotation_added"
            and (event.get("payload") or {}).get("autonomous_eligible") is True
            for event in ordered
        ):
            autonomous_eligible += 1
        if any(
            event.get("event_type") == "run_completed"
            and (event.get("payload") or {}).get("autonomous_completed") is True
            for event in ordered
        ):
            autonomous_completed += 1

    return {
        "calendarPlanningSpanSeconds": duration_summary(calendar_spans),
        "activeAgentPlanningSeconds": duration_summary(active_planning),
        "humanReviewLatencySeconds": duration_summary(human_review_latencies),
        "humanReviewLongGapCount": long_review_gaps,
        "autonomousEligibleRuns": autonomous_eligible,
        "autonomousCompletedRuns": autonomous_completed,
    }


def cohort_summary(events, stale_wait_seconds=86400):
    run_ids = {event.get("run_id") for event in events if event.get("run_id")}
    completed = [event for event in events if event.get("event_type") == "run_completed"]
    verified = [
        event
        for event in completed
        if (event.get("payload") or {}).get("verified") is True
    ]
    event_counts = {}
    for event in events:
        event_type = event.get("event_type", "unknown")
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
    return {
        "runs": len(run_ids),
        "events": len(events),
        "runCompleted": len(completed),
        "verifiedCompleted": len(verified),
        "eventCounts": event_counts,
        "timing": cohort_timing_summary(events, stale_wait_seconds=stale_wait_seconds),
    }


def segment_summaries(baseline_events, candidate_events):
    rows = {}
    for label, events in [("baselineCount", baseline_events), ("candidateCount", candidate_events)]:
        for event in events:
            key = event_segment_key(event)
            rows.setdefault(key, {"baselineCount": 0, "candidateCount": 0})
            rows[key][label] += 1
    summaries = []
    for (mode, depth, proof_scope, task_type), counts in sorted(rows.items()):
        summaries.append({
            "mode": mode,
            "depth": depth,
            "proofScope": proof_scope,
            "taskType": task_type,
            **counts,
        })
    return summaries


def display_path(root, path):
    path = Path(path)
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def heading_key(line):
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None
    hashes, _, title = stripped.partition(" ")
    if not title or not set(hashes) <= {"#"}:
        return None
    key = re.sub(r"[^a-z0-9]+", " ", title.strip().rstrip("#").lower()).strip()
    return len(hashes), key


def markdown_sections(text):
    sections = {}
    current = None
    for line in text.splitlines():
        parsed = heading_key(line)
        if parsed:
            _, current = parsed
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    return {key: "\n".join(lines).strip() for key, lines in sections.items()}


def find_section(sections, aliases):
    normalized = {re.sub(r"[^a-z0-9]+", " ", alias.lower()).strip() for alias in aliases}
    for key, value in sections.items():
        if key in normalized:
            return value
    return None


def first_nonempty_line(text, fallback="None supplied."):
    for line in (text or "").splitlines():
        clean = line.strip().lstrip("-").strip()
        if clean:
            return clean
    return fallback


def section_bullets(text):
    items = []
    for line in (text or "").splitlines():
        clean = line.strip()
        if clean.startswith("- "):
            items.append(clean[2:].strip())
    if items:
        return items
    return [first_nonempty_line(text)] if (text or "").strip() else []


def archive_summary_from_sections(sections):
    explicit = find_section(sections, ARCHIVE_SUMMARY_ALIASES)
    if explicit:
        return [redact_secrets(item) for item in section_bullets(explicit)[:10]]

    bullets = []
    goal = first_nonempty_line(find_section(sections, ["goal"]) or "", "")
    if goal:
        bullets.append(redact_secrets(goal))
    scope = section_bullets(find_section(sections, ["scope"]) or "")
    bullets.extend(redact_secrets(item) for item in scope[:4])
    verification = section_bullets(find_section(sections, ["verification", "proof"]) or "")
    if verification:
        bullets.append("Verification expected: " + "; ".join(redact_secrets(item) for item in verification[:2]))
    return bullets[:10]


def archive_summary_from_content(path):
    if not path:
        return None, [{"code": "missing_archive_summary_content", "severity": "fail", "message": "Archive requires PR changelog or closeout content with an Archive Summary."}]
    path = Path(path)
    if not path.exists():
        return None, [{"code": "missing_archive_summary_content", "severity": "fail", "message": f"Archive summary content file does not exist: {path}."}]
    text = read_text(path)
    sections = markdown_sections(text)
    raw_summary = find_section(sections, ARCHIVE_SUMMARY_ALIASES)
    if not raw_summary:
        return None, [{"code": "missing_archive_summary", "severity": "fail", "message": f"No Archive Summary section found in {path}."}]
    if has_secret(raw_summary):
        return None, [{"code": "secret_like_archive_summary", "severity": "fail", "message": "Archive Summary contains secret-like content; redact it before archive."}]
    bullets = [redact_secrets(item) for item in section_bullets(raw_summary)[:10]]
    return {"source": "content", "path": str(path), "bullets": bullets}, []


def parse_followups(text):
    followups = []
    lines = (text or "").splitlines()
    index = 0
    while index < len(lines):
        if lines[index].strip().lower() != "follow-up captured:":
            index += 1
            continue
        block = {}
        index += 1
        while index < len(lines):
            line = lines[index].strip()
            if not line:
                break
            if line.lower() == "follow-up captured:":
                index -= 1
                break
            match = re.match(r"-\s*([^:]+):\s*(.*)", line)
            if match:
                key = re.sub(r"[^a-z0-9]+", "_", match.group(1).lower()).strip("_")
                block[key] = match.group(2).strip()
            index += 1
        if block:
            followups.append(block)
        index += 1
    return followups


def add_finding(payload, code, severity, message, **details):
    finding = {
        "code": code,
        "severity": severity,
        "message": message,
    }
    finding.update(details)
    payload.setdefault("findings", []).append(finding)


def status_for(payload):
    status = "pass"
    for finding in payload.get("findings", []):
        severity = finding.get("severity", "warn")
        if STATUS_ORDER[severity] > STATUS_ORDER[status]:
            status = severity
    return status


def memory_lint_payload(path):
    root = Path.cwd().resolve()
    path = Path(path)
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "path": str(path),
        "findings": [],
        "sections": {},
    }
    if not path.exists():
        add_finding(payload, "missing_memory_file", "fail", f"Implementation Memory file does not exist: {path}")
        payload["status"] = status_for(payload)
        return payload

    text = read_text(path)
    sections = markdown_sections(text)
    found = {}
    for code, aliases in SECTION_REQUIRED:
        value = find_section(sections, aliases)
        found[code] = bool(value)
        if not value:
            add_finding(
                payload,
                "missing_memory_section",
                "fail",
                f"Implementation Memory is missing required section: {aliases[0]}.",
            )
    if has_secret(text):
        add_finding(
            payload,
            "secret_like_memory_content",
            "fail",
            "Implementation Memory contains secret-like content; redact it before using workflow helpers.",
        )
    payload["sections"] = found
    payload["path"] = display_path(root, path)
    payload["status"] = status_for(payload)
    return payload


def pr_for_changelog(repo):
    result = gh([
        "pr",
        "view",
        "--json",
        "number,state,mergedAt,url,title,baseRefName,headRefName,statusCheckRollup",
    ], cwd=repo)
    if result.returncode != 0:
        return None, result.stderr.strip() or result.stdout.strip()
    return json.loads(result.stdout), None


def markdown_list(items, empty="- None."):
    if not items:
        return empty
    return "\n".join(f"- {item}" for item in items)


def build_changelog_markdown(source_path, sections, pr, followups, findings):
    goal = find_section(sections, ["goal"]) or ""
    scope = find_section(sections, ["scope"]) or ""
    archive_summary = archive_summary_from_sections(sections)
    source_files = section_bullets(find_section(sections, [
        "source-of-truth files",
        "source of truth files",
        "source files",
    ]) or "")
    verification = section_bullets(find_section(sections, ["verification", "proof"]) or "")
    stale = find_section(sections, [
        "stale context warning",
        "stale-context warning",
        "stale context",
    ]) or "GitHub, branch, and thread state can change after generation."

    if pr:
        number = pr.get("number")
        url = pr.get("url") or ""
        label = f"[#{number}]({url})" if number and url else f"#{number or 'unknown'}"
        pr_rows = [f"| {label} | {pr.get('state', 'UNKNOWN')} | {redact_secrets(pr.get('title') or 'Untitled PR')} |"]
    else:
        pr_rows = ["| Cannot verify | Unknown | No current PR metadata available. |"]

    followup_lines = []
    for followup in followups:
        topic = redact_secrets(followup.get("topic", "Untitled follow-up"))
        strength = redact_secrets(followup.get("strength", "unknown strength"))
        why = redact_secrets(followup.get("why_it_matters", "No rationale supplied."))
        opener = redact_secrets(followup.get("suggested_opener", "No opener supplied."))
        followup_lines.append(f"- {topic} (`{strength}`): {why} Suggested opener: {opener}")

    cannot_verify = [
        finding["message"]
        for finding in findings
        if finding.get("severity") in {"warn", "review", "fail"}
    ]
    return "\n".join([
        "# PR Changelog",
        "",
        f"Source: `{source_path}`",
        "",
        "## Implementation Summary",
        "",
        first_nonempty_line(redact_secrets(goal)),
        "",
        "## Archive Summary",
        "",
        markdown_list(archive_summary, empty="- Cannot verify chat-level changes from CLI metadata alone. Supply an agent-authored Archive Summary in the PR changelog or closeout content."),
        "",
        "## Scope",
        "",
        redact_secrets(scope or "None supplied."),
        "",
        "## PRs",
        "",
        "| PR | State | Title |",
        "| --- | --- | --- |",
        *pr_rows,
        "",
        "## Source Files",
        "",
        markdown_list([redact_secrets(item) for item in source_files]),
        "",
        "## Verification Expected",
        "",
        markdown_list([redact_secrets(item) for item in verification]),
        "",
        "## Follow-Ups",
        "",
        markdown_list(followup_lines),
        "",
        "## Stale Context Warning",
        "",
        redact_secrets(stale.strip()),
        "",
        "## Cannot Verify",
        "",
        markdown_list(cannot_verify),
        "",
    ])


def load_merge_handoff(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def handoff_finding(code, message):
    return {"code": code, "severity": "fail", "message": message}


def validate_merge_handoff(data):
    findings = []
    if not isinstance(data, dict):
        return [handoff_finding("invalid_handoff", "Merge handoff must be a JSON object.")]
    missing = sorted(REQUIRED_HANDOFF_FIELDS - set(data))
    for field in missing:
        findings.append(handoff_finding("missing_handoff_field", f"Merge handoff is missing: {field}."))
    if data.get("schemaVersion") != "1.0":
        findings.append(handoff_finding("unsupported_handoff_schema", "Merge handoff schemaVersion must be 1.0."))

    title = data.get("title")
    if not isinstance(title, str) or not re.fullmatch(r"[^:\n]+: [^\n]+", title.strip()):
        findings.append(handoff_finding("invalid_handoff_title", "Title must use '<area>: <behavioral outcome>'."))

    problem = data.get("problem")
    if not isinstance(problem, dict):
        findings.append(handoff_finding("invalid_handoff_problem", "problem must be an object."))
    else:
        for field in ["context", "impact"]:
            if not isinstance(problem.get(field), str) or not problem[field].strip():
                findings.append(handoff_finding("missing_problem_framing", f"problem.{field} must be non-empty."))

    solution = data.get("solution")
    if not isinstance(solution, dict):
        findings.append(handoff_finding("invalid_handoff_solution", "solution must be an object."))
    else:
        if not isinstance(solution.get("outcome"), str) or not solution["outcome"].strip():
            findings.append(handoff_finding("missing_solution_outcome", "solution.outcome must be non-empty."))
        for field in ["invariants", "preserved", "nonGoals"]:
            value = solution.get(field, [])
            if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
                findings.append(handoff_finding("invalid_solution_list", f"solution.{field} must be a list of non-empty strings."))

    changelog = data.get("changelog")
    if not isinstance(changelog, str) or not changelog.strip():
        findings.append(handoff_finding("missing_changelog_entry", "changelog must be non-empty."))
    elif "\n" in changelog or "\r" in changelog:
        findings.append(handoff_finding("multiline_changelog_entry", "changelog must be a single line."))

    testing = data.get("testing")
    if not isinstance(testing, list) or not testing:
        findings.append(handoff_finding("missing_testing_evidence", "testing must contain at least one reported check."))
    else:
        for index, item in enumerate(testing, 1):
            if not isinstance(item, dict):
                findings.append(handoff_finding("invalid_testing_evidence", f"testing item {index} must be an object."))
                continue
            for field in ["command", "result", "proves"]:
                if not isinstance(item.get(field), str) or not item[field].strip():
                    findings.append(handoff_finding("invalid_testing_evidence", f"testing item {index}.{field} must be non-empty."))

    security_risk = data.get("securityRisk")
    if security_risk is not None and (not isinstance(security_risk, str) or not security_risk.strip()):
        findings.append(handoff_finding("invalid_security_risk", "securityRisk must be null or a non-empty string."))
    if has_secret(json.dumps(data, sort_keys=True)):
        findings.append(handoff_finding("secret_like_handoff", "Merge handoff contains secret-like content."))
    return findings


def render_pr_body(data):
    solution = data["solution"]
    solution_parts = [solution["outcome"].strip()]
    for label, field in [("Invariants", "invariants"), ("Preserved", "preserved"), ("Non-goals", "nonGoals")]:
        items = solution.get(field, [])
        if items:
            solution_parts.extend(["", f"{label}:", *[f"- {item.strip()}" for item in items]])

    testing = [
        f"- `{item['command'].strip()}` — **{item['result'].strip().upper()}** — {item['proves'].strip()}"
        for item in data["testing"]
    ]
    lines = [
        "## Problem",
        "",
        data["problem"]["context"].strip(),
        "",
        data["problem"]["impact"].strip(),
        "",
        "## Solution",
        "",
        *solution_parts,
        "",
        "## Changelog",
        "",
        f"- {data['changelog'].strip()}",
        "",
        "## Testing",
        "",
        *testing,
    ]
    if data.get("securityRisk"):
        lines.extend(["", "## Security / Risk", "", data["securityRisk"].strip()])
    return "\n".join(lines).rstrip() + "\n"


def ensure_unreleased_changelog(changelog_path, entry):
    changelog_path = Path(changelog_path)
    bullet = f"- {entry.strip()}"
    if changelog_path.exists():
        original = changelog_path.read_text(encoding="utf-8")
    else:
        original = ""
    if any(line.rstrip() == bullet for line in original.splitlines()):
        return False

    if not original.strip():
        updated = f"# Changelog\n\n## Unreleased\n\n{bullet}\n"
    else:
        lines = original.rstrip().splitlines()
        heading_index = next(
            (index for index, line in enumerate(lines) if line.strip().lower() == "## unreleased"),
            None,
        )
        if heading_index is None:
            updated = original.rstrip() + f"\n\n## Unreleased\n\n{bullet}\n"
        else:
            insert_at = heading_index + 1
            while insert_at < len(lines) and not lines[insert_at].strip():
                insert_at += 1
            lines[insert_at:insert_at] = [bullet, ""]
            updated = "\n".join(lines).rstrip() + "\n"
    changelog_path.write_text(updated, encoding="utf-8")
    return True


def command_merge_prepare(args):
    repo = Path(args.git_root).resolve()
    handoff_path = Path(args.handoff)
    if not handoff_path.is_absolute():
        handoff_path = repo / handoff_path
    body_path = Path(args.body_output)
    if not body_path.is_absolute():
        body_path = repo / body_path
    changelog_path = repo / "CHANGELOG.md"
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "findings": [],
        "title": None,
        "bodyPath": str(body_path),
        "changelogPath": str(changelog_path),
        "changelogEntry": None,
        "changelogChanged": False,
    }
    if not handoff_path.is_file():
        add_finding(payload, "missing_handoff_file", "fail", f"Merge handoff does not exist: {handoff_path}")
    else:
        try:
            data = load_merge_handoff(handoff_path)
        except (json.JSONDecodeError, OSError) as error:
            add_finding(payload, "invalid_handoff_file", "fail", str(error))
            data = None
        if data is not None:
            payload["findings"].extend(validate_merge_handoff(data))
            payload["title"] = data.get("title")
            payload["changelogEntry"] = data.get("changelog")
            if not payload["findings"]:
                body_path.parent.mkdir(parents=True, exist_ok=True)
                body_path.write_text(render_pr_body(data), encoding="utf-8")
                payload["changelogChanged"] = ensure_unreleased_changelog(changelog_path, data["changelog"])
    payload["status"] = status_for(payload)
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def repository_merge_settings(repo):
    result = gh([
        "repo",
        "view",
        "--json",
        "defaultBranchRef,mergeCommitAllowed,squashMergeAllowed,rebaseMergeAllowed",
    ], repo)
    if result.returncode != 0:
        return None, result.stderr.strip() or result.stdout.strip()
    return json.loads(result.stdout), None


def merge_method_from_settings(settings):
    if not settings:
        return "merge"
    if settings.get("mergeCommitAllowed"):
        return "merge"
    if settings.get("squashMergeAllowed"):
        return "squash"
    if settings.get("rebaseMergeAllowed"):
        return "rebase"
    return None


def merge_input_path(repo, path):
    path = Path(path)
    return path if path.is_absolute() else repo / path


def load_merge_inputs(args, payload):
    repo = Path(args.git_root).resolve()
    handoff_path = merge_input_path(repo, args.handoff)
    body_path = merge_input_path(repo, args.body)
    data = None
    body = ""
    if git(["rev-parse", "--is-inside-work-tree"], repo).returncode != 0:
        add_finding(payload, "git_root_not_repo", "fail", f"Not a git repository: {repo}")
    if not handoff_path.is_file():
        add_finding(payload, "missing_handoff_file", "fail", f"Merge handoff does not exist: {handoff_path}")
    else:
        try:
            data = load_merge_handoff(handoff_path)
        except (json.JSONDecodeError, OSError) as error:
            add_finding(payload, "invalid_handoff_file", "fail", str(error))
        if data is not None:
            payload["findings"].extend(validate_merge_handoff(data))
    if not body_path.is_file():
        add_finding(payload, "missing_pr_body", "fail", f"PR body does not exist: {body_path}")
    else:
        body = body_path.read_text(encoding="utf-8")
    payload["handoffPath"] = str(handoff_path)
    payload["bodyPath"] = str(body_path)
    return repo, data, body


def add_existing_pr_blockers(payload, pr):
    if not pr:
        return
    if pr.get("state") != "OPEN":
        add_finding(payload, "pull_request_not_open", "review", f"Pull request is {pr.get('state')}.")
    if pr.get("isDraft"):
        add_finding(payload, "pull_request_is_draft", "review", "Pull request is still a draft.")
    if pr.get("reviewDecision") in {"CHANGES_REQUESTED", "REVIEW_REQUIRED"}:
        add_finding(payload, "pull_request_review_pending", "review", f"Pull request review decision is {pr.get('reviewDecision')}.")
    if pr.get("mergeable") not in {"MERGEABLE", "UNKNOWN"}:
        add_finding(payload, "pull_request_not_mergeable", "review", f"Pull request mergeable state is {pr.get('mergeable')}.")
    check_status, check_message = checks_state(pr.get("statusCheckRollup", []))
    if check_status == "failing":
        add_finding(payload, "pull_request_checks_failing", "review", check_message)


def collect_merge_state(git_root, handoff, body):
    repo = Path(git_root).resolve()
    branch = branch_name(repo)
    settings, settings_error = repository_merge_settings(repo)
    pr, pr_error = current_pr(repo)
    default_branch = ((settings or {}).get("defaultBranchRef") or {}).get("name") or "main"
    default_counts = None
    remote_default = f"origin/{default_branch}"
    if git(["rev-parse", "--verify", remote_default], repo).returncode == 0:
        counts = git(["rev-list", "--left-right", "--count", f"{remote_default}...HEAD"], repo)
        if counts.returncode == 0 and len(counts.stdout.split()) == 2:
            behind, ahead = [int(value) for value in counts.stdout.split()]
            default_counts = {"behind": behind, "ahead": ahead}
    return {
        "repo": str(repo),
        "branch": branch,
        "dirty": dirty_paths(repo),
        "handoff": handoff,
        "body": body,
        "settings": settings,
        "settingsError": settings_error,
        "defaultBranch": default_branch,
        "defaultCounts": default_counts,
        "pr": pr,
        "prError": pr_error,
    }


def build_merge_plan(state):
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "findings": [],
        "mergePlan": {"canMerge": False, "actions": [], "blockers": [], "warnings": []},
        "branch": state.get("branch"),
        "defaultBranch": state.get("defaultBranch"),
        "pr": state.get("pr"),
    }
    handoff = state.get("handoff") or {}
    branch = state.get("branch") or ""
    if not branch or branch == state.get("defaultBranch") or branch in {"main", "master"}:
        add_finding(payload, "task_branch_required", "fail", "Merge automation requires a named task branch, not the default branch.")
    if state.get("dirty"):
        add_finding(payload, "uncommitted_merge_work", "fail", "Commit or preserve all merge work before creating the PR: " + ", ".join(state["dirty"][:4]))

    if handoff:
        expected_body = render_pr_body(handoff)
        if state.get("body") != expected_body:
            add_finding(payload, "pr_body_out_of_date", "fail", "PR body does not match the current merge handoff; run merge prepare again.")
        bullet = f"- {handoff.get('changelog', '').strip()}"
        changelog_path = Path(state["repo"]) / "CHANGELOG.md"
        changelog = changelog_path.read_text(encoding="utf-8") if changelog_path.is_file() else ""
        if not bullet.strip("- ") or sum(line.rstrip() == bullet for line in changelog.splitlines()) != 1:
            add_finding(payload, "changelog_mismatch", "fail", "CHANGELOG.md must contain the exact PR changelog entry once.")

    counts = state.get("defaultCounts")
    if counts and counts.get("behind"):
        add_finding(payload, "branch_behind_default", "review", f"Task branch is behind origin/{state['defaultBranch']} by {counts['behind']} commit(s).")

    if state.get("settingsError"):
        add_finding(payload, "merge_settings_unverified", "warn", "Could not verify repository merge settings; using merge-commit fallback.")
    merge_method = merge_method_from_settings(state.get("settings"))
    if not merge_method:
        add_finding(payload, "no_allowed_merge_method", "fail", "Repository reports no allowed pull-request merge method.")
    add_existing_pr_blockers(payload, state.get("pr"))

    payload["status"] = status_for(payload)
    pr = state.get("pr")
    pr_action = {
        "type": "gh_pr_edit" if pr else "gh_pr_create",
        "prNumber": pr.get("number") if pr else None,
    }
    actions = [
        {"type": "git_push", "branch": branch},
        pr_action,
        {"type": "gh_pr_checks_watch", "prNumber": pr.get("number") if pr else None},
        {"type": "gh_pr_merge", "prNumber": pr.get("number") if pr else None, "mergeMethod": merge_method},
        {"type": "delete_remote_branch", "branch": branch},
        {"type": "verify_default_branch", "branch": state.get("defaultBranch")},
    ]
    blockers = [item["code"] for item in payload["findings"] if item["severity"] in {"review", "fail"}]
    warnings = [item["code"] for item in payload["findings"] if item["severity"] == "warn"]
    payload["mergePlan"] = {
        "canMerge": payload["status"] in {"pass", "warn"},
        "actions": actions if payload["status"] in {"pass", "warn"} else [],
        "blockers": blockers,
        "warnings": warnings,
    }
    return payload


def build_merge_payload(args):
    shell = {"schemaVersion": "1.0", "status": "pass", "findings": []}
    repo, data, body = load_merge_inputs(args, shell)
    if shell["findings"]:
        shell["status"] = status_for(shell)
        shell["mergePlan"] = {"canMerge": False, "actions": [], "blockers": [item["code"] for item in shell["findings"]], "warnings": []}
        return shell
    state = collect_merge_state(repo, data, body)
    return build_merge_plan(state)


def refreshed_pr_is_mergeable(payload, pr):
    if not pr:
        add_finding(payload, "pull_request_missing_after_publish", "fail", "Could not find the pull request after publishing it.")
        return False
    before = len(payload["findings"])
    add_existing_pr_blockers(payload, pr)
    check_status, check_message = checks_state(pr.get("statusCheckRollup", []))
    if check_status != "passing":
        add_finding(payload, f"pull_request_checks_{check_status}", "fail", check_message)
    return len(payload["findings"]) == before


def wait_for_pr_checks(repo, timeout_seconds=60, poll_seconds=2):
    deadline = time.monotonic() + timeout_seconds
    last_error = None
    while True:
        pr, last_error = current_pr(repo)
        if pr and pr.get("statusCheckRollup"):
            return pr, None
        if time.monotonic() >= deadline:
            return pr, last_error or f"No PR status checks were reported within {timeout_seconds} seconds."
        time.sleep(poll_seconds)


def delete_remote_branch(repo, branch, git_runner=None):
    git_runner = git_runner or git
    probe = git_runner(["ls-remote", "--exit-code", "--heads", "origin", branch], repo)
    if probe.returncode == 2:
        return subprocess.CompletedProcess(probe.args, 0, probe.stdout, probe.stderr)
    if probe.returncode != 0:
        return probe

    deletion = git_runner(["push", "origin", "--delete", branch], repo)
    if deletion.returncode == 0:
        return deletion

    confirmation = git_runner(["ls-remote", "--exit-code", "--heads", "origin", branch], repo)
    if confirmation.returncode == 2:
        return subprocess.CompletedProcess(deletion.args, 0, deletion.stdout, deletion.stderr)
    return deletion


def execute_merge_plan(payload, git_root, handoff_path, body_path):
    repo = Path(git_root).resolve()
    executed = []
    branch = payload.get("branch")
    default_branch = payload.get("defaultBranch") or "main"
    handoff = load_merge_handoff(handoff_path)
    pr = payload.get("pr")
    for action in payload.get("mergePlan", {}).get("actions", []):
        action_type = action["type"]
        if action_type == "git_push":
            result = git(["push", "-u", "origin", f"HEAD:{branch}"], repo)
        elif action_type == "gh_pr_create":
            result = gh([
                "pr", "create", "--title", handoff["title"], "--body-file", str(body_path),
                "--base", default_branch, "--head", branch,
            ], repo)
        elif action_type == "gh_pr_edit":
            result = gh(["pr", "edit", str(pr.get("number")), "--title", handoff["title"], "--body-file", str(body_path)], repo)
        elif action_type == "gh_pr_checks_watch":
            pr, checks_error = wait_for_pr_checks(repo)
            if checks_error:
                add_finding(payload, "pull_request_checks_missing", "fail", checks_error)
                break
            action["prNumber"] = pr.get("number")
            result = gh(["pr", "checks", str(pr.get("number")), "--watch"], repo)
        elif action_type == "gh_pr_merge":
            pr, _ = current_pr(repo)
            if not refreshed_pr_is_mergeable(payload, pr):
                break
            action["prNumber"] = pr.get("number")
            method = action.get("mergeMethod") or "merge"
            result = gh(["pr", "merge", str(pr.get("number")), f"--{method}"], repo)
        elif action_type == "delete_remote_branch":
            result = delete_remote_branch(repo, branch)
        elif action_type == "verify_default_branch":
            fetch = git(["fetch", "origin", default_branch], repo)
            if fetch.returncode != 0:
                result = fetch
            else:
                result = git(["merge-base", "--is-ancestor", "HEAD", f"origin/{default_branch}"], repo)
        else:
            add_finding(payload, "unknown_merge_action", "fail", f"Unknown merge action: {action_type}")
            break
        if result.returncode != 0:
            add_finding(payload, f"{action_type}_failed", "fail", result.stderr.strip() or result.stdout.strip() or f"{action_type} failed")
            break
        executed.append(action)

    payload["executedActions"] = executed
    payload["pr"] = pr
    payload["status"] = status_for(payload)
    return payload


def command_merge_plan(args):
    payload = build_merge_payload(args)
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_merge_execute(args):
    payload = build_merge_payload(args)
    if payload["status"] not in {"pass", "warn"}:
        print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    repo = Path(args.git_root).resolve()
    handoff_path = merge_input_path(repo, args.handoff)
    body_path = merge_input_path(repo, args.body)
    payload = execute_merge_plan(payload, repo, handoff_path, body_path)
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def repo_relative_scope_path(repo, raw_path):
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = repo / candidate
    candidate = candidate.resolve()
    try:
        return candidate.relative_to(repo).as_posix()
    except ValueError:
        return None


def closeout_fail(payload, code, message):
    add_finding(payload, code, "fail", message)
    payload["status"] = status_for(payload)
    payload["remainingAppActions"] = []
    return payload


def closeout_install_command(repo, args, check=False):
    command = [str(repo / "scripts" / "install.sh"), "--target", args.install_target]
    if check:
        command.append("--check")
    if args.instructions_reviewed:
        command.append("--instructions-reviewed")
    command.extend(["--response-style", args.response_style])
    if args.install_target == "codex":
        command.extend(["--codex-preferences", args.codex_preferences])
    return command


def command_closeout_execute(args):
    repo = Path(args.git_root).resolve()
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "findings": [],
        "commit": None,
        "merge": None,
        "install": None,
        "archive": None,
        "remainingAppActions": [],
    }
    if git(["rev-parse", "--is-inside-work-tree"], repo).returncode != 0:
        closeout_fail(payload, "git_root_not_repo", f"Not a git repository: {repo}")
        print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]

    handoff_path = merge_input_path(repo, args.handoff)
    if not handoff_path.is_file():
        closeout_fail(payload, "missing_handoff_file", f"Merge handoff does not exist: {handoff_path}")
        print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    try:
        handoff = load_merge_handoff(handoff_path)
    except (json.JSONDecodeError, OSError) as error:
        closeout_fail(payload, "invalid_handoff_file", str(error))
        print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    payload["findings"].extend(validate_merge_handoff(handoff))
    if payload["findings"]:
        payload["status"] = status_for(payload)
        print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]

    archive_summary, archive_findings = archive_summary_from_content(args.content)
    for finding in archive_findings:
        add_finding(payload, finding["code"], finding["severity"], finding["message"])
    parsed_title = parse_thread_title(args.title)
    parsed_suggestion = parse_thread_title(args.suggested_title) if args.suggested_title else None
    if parsed_title["format"] != "current" and (not parsed_suggestion or parsed_suggestion["format"] != "current"):
        add_finding(
            payload,
            "invalid_archive_title",
            "fail",
            "Provide a current 'p#: four word goal' title or a valid --suggested-title before closeout begins.",
        )
    if payload["findings"]:
        payload["status"] = status_for(payload)
        print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    payload["archiveSummary"] = archive_summary

    settings, settings_error = repository_merge_settings(repo)
    default_branch = ((settings or {}).get("defaultBranchRef") or {}).get("name") or "main"
    task_branch = branch_name(repo)
    if settings_error:
        add_finding(payload, "merge_settings_unverified", "warn", "Could not verify repository merge settings; using the default branch reported by local convention.")
    if not task_branch or task_branch in {default_branch, "main", "master"}:
        closeout_fail(payload, "task_branch_required", "Closeout execute requires a named task branch, not the default branch.")
        print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]

    scoped_paths = []
    for raw_path in args.stage:
        relative = repo_relative_scope_path(repo, raw_path)
        if relative is None:
            closeout_fail(payload, "stage_path_outside_repo", f"Stage path is outside the repository: {raw_path}")
        elif relative not in scoped_paths:
            scoped_paths.append(relative)
    if payload["status"] == "fail":
        print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]

    existing_dirty = dirty_paths(repo)
    unscoped_dirty = sorted(set(existing_dirty) - set(scoped_paths))
    if unscoped_dirty:
        closeout_fail(payload, "unscoped_dirty_work", "Closeout refused unrelated or unlisted work: " + ", ".join(unscoped_dirty[:6]))
        print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]

    if args.install_target != "none":
        install_env = os.environ.copy()
        if args.agent_home:
            install_env["GAUNTLET_AGENT_HOME"] = str(Path(args.agent_home).expanduser())
        install_preflight = subprocess.run(
            closeout_install_command(repo, args, check=True),
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=install_env,
        )
        payload["install"] = {
            "target": args.install_target,
            "applied": False,
            "preflight": install_preflight.returncode == 0,
        }
        if install_preflight.returncode != 0:
            closeout_fail(
                payload,
                "local_install_preflight_failed",
                install_preflight.stderr.strip() or install_preflight.stdout.strip(),
            )
            print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]

    body_handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix="-gauntlet-pr.md")
    body_path = Path(body_handle.name)
    body_handle.write(render_pr_body(handoff))
    body_handle.close()
    try:
        ensure_unreleased_changelog(repo / "CHANGELOG.md", handoff["changelog"])
        commit_scope = [*scoped_paths, "CHANGELOG.md"]
        dirty_after_prepare = dirty_paths(repo)
        unscoped_after_prepare = sorted(set(dirty_after_prepare) - set(commit_scope))
        if unscoped_after_prepare:
            closeout_fail(payload, "unscoped_dirty_work", "Closeout preparation produced or found unlisted work: " + ", ".join(unscoped_after_prepare[:6]))
            print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]

        add_result = git(["add", "--", *commit_scope], repo)
        if add_result.returncode != 0:
            closeout_fail(payload, "git_add_failed", add_result.stderr.strip() or add_result.stdout.strip())
            print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]
        cached = git(["diff", "--cached", "--name-only"], repo)
        cached_paths = [line.strip() for line in cached.stdout.splitlines() if line.strip()]
        if cached.returncode != 0:
            closeout_fail(payload, "git_diff_cached_failed", cached.stderr.strip() or cached.stdout.strip())
            print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]
        unexpected_cached = sorted(set(cached_paths) - set(commit_scope))
        if unexpected_cached:
            closeout_fail(payload, "unscoped_staged_work", "Closeout refused staged paths outside the explicit scope: " + ", ".join(unexpected_cached[:6]))
            print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]
        if cached_paths:
            commit_result = git(["commit", "-m", handoff["title"]], repo)
            if commit_result.returncode != 0:
                closeout_fail(payload, "git_commit_failed", commit_result.stderr.strip() or commit_result.stdout.strip())
                print_payload(payload, args.json)
                return EXIT_CODES[payload["status"]]
            commit_oid = git(["rev-parse", "HEAD"], repo).stdout.strip()
            payload["commit"] = {"oid": commit_oid, "subject": handoff["title"], "paths": cached_paths, "created": True}
        else:
            fetch_default = git(["fetch", "origin", default_branch], repo)
            committed = git(["diff", "--name-only", f"origin/{default_branch}...HEAD"], repo) if fetch_default.returncode == 0 else fetch_default
            committed_paths = [line.strip() for line in committed.stdout.splitlines() if line.strip()]
            tip_subject = git(["log", "-1", "--pretty=%s"], repo).stdout.strip()
            unexpected_committed = sorted(set(committed_paths) - set(commit_scope))
            if committed.returncode != 0 or not committed_paths or tip_subject != handoff["title"] or unexpected_committed:
                details = ", ".join(unexpected_committed[:6]) if unexpected_committed else "no matching scoped closeout commit"
                closeout_fail(payload, "closeout_resume_mismatch", "Closeout cannot safely resume this branch: " + details)
                print_payload(payload, args.json)
                return EXIT_CODES[payload["status"]]
            commit_oid = git(["rev-parse", "HEAD"], repo).stdout.strip()
            payload["commit"] = {"oid": commit_oid, "subject": tip_subject, "paths": committed_paths, "created": False}

        merge_args = argparse.Namespace(git_root=repo, handoff=handoff_path, body=body_path, json=True)
        merge_payload = build_merge_payload(merge_args)
        if merge_payload["status"] in {"pass", "warn"}:
            merge_payload = execute_merge_plan(merge_payload, repo, handoff_path, body_path)
        payload["merge"] = merge_payload
        payload["findings"].extend(merge_payload.get("findings", []))
        payload["status"] = status_for(payload)
        if payload["status"] not in {"pass", "warn"}:
            payload["remainingAppActions"] = []
            print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]

        fetch = git(["fetch", "origin", default_branch], repo)
        switch = git(["switch", default_branch], repo) if fetch.returncode == 0 else fetch
        pull = git(["pull", "--ff-only", "origin", default_branch], repo) if switch.returncode == 0 else switch
        delete_local = git(["branch", "-d", task_branch], repo) if pull.returncode == 0 else pull
        for code, result in [
            ("fetch_default_failed", fetch),
            ("switch_default_failed", switch),
            ("pull_default_failed", pull),
            ("delete_local_branch_failed", delete_local),
        ]:
            if result.returncode != 0:
                closeout_fail(payload, code, result.stderr.strip() or result.stdout.strip())
                print_payload(payload, args.json)
                return EXIT_CODES[payload["status"]]

        if args.install_target != "none":
            install_env = os.environ.copy()
            if args.agent_home:
                install_env["GAUNTLET_AGENT_HOME"] = str(Path(args.agent_home).expanduser())
            install_result = subprocess.run(
                closeout_install_command(repo, args),
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=install_env,
            )
            payload["install"] = {
                "target": args.install_target,
                "applied": install_result.returncode == 0,
                "preflight": True,
            }
            if install_result.returncode != 0:
                closeout_fail(payload, "local_install_failed", install_result.stderr.strip() or install_result.stdout.strip())
                print_payload(payload, args.json)
                return EXIT_CODES[payload["status"]]
        else:
            payload["install"] = {"target": "none", "applied": False}

        archive_args = argparse.Namespace(
            title=args.title,
            suggested_title=args.suggested_title,
            content=args.content,
            git_root=repo,
            require_kickoff=False,
            require_assumptions=False,
            archive_anyway=False,
            confirm_git_risk=False,
            allow_dirty=[],
            json=True,
        )
        archive_payload = build_archive_payload(archive_args)
        if archive_payload["status"] in {"pass", "warn"}:
            archive_payload = execute_archive_actions(archive_payload, repo)
        payload["archive"] = archive_payload
        payload["findings"].extend(archive_payload.get("findings", []))
        payload["status"] = status_for(payload)
        payload["remainingAppActions"] = archive_payload.get("remainingAppActions", []) if payload["status"] in {"pass", "warn"} else []
        print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    finally:
        body_path.unlink(missing_ok=True)


def dirty_paths(repo):
    status = git(["status", "--porcelain", "--untracked-files=all"], repo)
    if status.returncode != 0:
        raise RuntimeError(status.stderr.strip() or "git status failed")
    return [line[3:] if len(line) > 3 else line for line in status.stdout.splitlines() if line.strip()]


def branch_name(repo):
    branch = git(["branch", "--show-current"], repo)
    if branch.returncode != 0:
        return ""
    return branch.stdout.strip()


def upstream_counts(repo):
    upstream = git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], repo)
    if upstream.returncode != 0:
        return None
    counts = git(["rev-list", "--left-right", "--count", "@{u}...HEAD"], repo)
    if counts.returncode != 0:
        raise RuntimeError(counts.stderr.strip() or "could not compare upstream")
    parts = counts.stdout.strip().split()
    if len(parts) != 2:
        raise RuntimeError(f"unexpected upstream count output: {counts.stdout}")
    return {
        "upstream": upstream.stdout.strip(),
        "behind": int(parts[0]),
        "ahead": int(parts[1]),
    }


def run_checker(args):
    cmd = [str(CHECKER), "--archive", "--json"]
    if args.title:
        cmd += ["--title", args.title]
    if getattr(args, "suggested_title", None):
        cmd += ["--suggested-title", args.suggested_title]
    if getattr(args, "content", None):
        cmd += ["--content", str(args.content)]
    if getattr(args, "require_kickoff", False):
        cmd.append("--require-kickoff")
    if getattr(args, "require_assumptions", False):
        cmd.append("--require-assumptions")
    if getattr(args, "archive_anyway", False):
        cmd.append("--archive-anyway")

    result = run_cmd(cmd, cwd=ROOT)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"workflow etiquette checker did not emit JSON: {error}\n{result.stdout}\n{result.stderr}") from error


def checks_state(status_rollup):
    if not status_rollup:
        return "missing", "No PR status checks were reported."

    pending = []
    failing = []
    for check in status_rollup:
        typename = check.get("__typename")
        if typename == "CheckRun":
            status = check.get("status")
            conclusion = check.get("conclusion")
            name = check.get("name", "check")
            if status != "COMPLETED":
                pending.append(name)
            elif conclusion not in PASSING_CHECK_CONCLUSIONS:
                failing.append(f"{name}={conclusion}")
        else:
            state = check.get("state") or check.get("conclusion") or check.get("status")
            name = check.get("context") or check.get("name") or "status"
            if state not in PASSING_STATUS_STATES:
                failing.append(f"{name}={state}")

    if failing:
        return "failing", "PR checks are failing: " + ", ".join(failing[:4])
    if pending:
        return "pending", "PR checks are still pending: " + ", ".join(pending[:4])
    return "passing", "PR checks passed."


def current_pr(repo):
    result = gh([
        "pr",
        "view",
        "--json",
        "number,state,isDraft,mergeable,mergedAt,statusCheckRollup,url,baseRefName,headRefName,reviewDecision",
    ], cwd=repo)
    if result.returncode != 0:
        return None, result.stderr.strip() or result.stdout.strip()
    return json.loads(result.stdout), None


def github_archive_actions(repo, payload, args):
    actions = []
    if not repo:
        return actions

    repo = Path(repo).resolve()
    inside = git(["rev-parse", "--is-inside-work-tree"], repo)
    if inside.returncode != 0:
        return actions

    allow_dirty = {str(Path(path)) for path in getattr(args, "allow_dirty", [])}
    dirty = dirty_paths(repo)
    if dirty:
        unexpected_dirty = [path for path in dirty if path not in allow_dirty]
        if not unexpected_dirty:
            add_finding(
                payload,
                "dirty_worktree_allowlisted",
                "warn",
                "Dirty files are explicitly allowlisted for this archive: " + ", ".join(dirty[:4]) + ".",
            )
        elif getattr(args, "confirm_git_risk", False):
            add_finding(
                payload,
                "git_risk_confirmed",
                "warn",
                "User confirmed archive can proceed even though git has unpreserved work: "
                + ", ".join(unexpected_dirty[:4])
                + ".",
            )
        else:
            add_finding(
                payload,
                "dirty_worktree",
                "review",
                "Worktree has uncommitted or untracked files: " + ", ".join(unexpected_dirty[:4]) + ".",
            )
            add_finding(
                payload,
                "git_risk_confirmation_required",
                "review",
                "Ask the user to confirm whether this unpreserved work should be left out of git before archiving.",
            )
            return actions

    branch = branch_name(repo)
    counts = upstream_counts(repo)
    if counts and counts["behind"]:
        add_finding(
            payload,
            "branch_behind_upstream",
            "review",
            f"Branch is behind {counts['upstream']} by {counts['behind']} commit(s).",
        )
        return actions

    defaultish = branch in {"main", "master"}
    if defaultish:
        if counts and counts["ahead"]:
            if getattr(args, "confirm_git_risk", False):
                add_finding(
                    payload,
                    "default_branch_ahead_confirmed",
                    "warn",
                    "User confirmed archive can proceed even though the default branch has unpushed commits.",
                )
            else:
                add_finding(
                    payload,
                    "default_branch_ahead",
                    "review",
                    f"Default branch has {counts['ahead']} unpushed commit(s); push or confirm abandonment before archive.",
                )
                add_finding(
                    payload,
                    "git_risk_confirmation_required",
                    "review",
                    "Ask the user to confirm before archiving with unpushed default-branch commits.",
                )
        return actions

    if counts and counts["ahead"]:
        actions.append({"type": "git_push", "upstream": counts["upstream"], "ahead": counts["ahead"]})
        add_finding(
            payload,
            "branch_push_needed_before_pr_merge",
            "review",
            "Branch has local commits that must be pushed before PR checks can be trusted.",
        )
        return actions

    pr, error = current_pr(repo)
    if not pr:
        if getattr(args, "confirm_git_risk", False):
            add_finding(
                payload,
                "missing_pull_request_confirmed",
                "warn",
                "User confirmed archive can proceed without a merged pull request for this branch.",
            )
            return actions
        add_finding(
            payload,
            "missing_pull_request",
            "review",
            f"No pull request found for branch {branch}: {error or 'unknown gh error'}.",
        )
        add_finding(
            payload,
            "git_risk_confirmation_required",
            "review",
            "Ask the user to confirm before archiving work that is not merged through a PR.",
        )
        return actions

    if pr.get("state") == "MERGED" or pr.get("mergedAt"):
        return actions
    if pr.get("state") != "OPEN":
        add_finding(payload, "pull_request_not_open", "review", f"Pull request is {pr.get('state')}.")
        return actions
    if pr.get("isDraft"):
        add_finding(payload, "pull_request_is_draft", "review", "Pull request is still a draft.")
        return actions
    if pr.get("reviewDecision") in {"CHANGES_REQUESTED", "REVIEW_REQUIRED"}:
        add_finding(
            payload,
            "pull_request_review_pending",
            "review",
            f"Pull request review decision is {pr.get('reviewDecision')}.",
        )
        return actions
    if pr.get("mergeable") not in {"MERGEABLE", "UNKNOWN"}:
        add_finding(payload, "pull_request_not_mergeable", "review", f"Pull request mergeable state is {pr.get('mergeable')}.")
        return actions

    check_status, check_message = checks_state(pr.get("statusCheckRollup", []))
    if check_status != "passing":
        add_finding(payload, f"pull_request_checks_{check_status}", "review", check_message)
        return actions

    actions.append({
        "type": "gh_pr_merge",
        "prNumber": pr.get("number"),
        "url": pr.get("url"),
        "mergeMethod": "merge",
        "deleteBranch": True,
    })
    return actions


def rebuild_archive_plan(payload, git_actions):
    prior_plan = payload.get("archivePlan") or {}
    prior_actions = prior_plan.get("actions") or []
    prefix_actions = []
    for action in prior_actions:
        if action.get("type") not in {"git_push", "archive_thread", "present_archive_summary"}:
            prefix_actions.append(action)

    status = status_for(payload)
    payload["status"] = status
    blockers = [
        finding["code"]
        for finding in payload.get("findings", [])
        if finding.get("severity") in {"review", "fail"}
    ]
    warnings = [
        finding["code"]
        for finding in payload.get("findings", [])
        if finding.get("severity") == "warn"
    ]
    actions = []
    if status in {"pass", "warn"}:
        summary = payload.get("archiveSummary") or {}
        bullets = summary.get("bullets") or []
        actions = [*prefix_actions, *git_actions]
        actions.append({
            "type": "present_archive_summary",
            "heading": "Archive Summary",
            "bullets": bullets,
        })
        actions.append({"type": "archive_thread"})

    payload["archivePlan"] = {
        "canArchive": status in {"pass", "warn"},
        "requiresReview": status in {"review", "fail"},
        "actions": actions,
        "blockers": blockers,
        "warnings": warnings,
    }
    return payload


def build_archive_payload(args):
    original_content = getattr(args, "content", None)
    temporary_content = None
    if original_content and str(original_content) == "-":
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write(sys.stdin.read())
            temporary_content = Path(handle.name)
        args.content = temporary_content

    try:
        payload = run_checker(args)
        summary, findings = archive_summary_from_content(getattr(args, "content", None))
        for finding in findings:
            add_finding(payload, finding["code"], finding["severity"], finding["message"])
        payload["archiveSummary"] = summary or {
            "source": "fallback",
            "bullets": [
                "Cannot verify chat-level changes from CLI metadata alone. Supply the PR changelog or closeout content with an Archive Summary.",
            ],
        }
        git_actions = []
        if status_for(payload) in {"pass", "warn"}:
            git_actions = github_archive_actions(args.git_root, payload, args)
        return rebuild_archive_plan(payload, git_actions)
    finally:
        args.content = original_content
        if temporary_content:
            temporary_content.unlink(missing_ok=True)


def execute_archive_actions(payload, git_root):
    executed = []
    remaining_app = []
    for action in payload.get("archivePlan", {}).get("actions", []):
        action_type = action.get("type")
        if action_type in DEFERRED_AGENT_ACTIONS:
            remaining_app.append(action)
        elif action_type == "git_push":
            result = git(["push"], git_root)
            if result.returncode != 0:
                add_finding(payload, "git_push_failed", "fail", result.stderr.strip() or result.stdout.strip())
                break
            executed.append(action)
        elif action_type == "gh_pr_merge":
            pr_number = str(action.get("prNumber"))
            result = gh(["pr", "merge", pr_number, "--merge", "--delete-branch"], git_root)
            if result.returncode != 0:
                add_finding(payload, "gh_pr_merge_failed", "fail", result.stderr.strip() or result.stdout.strip())
                break
            executed.append(action)
        else:
            add_finding(payload, "unknown_archive_action", "fail", f"Unknown archive action: {action_type}")
            break

    payload["status"] = status_for(payload)
    payload["executedActions"] = executed
    payload["remainingAppActions"] = remaining_app if payload["status"] in {"pass", "warn"} else []
    return payload


def print_payload(payload, as_json):
    if as_json:
        print(json.dumps(payload, indent=2))
        return
    summary = payload.get("archiveSummary") or {}
    bullets = summary.get("bullets") or []
    if bullets:
        print("Archive Summary")
        for bullet in bullets:
            print(f"- {bullet}")
        if payload["status"] in {"pass", "warn"}:
            return
        print()
    print(f"Gauntlet: {payload['status']}")
    for finding in payload.get("findings", []):
        print(f"- [{finding['severity']}] {finding['code']}: {finding['message']}")
    for action in payload.get("archivePlan", {}).get("actions", []):
        print(f"- action: {action.get('type')}")


def command_archive_plan(args):
    payload = build_archive_payload(args)
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_archive_execute(args):
    payload = build_archive_payload(args)
    if payload["status"] not in {"pass", "warn"}:
        print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    payload = execute_archive_actions(payload, args.git_root)
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_followup_note(args):
    lines = [
        "Follow-up captured:",
        f"- Topic: {args.topic}",
        f"- Strength: {args.strength}",
        f"- Why it matters: {args.why}",
        f"- Context already known: {args.context}",
        f"- Suggested opener: {args.opener}",
    ]
    print("\n".join(lines))
    return 0


def command_memory_lint(args):
    payload = memory_lint_payload(args.path)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Implementation Memory lint: {payload['status']}")
        for finding in payload.get("findings", []):
            print(f"- [{finding['severity']}] {finding['code']}: {finding['message']}")
    return EXIT_CODES[payload["status"]]


def command_changelog_pr(args):
    source_paths = [path for path in [args.accepted_spec, args.plan] if path]
    legacy_memory = getattr(args, "implementation_memory", None)
    if not source_paths and legacy_memory:
        source_paths = [legacy_memory]
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "source": str(source_paths[0]) if source_paths else "",
        "sources": [str(path) for path in source_paths],
        "findings": [],
        "pr": None,
        "markdown": "",
    }
    if not source_paths:
        add_finding(payload, "missing_changelog_source", "fail", "Provide --accepted-spec and/or --plan.")
    missing_paths = [Path(path) for path in source_paths if not Path(path).exists()]
    for path in missing_paths:
        add_finding(payload, "missing_changelog_source", "fail", f"Changelog source does not exist: {path}")
    if legacy_memory and not args.accepted_spec and not args.plan:
        add_finding(payload, "legacy_implementation_memory", "warn", "--implementation-memory is deprecated; use --accepted-spec and --plan.")
    if payload["findings"] and any(item["severity"] == "fail" for item in payload["findings"]):
        payload["status"] = status_for(payload)
        payload["markdown"] = build_changelog_markdown(", ".join(str(path) for path in source_paths) or "missing", {}, None, [], payload["findings"])
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(payload["markdown"])
        return EXIT_CODES[payload["status"]]

    paths = [Path(path) for path in source_paths]
    text = "\n\n".join(read_text(path) for path in paths)
    sections = markdown_sections(text)
    followups = parse_followups(text)

    repo = Path(args.git_root).resolve()
    inside = git(["rev-parse", "--is-inside-work-tree"], repo)
    pr = None
    if inside.returncode != 0:
        add_finding(payload, "git_root_not_repo", "warn", f"Cannot verify PR metadata because {repo} is not a git repo.")
    else:
        pr, error = pr_for_changelog(repo)
        if pr:
            payload["pr"] = {
                "number": pr.get("number"),
                "state": pr.get("state"),
                "url": pr.get("url"),
                "title": pr.get("title"),
                "baseRefName": pr.get("baseRefName"),
                "headRefName": pr.get("headRefName"),
                "mergedAt": pr.get("mergedAt"),
            }
        else:
            add_finding(payload, "cannot_verify_pr_metadata", "warn", f"Could not verify current PR metadata: {error or 'unknown gh error'}.")

    payload["status"] = status_for(payload)
    source_display = ", ".join(display_path(Path.cwd().resolve(), path) for path in paths)
    payload["markdown"] = build_changelog_markdown(source_display, sections, pr, followups, payload["findings"])
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload["markdown"], encoding="utf-8")
        payload["output"] = str(output)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(payload["markdown"])
    return EXIT_CODES[payload["status"]]


def payload_from_args(args):
    payload = {}
    if getattr(args, "payload_file", None):
        path = Path(args.payload_file)
        if not path.exists():
            raise RuntimeError(f"Payload file does not exist: {path}")
        payload.update(json.loads(read_text(path)))
    if getattr(args, "payload_json", None):
        payload.update(json.loads(args.payload_json))
    return payload


def print_json_or_brief(payload, as_json, brief):
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        print(brief)


def command_analytics_emit(args):
    payload = payload_from_args(args)
    event, path = append_analytics_event(
        args.project_root,
        args.event_type,
        args.run_id,
        payload,
        agent=args.agent,
        gauntlet_version=args.gauntlet_version,
        path=args.path,
        dry_run=args.dry_run,
        created_at=args.created_at,
    )
    result = {
        "schemaVersion": "1.0",
        "status": "pass",
        "localPrivate": True,
        "path": str(path),
        "dryRun": args.dry_run,
        "event": event,
        "findings": [],
    }
    if args.event_type not in ANALYTICS_EVENT_TYPES:
        add_finding(
            result,
            "unknown_event_type",
            "warn",
            f"Event type is not in Gauntlet's known local analytics vocabulary: {args.event_type}.",
        )
        result["status"] = status_for(result)
    print_json_or_brief(result, args.json, f"Analytics event recorded: {args.event_type}")
    return EXIT_CODES[result["status"]]


def command_analytics_closeout(args):
    attempt_memory_expired = 0
    if args.expire_attempt_memory:
        memory_path = attempt_memory_path(args.project_root, args.attempt_memory_path)
        entries = read_attempt_entries(memory_path)
        kept = [
            entry for entry in entries
            if args.run_id not in set(entry.get("runIds") or [])
        ]
        attempt_memory_expired = len(entries) - len(kept)
        write_attempt_entries(memory_path, kept)

    summary = {
        "filesChanged": args.file_changed,
        "filesChangedCount": len(args.file_changed),
        "proofCompleted": args.proof,
        "testsCompletedCount": len(args.proof),
        "unresolvedRisks": args.risk,
        "attemptMemoryExpired": attempt_memory_expired,
    }
    event_payload = {
        "files_changed": args.file_changed,
        "files_changed_count": len(args.file_changed),
        "proof_commands": args.proof,
        "proof_completed_count": len(args.proof),
        "risk_notes": args.risk,
        "unresolved_risk_count": len(args.risk),
        "attempt_memory_expired": attempt_memory_expired,
    }
    event, path = append_analytics_event(
        args.project_root,
        "closeout_completed",
        args.run_id,
        event_payload,
        agent=args.agent,
        gauntlet_version=args.gauntlet_version,
        path=args.path,
    )
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "localPrivate": True,
        "path": str(path),
        "summary": summary,
        "event": event,
        "actions": [],
        "attemptMemoryExpired": attempt_memory_expired,
        "findings": [],
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("Gauntlet Closeout Facts")
        print(f"- Files changed: {summary['filesChangedCount']}")
        for item in summary["filesChanged"]:
            print(f"  - {item}")
        print(f"- Proof/tests completed: {summary['testsCompletedCount']}")
        for item in summary["proofCompleted"]:
            print(f"  - {item}")
        print("- Unresolved risks:")
        for item in summary["unresolvedRisks"] or ["None reported."]:
            print(f"  - {item}")
        print(f"- Attempt memory expired: {attempt_memory_expired}")
    return 0


def command_analytics_summarize(args):
    path = analytics_events_path(args.project_root, args.path)
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "localPrivate": True,
        "path": str(path),
        "baseline": {"label": args.baseline},
        "candidate": {"label": args.candidate},
        "confidence": "no claim",
        "segments": [],
        "findings": [],
    }
    if not args.baseline or not args.candidate:
        add_finding(
            payload,
            "missing_baseline_or_candidate",
            "review",
            "Provide both --baseline and --candidate so Gauntlet does not guess which cohorts to compare.",
        )
        payload["status"] = status_for(payload)
        print_json_or_brief(payload, args.json, "Need --baseline and --candidate to summarize impact.")
        return EXIT_CODES[payload["status"]]

    events = read_analytics_events(path)
    baseline_events = [event for event in events if event_cohort(event) == args.baseline]
    candidate_events = [event for event in events if event_cohort(event) == args.candidate]
    baseline_summary = cohort_summary(baseline_events, stale_wait_seconds=args.stale_wait_seconds)
    candidate_summary = cohort_summary(candidate_events, stale_wait_seconds=args.stale_wait_seconds)
    payload["baseline"].update(baseline_summary)
    payload["candidate"].update(candidate_summary)
    payload["confidence"] = confidence_label(baseline_summary["runs"], candidate_summary["runs"])
    payload["segments"] = segment_summaries(baseline_events, candidate_events)
    if payload["confidence"] == "no claim":
        add_finding(
            payload,
            "insufficient_comparable_samples",
            "warn",
            "One or both cohorts have no comparable local runs.",
        )
    elif payload["confidence"] == "anecdotal":
        payload["note"] = "Counts are useful for review but too small for a strong public claim."
    payload["status"] = status_for(payload)

    derived = analytics_dir(args.project_root) / "derived-summary.json"
    derived.parent.mkdir(parents=True, exist_ok=True)
    derived.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    payload["derivedSummary"] = str(derived)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Analytics summary: {args.baseline} -> {args.candidate} ({payload['confidence']})")
        print(f"- Baseline runs: {baseline_summary['runs']} events: {baseline_summary['events']}")
        print(f"- Candidate runs: {candidate_summary['runs']} events: {candidate_summary['events']}")
    return EXIT_CODES[payload["status"]]


def read_attempt_entries(path):
    path = Path(path)
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def write_attempt_entries(path, entries):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")


def prune_attempt_entries(entries, max_age_days=None, now=None):
    if max_age_days is None:
        return entries
    now_time = parse_event_time(now) if now else datetime.now(timezone.utc)
    if not now_time:
        return entries
    max_age_seconds = max_age_days * 86400
    kept = []
    for entry in entries:
        last_seen = parse_event_time(entry.get("lastSeen"))
        if not last_seen:
            kept.append(entry)
            continue
        age = int((now_time - last_seen).total_seconds())
        if age <= max_age_seconds:
            kept.append(entry)
    return kept


def command_attempt_memory_add(args):
    project_root = Path(args.project_root).resolve()
    salt = local_salt(project_root)
    path = attempt_memory_path(project_root, args.path)
    entries = read_attempt_entries(path)
    fingerprint_hash = local_hash(args.fingerprint, salt)
    now = utc_timestamp()
    found = None
    for entry in entries:
        if entry.get("fingerprintHash") == fingerprint_hash:
            found = entry
            break
    if found:
        found["repeatCount"] = int(found.get("repeatCount", 1)) + 1
        found["lastSeen"] = now
        found["summary"] = redact_secrets(args.summary)
        found["kind"] = args.kind
        run_ids = list(dict.fromkeys([*(found.get("runIds") or []), args.run_id]))
        found["runIds"] = [run_id for run_id in run_ids if run_id]
    else:
        entries.append({
            "schemaVersion": "1.0",
            "kind": args.kind,
            "fingerprintHash": fingerprint_hash,
            "summary": redact_secrets(args.summary),
            "repeatCount": 1,
            "firstSeen": now,
            "lastSeen": now,
            "runIds": [args.run_id] if args.run_id else [],
        })

    entries = prune_attempt_entries(entries, max_age_days=args.max_age_days, now=args.now)
    entries = sorted(entries, key=lambda item: item.get("lastSeen", ""))[-args.max_active:]
    write_attempt_entries(path, entries)
    event, event_path = append_analytics_event(
        project_root,
        "attempt_memory_written",
        args.run_id,
        {
            "kind": args.kind,
            "fingerprint_hash": fingerprint_hash,
            "active_count": len(entries),
        },
        agent=args.agent,
        gauntlet_version=args.gauntlet_version,
        path=args.analytics_path,
    )
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "localPrivate": True,
        "path": str(path),
        "analyticsPath": str(event_path),
        "activeCount": len(entries),
        "entry": next((entry for entry in entries if entry.get("fingerprintHash") == fingerprint_hash), None),
        "event": event,
        "findings": [],
    }
    print_json_or_brief(payload, args.json, f"Attempt memory entries: {len(entries)}")
    return 0


def command_attempt_memory_list(args):
    project_root = Path(args.project_root).resolve()
    path = attempt_memory_path(project_root, args.path)
    entries = read_attempt_entries(path)
    pruned_entries = prune_attempt_entries(entries, max_age_days=args.max_age_days, now=args.now)
    if pruned_entries != entries:
        write_attempt_entries(path, pruned_entries)
    entries = pruned_entries
    event, event_path = append_analytics_event(
        project_root,
        "attempt_memory_read",
        args.run_id,
        {"active_count": len(entries)},
        agent=args.agent,
        gauntlet_version=args.gauntlet_version,
        path=args.analytics_path,
    )
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "localPrivate": True,
        "path": str(path),
        "analyticsPath": str(event_path),
        "activeCount": len(entries),
        "entries": entries,
        "event": event,
        "findings": [],
    }
    print_json_or_brief(payload, args.json, f"Attempt memory entries: {len(entries)}")
    return 0


def followup_from_args(args):
    if args.content:
        if not args.content.exists():
            return {}, [{"code": "missing_followup_file", "severity": "fail", "message": f"Follow-up content file does not exist: {args.content}."}]
        followups = parse_followups(read_text(args.content))
        if followups:
            return followups[0], []
        return {}, [{"code": "missing_followup_block", "severity": "fail", "message": f"No follow-up block found in {args.content}."}]
    required = {
        "topic": args.topic,
        "strength": args.strength,
        "why_it_matters": args.why,
        "context_already_known": args.context,
        "suggested_opener": args.opener,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        return {}, [{"code": "missing_followup_fields", "severity": "fail", "message": "Missing follow-up fields: " + ", ".join(missing) + "."}]
    return required, []


def command_followup_thread(args):
    payload = {
        "schemaVersion": "1.0",
        "status": "pass",
        "findings": [],
        "actions": [],
    }
    parsed_title = parse_thread_title(args.title)
    if parsed_title["format"] == "malformed":
        if parsed_title.get("reason") == "goal_word_count":
            add_finding(
                payload,
                "title_goal_word_count",
                "fail",
                "Thread title goal must contain exactly four whitespace-delimited words; "
                f"found {parsed_title['actualWordCount']}.",
                actualWordCount=parsed_title["actualWordCount"],
                requiredWordCount=parsed_title["requiredWordCount"],
            )
        else:
            add_finding(
                payload,
                "malformed_thread_title",
                "fail",
                "Thread title must use 'p#: four word goal' or 'p#-auto: four word goal'.",
            )

    followup, findings = followup_from_args(args)
    for finding in findings:
        add_finding(payload, finding["code"], finding["severity"], finding["message"])
    if followup and has_secret("\n".join(followup.values())):
        add_finding(
            payload,
            "secret_like_followup_content",
            "fail",
            "Follow-up content contains secret-like text; redact it before creating a thread packet.",
        )

    if payload["findings"]:
        payload["status"] = status_for(payload)
    else:
        source_line = f"Source thread: {args.source_thread}" if args.source_thread else "Source thread: not supplied"
        message = "\n".join([
            followup.get("suggested_opener", ""),
            "",
            "Follow-up captured:",
            f"- Topic: {followup.get('topic', '')}",
            f"- Strength: {followup.get('strength', '')}",
            f"- Why it matters: {followup.get('why_it_matters', '')}",
            f"- Context already known: {followup.get('context_already_known', '')}",
            f"- Suggested opener: {followup.get('suggested_opener', '')}",
            f"- {source_line}",
        ]).strip()
        payload["actions"].append({
            "type": "create_thread",
            "title": args.title,
            "cwd": str(Path(args.cwd).resolve()) if args.cwd else str(Path.cwd().resolve()),
            "message": message,
        })
        payload["status"] = status_for(payload)

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Follow-up thread packet: {payload['status']}")
        for action in payload.get("actions", []):
            print(f"- action: {action['type']} title={action['title']}")
        for finding in payload.get("findings", []):
            print(f"- [{finding['severity']}] {finding['code']}: {finding['message']}")
    return EXIT_CODES[payload["status"]]


def command_diagram_find(args):
    index = ROOT / "docs" / "gauntlet-diagrams" / "index.md"
    matches = []
    if index.exists():
        for line in index.read_text(encoding="utf-8").splitlines():
            if not line.startswith("| `"):
                continue
            if args.query.lower() in line.lower():
                cells = [cell.strip() for cell in line.strip("|").split("|")]
                if len(cells) >= 5:
                    matches.append({
                        "id": cells[0].strip("`"),
                        "title": cells[1],
                        "feature": cells[2].strip("`"),
                        "tags": [tag.strip().strip("`") for tag in cells[3].split(",")],
                        "path": cells[4].strip("`"),
                    })
    payload = {"schemaVersion": "1.0", "status": "pass", "matches": matches}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for match in matches:
            print(f"{match['id']}: {match['path']}")
    return 0


def command_install_verify(args):
    agent_home = Path(args.agent_home).expanduser()
    if not agent_home.is_absolute():
        agent_home = (Path.cwd() / agent_home).absolute()
    findings = []
    def require(path, code):
        if not path.exists():
            findings.append({"code": code, "severity": "fail", "message": f"Missing {path}"})

    require(agent_home / "gauntlet" / "AGENTS.md", "missing_installed_agents")
    require(agent_home / "gauntlet" / "router" / "AGENTS.md", "missing_router_source")
    require(agent_home / "gauntlet" / "router" / "response-style.md", "missing_response_style_source")
    require(agent_home / "gauntlet" / "scripts" / "check-gauntlet-workflow.py", "missing_installed_workflow_check")
    require(agent_home / "gauntlet" / "scripts" / "gauntlet.py", "missing_installed_gauntlet_cli")
    require(agent_home / "gauntlet" / "scripts" / "install-codex-agents.py", "missing_custom_agent_installer")
    require(agent_home / "gauntlet" / "scripts" / "subagent-audit.py", "missing_subagent_audit_exporter")
    require(agent_home / "gauntlet" / "scripts" / "route-codex-agent.py", "missing_custom_agent_router")
    require(agent_home / "gauntlet" / "docs" / "local-documentation.md", "missing_local_documentation_policy")
    require(agent_home / "gauntlet" / "templates" / "local-docs" / "doc_org.md.tmpl", "missing_local_document_template")
    require(agent_home / "skills", "missing_installed_skills")

    installed_router = agent_home / "gauntlet" / "AGENTS.md"
    if installed_router.exists():
        router_text = installed_router.read_text(encoding="utf-8")
        expected_root = str(agent_home / "gauntlet")
        expected_skills = str(agent_home / "skills")
        if any(placeholder in router_text for placeholder in ["{{GAUNTLET_ROOT}}", "{{AGENT_HOME}}", "{{RESPONSE_STYLE}}"]):
            findings.append({"code": "unresolved_router_placeholder", "severity": "fail", "message": "Installed router contains an unresolved path placeholder."})
        if expected_root not in router_text:
            findings.append({"code": "missing_installed_root_path", "severity": "fail", "message": "Installed router lacks the rendered Gauntlet root."})
        if expected_skills not in router_text:
            findings.append({"code": "missing_installed_skills_path", "severity": "fail", "message": "Installed router lacks the rendered skills root."})
        if len(router_text.encode("utf-8")) >= 32768:
            findings.append({"code": "installed_router_too_large", "severity": "fail", "message": "Installed router exceeds the 32 KiB default instruction budget."})

    if args.target == "codex":
        codex_agents = agent_home / "AGENTS.md"
        require(codex_agents, "missing_codex_agents")
        if codex_agents.exists():
            text = codex_agents.read_text(encoding="utf-8")
            if text.count("BEGIN GAUNTLET MANAGED BLOCK") != 1 or text.count("END GAUNTLET MANAGED BLOCK") != 1:
                findings.append({"code": "invalid_codex_managed_block", "severity": "fail", "message": "Codex AGENTS.md must contain exactly one complete Gauntlet managed block."})
            if "Gauntlet Workflow Router" not in text:
                findings.append({"code": "missing_codex_router", "severity": "fail", "message": "Codex AGENTS.md lacks the installed Gauntlet router."})
        source = agent_home / "gauntlet" / "agents" / "codex"
        verifier = agent_home / "gauntlet" / "scripts" / "install-codex-agents.py"
        if source.is_dir() and verifier.is_file():
            result = subprocess.run(
                [sys.executable, str(verifier), "verify", "--source", str(source), "--agent-home", str(agent_home)],
                text=True, capture_output=True,
            )
            if result.returncode:
                findings.append({"code": "invalid_codex_custom_agents", "severity": "fail", "message": result.stderr.strip() or result.stdout.strip()})
    if args.target == "claude":
        claude_md = agent_home / "CLAUDE.md"
        require(claude_md, "missing_claude_md")
        if claude_md.exists():
            text = claude_md.read_text(encoding="utf-8")
            expected_import = f"@{agent_home}/gauntlet/AGENTS.md"
            if "BEGIN GAUNTLET MANAGED BLOCK" not in text:
                findings.append({"code": "missing_claude_managed_block", "severity": "fail", "message": "CLAUDE.md lacks Gauntlet managed block."})
            if expected_import not in text:
                findings.append({"code": "missing_claude_agents_import", "severity": "fail", "message": "CLAUDE.md does not import installed AGENTS.md."})

    payload = {"schemaVersion": "1.0", "status": "pass", "target": args.target, "agentHome": str(agent_home), "findings": findings}
    payload["status"] = status_for(payload)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Install verify: {payload['status']}")
        for finding in findings:
            print(f"- [{finding['severity']}] {finding['code']}: {finding['message']}")
    return EXIT_CODES[payload["status"]]


def add_archive_args(parser):
    parser.add_argument("--title", default=None)
    parser.add_argument("--suggested-title", default=None)
    parser.add_argument("--content", type=Path, default=None)
    parser.add_argument("--git-root", type=Path, default=Path.cwd())
    parser.add_argument("--require-kickoff", action="store_true")
    parser.add_argument("--require-assumptions", action="store_true")
    parser.add_argument("--archive-anyway", action="store_true")
    parser.add_argument("--confirm-git-risk", action="store_true")
    parser.add_argument("--allow-dirty", action="append", default=[])
    parser.add_argument("--json", action="store_true")


def build_parser():
    parser = argparse.ArgumentParser(description="Gauntlet workflow helper CLI.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    archive = subcommands.add_parser("archive", help="Plan or execute archive-safe actions.")
    archive_subcommands = archive.add_subparsers(dest="archive_command", required=True)
    archive_plan = archive_subcommands.add_parser("plan")
    add_archive_args(archive_plan)
    archive_plan.set_defaults(func=command_archive_plan)
    archive_execute = archive_subcommands.add_parser("execute")
    add_archive_args(archive_execute)
    archive_execute.set_defaults(func=command_archive_execute)

    merge = subcommands.add_parser("merge", help="Prepare or execute a contextual pull-request merge.")
    merge_subcommands = merge.add_subparsers(dest="merge_command", required=True)
    merge_prepare = merge_subcommands.add_parser("prepare")
    merge_prepare.add_argument("--git-root", type=Path, default=Path.cwd())
    merge_prepare.add_argument("--handoff", type=Path, required=True)
    merge_prepare.add_argument("--body-output", type=Path, default=Path(".gauntlet/pr-body.md"))
    merge_prepare.add_argument("--json", action="store_true")
    merge_prepare.set_defaults(func=command_merge_prepare)
    for name, func in [("plan", command_merge_plan), ("execute", command_merge_execute)]:
        merge_command = merge_subcommands.add_parser(name)
        merge_command.add_argument("--git-root", type=Path, default=Path.cwd())
        merge_command.add_argument("--handoff", type=Path, required=True)
        merge_command.add_argument("--body", type=Path, default=Path(".gauntlet/pr-body.md"))
        merge_command.add_argument("--json", action="store_true")
        merge_command.set_defaults(func=func)

    closeout = subcommands.add_parser("closeout", help="Commit scoped work, merge it through a PR, install it locally, and plan task archival.")
    closeout_subcommands = closeout.add_subparsers(dest="closeout_command", required=True)
    closeout_execute = closeout_subcommands.add_parser("execute")
    closeout_execute.add_argument("--git-root", type=Path, default=Path.cwd())
    closeout_execute.add_argument("--handoff", type=Path, required=True)
    closeout_execute.add_argument("--stage", action="append", required=True)
    closeout_execute.add_argument("--install-target", choices=["none", "codex", "claude"], default="none")
    closeout_execute.add_argument("--agent-home", default=None)
    closeout_execute.add_argument("--instructions-reviewed", action="store_true")
    closeout_execute.add_argument("--response-style", choices=["gauntlet", "existing"], default="gauntlet")
    closeout_execute.add_argument(
        "--codex-preferences",
        choices=["prompt", "gauntlet", "existing", "skip"],
        default="prompt",
    )
    closeout_execute.add_argument("--title", required=True)
    closeout_execute.add_argument("--suggested-title", default=None)
    closeout_execute.add_argument("--content", type=Path, required=True)
    closeout_execute.add_argument("--json", action="store_true")
    closeout_execute.set_defaults(func=command_closeout_execute)

    install = subcommands.add_parser("install", help="Installed-layout helpers.")
    install_subcommands = install.add_subparsers(dest="install_command", required=True)
    install_verify = install_subcommands.add_parser("verify")
    install_verify.add_argument("--target", choices=["codex", "claude"], required=True)
    install_verify.add_argument("--agent-home", required=True)
    install_verify.add_argument("--json", action="store_true")
    install_verify.set_defaults(func=command_install_verify)

    docs = subcommands.add_parser("docs", help="Manage the default-on canonical local product-document profile.")
    docs_subcommands = docs.add_subparsers(dest="docs_command", required=True)
    docs_init = docs_subcommands.add_parser("init")
    docs_init.add_argument("--project-root", type=Path, default=Path.cwd())
    docs_init.add_argument("--epic-prefix", required=True)
    docs_init.add_argument("--dry-run", action="store_true")
    docs_init.add_argument("--json", action="store_true")
    docs_init.set_defaults(func=command_docs_init)
    docs_ensure = docs_subcommands.add_parser("ensure", help="Materialize the default profile when a covered document task needs it.")
    docs_ensure.add_argument("--project-root", type=Path, default=Path.cwd())
    docs_ensure.add_argument("--epic-prefix", default=None)
    docs_ensure.add_argument("--dry-run", action="store_true")
    docs_ensure.add_argument("--json", action="store_true")
    docs_ensure.set_defaults(func=command_docs_ensure)
    docs_disable = docs_subcommands.add_parser("disable", help="Opt this project out of the default local-document profile.")
    docs_disable.add_argument("--project-root", type=Path, default=Path.cwd())
    docs_disable.add_argument("--json", action="store_true")
    docs_disable.set_defaults(func=command_docs_disable)
    docs_enable = docs_subcommands.add_parser("enable", help="Remove this project's local-document opt-out marker.")
    docs_enable.add_argument("--project-root", type=Path, default=Path.cwd())
    docs_enable.add_argument("--json", action="store_true")
    docs_enable.set_defaults(func=command_docs_enable)
    docs_check = docs_subcommands.add_parser("check")
    docs_check.add_argument("--project-root", type=Path, default=Path.cwd())
    docs_check.add_argument("--json", action="store_true")
    docs_check.set_defaults(func=command_docs_check)
    docs_epic = docs_subcommands.add_parser("epic")
    docs_epic_subcommands = docs_epic.add_subparsers(dest="docs_epic_command", required=True)
    docs_epic_create = docs_epic_subcommands.add_parser("create")
    docs_epic_create.add_argument("--project-root", type=Path, default=Path.cwd())
    docs_epic_create.add_argument("--title", required=True)
    docs_epic_create.add_argument("--number", type=int, default=None)
    docs_epic_create.add_argument("--prd", default=None, help="Append the new Epic to an existing PRD under local-docs/epics.")
    docs_epic_create.add_argument("--json", action="store_true")
    docs_epic_create.set_defaults(func=command_docs_epic_create)

    followup = subcommands.add_parser("followup", help="Follow-up helpers.")
    followup_subcommands = followup.add_subparsers(dest="followup_command", required=True)
    followup_note = followup_subcommands.add_parser("note")
    followup_note.add_argument("--topic", required=True)
    followup_note.add_argument("--strength", choices=["strong follow-up", "follow-up for later"], required=True)
    followup_note.add_argument("--why", required=True)
    followup_note.add_argument("--context", required=True)
    followup_note.add_argument("--opener", required=True)
    followup_note.set_defaults(func=command_followup_note)
    followup_thread = followup_subcommands.add_parser("thread")
    followup_thread.add_argument("--content", type=Path, default=None)
    followup_thread.add_argument("--topic", default=None)
    followup_thread.add_argument("--strength", choices=["strong follow-up", "follow-up for later"], default=None)
    followup_thread.add_argument("--why", default=None)
    followup_thread.add_argument("--context", default=None)
    followup_thread.add_argument("--opener", default=None)
    followup_thread.add_argument("--title", required=True)
    followup_thread.add_argument("--cwd", type=Path, default=None)
    followup_thread.add_argument("--source-thread", default=None)
    followup_thread.add_argument("--json", action="store_true")
    followup_thread.set_defaults(func=command_followup_thread)

    memory = subcommands.add_parser("memory", help="Implementation Memory helpers.")
    memory_subcommands = memory.add_subparsers(dest="memory_command", required=True)
    memory_lint = memory_subcommands.add_parser("lint")
    memory_lint.add_argument("--path", type=Path, required=True)
    memory_lint.add_argument("--json", action="store_true")
    memory_lint.set_defaults(func=command_memory_lint)

    analytics = subcommands.add_parser("analytics", help="Local private analytics helpers.")
    analytics_subcommands = analytics.add_subparsers(dest="analytics_command", required=True)
    analytics_emit = analytics_subcommands.add_parser("emit")
    analytics_emit.add_argument("--project-root", type=Path, default=Path.cwd())
    analytics_emit.add_argument("--path", type=Path, default=None)
    analytics_emit.add_argument("--run-id", default=None)
    analytics_emit.add_argument("--event-type", required=True)
    analytics_emit.add_argument("--created-at", default=None)
    analytics_emit.add_argument("--payload-json", default=None)
    analytics_emit.add_argument("--payload-file", type=Path, default=None)
    analytics_emit.add_argument("--agent", default="codex")
    analytics_emit.add_argument("--gauntlet-version", default="2.0.2")
    analytics_emit.add_argument("--dry-run", action="store_true")
    analytics_emit.add_argument("--json", action="store_true")
    analytics_emit.set_defaults(func=command_analytics_emit)

    analytics_closeout = analytics_subcommands.add_parser("closeout")
    analytics_closeout.add_argument("--project-root", type=Path, default=Path.cwd())
    analytics_closeout.add_argument("--path", type=Path, default=None)
    analytics_closeout.add_argument("--run-id", default=None)
    analytics_closeout.add_argument("--file-changed", action="append", default=[])
    analytics_closeout.add_argument("--proof", action="append", default=[])
    analytics_closeout.add_argument("--risk", action="append", default=[])
    analytics_closeout.add_argument("--attempt-memory-path", type=Path, default=None)
    analytics_closeout.add_argument("--expire-attempt-memory", action="store_true")
    analytics_closeout.add_argument("--agent", default="codex")
    analytics_closeout.add_argument("--gauntlet-version", default="2.0.2")
    analytics_closeout.add_argument("--json", action="store_true")
    analytics_closeout.set_defaults(func=command_analytics_closeout)

    analytics_summarize = analytics_subcommands.add_parser("summarize")
    analytics_summarize.add_argument("--project-root", type=Path, default=Path.cwd())
    analytics_summarize.add_argument("--path", type=Path, default=None)
    analytics_summarize.add_argument("--baseline", default=None)
    analytics_summarize.add_argument("--candidate", default=None)
    analytics_summarize.add_argument("--stale-wait-seconds", type=int, default=86400)
    analytics_summarize.add_argument("--json", action="store_true")
    analytics_summarize.set_defaults(func=command_analytics_summarize)

    attempt_memory = subcommands.add_parser("attempt-memory", help="Bounded local attempt memory helpers.")
    attempt_memory_subcommands = attempt_memory.add_subparsers(dest="attempt_memory_command", required=True)
    attempt_memory_add = attempt_memory_subcommands.add_parser("add")
    attempt_memory_add.add_argument("--project-root", type=Path, default=Path.cwd())
    attempt_memory_add.add_argument("--path", type=Path, default=None)
    attempt_memory_add.add_argument("--analytics-path", type=Path, default=None)
    attempt_memory_add.add_argument("--run-id", default=None)
    attempt_memory_add.add_argument("--kind", choices=["failed_attempt", "proof_failure", "rejected_alternative", "observation"], required=True)
    attempt_memory_add.add_argument("--fingerprint", required=True)
    attempt_memory_add.add_argument("--summary", required=True)
    attempt_memory_add.add_argument("--max-active", type=int, default=50)
    attempt_memory_add.add_argument("--max-age-days", type=int, default=None)
    attempt_memory_add.add_argument("--now", default=None)
    attempt_memory_add.add_argument("--agent", default="codex")
    attempt_memory_add.add_argument("--gauntlet-version", default="2.0.2")
    attempt_memory_add.add_argument("--json", action="store_true")
    attempt_memory_add.set_defaults(func=command_attempt_memory_add)

    attempt_memory_list = attempt_memory_subcommands.add_parser("list")
    attempt_memory_list.add_argument("--project-root", type=Path, default=Path.cwd())
    attempt_memory_list.add_argument("--path", type=Path, default=None)
    attempt_memory_list.add_argument("--analytics-path", type=Path, default=None)
    attempt_memory_list.add_argument("--run-id", default=None)
    attempt_memory_list.add_argument("--max-age-days", type=int, default=None)
    attempt_memory_list.add_argument("--now", default=None)
    attempt_memory_list.add_argument("--agent", default="codex")
    attempt_memory_list.add_argument("--gauntlet-version", default="2.0.2")
    attempt_memory_list.add_argument("--json", action="store_true")
    attempt_memory_list.set_defaults(func=command_attempt_memory_list)

    changelog = subcommands.add_parser("changelog", help="Changelog generation helpers.")
    changelog_subcommands = changelog.add_subparsers(dest="changelog_command", required=True)
    changelog_pr = changelog_subcommands.add_parser("pr")
    changelog_pr.add_argument("--accepted-spec", type=Path, default=None)
    changelog_pr.add_argument("--plan", type=Path, default=None)
    changelog_pr.add_argument("--implementation-memory", type=Path, default=None, help=argparse.SUPPRESS)
    changelog_pr.add_argument("--git-root", type=Path, default=Path.cwd())
    changelog_pr.add_argument("--output", type=Path, default=None)
    changelog_pr.add_argument("--json", action="store_true")
    changelog_pr.set_defaults(func=command_changelog_pr)

    diagram = subcommands.add_parser("diagram", help="Saved diagram helpers.")
    diagram_subcommands = diagram.add_subparsers(dest="diagram_command", required=True)
    diagram_find = diagram_subcommands.add_parser("find")
    diagram_find.add_argument("--query", required=True)
    diagram_find.add_argument("--json", action="store_true")
    diagram_find.set_defaults(func=command_diagram_find)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except RuntimeError as error:
        payload = {
            "schemaVersion": "1.0",
            "status": "fail",
            "findings": [{"code": "command_failed", "severity": "fail", "message": str(error)}],
        }
        print_payload(payload, getattr(args, "json", False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
