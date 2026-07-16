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

from thread_titles import epic_task_title, parse_thread_title, product_task_title


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
CHECKER = SCRIPTS / "check-workflow-etiquette.py"
LOCAL_DOC_TEMPLATES = ROOT / "templates" / "local-docs"
EPIC_COPY_TEMPLATE = ROOT / "templates" / "epic-execution-copy.json"
LOCAL_DOC_OPT_OUT = Path(".gauntlet") / "doc-org.disabled"
DOC_EXECUTION_BLOCK_BEGIN = "<!-- BEGIN GAUNTLET EXECUTION CONTRACT v2 -->"
DOC_EXECUTION_BLOCK_END = "<!-- END GAUNTLET EXECUTION CONTRACT v2 -->"
DOC_EXECUTION_LEGACY_HASHES = {
    "5315292c4648aaa6bc04bd810730c7f480a79efb01e81cc882966a63407538e8",
}
EPIC_LAUNCH_SCHEMA = "gauntlet.epic-launch.v1"
EPIC_STATES = {
    "planned", "starting", "in-progress", "needs-decision",
    "implementation-complete", "failed", "stopped",
}
DEPENDENCY_BOUNDARIES = {"merged", "deployed", "productionProved"}
HIGH_CONSEQUENCE_TRIGGERS = {
    "billing-paid-actions",
    "credentials-auth-permissions",
    "migrations-data-loss",
    "production-authority",
    "destructive-actions",
}
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
REQUIRED_RUN_HANDOFF_FIELDS = {
    "schemaVersion", "title", "binding", "acceptedCriteria", "changedPaths",
    "completion", "deferrals", "epic", "releaseGates", "verificationReceipts",
}
RUN_BINDING_FIELDS = {
    "runId",
    "generation",
    "sourceLockSha256",
    "graphSha256",
    "repository",
    "branch",
    "headSha",
    "epicVerificationSha256",
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
    for name in ["drafts", "epics", "research"]:
        path = context["docsRoot"] / name
        if path.is_symlink():
            findings.append({
                "code": "local_document_symlink",
                "severity": "fail",
                "message": f"Canonical local-document paths must not be symlinks: {path}",
            })
        elif path.exists() and not path.is_dir():
            findings.append({
                "code": "invalid_local_document_directory",
                "severity": "fail",
                "message": f"Local-document path is not a directory: {path}",
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


def managed_execution_block():
    template = (LOCAL_DOC_TEMPLATES / "doc_org.md.tmpl").read_text(encoding="utf-8")
    start = template.index(DOC_EXECUTION_BLOCK_BEGIN)
    end = template.index(DOC_EXECUTION_BLOCK_END, start) + len(DOC_EXECUTION_BLOCK_END)
    return template[start:end] + "\n\n"


def migrate_doc_execution_contract(text):
    """Return (updated, state) without rewriting project-authored policy."""
    begin_count = text.count(DOC_EXECUTION_BLOCK_BEGIN)
    end_count = text.count(DOC_EXECUTION_BLOCK_END)
    current = managed_execution_block()
    if begin_count or end_count:
        if begin_count != 1 or end_count != 1:
            return text, "ambiguous"
        start = text.index(DOC_EXECUTION_BLOCK_BEGIN)
        end = text.index(DOC_EXECUTION_BLOCK_END, start) + len(DOC_EXECUTION_BLOCK_END)
        observed = text[start:end] + "\n\n"
        if observed != current:
            return text, "customized"
        return text, "current"

    start_marker = "## PRD Compilation And Ticket Graph\n"
    end_marker = "## Future Tasks\n"
    if text.count(start_marker) != 1 or text.count(end_marker) != 1:
        return text, "ambiguous"
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    legacy = text[start:end]
    if sha256_bytes(legacy.encode("utf-8")) not in DOC_EXECUTION_LEGACY_HASHES:
        return text, "customized"
    return text[:start] + current + text[end:], "migrated"


def ensure_doc_execution_contract(context, dry_run=False):
    path = context["policyPath"]
    if not path.is_file():
        return [], False
    original = path.read_text(encoding="utf-8")
    updated, state = migrate_doc_execution_contract(original)
    findings = []
    if state == "migrated":
        if not dry_run:
            atomic_write_text(path, updated)
        findings.append({
            "code": "local_execution_contract_migrated" if not dry_run else "local_execution_contract_migration_planned",
            "severity": "pass",
            "message": "Gauntlet updated only the versioned local execution contract and preserved project-authored policy bytes.",
        })
        return findings, True
    if state in {"ambiguous", "customized"}:
        findings.append({
            "code": "local_execution_contract_review",
            "severity": "review",
            "message": "The materialized doc_org.md execution contract is customized or ambiguous; Gauntlet left it unchanged for human review.",
        })
    return findings, False


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
    for directory in [context["docsRoot"] / "drafts", context["docsRoot"] / "epics", context["docsRoot"] / "research"]:
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


def local_product_document_paths(context):
    paths = []
    for root in [context["docsRoot"] / "drafts", context["docsRoot"] / "epics"]:
        if not root.is_dir() or root.is_symlink():
            continue
        paths.extend(
            path for path in root.rglob("*.md")
            if path.is_file() and not path.is_symlink()
        )
    return sorted(paths)


def guided_draft_destination(context, template):
    templates = {
        "founding-hypothesis": ("FOUNDING_HYPOTHESIS.md.tmpl", "FOUNDING_HYPOTHESIS.md"),
        "peter-yang": ("PETER_YANG_PRD.md.tmpl", "PETER_YANG_PRD.md"),
    }
    template_name, filename = templates[template]
    return template_name, context["docsRoot"] / "drafts" / filename


def create_guided_draft(context, template, dry_run=False):
    template_name, draft_path = guided_draft_destination(context, template)
    drafts_root = context["docsRoot"] / "drafts"
    findings = []
    if drafts_root.is_symlink() or (drafts_root.exists() and not drafts_root.is_dir()):
        findings.append({
            "code": "invalid_drafts_directory",
            "severity": "fail",
            "message": f"Drafts path must be a real directory: {drafts_root}",
        })
        return findings, draft_path
    if draft_path.exists() or draft_path.is_symlink():
        findings.append({
            "code": "draft_exists",
            "severity": "fail",
            "message": f"Refusing to overwrite an existing product draft: {draft_path}",
        })
        return findings, draft_path
    date = datetime.now().astimezone().date().isoformat()
    rendered = render_local_doc_template(template_name, {"DATE": date})
    if not dry_run:
        drafts_root.mkdir(parents=True, exist_ok=True)
        write_new_file(draft_path, rendered)
    findings.append({
        "code": "guided_draft_planned" if dry_run else "guided_draft_created",
        "severity": "pass",
        "message": f"Gauntlet {'would create' if dry_run else 'created'} an unanswered {template} draft.",
    })
    return findings, draft_path


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
        drafts_root = context["docsRoot"] / "drafts"
        created = []
        preserved = []
        if drafts_root.is_dir() and not drafts_root.is_symlink():
            preserved.append(str(drafts_root))
        else:
            created.append(str(drafts_root))
            if not args.dry_run:
                drafts_root.mkdir(parents=False, exist_ok=False)
        migration_findings, migrated = ensure_doc_execution_contract(context, dry_run=args.dry_run)
        findings = migration_findings + local_docs_validation_findings(context, require_profile=True)
        return local_docs_payload(
            args,
            context,
            findings,
            mode="default-on",
            materialized=True,
            created=created,
            preserved=preserved,
            migrated=migrated,
            dryRun=args.dry_run,
        )

    had_product_document = bool(local_product_document_paths(context))
    _, founding_candidate = guided_draft_destination(context, "founding-hypothesis")
    if not had_product_document and (founding_candidate.exists() or founding_candidate.is_symlink()):
        return local_docs_payload(
            args,
            context,
            [{
                "code": "draft_exists",
                "severity": "fail",
                "message": f"Refusing to overwrite an existing product draft path: {founding_candidate}",
            }],
            mode="default-on",
            materialized=False,
            created=[],
            preserved=[],
            dryRun=args.dry_run,
            foundingDraftPath=str(founding_candidate),
        )
    prefix = args.epic_prefix or (local_epic_prefix(context["indexPath"]) if context["indexPath"].is_file() else inferred_epic_prefix(context))
    findings, created, preserved = initialize_local_docs(args, context, prefix)
    founding_draft_path = None
    if not had_product_document and not any(finding.get("severity") == "fail" for finding in findings):
        draft_findings, founding_draft_path = create_guided_draft(
            context, "founding-hypothesis", dry_run=args.dry_run,
        )
        findings.extend(draft_findings)
        if not any(finding.get("severity") == "fail" for finding in draft_findings):
            created.append(str(founding_draft_path))
    if not args.dry_run and not any(finding.get("severity") == "fail" for finding in findings):
        migration_findings, _ = ensure_doc_execution_contract(context, dry_run=False)
        findings.extend(migration_findings)
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
        foundingDraftPath=str(founding_draft_path) if founding_draft_path else None,
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
    if not opted_out and context["policyPath"].is_file():
        migration_findings, _ = ensure_doc_execution_contract(context, dry_run=True)
        findings.extend(migration_findings)
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


def command_docs_draft_create(args):
    context = local_docs_context(args.project_root)
    _, draft_candidate = guided_draft_destination(context, args.template)
    if draft_candidate.exists() or draft_candidate.is_symlink():
        return local_docs_payload(
            args,
            context,
            [{
                "code": "draft_exists",
                "severity": "fail",
                "message": f"Refusing to overwrite an existing product draft: {draft_candidate}",
            }],
            template=args.template,
            draftPath=str(draft_candidate),
            dryRun=args.dry_run,
        )
    if local_docs_opted_out(context):
        findings = local_docs_path_findings(context) + [{
            "code": "local_document_profile_opted_out",
            "severity": "fail",
            "message": f"Project opted out of default local documents through {context['optOutPath']}; run docs enable before creating a draft.",
        }]
    elif all(path.exists() for path in [context["policyPath"], context["docsRoot"], context["indexPath"]]):
        findings = local_docs_validation_findings(context, require_profile=True)
    else:
        findings, _, _ = initialize_local_docs(args, context, inferred_epic_prefix(context))
        if not args.dry_run and not any(finding.get("severity") == "fail" for finding in findings):
            findings.extend(local_docs_validation_findings(context, require_profile=True))
    if any(finding.get("severity") == "fail" for finding in findings):
        return local_docs_payload(args, context, findings, template=args.template, dryRun=args.dry_run)

    draft_findings, draft_path = create_guided_draft(context, args.template, dry_run=args.dry_run)
    findings.extend(draft_findings)
    return local_docs_payload(
        args,
        context,
        findings,
        template=args.template,
        draftPath=str(draft_path),
        dryRun=args.dry_run,
    )


def local_draft_path(context, supplied):
    drafts_root = context["docsRoot"] / "drafts"
    candidate = Path(supplied).expanduser()
    if not candidate.is_absolute():
        candidate = drafts_root / candidate
    candidate = candidate.absolute()
    if candidate.is_symlink():
        raise RuntimeError(f"A promoted draft must not be a symlink: {candidate}")
    resolved_root = drafts_root.resolve()
    resolved = candidate.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise RuntimeError("A promoted draft must be inside local-docs/drafts.") from exc
    current = candidate.parent
    resolved_docs_root = context["docsRoot"].resolve()
    while current.resolve() != resolved_docs_root:
        if current.is_symlink():
            raise RuntimeError(f"A promoted draft path must not use symlinks: {candidate}")
        if current == current.parent:
            raise RuntimeError("A promoted draft must be inside local-docs/drafts.")
        current = current.parent
    if candidate.parent.resolve() != resolved_root:
        raise RuntimeError("A promoted draft must be directly inside local-docs/drafts.")
    if not resolved.is_file():
        raise RuntimeError(f"A promoted draft must already exist: {candidate}")
    return resolved


def command_docs_draft_promote(args):
    context = local_docs_context(args.project_root)
    if local_docs_opted_out(context):
        findings = local_docs_path_findings(context) + [{
            "code": "local_document_profile_opted_out",
            "severity": "fail",
            "message": f"Project opted out of default local documents through {context['optOutPath']}; run docs enable before promoting a draft.",
        }]
    elif all(path.exists() for path in [context["policyPath"], context["docsRoot"], context["indexPath"]]):
        findings = local_docs_validation_findings(context, require_profile=True)
    else:
        findings = local_docs_path_findings(context) + [{
            "code": "local_document_profile_missing",
            "severity": "fail",
            "message": "Create a local product draft before promoting it.",
        }]
    if any(finding.get("severity") == "fail" for finding in findings):
        return local_docs_payload(args, context, findings, dryRun=args.dry_run)
    if not valid_epic_title(args.title):
        findings.append({
            "code": "invalid_epic_title",
            "severity": "fail",
            "message": "Epic title must be one non-empty line, at most 120 characters, without Markdown link or control delimiters.",
        })
        return local_docs_payload(args, context, findings, dryRun=args.dry_run)

    draft_path = local_draft_path(context, args.draft)
    prefix = local_epic_prefix(context["indexPath"])
    if not re.fullmatch(r"[A-Z][A-Z0-9]{1,11}", prefix):
        raise RuntimeError(f"Local document index has an invalid epic prefix: {prefix}")
    existing = allocated_epic_numbers(context, prefix)
    number = args.number if args.number is not None else ((max(existing) + 1) if existing else 1)
    if number < 1 or number > 999:
        findings.append({"code": "invalid_epic_number", "severity": "fail", "message": "Epic number must be between 001 and 999."})
        return local_docs_payload(args, context, findings, draftPath=str(draft_path), dryRun=args.dry_run)
    sequence = f"{number:03d}"
    epic_id = f"{prefix}-{sequence}"
    if number in existing:
        findings.append({"code": "epic_id_exists", "severity": "fail", "message": f"Epic ID already exists: {epic_id}"})
        return local_docs_payload(args, context, findings, draftPath=str(draft_path), dryRun=args.dry_run)

    epics_root = context["docsRoot"] / "epics"
    epic_root = epics_root / sequence
    prd_path = epic_root / f"{sequence}_{epic_title_slug(args.title)}_PRD.md"
    if epic_root.exists() or epic_root.is_symlink() or prd_path.exists():
        findings.append({"code": "epic_exists", "severity": "fail", "message": f"Epic destination already exists: {epic_root}"})
        return local_docs_payload(args, context, findings, draftPath=str(draft_path), dryRun=args.dry_run)

    index_path = context["indexPath"]
    index_text = index_path.read_text(encoding="utf-8")
    marker = "<!-- EPICS -->"
    if index_text.count(marker) != 1:
        raise RuntimeError(f"Local document index must contain exactly one epic insertion marker: {index_path}")
    date = datetime.now().astimezone().date().isoformat()
    relative = prd_path.relative_to(context["docsRoot"])
    row = f"| `{epic_id}` | [{args.title}]({relative.as_posix()}) | PRD | Proposed | {date} | None | None | Not implemented | Not verified |\n"
    updated_index = index_text.replace(marker, row + marker, 1)
    if args.dry_run:
        return local_docs_payload(
            args,
            context,
            findings,
            epicId=epic_id,
            epicRoot=str(epic_root),
            prdPath=str(prd_path),
            draftPath=str(draft_path),
            dryRun=True,
        )

    moved = False
    try:
        epic_root.mkdir(parents=False, exist_ok=False)
        for child in ["prompts", "research", "decisions", "runs"]:
            (epic_root / child).mkdir()
        os.replace(draft_path, prd_path)
        moved = True
        atomic_write_text(index_path, updated_index)
    except Exception:
        if moved and prd_path.is_file() and not draft_path.exists():
            os.replace(prd_path, draft_path)
        if epic_root.exists() and not epic_root.is_symlink():
            shutil.rmtree(epic_root)
        if index_path.is_file() and index_path.read_text(encoding="utf-8") != index_text:
            atomic_write_text(index_path, index_text)
        raise
    return local_docs_payload(
        args,
        context,
        findings,
        epicId=epic_id,
        epicRoot=str(epic_root),
        prdPath=str(prd_path),
        draftPath=str(draft_path),
        dryRun=False,
    )


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def epic_source_sections(source_text):
    matches = list(re.finditer(r"^## Epic ([A-Z][A-Z0-9]*-\d{3}):\s*(.+?)\s*$", source_text, re.MULTILINE))
    sections = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source_text)
        section = source_text[match.start():end].rstrip() + "\n"
        sections[match.group(1)] = {
            "id": match.group(1),
            "title": match.group(2).strip(),
            "text": section,
        }
    return sections


def epic_metadata(section_text, name, default=None):
    match = re.search(rf"^{re.escape(name)}:[ \t]*([^\r\n]*)[ \t]*$", section_text, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else default


def parse_dependency_list(raw):
    if not raw or raw.strip().lower() in {"none", "n/a", "not applicable"}:
        return []
    dependencies = []
    for item in raw.split(","):
        value = item.strip().strip("`")
        match = re.fullmatch(r"([A-Z][A-Z0-9]*-\d{3})(?:@(merged|deployed|productionProved))?", value)
        if not match:
            raise ValueError(f"Invalid Epic dependency: {item.strip()}")
        dependencies.append({"epicId": match.group(1), "boundary": match.group(2) or "merged"})
    return dependencies


def parse_release_stages(raw):
    requested = {"merge"}
    if raw:
        values = {item.strip().lower().replace("_", "-") for item in raw.split(",") if item.strip()}
        aliases = {
            "production": "production-verification",
            "production-proof": "production-verification",
            "productionproved": "production-verification",
        }
        requested = {aliases.get(value, value) for value in values}
    unknown = requested - {"merge", "deployment", "production-verification"}
    if unknown:
        raise ValueError("Unknown release stage: " + ", ".join(sorted(unknown)))
    if "production-verification" in requested and "deployment" not in requested:
        raise ValueError("Production verification requires deployment")
    if "merge" not in requested:
        raise ValueError("Every Epic release requires merge")
    return sorted(requested)


def parse_consequence_triggers(raw):
    if raw is None:
        return []
    if not raw.strip():
        raise ValueError("High-consequence triggers must be literal `none` or a non-empty canonical list")
    if raw.strip().lower() == "none":
        return []
    triggers = sorted({item.strip().lower() for item in raw.split(",") if item.strip()})
    unknown = set(triggers) - HIGH_CONSEQUENCE_TRIGGERS
    if unknown:
        raise ValueError("Unknown high-consequence trigger: " + ", ".join(sorted(unknown)))
    return triggers


def implementation_target_ids(source_text):
    match = re.search(r"^Implementation target:\s*(.*?)\s*$", source_text, re.MULTILINE | re.IGNORECASE)
    if not match:
        raise ValueError("PRD is missing Implementation target")
    ids = re.findall(r"[A-Z][A-Z0-9]*-\d{3}", match.group(1))
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Implementation target must contain unique stable Epic IDs")
    return ids


def validate_epic_dependency_graph(epics, target_ids):
    target = set(target_ids)
    for epic_id in target_ids:
        for dependency in epics[epic_id]["dependencies"]:
            dependency_id = dependency["epicId"]
            if dependency_id not in epics:
                raise ValueError(f"{epic_id} depends on unknown Epic {dependency_id}")
            if dependency_id not in target:
                status = epics[dependency_id]["sourceStatus"].lower()
                if status not in {"complete", "implemented", "release-complete"}:
                    raise ValueError(f"{epic_id} depends on {dependency_id}, which is outside the target and not complete")

    visiting = set()
    visited = set()

    def visit(epic_id):
        if epic_id in visiting:
            raise ValueError(f"Epic dependency cycle includes {epic_id}")
        if epic_id in visited:
            return
        visiting.add(epic_id)
        for dependency in epics[epic_id]["dependencies"]:
            if dependency["epicId"] in target:
                visit(dependency["epicId"])
        visiting.remove(epic_id)
        visited.add(epic_id)

    for epic_id in target_ids:
        visit(epic_id)


def build_epic_launch_set(source_path, target_ids, priority="p1"):
    source_path = Path(source_path).resolve()
    source_bytes = source_path.read_bytes()
    source_text = source_bytes.decode("utf-8")
    declared_target = implementation_target_ids(source_text)
    if target_ids and list(target_ids) != declared_target:
        raise ValueError("Requested target must exactly match the PRD Implementation target in canonical order")
    target_ids = sorted(declared_target)
    sections = epic_source_sections(source_text)
    parsed = {}
    for epic_id, section in sections.items():
        status = epic_metadata(section["text"], "Epic status", "")
        dependencies = parse_dependency_list(epic_metadata(section["text"], "Depends on", "None"))
        consequence_raw = epic_metadata(section["text"], "High-consequence triggers", None)
        if consequence_raw is None and epic_id in target_ids:
            raise ValueError(f"{epic_id} must declare `High-consequence triggers: none` or canonical trigger IDs")
        parsed[epic_id] = {
            "title": section["title"],
            "dependencies": dependencies,
            "releaseStages": parse_release_stages(epic_metadata(section["text"], "Release stages", "merge")),
            "consequenceTriggers": parse_consequence_triggers(consequence_raw),
            "sourceStatus": status,
        }
    missing = [epic_id for epic_id in target_ids if epic_id not in parsed]
    if missing:
        raise ValueError("Implementation target is missing Epic sections: " + ", ".join(missing))
    for epic_id in target_ids:
        section_text = sections[epic_id]["text"]
        epic = parsed[epic_id]
        if epic["sourceStatus"].lower() != "accepted":
            raise ValueError(f"{epic_id} must be Accepted before launch")
        required = {
            "Build ready": "yes",
            "Ships independently": "yes",
            "Rolls back independently": "yes",
        }
        for field, expected in required.items():
            actual = (epic_metadata(section_text, field, "") or "").lower()
            if actual != expected:
                raise ValueError(f"{epic_id} must declare `{field}: {expected}`")
    validate_epic_dependency_graph(parsed, target_ids)

    source = {"path": str(source_path), "sha256": sha256_bytes(source_bytes)}
    coverage = {
        "schemaVersion": EPIC_LAUNCH_SCHEMA,
        "source": source,
        "targetEpicIds": target_ids,
        "epics": {
            epic_id: {
                "title": parsed[epic_id]["title"],
                "dependencies": parsed[epic_id]["dependencies"],
                "releaseStages": parsed[epic_id]["releaseStages"],
                "consequenceTriggers": parsed[epic_id]["consequenceTriggers"],
            }
            for epic_id in target_ids
        },
    }
    coverage_sha = sha256_bytes(canonical_json(coverage).encode("utf-8"))
    epics = {}
    for epic_id in target_ids:
        epics[epic_id] = {
            **coverage["epics"][epic_id],
            "taskId": None,
            "runPath": None,
            "status": "planned",
            "blocker": None,
            "stopDisposition": None,
            "startReconciliation": None,
            "emittedEvents": [],
        }
    return {
        "schemaVersion": EPIC_LAUNCH_SCHEMA,
        "source": source,
        "targetEpicIds": target_ids,
        "coverageSha256": coverage_sha,
        "epics": epics,
        "aggregateEmittedEvents": [],
    }, source_text


def write_launch_set(path, data):
    atomic_write_text(Path(path), json.dumps(data, indent=2, sort_keys=True) + "\n")


def launch_coverage_projection(data):
    return {
        "schemaVersion": data["schemaVersion"],
        "source": {key: data["source"][key] for key in ["path", "sha256"]},
        "targetEpicIds": data["targetEpicIds"],
        "epics": {
            epic_id: {
                "title": data["epics"][epic_id]["title"],
                "dependencies": data["epics"][epic_id]["dependencies"],
                "releaseStages": data["epics"][epic_id]["releaseStages"],
                "consequenceTriggers": data["epics"][epic_id]["consequenceTriggers"],
            }
            for epic_id in data["targetEpicIds"]
        },
    }


def launch_task_key(launch, epic_id):
    return sha256_bytes(f"{launch['coverageSha256']}:{epic_id}".encode("utf-8"))[:24]


def load_launch_set(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schemaVersion") != EPIC_LAUNCH_SCHEMA:
        raise ValueError(f"Unsupported Epic launch schema: {data.get('schemaVersion')}")
    required = {"schemaVersion", "source", "targetEpicIds", "coverageSha256", "epics", "aggregateEmittedEvents"}
    if set(data) != required:
        raise ValueError("Epic launch set has unexpected or missing top-level fields")
    if len(data["targetEpicIds"]) != len(set(data["targetEpicIds"])) or set(data["epics"]) != set(data["targetEpicIds"]):
        raise ValueError("Epic launch membership must exactly match targetEpicIds")
    expected_coverage = sha256_bytes(canonical_json(launch_coverage_projection(data)).encode("utf-8"))
    if data["coverageSha256"] != expected_coverage:
        raise ValueError("Epic launch coverage no longer matches its immutable coverage digest")
    for epic_id, epic in data["epics"].items():
        if epic.get("status") not in EPIC_STATES:
            raise ValueError(f"Invalid state for {epic_id}: {epic.get('status')}")
    return path, data


def launch_source_text(launch):
    snapshot = launch["source"].get("snapshotPath")
    if not snapshot:
        raise ValueError("Epic launch set is missing its immutable source snapshot")
    path = Path(snapshot)
    content = path.read_bytes()
    if sha256_bytes(content) != launch["source"]["sha256"]:
        raise ValueError("Epic launch source snapshot does not match the locked source hash")
    return content.decode("utf-8")


def lifecycle_copy_contract():
    data = json.loads(EPIC_COPY_TEMPLATE.read_text(encoding="utf-8"))
    if data.get("schemaVersion") != "gauntlet.epic-copy.v1":
        raise ValueError("Unsupported Epic lifecycle copy template")
    return data


def render_lifecycle_copy(event, facts, variant="default"):
    contract = lifecycle_copy_contract()
    event_contract = contract["events"].get(event)
    if not event_contract:
        raise ValueError(f"Unknown Epic lifecycle event: {event}")
    required = event_contract.get("required", [])
    missing = [key for key in required if key not in facts]
    if missing:
        raise ValueError(f"Lifecycle event {event} is missing facts: {', '.join(missing)}")
    safe_facts = {key: str(value) for key, value in facts.items()}
    if has_secret(canonical_json(safe_facts)):
        raise ValueError("Lifecycle copy facts contain secret-like content")
    template = event_contract.get("variants", {}).get(variant) or event_contract.get("template")
    if not template:
        raise ValueError(f"Lifecycle event {event} has no {variant} template")
    return template.format_map(safe_facts).strip()


def completion_projection_for_run(repo, run_path):
    if not run_path:
        return None
    output, error = run_prd_controller(repo, ["completion", "--run", str(Path(run_path).resolve())])
    if error:
        return {"available": False, "error": error}
    try:
        data = json.loads(output)
    except json.JSONDecodeError as exc:
        return {"available": False, "error": f"completion did not emit JSON: {exc}"}
    data["available"] = True
    return data


def completion_allows_archive(completion):
    return isinstance(completion, dict) and completion.get("complete") is True


def dependency_satisfied(epic, dependency, projections):
    projection = projections.get(dependency["epicId"])
    if not projection or projection.get("available") is not True:
        return False
    field = {"merged": "merged", "deployed": "deployed", "productionProved": "productionProved"}[dependency["boundary"]]
    return projection.get(field) is True


def launch_projections(repo, launch):
    return {
        epic_id: completion_projection_for_run(repo, epic.get("runPath"))
        for epic_id, epic in launch["epics"].items()
    }


def ready_launch_epics(launch, projections):
    target = set(launch["targetEpicIds"])
    ready = []
    for epic_id in launch["targetEpicIds"]:
        epic = launch["epics"][epic_id]
        if epic["status"] != "planned":
            continue
        target_dependencies = [item for item in epic["dependencies"] if item["epicId"] in target]
        if all(dependency_satisfied(epic, item, projections) for item in target_dependencies):
            ready.append(epic_id)
    return ready


def epic_task_packet(launch_path, launch, epic_id, repo):
    section = epic_source_sections(launch_source_text(launch))[epic_id]["text"]
    epic = launch["epics"][epic_id]
    dependency_outputs = []
    projections = launch_projections(repo, launch)
    for dependency in epic["dependencies"]:
        if dependency["epicId"] in projections and projections[dependency["epicId"]]:
            projection = projections[dependency["epicId"]]
            dependency_outputs.append({
                "epicId": dependency["epicId"],
                "boundary": dependency["boundary"],
                "exactRevision": projection.get("exactRevision"),
            })
    source_path = Path(launch["source"]["snapshotPath"])
    try:
        source_reference = source_path.relative_to(Path(repo).resolve()).as_posix()
    except ValueError:
        source_reference = source_path.name
    try:
        launch_reference = Path(launch_path).resolve().relative_to(Path(repo).resolve()).as_posix()
    except ValueError:
        launch_reference = Path(launch_path).name
    packet = {
        "schemaVersion": "gauntlet.epic-task.v1",
        "mode": "single-epic-non-recursive",
        "epicId": epic_id,
        "epicTitle": epic["title"],
        "sourceReference": source_reference,
        "sourceSha256": launch["source"]["sha256"],
        "coverageSha256": launch["coverageSha256"],
        "launchSet": launch_reference,
        "taskKey": launch_task_key(launch, epic_id),
        "dependencyOutputs": dependency_outputs,
    }
    opening = render_lifecycle_copy("epic_start", {
        "epic_id": epic_id,
        "epic_title": epic["title"],
        "dependency_note": "Its declared implementation dependencies are satisfied." if epic["dependencies"] else "It has no implementation dependencies.",
    })
    message = "\n".join([
        opening,
        "",
        "<gauntlet_epic_task>",
        canonical_json(packet),
        "</gauntlet_epic_task>",
        "",
        section.rstrip(),
    ])
    if has_secret(message):
        raise ValueError(f"Epic task packet for {epic_id} contains secret-like content")
    return message


def launch_state(launch, projections):
    states = [epic["status"] for epic in launch["epics"].values()]
    if any(state == "needs-decision" for state in states):
        return "needs-decision"
    if any(state == "failed" for state in states):
        return "failed"
    if all(state in {"implementation-complete", "stopped"} for state in states):
        complete = True
        for epic_id, epic in launch["epics"].items():
            if epic["status"] == "stopped":
                continue
            projection = projections.get(epic_id) or {}
            if projection.get("complete") is not True:
                complete = False
        return "release-complete" if complete else "implementation-complete"
    if any(state in {"starting", "in-progress", "implementation-complete"} for state in states):
        return "running"
    return "planned"


def epic_launch_payload(launch_path, launch, repo, **extra):
    projections = launch_projections(repo, launch)
    return {
        "schemaVersion": EPIC_LAUNCH_SCHEMA,
        "status": "pass",
        "launchSet": str(Path(launch_path).resolve()),
        "launchState": launch_state(launch, projections),
        "targetCount": len(launch["targetEpicIds"]),
        "epics": launch["epics"],
        "projections": projections,
        "findings": [],
        **extra,
    }


def command_epic_tasks_init(args):
    payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "pass", "findings": [], "actions": []}
    try:
        launch, source_text = build_epic_launch_set(args.source, args.target, priority=args.priority)
        launch_path = Path(args.launch_set).resolve()
        snapshot_path = launch_path.with_name(launch_path.stem + ".source.md")
        if launch_path.exists() or snapshot_path.exists():
            raise ValueError("Epic launch initialization refuses to overwrite an existing launch set or snapshot")
        launch["source"]["snapshotPath"] = str(snapshot_path)
        try:
            atomic_write_text(snapshot_path, source_text)
            write_launch_set(launch_path, launch)
        except Exception:
            if launch_path.exists():
                launch_path.unlink()
            if snapshot_path.exists():
                snapshot_path.unlink()
            raise
        payload.update(epic_launch_payload(launch_path, launch, args.git_root))
        payload["productTaskTitle"] = product_task_title(args.priority, launch["targetEpicIds"][0].split("-", 1)[0])
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        add_finding(payload, "epic_launch_init_failed", "fail", str(exc))
        payload["status"] = status_for(payload)
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_epic_tasks_plan(args):
    try:
        launch_path, launch = load_launch_set(args.launch_set)
        projections = launch_projections(args.git_root, launch)
        ready = ready_launch_epics(launch, projections)
        actions = []
        for epic_id in ready:
            epic = launch["epics"][epic_id]
            epic["status"] = "starting"
            actions.append({
                "type": "create_thread",
                "taskKey": launch_task_key(launch, epic_id),
                "title": epic_task_title("p1", epic_id, epic["title"]),
                "cwd": str(Path(args.git_root).resolve()),
                "message": epic_task_packet(launch_path, launch, epic_id, args.git_root),
            })
        if ready:
            write_launch_set(launch_path, launch)
        reconcile = [
            {"epicId": epic_id, "taskKey": launch_task_key(launch, epic_id)}
            for epic_id, epic in launch["epics"].items()
            if epic["status"] == "starting" and not epic["taskId"] and epic_id not in ready
        ]
        payload = epic_launch_payload(launch_path, launch, args.git_root, actions=actions, reconcileRequired=reconcile)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "fail", "findings": [{"code": "epic_launch_plan_failed", "severity": "fail", "message": str(exc)}], "actions": []}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def maybe_aggregate_start_event(launch):
    if "aggregate_start" in launch["aggregateEmittedEvents"]:
        return None
    started = sum(1 for epic in launch["epics"].values() if epic["taskId"])
    if not started or any(epic["status"] == "starting" and not epic["taskId"] for epic in launch["epics"].values()):
        return None
    queued = sum(1 for epic in launch["epics"].values() if epic["status"] == "planned")
    launch["aggregateEmittedEvents"].append("aggregate_start")
    return {
        "event": "aggregate_start",
        "copy": render_lifecycle_copy("aggregate_start", {
            "target_count": len(launch["targetEpicIds"]),
            "started_count": started,
            "queued_count": queued,
        }, variant="break"),
    }


def command_epic_tasks_record_task(args):
    try:
        launch_path, launch = load_launch_set(args.launch_set)
        epic = launch["epics"].get(args.epic)
        if not epic:
            raise ValueError(f"Epic is not in the launch set: {args.epic}")
        if launch_task_key(launch, args.epic) != args.task_key:
            raise ValueError("Epic task key does not match the launch set")
        if epic["taskId"] and epic["taskId"] != args.task_id:
            raise ValueError(f"{args.epic} is already mapped to a different task ID")
        if not epic["taskId"] and epic["status"] != "starting":
            raise ValueError("A new Epic task can be recorded only from the starting state")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,255}", args.task_id):
            raise ValueError("Task ID has an invalid format")
        events = []
        if not epic["taskId"]:
            epic["taskId"] = args.task_id
            epic["status"] = "in-progress"
            if "epic_start" not in epic["emittedEvents"]:
                epic["emittedEvents"].append("epic_start")
                events.append({"event": "epic_start", "epicId": args.epic, "copy": render_lifecycle_copy("epic_start", {
                    "epic_id": args.epic,
                    "epic_title": epic["title"],
                    "dependency_note": "Its declared implementation dependencies are satisfied." if epic["dependencies"] else "It has no implementation dependencies.",
                })})
        aggregate = maybe_aggregate_start_event(launch)
        if aggregate:
            events.append(aggregate)
        write_launch_set(launch_path, launch)
        payload = epic_launch_payload(launch_path, launch, args.git_root, lifecycleEvents=events)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "fail", "findings": [{"code": "epic_task_record_failed", "severity": "fail", "message": str(exc)}], "lifecycleEvents": []}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_epic_tasks_release_start(args):
    try:
        launch_path, launch = load_launch_set(args.launch_set)
        epic = launch["epics"].get(args.epic)
        if not epic or launch_task_key(launch, args.epic) != args.task_key:
            raise ValueError("Epic task key does not match the launch set")
        if epic["taskId"]:
            raise ValueError("A recorded Epic task cannot be released for recreation")
        if epic["status"] != "starting":
            raise ValueError("Only an ambiguous starting action can be released")
        index_path = Path(args.native_index).resolve()
        native_index = json.loads(index_path.read_text(encoding="utf-8"))
        if not isinstance(native_index, dict) or set(native_index) != {"schemaVersion", "query", "threads", "unavailableHosts"}:
            raise ValueError("Native task index has an unsupported shape")
        if native_index.get("schemaVersion") != 2 or native_index.get("query") != args.task_key:
            raise ValueError("Native task index must be the exact Codex task-key query")
        if native_index.get("threads") != [] or native_index.get("unavailableHosts") != []:
            raise ValueError("Native task index does not prove this task key is absent on every available host")
        if has_secret(canonical_json(native_index)):
            raise ValueError("Native task index contains unsafe content")
        epic["startReconciliation"] = {
            "adapter": "codex-app-list-threads-v2",
            "nativeIndexSha256": sha256_bytes(canonical_json(native_index).encode("utf-8")),
            "result": "absent",
        }
        epic["status"] = "planned"
        write_launch_set(launch_path, launch)
        payload = epic_launch_payload(launch_path, launch, args.git_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "fail", "findings": [{"code": "epic_task_release_failed", "severity": "fail", "message": str(exc)}]}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_epic_tasks_record_run(args):
    try:
        launch_path, launch = load_launch_set(args.launch_set)
        epic = launch["epics"].get(args.epic)
        if not epic or not epic["taskId"]:
            raise ValueError("Record the Epic task before its Execution Run")
        run_path = Path(args.run).resolve()
        source_lock_path = run_path / "source-lock.json"
        if not source_lock_path.is_file():
            raise ValueError(f"Execution Run lacks source-lock.json: {run_path}")
        source_lock = json.loads(source_lock_path.read_text(encoding="utf-8"))
        locked_epics = source_lock.get("target_epic_ids") or source_lock.get("target_epics") or source_lock.get("targetEpicIds") or []
        if isinstance(locked_epics, dict):
            locked_epics = list(locked_epics)
        if locked_epics != [args.epic]:
            raise ValueError("Execution Run must lock exactly the recorded Epic")
        if set(source_lock.get("epics") or {}) != {args.epic}:
            raise ValueError("Execution Run source-lock Epic facts must match the recorded Epic exactly")
        locked_launch = source_lock.get("launch_set") or {}
        if Path(locked_launch.get("path", "")).resolve() != launch_path:
            raise ValueError("Execution Run is bound to a different Epic launch set")
        if locked_launch.get("coverage_sha256") != launch["coverageSha256"] or locked_launch.get("task_id") != epic["taskId"]:
            raise ValueError("Execution Run launch coverage or native task identity does not match")
        if epic["runPath"] and Path(epic["runPath"]).resolve() != run_path:
            raise ValueError("Epic is already mapped to a different Execution Run")
        epic["runPath"] = str(run_path)
        write_launch_set(launch_path, launch)
        payload = epic_launch_payload(launch_path, launch, args.git_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "fail", "findings": [{"code": "epic_run_record_failed", "severity": "fail", "message": str(exc)}]}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_epic_tasks_status(args):
    try:
        launch_path, launch = load_launch_set(args.launch_set)
        payload = epic_launch_payload(launch_path, launch, args.git_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "fail", "findings": [{"code": "epic_launch_status_failed", "severity": "fail", "message": str(exc)}]}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_epic_tasks_blocker(args):
    try:
        launch_path, launch = load_launch_set(args.launch_set)
        epic = launch["epics"].get(args.epic)
        if not epic:
            raise ValueError(f"Epic is not in the launch set: {args.epic}")
        if not epic.get("taskId") or epic["status"] not in {"in-progress", "needs-decision"}:
            raise ValueError("Only a started Epic task can report a blocker")
        blocker = json.loads(Path(args.blocker).read_text(encoding="utf-8"))
        allowed = {"classification", "decision", "recommendation", "reason", "impact", "authorityNotGranted", "question"}
        if set(blocker) - allowed or "classification" not in blocker:
            raise ValueError("Blocker contains unknown fields or lacks classification")
        if blocker["classification"] not in {"recoverable", "needs-parent", "requires-user", "terminal"}:
            raise ValueError("Unknown blocker classification")
        if blocker["classification"] == "requires-user":
            required = allowed
        elif blocker["classification"] == "terminal":
            required = {"classification", "reason"}
        else:
            required = {"classification", "reason"}
        missing = required - set(blocker)
        if missing:
            raise ValueError("Blocker is missing required fields: " + ", ".join(sorted(missing)))
        if has_secret(canonical_json(blocker)):
            raise ValueError("Blocker contains secret-like content")
        events = []
        epic["blocker"] = blocker
        if blocker["classification"] == "requires-user":
            epic["status"] = "needs-decision"
            digest = "material_blocker:" + sha256_bytes(canonical_json(blocker).encode("utf-8"))[:16]
            if digest not in epic["emittedEvents"]:
                epic["emittedEvents"].append(digest)
                continuing = sum(
                    1 for other_id, other in launch["epics"].items()
                    if other_id != args.epic and other["status"] in {"starting", "in-progress", "implementation-complete"}
                )
                events.append({"event": "material_blocker", "epicId": args.epic, "copy": render_lifecycle_copy("material_blocker", {
                    "epic_id": args.epic,
                    "decision": blocker["decision"],
                    "recommendation": blocker["recommendation"],
                    "reason": blocker["reason"],
                    "impact": blocker["impact"],
                    "authority_not_granted": blocker["authorityNotGranted"],
                    "other_epics_continuing": continuing,
                    "question": blocker["question"],
                })})
        elif blocker["classification"] == "terminal":
            epic["status"] = "failed"
        write_launch_set(launch_path, launch)
        payload = epic_launch_payload(launch_path, launch, args.git_root, lifecycleEvents=events)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "fail", "findings": [{"code": "epic_blocker_record_failed", "severity": "fail", "message": str(exc)}], "lifecycleEvents": []}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_epic_tasks_resolve_blocker(args):
    try:
        launch_path, launch = load_launch_set(args.launch_set)
        epic = launch["epics"].get(args.epic)
        if not epic or epic["status"] != "needs-decision" or not epic["blocker"]:
            raise ValueError("Epic has no user decision awaiting resolution")
        if args.disposition == "continue":
            epic["status"] = "in-progress"
            epic["blocker"] = None
        else:
            if not args.reason:
                raise ValueError("Stopping an Epic requires an accepted disposition reason")
            if has_secret(args.reason):
                raise ValueError("Stop disposition contains secret-like content")
            epic["status"] = "stopped"
            epic["stopDisposition"] = args.reason
            epic["blocker"] = None
        write_launch_set(launch_path, launch)
        payload = epic_launch_payload(launch_path, launch, args.git_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "fail", "findings": [{"code": "epic_blocker_resolution_failed", "severity": "fail", "message": str(exc)}]}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def pending_gate_text(projection):
    gates = projection.get("pendingGates") or []
    if not gates:
        return "no applicable release gates"
    labels = []
    for gate in gates:
        if isinstance(gate, dict):
            labels.append(str(gate.get("stage") or gate.get("id") or "an unnamed gate"))
        else:
            labels.append(str(gate))
    return ", ".join(labels)


def maybe_finish_events(launch, projections):
    events = []
    for epic_id in launch["targetEpicIds"]:
        epic = launch["epics"][epic_id]
        projection = projections.get(epic_id) or {}
        if epic["status"] != "stopped" and projection.get("available") is True and projection.get("implemented") is True:
            epic["status"] = "implementation-complete"
            if "epic_finish" not in epic["emittedEvents"]:
                epic["emittedEvents"].append("epic_finish")
                remaining = sum(
                    1 for other_id, other in launch["epics"].items()
                    if other_id != epic_id and other["status"] not in {"implementation-complete", "stopped"}
                )
                events.append({"event": "epic_finish", "epicId": epic_id, "copy": render_lifecycle_copy("epic_finish", {
                    "epic_id": epic_id,
                    "epic_title": epic["title"],
                    "exact_revision": projection.get("exactRevision") or "an unavailable revision",
                    "verification_summary": projection.get("verificationSummary") or "final Epic verification passed",
                    "pending_release_gates": pending_gate_text(projection),
                    "remaining_count": remaining,
                })})
    finished = all(epic["status"] in {"implementation-complete", "stopped"} for epic in launch["epics"].values())
    if finished and "aggregate_finish" not in launch["aggregateEmittedEvents"]:
        launch["aggregateEmittedEvents"].append("aggregate_finish")
        stopped = [f"{epic_id} ({epic['stopDisposition']})" for epic_id, epic in launch["epics"].items() if epic["status"] == "stopped"]
        implemented = sum(1 for epic in launch["epics"].values() if epic["status"] == "implementation-complete")
        release_states = []
        pending = []
        for epic_id, projection in projections.items():
            if not projection or projection.get("available") is not True:
                continue
            release_states.append(
                f"{epic_id}: implemented={str(bool(projection.get('implemented'))).lower()}, "
                f"merged={str(bool(projection.get('merged'))).lower()}, deployed={str(bool(projection.get('deployed'))).lower()}, "
                f"production-proved={str(bool(projection.get('productionProved'))).lower()}"
            )
            if projection.get("pendingGates"):
                pending.append(f"{epic_id}: {pending_gate_text(projection)}")
        if stopped:
            copy = (
                f"Implementation has reached its accepted stopping point for all {len(launch['targetEpicIds'])} targeted Epics. "
                f"{implemented} are implementation-complete; stopped with an accepted disposition: {', '.join(stopped)}. "
                f"Release state: {'; '.join(release_states) or 'unavailable'}. {'Pending gates: ' + '; '.join(pending) + '.' if pending else ''}"
            ).strip()
        else:
            copy = render_lifecycle_copy("aggregate_finish", {
                "implemented_count": implemented,
                "exact_release_state": "; ".join(release_states) or "unavailable",
                "pending_gates": ("Pending gates: " + "; ".join(pending) + ".") if pending else "No applicable gates remain.",
            })
        events.append({"event": "aggregate_finish", "copy": copy})
    return events


def command_epic_tasks_reconcile(args):
    try:
        launch_path, launch = load_launch_set(args.launch_set)
        projections = launch_projections(args.git_root, launch)
        events = maybe_finish_events(launch, projections)
        ready = ready_launch_epics(launch, projections)
        actions = []
        for epic_id in ready:
            epic = launch["epics"][epic_id]
            epic["status"] = "starting"
            actions.append({
                "type": "create_thread",
                "taskKey": launch_task_key(launch, epic_id),
                "title": epic_task_title("p1", epic_id, epic["title"]),
                "cwd": str(Path(args.git_root).resolve()),
                "message": epic_task_packet(launch_path, launch, epic_id, args.git_root),
            })
        write_launch_set(launch_path, launch)
        payload = epic_launch_payload(launch_path, launch, args.git_root, lifecycleEvents=events, actions=actions)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "fail", "findings": [{"code": "epic_launch_reconcile_failed", "severity": "fail", "message": str(exc)}], "lifecycleEvents": [], "actions": []}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def replace_epic_metadata(source_text, epic_id, updates):
    sections = epic_source_sections(source_text)
    if epic_id not in sections:
        raise ValueError(f"Canonical PRD no longer contains {epic_id}")
    section = sections[epic_id]["text"]
    updated = section
    heading_end = updated.find("\n") + 1
    for field, value in updates.items():
        pattern = re.compile(rf"^{re.escape(field)}:\s*.*$", re.MULTILINE | re.IGNORECASE)
        replacement = f"{field}: {value}"
        if pattern.search(updated):
            updated = pattern.sub(replacement, updated, count=1)
        else:
            updated = updated[:heading_end] + "\n" + replacement + updated[heading_end:]
            heading_end += len(replacement) + 1
    start = source_text.index(section)
    return source_text[:start] + updated + source_text[start + len(section):]


def epic_acceptance_identity(source_text, epic_id):
    sections = epic_source_sections(source_text)
    if epic_id not in sections:
        raise ValueError(f"Canonical PRD no longer contains {epic_id}")
    controller_fields = {"epic status", "implemented by", "verified by"}
    lines = []
    for line in sections[epic_id]["text"].splitlines():
        match = re.match(r"^([A-Za-z][A-Za-z ]+):\s*.*$", line)
        if match and match.group(1).strip().lower() in controller_fields:
            continue
        lines.append(line.rstrip())
    return sha256_bytes(("\n".join(lines).strip() + "\n").encode("utf-8"))


def index_epic_cells(index_text, epic_id):
    for line in index_text.splitlines():
        if re.match(rf"^\|\s*`{re.escape(epic_id)}`\s*\|", line):
            cells = [cell.strip() for cell in line.split("|")]
            if len(cells) < 11:
                raise ValueError(f"Index row for {epic_id} has an unexpected shape")
            return {"status": cells[4], "implementation": cells[8], "verification": cells[9]}
    raise ValueError(f"Local document index has no row for {epic_id}")


def placeholder_index_value(value, kind):
    lowered = value.lower()
    markers = {
        "implementation": ("not started", "not implemented", "not authorized", "build-ready"),
        "verification": ("not verified", "not authorized", "build-ready"),
    }
    return any(marker in lowered for marker in markers[kind])


def update_epic_index(index_text, epic_id, status, implementation, verification):
    lines = index_text.splitlines()
    found = False
    for index, line in enumerate(lines):
        if not re.match(rf"^\|\s*`{re.escape(epic_id)}`\s*\|", line):
            continue
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) < 11:
            raise ValueError(f"Index row for {epic_id} has an unexpected shape")
        cells[4] = status
        cells[8] = implementation
        cells[9] = verification
        lines[index] = "| " + " | ".join(cells[1:-1]) + " |"
        found = True
        break
    if not found:
        raise ValueError(f"Local document index has no row for {epic_id}")
    return "\n".join(lines) + ("\n" if index_text.endswith("\n") else "")


def command_epic_tasks_reconcile_docs(args):
    try:
        launch_path, launch = load_launch_set(args.launch_set)
        epic = launch["epics"].get(args.epic)
        if not epic or not epic.get("runPath"):
            raise ValueError("Epic has no recorded Execution Run")
        projection = completion_projection_for_run(args.git_root, epic["runPath"])
        if not projection or projection.get("available") is not True or projection.get("implemented") is not True:
            raise ValueError("Canonical documents require an implemented completion projection")
        if projection.get("sourceSha256") != launch["source"]["sha256"]:
            raise ValueError("Completion projection does not match the launch-set source lock")
        primary = primary_worktree(args.git_root)
        source_path = Path(launch["source"]["path"]).resolve()
        try:
            source_path.relative_to(primary)
        except ValueError as exc:
            raise ValueError("Canonical PRD is not in the primary worktree") from exc
        index_path = primary / "local-docs" / "INDEX.md"
        exact_revision = projection.get("exactRevision") or "revision unavailable"
        final_status = "Complete" if projection.get("complete") is True else "Implementation-complete"
        source_before = source_path.read_text(encoding="utf-8")
        index_before = index_path.read_text(encoding="utf-8")
        locked_source = launch_source_text(launch)
        if epic_acceptance_identity(source_before, args.epic) != epic_acceptance_identity(locked_source, args.epic):
            raise ValueError("Canonical Epic acceptance changed after launch; start a new run for the revised source")
        existing_cells = index_epic_cells(index_before, args.epic)
        desired_implementation = f"Execution Run `{Path(epic['runPath']).name}` at `{exact_revision}`"
        desired_verification = f"Final Epic verification passed on `{exact_revision}`"
        if existing_cells["status"] not in {"Accepted", final_status}:
            raise ValueError("Canonical index status conflicts with the launch and completion projection")
        if existing_cells["implementation"] != desired_implementation and not placeholder_index_value(existing_cells["implementation"], "implementation"):
            raise ValueError("Canonical index implementation cell conflicts with the completion projection")
        if existing_cells["verification"] != desired_verification and not placeholder_index_value(existing_cells["verification"], "verification"):
            raise ValueError("Canonical index verification cell conflicts with the completion projection")
        source_after = replace_epic_metadata(source_before, args.epic, {
            "Epic status": final_status,
            "Implemented by": f"Execution Run {Path(epic['runPath']).name} at `{exact_revision}`",
            "Verified by": f"Final Epic verification on `{exact_revision}`",
        })
        index_after = update_epic_index(
            index_before, args.epic, final_status,
            desired_implementation,
            desired_verification,
        )
        if source_after != source_before:
            atomic_write_text(source_path, source_after)
        if index_after != index_before:
            atomic_write_text(index_path, index_after)
        payload = epic_launch_payload(
            launch_path, launch, args.git_root,
            reconciled={"epicId": args.epic, "prd": str(source_path), "index": str(index_path), "changed": source_after != source_before or index_after != index_before},
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "fail", "findings": [{"code": "canonical_epic_reconcile_failed", "severity": "fail", "message": str(exc)}]}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def launch_merge_lease_path(launch_path):
    launch_path = Path(launch_path).resolve()
    return launch_path.with_name(launch_path.stem + ".merge-lease.json")


def current_default_head(repo):
    symbolic = git(["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"], repo)
    remote_ref = symbolic.stdout.strip() if symbolic.returncode == 0 else "origin/main"
    result = git(["rev-parse", remote_ref], repo)
    if result.returncode != 0:
        result = git(["rev-parse", "main"], repo)
    if result.returncode != 0:
        raise ValueError("Cannot resolve the current default-branch head")
    return result.stdout.strip(), remote_ref


def refresh_default_head(repo):
    remote = git(["remote", "get-url", "origin"], repo)
    if remote.returncode == 0:
        fetched = git(["fetch", "origin"], repo)
        if fetched.returncode != 0:
            raise ValueError(fetched.stderr.strip() or fetched.stdout.strip() or "Cannot refresh origin before merge")
    return current_default_head(repo)


def run_launch_lease_context(run_path, handoff):
    run_path = Path(run_path).resolve()
    lock_path = run_path / "source-lock.json"
    if not lock_path.is_file():
        raise ValueError("Run-backed merge requires source-lock.json with an Epic launch binding")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    target = lock.get("target_epic_ids")
    launch_binding = lock.get("launch_set")
    if not isinstance(target, list) or len(target) != 1 or not isinstance(launch_binding, dict):
        raise ValueError("Run-backed merge requires exactly one launch-bound Epic")
    launch_path, launch = load_launch_set(launch_binding.get("path", ""))
    launch_source_text(launch)
    epic_id = target[0]
    epic = launch["epics"].get(epic_id)
    if (
        launch_binding.get("coverage_sha256") != launch["coverageSha256"]
        or handoff.get("epic", {}).get("id") != epic_id
        or handoff.get("binding", {}).get("runId") != run_path.name
        or not epic
        or epic.get("taskId") != launch_binding.get("task_id")
        or Path(epic.get("runPath") or "").resolve() != run_path
    ):
        raise ValueError("Run, launch coverage, Epic, task, or run-path binding does not match")
    return launch_path, launch, epic_id


def acquire_run_merge_lease(repo, run_path, handoff):
    launch_path, launch, epic_id = run_launch_lease_context(run_path, handoff)
    candidate = handoff["binding"]["headSha"]
    default_head, default_ref = refresh_default_head(repo)
    if git(["merge-base", "--is-ancestor", default_head, candidate], repo).returncode != 0:
        raise ValueError("Verified Epic candidate does not contain the current default-branch head; re-integrate and reverify")
    lease = {
        "schemaVersion": "gauntlet.epic-merge-lease.v1",
        "coverageSha256": launch["coverageSha256"],
        "epicId": epic_id,
        "candidateHead": candidate,
        "baseHead": default_head,
        "baseRef": default_ref,
    }
    lease_path = launch_merge_lease_path(launch_path)
    persist_merge_lease(repo, lease_path, lease, default_head)
    return lease_path, lease


def persist_merge_lease(repo, lease_path, lease, default_head):
    if lease_path.exists():
        current = json.loads(lease_path.read_text(encoding="utf-8"))
        if current != lease:
            if current.get("epicId") == lease["epicId"] and current.get("candidateHead") == lease["candidateHead"]:
                lease_path.unlink()
                raise ValueError("Default branch changed while this Epic held the merge lease; re-integrate and reverify")
            if current.get("epicId") == lease["epicId"]:
                old_candidate = current.get("candidateHead")
                if default_represents_candidate(repo, old_candidate, default_head):
                    raise ValueError("The previous leased Epic candidate is already on the default branch; reconcile that merge before replacing the lease")
                atomic_write_text(lease_path, json.dumps(lease, indent=2, sort_keys=True) + "\n")
            else:
                raise ValueError(f"Default-branch merge lease is held by {current.get('epicId', 'another Epic')}")
    else:
        write_new_file(lease_path, json.dumps(lease, indent=2, sort_keys=True) + "\n")


def validate_run_merge_lease(repo, lease_path, lease):
    if not Path(lease_path).is_file() or json.loads(Path(lease_path).read_text(encoding="utf-8")) != lease:
        raise ValueError("Run-backed merge lease disappeared or changed")
    default_head, _ = refresh_default_head(repo)
    if default_head != lease["baseHead"]:
        Path(lease_path).unlink(missing_ok=True)
        raise ValueError("Default branch advanced after lease acquisition; re-integrate and reverify")
    if git(["merge-base", "--is-ancestor", lease["baseHead"], lease["candidateHead"]], repo).returncode != 0:
        raise ValueError("Leased candidate no longer contains its verified default-branch base")


def default_represents_candidate(repo, candidate, default_head):
    ancestry = git(["merge-base", "--is-ancestor", candidate, default_head], repo)
    if ancestry.returncode == 0:
        return True
    if ancestry.returncode != 1:
        raise ValueError(ancestry.stderr.strip() or "Cannot determine candidate ancestry")
    candidate_tree = git(["rev-parse", f"{candidate}^{{tree}}"], repo)
    default_tree = git(["rev-parse", f"{default_head}^{{tree}}"], repo)
    if candidate_tree.returncode != 0 or default_tree.returncode != 0:
        raise ValueError(candidate_tree.stderr.strip() or default_tree.stderr.strip() or "Cannot compare candidate and default trees")
    return (
        candidate_tree.stdout.strip() == default_tree.stdout.strip()
    )


def release_run_merge_lease(repo, lease_path, lease, merged_head):
    default_head, _ = refresh_default_head(repo)
    if not default_represents_candidate(repo, lease["candidateHead"], merged_head):
        raise ValueError("Recorded merge head preserves neither candidate ancestry nor the exact candidate tree")
    if git(["merge-base", "--is-ancestor", merged_head, default_head], repo).returncode != 0:
        raise ValueError("Current default branch does not contain the recorded merge head")
    if not Path(lease_path).is_file() or json.loads(Path(lease_path).read_text(encoding="utf-8")) != lease:
        raise ValueError("Run-backed merge lease changed before release")
    Path(lease_path).unlink()


def persisted_run_merge_lease(run_path, handoff):
    """Return the exact launch lease for interrupted merge recovery, if one exists."""
    launch_path, launch, epic_id = run_launch_lease_context(run_path, handoff)
    lease_path = launch_merge_lease_path(launch_path)
    if not lease_path.is_file():
        return None
    lease = json.loads(lease_path.read_text(encoding="utf-8"))
    expected = {
        "schemaVersion": "gauntlet.epic-merge-lease.v1",
        "coverageSha256": launch["coverageSha256"],
        "epicId": epic_id,
        "candidateHead": handoff["binding"]["headSha"],
    }
    if any(lease.get(key) != value for key, value in expected.items()):
        raise ValueError("Persisted merge lease does not match this launch-bound Epic candidate")
    if not nonempty_string(lease.get("baseHead")) or not nonempty_string(lease.get("baseRef")):
        raise ValueError("Persisted merge lease is incomplete")
    return lease_path, lease


def recorded_run_merge_head(run_path):
    manifest = json.loads((Path(run_path) / "manifest.json").read_text(encoding="utf-8"))
    main_sha = manifest.get("release", {}).get("merge", {}).get("main_sha")
    if not re.fullmatch(r"[0-9a-f]{7,64}", main_sha or ""):
        raise ValueError("Execution Run has no valid recorded merge head")
    return main_sha


def command_epic_tasks_merge_lease_acquire(args):
    try:
        launch_path, launch = load_launch_set(args.launch_set)
        epic = launch["epics"].get(args.epic)
        if not epic or not epic.get("runPath"):
            raise ValueError("Epic has no recorded Execution Run")
        projection = completion_projection_for_run(args.git_root, epic["runPath"])
        if not projection or projection.get("available") is not True or projection.get("implemented") is not True:
            raise ValueError("Merge lease requires an implemented completion projection")
        if projection.get("exactRevision") != args.candidate_head:
            raise ValueError("Candidate head differs from the final Epic verification revision")
        default_head, default_ref = current_default_head(args.git_root)
        if default_head != args.verified_base:
            raise ValueError(f"Default branch advanced from {args.verified_base} to {default_head}; re-integrate and reverify before merging")
        if git(["merge-base", "--is-ancestor", default_head, args.candidate_head], args.git_root).returncode != 0:
            raise ValueError("Candidate does not contain the verified default-branch base; re-integrate and reverify before merging")
        lease_path = launch_merge_lease_path(launch_path)
        lease = {
            "schemaVersion": "gauntlet.epic-merge-lease.v1",
            "coverageSha256": launch["coverageSha256"],
            "epicId": args.epic,
            "candidateHead": args.candidate_head,
            "baseHead": args.verified_base,
            "baseRef": default_ref,
        }
        persist_merge_lease(args.git_root, lease_path, lease, default_head)
        payload = epic_launch_payload(launch_path, launch, args.git_root, mergeLease=lease)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "fail", "findings": [{"code": "epic_merge_lease_failed", "severity": "fail", "message": str(exc)}]}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_epic_tasks_merge_lease_release(args):
    try:
        launch_path, launch = load_launch_set(args.launch_set)
        lease_path = launch_merge_lease_path(launch_path)
        if not lease_path.is_file():
            raise ValueError("No Epic merge lease exists")
        lease = json.loads(lease_path.read_text(encoding="utf-8"))
        if lease.get("epicId") != args.epic or lease.get("candidateHead") != args.candidate_head:
            raise ValueError("Merge lease does not match the releasing Epic and candidate")
        default_head, _ = refresh_default_head(args.git_root)
        if git(["merge-base", "--is-ancestor", args.merged_head, default_head], args.git_root).returncode != 0:
            raise ValueError("Currently observed default branch does not contain the recorded merged head")
        if not default_represents_candidate(args.git_root, args.candidate_head, args.merged_head):
            raise ValueError("Merged revision does not contain the leased candidate head")
        lease_path.unlink()
        payload = epic_launch_payload(launch_path, launch, args.git_root, releasedMergeLease={"epicId": args.epic, "mergedHead": args.merged_head})
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"schemaVersion": EPIC_LAUNCH_SCHEMA, "status": "fail", "findings": [{"code": "epic_merge_lease_release_failed", "severity": "fail", "message": str(exc)}]}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


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


def archive_summary_from_run(repo, run_path):
    output, error = run_prd_controller(repo, ["completion", "--run", str(Path(run_path).resolve())])
    if error:
        return None, [{"code": "run_completion_unavailable", "severity": "fail", "message": error}]
    try:
        completion = json.loads(output)
        lock = json.loads((Path(run_path).resolve() / "source-lock.json").read_text(encoding="utf-8"))
        epic_id = lock["target_epic_ids"][0]
        epic = lock["epics"][epic_id]
    except (KeyError, IndexError, json.JSONDecodeError, OSError) as exc:
        return None, [{"code": "invalid_run_completion", "severity": "fail", "message": str(exc)}]
    bullets = [
        f"{epic_id}: {epic['title']} — {completion['exactState']}.",
        f"Final Epic verification revision: {completion.get('exactRevision') or 'unavailable'}.",
    ]
    pending = completion.get("pendingGates") or []
    bullets.append("Pending gates: " + (", ".join(pending) if pending else "none") + ".")
    return {"source": "completion-projection", "run": Path(run_path).resolve().name, "bullets": bullets}, []


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


def validate_handoff_v1_fields(data, expected_schema="1.0"):
    findings = []
    if not isinstance(data, dict):
        return [handoff_finding("invalid_handoff", "Merge handoff must be a JSON object.")]
    missing = sorted(REQUIRED_HANDOFF_FIELDS - set(data))
    for field in missing:
        findings.append(handoff_finding("missing_handoff_field", f"Merge handoff is missing: {field}."))
    if data.get("schemaVersion") != expected_schema:
        findings.append(handoff_finding("unsupported_handoff_schema", f"Merge handoff schemaVersion must be {expected_schema}."))

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


def nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def validate_string_list(findings, value, code, label, allow_empty=True):
    if not isinstance(value, list) or (not allow_empty and not value) or not all(nonempty_string(item) for item in value):
        findings.append(handoff_finding(code, f"{label} must be {'a non-empty' if not allow_empty else 'a'} list of non-empty strings."))


def validate_run_merge_handoff(data):
    findings = []
    if not isinstance(data, dict):
        return [handoff_finding("invalid_run_projection", "Run projection must be a JSON object.")]
    if data.get("schemaVersion") != "3.0":
        findings.append(handoff_finding("invalid_run_schema", "Run projection schemaVersion must be 3.0."))
    for field in sorted(REQUIRED_RUN_HANDOFF_FIELDS - set(data)):
        findings.append(handoff_finding("missing_run_projection_field", f"Run projection is missing: {field}."))
    unknown = set(data) - REQUIRED_RUN_HANDOFF_FIELDS
    if unknown:
        findings.append(handoff_finding("unknown_run_projection_field", "Run projection contains unsupported fields: " + ", ".join(sorted(unknown)) + "."))
    if not nonempty_string(data.get("title")):
        findings.append(handoff_finding("invalid_run_title", "title must be non-empty."))

    binding = data.get("binding")
    if not isinstance(binding, dict):
        findings.append(handoff_finding("invalid_run_binding", "binding must be an object."))
    else:
        if set(binding) != RUN_BINDING_FIELDS:
            findings.append(handoff_finding("invalid_run_binding", "binding must contain exactly the schema 3.0 binding fields."))
        if not nonempty_string(binding.get("runId")) or not nonempty_string(binding.get("repository")):
            findings.append(handoff_finding("invalid_run_binding", "binding.runId and binding.repository must be non-empty."))
        if not isinstance(binding.get("generation"), int) or isinstance(binding.get("generation"), bool) or binding.get("generation", -1) < 0:
            findings.append(handoff_finding("invalid_run_binding", "binding.generation must be a non-negative integer."))
        for field in ["branch", "headSha"]:
            if not nonempty_string(binding.get(field)):
                findings.append(handoff_finding("invalid_run_binding", f"binding.{field} must be non-empty."))
        for field in ["sourceLockSha256", "graphSha256", "epicVerificationSha256"]:
            if not isinstance(binding.get(field), str) or not re.fullmatch(r"[0-9a-f]{64}", binding[field]):
                findings.append(handoff_finding("invalid_run_binding_hash", f"binding.{field} must be a lowercase SHA-256 digest."))

    epic = data.get("epic")
    if not isinstance(epic, dict) or set(epic) != {"id", "title", "scopeAreas"}:
        findings.append(handoff_finding("invalid_epic_projection", "epic must contain id, title, and scopeAreas."))
    else:
        if not nonempty_string(epic.get("id")) or not nonempty_string(epic.get("title")):
            findings.append(handoff_finding("invalid_epic_projection", "epic.id and epic.title must be non-empty."))
        scopes = epic.get("scopeAreas")
        if not isinstance(scopes, list) or not scopes:
            findings.append(handoff_finding("invalid_epic_projection", "epic.scopeAreas must be non-empty."))
        else:
            for index, scope in enumerate(scopes, 1):
                if not isinstance(scope, dict) or set(scope) != {"id", "responsibility"} or any(not nonempty_string(scope.get(key)) for key in ["id", "responsibility"]):
                    findings.append(handoff_finding("invalid_epic_scope", f"epic.scopeAreas item {index} must contain id and responsibility."))
    validate_string_list(findings, data.get("acceptedCriteria"), "invalid_accepted_criteria", "acceptedCriteria", allow_empty=False)
    validate_string_list(findings, data.get("changedPaths"), "invalid_changed_paths", "changedPaths")
    validate_string_list(findings, data.get("verificationReceipts"), "invalid_verification_receipts", "verificationReceipts", allow_empty=False)

    completion = data.get("completion")
    completion_fields = {"implemented", "merged", "deployed", "productionProved", "complete", "epicId", "exactRevision", "exactState", "pendingGates", "sourceSha256", "verificationSummary"}
    if not isinstance(completion, dict) or set(completion) != completion_fields:
        findings.append(handoff_finding("invalid_completion_projection", "completion has an unsupported shape."))
    else:
        for field in ["implemented", "merged", "deployed", "productionProved", "complete"]:
            if not isinstance(completion.get(field), bool):
                findings.append(handoff_finding("invalid_completion_projection", f"completion.{field} must be boolean."))
        implemented = completion.get("implemented") is True
        merged = completion.get("merged") is True
        deployed = completion.get("deployed") is True
        production_proved = completion.get("productionProved") is True
        complete = completion.get("complete") is True
        if (merged and not implemented) or (deployed and not merged) or (production_proved and not deployed) or (complete and not (implemented and merged)):
            findings.append(handoff_finding("contradictory_completion_projection", "Completion stages must be monotonic and complete requires implemented plus merged."))
        if implemented and not re.fullmatch(r"[0-9a-f]{40,64}", completion.get("exactRevision") or ""):
            findings.append(handoff_finding("invalid_completion_projection", "Implemented state requires an exact revision."))
        if not implemented and completion.get("exactRevision") is not None:
            findings.append(handoff_finding("invalid_completion_projection", "An unimplemented state cannot claim an exact verified revision."))
        if implemented and not nonempty_string(completion.get("verificationSummary")):
            findings.append(handoff_finding("invalid_completion_projection", "Implemented state requires a final verification summary."))
        if not re.fullmatch(r"[0-9a-f]{64}", completion.get("sourceSha256") or ""):
            findings.append(handoff_finding("invalid_completion_projection", "completion.sourceSha256 must be a lowercase SHA-256 digest."))
        expected_state = (
            "complete" if complete else
            "production-proved" if production_proved else
            "deployed" if deployed else
            "merged" if merged else
            "implementation-complete" if implemented else
            "in-progress"
        )
        if completion.get("exactState") != expected_state:
            findings.append(handoff_finding("contradictory_completion_projection", f"completion.exactState must be {expected_state} for the declared stage facts."))
        validate_string_list(findings, completion.get("pendingGates"), "invalid_completion_projection", "completion.pendingGates")

    deferrals = data.get("deferrals")
    if not isinstance(deferrals, dict) or set(deferrals) != {"cannotVerify", "nonGoals"}:
        findings.append(handoff_finding("invalid_deferrals", "deferrals must contain cannotVerify and nonGoals."))
    else:
        validate_string_list(findings, deferrals.get("cannotVerify"), "invalid_deferrals", "deferrals.cannotVerify")
        validate_string_list(findings, deferrals.get("nonGoals"), "invalid_deferrals", "deferrals.nonGoals")

    gates = data.get("releaseGates")
    if not isinstance(gates, list) or not gates:
        findings.append(handoff_finding("missing_release_gate", "releaseGates must be non-empty."))
    else:
        seen = set()
        required_gate_fields = {"id", "stage", "status", "summary", "evidenceRefs", "blocksPr", "blocksOverallCompletion"}
        for index, gate in enumerate(gates, 1):
            if not isinstance(gate, dict) or set(gate) != required_gate_fields:
                findings.append(handoff_finding("invalid_release_gate", f"releaseGates item {index} has an unsupported shape."))
                continue
            for field in ["id", "stage", "status", "summary"]:
                if not nonempty_string(gate.get(field)):
                    findings.append(handoff_finding("invalid_release_gate", f"releaseGates item {index}.{field} must be non-empty."))
            if gate.get("status") not in {"pass", "fail", "pending", "stale", "not-required", "not-applicable"}:
                findings.append(handoff_finding("invalid_release_gate", f"releaseGates item {index}.status is unsupported."))
            if gate.get("id") in seen:
                findings.append(handoff_finding("duplicate_release_gate", f"Release gate {gate.get('id')} appears more than once."))
            seen.add(gate.get("id"))
            for field in ["blocksPr", "blocksOverallCompletion"]:
                if not isinstance(gate.get(field), bool):
                    findings.append(handoff_finding("invalid_release_gate", f"releaseGates item {index}.{field} must be boolean."))
            validate_string_list(findings, gate.get("evidenceRefs"), "invalid_release_gate_evidence", f"releaseGates item {index}.evidenceRefs")
    if isinstance(epic, dict) and isinstance(completion, dict):
        if epic.get("id") != completion.get("epicId"):
            findings.append(handoff_finding("completion_epic_mismatch", "completion.epicId must equal epic.id."))
    if isinstance(binding, dict) and isinstance(completion, dict) and completion.get("implemented") is True:
        if binding.get("headSha") != completion.get("exactRevision"):
            findings.append(handoff_finding("completion_revision_mismatch", "The implemented revision must equal binding.headSha."))
    if isinstance(gates, list) and isinstance(completion, dict):
        open_overall = [
            gate for gate in gates if isinstance(gate, dict) and gate.get("blocksOverallCompletion") is True
            and gate.get("status") not in {"pass", "not-applicable"}
        ]
        if completion.get("complete") is True and open_overall:
            findings.append(handoff_finding("contradictory_completion_projection", "Complete state cannot retain an open overall-completion release gate."))
        if completion.get("complete") is True and completion.get("pendingGates"):
            findings.append(handoff_finding("contradictory_completion_projection", "Complete state cannot retain pending gates."))
        if completion.get("complete") is not True and not completion.get("pendingGates"):
            findings.append(handoff_finding("contradictory_completion_projection", "An incomplete state must name at least one pending gate."))
    if has_secret(json.dumps(data, sort_keys=True)):
        findings.append(handoff_finding("secret_like_run_projection", "Run projection contains secret-like content."))
    return findings


def validate_merge_handoff(data):
    if isinstance(data, dict) and data.get("schemaVersion") == "3.0":
        return validate_run_merge_handoff(data)
    return validate_handoff_v1_fields(data)


def merge_binding_digest(data):
    return hashlib.sha256(json.dumps(data["binding"], sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def render_run_pr_body(data):
    epic = data["epic"]
    completion = data["completion"]
    lines = [
        f"## Epic {epic['id']}: {epic['title']}", "",
        f"Implementation state: **{completion['exactState']}**", "",
        "### Scope Areas", "",
        *[f"- `{scope['id']}` — {scope['responsibility']}" for scope in epic["scopeAreas"]], "",
        "## Accepted Criteria", "",
        *[f"- {item}" for item in data["acceptedCriteria"]], "",
        "## Changed Paths", "",
        *([f"- `{path}`" for path in data["changedPaths"]] or ["- None recorded."]), "",
        "## Verification", "",
        f"- Exact verified revision: `{completion['exactRevision']}`",
        f"- {completion['verificationSummary'] or 'Final Epic verification passed.'}",
        *[f"- Receipt: `{receipt}`" for receipt in data["verificationReceipts"]], "",
        "## Completion State", "",
        f"- Implemented: {'yes' if completion['implemented'] else 'no'}",
        f"- Merged: {'yes' if completion['merged'] else 'no'}",
        f"- Deployed: {'yes' if completion['deployed'] else 'no'}",
        f"- Production-proved: {'yes' if completion['productionProved'] else 'no'}",
        f"- Complete across applicable stages: {'yes' if completion['complete'] else 'no'}", "",
        "## Deferrals", "",
        *([f"- Cannot verify: {item}" for item in data["deferrals"]["cannotVerify"]] or ["- Cannot verify: none."]),
        *([f"- Non-goal: {item}" for item in data["deferrals"]["nonGoals"]] or ["- Non-goals: none."]), "",
        "## Release Gates", "",
    ]
    for gate in data["releaseGates"]:
        evidence = f" Evidence: {', '.join(item.strip() for item in gate['evidenceRefs'])}." if gate["evidenceRefs"] else ""
        lines.append(
            f"- **{gate['id'].strip()} — {gate['stage'].strip()}**: {gate['status'].strip()} — "
            f"{gate['summary'].strip()} (blocks PR: {'yes' if gate['blocksPr'] else 'no'}; "
            f"blocks overall completion: {'yes' if gate['blocksOverallCompletion'] else 'no'}).{evidence}"
        )
    lines.extend(["", f"<!-- gauntlet-merge-binding: {merge_binding_digest(data)} -->"])
    return "\n".join(lines).rstrip() + "\n"


def render_pr_body(data):
    if data.get("schemaVersion") == "3.0":
        return render_run_pr_body(data)
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


def projection_changelog_entry(data):
    if data.get("schemaVersion") == "3.0":
        epic = data["epic"]
        return f"Implement {epic['id']}: {epic['title']}."
    return data["changelog"]


def pending_run_merge_gates(handoff):
    return [
        gate for gate in handoff.get("releaseGates", [])
        if gate.get("stage") == "merge" and gate.get("id") != "merge-to-default"
        and gate.get("status") not in {"pass", "not-applicable"}
    ]


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


def repository_identity(repo):
    remote = git(["config", "--get", "remote.origin.url"], repo)
    if remote.returncode == 0 and remote.stdout.strip():
        return remote.stdout.strip()
    return str(Path(repo).resolve())


def current_head(repo):
    result = git(["rev-parse", "HEAD"], repo)
    return result.stdout.strip() if result.returncode == 0 else ""


def run_project_pr(repo, run_path):
    controller = prd_controller_path()
    if not controller.is_file():
        return None, f"Execution Run projection controller does not exist: {controller}"
    result = run_cmd([sys.executable, str(controller), "project-pr", "--run", str(Path(run_path).resolve())], cwd=repo)
    if result.returncode != 0:
        return None, result.stderr.strip() or result.stdout.strip() or "project-pr failed"
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        return None, f"project-pr did not emit JSON: {error}"
    return data, None


def run_prd_controller(repo, arguments):
    controller = prd_controller_path()
    if not controller.is_file():
        return None, f"Execution Run controller does not exist: {controller}"
    result = run_cmd([sys.executable, str(controller), *arguments], cwd=repo)
    if result.returncode != 0:
        return None, result.stderr.strip() or result.stdout.strip() or "prd-run command failed"
    return result.stdout, None


def prd_controller_path():
    override = os.environ.get("GAUNTLET_DEV_PRD_CONTROLLER")
    if override:
        if os.environ.get("GAUNTLET_ALLOW_DEV_CONTROLLER") != "1":
            return Path("/__gauntlet_untrusted_controller_override_rejected__")
        return Path(override).resolve()
    return SCRIPTS / "prd-run.py"


def run_authority_granted(repo, run_path, capability):
    output, error = run_prd_controller(repo, [
        "authority-status", "--run", str(Path(run_path).resolve()), "--capability", capability,
    ])
    if error:
        return False, error
    try:
        status = json.loads(output)
    except json.JSONDecodeError as exc:
        return False, f"authority-status did not emit JSON: {exc}"
    if status.get("capability") != capability or status.get("granted") is not True:
        return False, f"Execution Run has not granted {capability} authority"
    return True, None


def review_unit_status(repo, run_path, unit_id):
    output, error = run_prd_controller(repo, [
        "review-unit-status", "--run", str(Path(run_path).resolve()), "--unit", unit_id,
    ])
    if error:
        return None, error
    try:
        return json.loads(output), None
    except json.JSONDecodeError as exc:
        return None, f"review-unit-status did not emit JSON: {exc}"


def update_review_unit(repo, run_path, unit_id, action, **fields):
    arguments = ["review-unit", "--run", str(Path(run_path).resolve()), "--unit", unit_id, "--action", action]
    for key, value in fields.items():
        if value is not None:
            arguments.extend(["--" + key.replace("_", "-"), str(value)])
    _, error = run_prd_controller(repo, arguments)
    return error


def review_unit_pr(repo, branch):
    result = gh([
        "pr", "list", "--head", branch, "--state", "open", "--limit", "1", "--json",
        "number,state,isDraft,mergeable,mergedAt,mergeCommit,statusCheckRollup,url,baseRefName,headRefName,headRefOid,reviewDecision",
    ], repo)
    if result.returncode != 0:
        return None, result.stderr.strip() or result.stdout.strip()
    try:
        values = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return None, f"GitHub review-unit query returned invalid JSON: {exc}"
    return (values[0] if values else None), None


def review_pr_identity_error(pr, integration_branch, branch, head_sha):
    if not pr:
        return "No open review-unit PR exists for the review branch."
    if pr.get("state") != "OPEN":
        return "Review-unit PR must be open."
    if pr.get("baseRefName") != integration_branch or pr.get("headRefName") != branch:
        return "Review-unit PR base or head branch does not match the frozen Review Unit."
    if pr.get("headRefOid") != head_sha:
        return "Review-unit PR head changed; rerun checks against the exact remote head."
    return None


def render_review_unit_body(status):
    unit = status["unit"]
    epics = sorted({ticket["epicId"] for ticket in unit["tickets"]})
    lines = [
        "## Review Unit",
        "",
        f"Unit `{unit['id']}` covers Epics {', '.join(epics)} and targets integration branch `{status['integrationBranch']}`.",
        "",
        "## Included Tickets",
        "",
    ]
    for ticket in unit["tickets"]:
        lines.append(f"- **{ticket['id']} — {ticket['title']}**: {ticket['objective']}")
    lines.extend([
        "",
        "## Integration Contract",
        "",
        "- Checks bind this review branch to the current integration-branch commit and its synthetic merge tree.",
        "- Advancing the integration branch invalidates the merge-sensitive check and requires a recheck.",
        "- Merging this PR grants no authority to merge the final Project PR to the default branch.",
        "",
    ])
    return "\n".join(lines)


def review_unit_title(status):
    unit = status["unit"]
    titles = ", ".join(ticket["title"] for ticket in unit["tickets"][:2])
    if len(unit["tickets"]) > 2:
        titles += f" and {len(unit['tickets']) - 2} more"
    return f"review({unit['id'].lower()}): {titles}"


def review_unit_body_path(repo, unit_id, requested=None):
    path = Path(requested) if requested else Path(".gauntlet") / f"review-unit-{unit_id.lower()}.md"
    return path if path.is_absolute() else Path(repo) / path


def review_unit_plan_payload(args, write_body=False):
    repo = Path(args.git_root).resolve()
    run_path = merge_input_path(repo, args.run)
    payload = {
        "schemaVersion": "1.0", "status": "pass", "findings": [], "actions": [],
        "run": str(run_path), "unit": args.unit,
    }
    status, error = review_unit_status(repo, run_path, args.unit)
    if error:
        add_finding(payload, "review_unit_status_failed", "fail", error)
        payload["status"] = status_for(payload)
        return payload
    payload["reviewUnit"] = status
    unit = status["unit"]
    branch = branch_name(repo)
    integration_branch = status["integrationBranch"]
    payload["branch"] = branch
    payload["integrationBranch"] = integration_branch
    body_path = review_unit_body_path(repo, args.unit, getattr(args, "body", None) or getattr(args, "body_output", None))
    payload["bodyPath"] = str(body_path)

    if status.get("prStrategy") != "review-prs-plus-final":
        add_finding(payload, "review_unit_strategy_required", "fail", "Review-unit PRs require review-prs-plus-final.")
    if not branch or branch == integration_branch or branch in {"main", "master"}:
        add_finding(payload, "review_unit_branch_required", "fail", "Run this command from the dedicated review-unit branch, not the integration or default branch.")
    recorded_branch = unit.get("branch")
    if recorded_branch and recorded_branch != branch:
        add_finding(payload, "review_unit_branch_mismatch", "fail", f"Unit {args.unit} is bound to {recorded_branch}, not {branch}.")
    if any(ticket["status"] != "integrated" for ticket in unit["tickets"]):
        add_finding(payload, "review_unit_tickets_not_integrated", "fail", "Every review-unit Ticket must have parent integration evidence before its PR can open.")
    incomplete_dependencies = [
        dependency for dependency in unit.get("dependencies", [])
        if status.get("dependencyStates", {}).get(dependency) not in {"merged", "verified", "cleanup-eligible", "cleaned"}
    ]
    if incomplete_dependencies:
        add_finding(payload, "review_unit_dependencies_pending", "fail", "Review-unit dependencies are not merged: " + ", ".join(incomplete_dependencies))
    required_authority = ("push-review-branch", "open-review-pr") + (() if write_body else ("merge-to-integration",))
    missing_authority = [key for key in required_authority if not status.get("authority", {}).get(key)]
    if missing_authority:
        add_finding(payload, "review_unit_authority_missing", "fail", "Missing review-unit authority: " + ", ".join(missing_authority))
    if dirty_paths(repo):
        add_finding(payload, "uncommitted_review_unit_work", "fail", "Commit or preserve review-unit work before opening its PR.")

    if write_body and not payload["findings"]:
        body_path.parent.mkdir(parents=True, exist_ok=True)
        body_path.write_text(render_review_unit_body(status), encoding="utf-8")
    elif not write_body:
        expected = render_review_unit_body(status)
        if not body_path.is_file() or body_path.read_text(encoding="utf-8") != expected:
            add_finding(payload, "review_unit_body_out_of_date", "fail", "Run review-unit prepare again before plan or execute.")

    fetch = git(["fetch", "origin", integration_branch], repo)
    if fetch.returncode != 0:
        add_finding(payload, "review_unit_base_fetch_failed", "fail", fetch.stderr.strip() or fetch.stdout.strip())
    else:
        base = git(["rev-parse", f"origin/{integration_branch}"], repo)
        if base.returncode == 0:
            payload["testedBaseSha"] = base.stdout.strip()
    pr, pr_error = review_unit_pr(repo, branch) if branch else (None, None)
    payload["pr"] = pr
    if pr_error:
        add_finding(payload, "review_unit_pr_unverified", "warn", pr_error)
    if pr:
        if pr.get("baseRefName") != integration_branch or pr.get("headRefName") != branch:
            add_finding(payload, "review_unit_pr_branch_mismatch", "fail", "Existing review PR does not match the frozen head/base branches.")
    payload["status"] = status_for(payload)
    if payload["status"] in {"pass", "warn"}:
        payload["actions"] = [
            {"type": "git_push", "branch": branch},
            {"type": "gh_pr_edit" if pr else "gh_pr_create"},
            {"type": "record_review_opened"},
            {"type": "gh_pr_checks_watch"},
            {"type": "record_review_checked"},
            {"type": "record_review_merge_lock"},
            {"type": "git_push_integration_with_lease"},
            {"type": "verify_review_merge"},
            {"type": "cleanup_review_branch"},
        ]
    return payload


def command_review_unit_prepare(args):
    payload = review_unit_plan_payload(args, write_body=True)
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_review_unit_plan(args):
    payload = review_unit_plan_payload(args)
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def wait_for_review_unit_checks(repo, branch, timeout_seconds=60, poll_seconds=2):
    deadline = time.monotonic() + timeout_seconds
    last_error = None
    while True:
        pr, last_error = review_unit_pr(repo, branch)
        if pr and pr.get("statusCheckRollup"):
            return pr, None
        if time.monotonic() >= deadline:
            return pr, last_error or f"No review-unit checks were reported within {timeout_seconds} seconds."
        time.sleep(poll_seconds)


def synthetic_merge_tree(repo, base_sha, head_sha):
    result = git(["merge-tree", "--write-tree", base_sha, head_sha], repo)
    if result.returncode != 0:
        return None, result.stderr.strip() or result.stdout.strip() or "synthetic merge failed"
    first = result.stdout.splitlines()[0].strip() if result.stdout.splitlines() else ""
    if not re.fullmatch(r"[0-9a-f]{40,64}", first):
        return None, "git merge-tree did not return a merge tree object ID"
    return first, None


def find_review_merge(repo, tip, base_sha, head_sha, tree_sha):
    history = git(["rev-list", "--first-parent", tip, f"^{base_sha}"], repo)
    if history.returncode != 0:
        return None
    for commit in history.stdout.splitlines():
        parents = git(["rev-list", "--parents", "-n", "1", commit], repo)
        tree = git(["rev-parse", f"{commit}^{{tree}}"], repo)
        values = parents.stdout.split() if parents.returncode == 0 else []
        if len(values) == 3 and values[1:] == [base_sha, head_sha] and tree.returncode == 0 and tree.stdout.strip() == tree_sha:
            return commit
    return None


def review_unit_evidence_path(run_path, unit_id, kind, discriminator):
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", unit_id.lower())
    return Path(run_path) / "evidence" / f"review-unit-{safe}-{kind}-{discriminator[:12]}.md"


def command_review_unit_execute(args):
    payload = review_unit_plan_payload(args)
    if payload["status"] not in {"pass", "warn"}:
        print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    repo = Path(args.git_root).resolve()
    run_path = merge_input_path(repo, args.run)
    branch = payload["branch"]
    integration_branch = payload["integrationBranch"]
    body_path = Path(payload["bodyPath"])
    executed = []

    def fail(code, message):
        add_finding(payload, code, "fail", message)
        payload["status"] = status_for(payload)

    status, error = review_unit_status(repo, run_path, args.unit)
    if error:
        fail("review_unit_status_failed", error)
    unit = (status or {}).get("unit", {})

    if payload["status"] in {"pass", "warn"} and unit.get("state") == "pending":
        result = git(["push", "-u", "origin", f"HEAD:{branch}"], repo)
        if result.returncode != 0:
            fail("review_unit_push_failed", result.stderr.strip() or result.stdout.strip())
        else:
            executed.append({"type": "git_push", "branch": branch})
            pr, _ = review_unit_pr(repo, branch)
            if pr:
                result = gh(["pr", "edit", str(pr["number"]), "--title", review_unit_title(status), "--body-file", str(body_path)], repo)
                action = "gh_pr_edit"
            else:
                result = gh([
                    "pr", "create", "--title", review_unit_title(status), "--body-file", str(body_path),
                    "--base", integration_branch, "--head", branch,
                ], repo)
                action = "gh_pr_create"
            if result.returncode != 0:
                fail(f"review_unit_{action}_failed", result.stderr.strip() or result.stdout.strip())
            else:
                executed.append({"type": action})
                pr, pr_error = review_unit_pr(repo, branch)
                if not pr:
                    fail("review_unit_pr_missing", pr_error or "Review-unit PR was not discoverable after publication.")
                else:
                    identity_error = review_pr_identity_error(pr, integration_branch, branch, current_head(repo))
                    if identity_error:
                        fail("review_unit_pr_identity_mismatch", identity_error)
                    else:
                        error = update_review_unit(
                            repo, run_path, args.unit, "opened", branch=branch,
                            pr=pr.get("url") or f"#{pr.get('number')}",
                        )
                        if error:
                            fail("record_review_opened_failed", error)
                        else:
                            executed.append({"type": "record_review_opened"})
                            status, _ = review_unit_status(repo, run_path, args.unit)
                            unit = status["unit"]

    local_head = current_head(repo)
    checked = unit.get("check", {})
    base_drift = unit.get("state") == "merge-locked" and payload.get("testedBaseSha") != checked.get("tested_base_sha")
    recoverable_merge = None
    if base_drift:
        recoverable_merge = find_review_merge(
            repo, f"origin/{integration_branch}", checked.get("tested_base_sha"),
            checked.get("head_sha"), checked.get("tested_tree_sha"),
        )
    should_check = unit.get("state") in {"opened", "checked"} or (
        unit.get("state") == "merge-locked" and (
            local_head != checked.get("head_sha") or (base_drift and recoverable_merge is None)
        )
    )
    if payload["status"] in {"pass", "warn"} and should_check:
        refresh = git(["fetch", "origin", integration_branch, branch], repo)
        if refresh.returncode != 0:
            fail("review_unit_refresh_failed", refresh.stderr.strip() or refresh.stdout.strip())
        else:
            base = git(["rev-parse", f"origin/{integration_branch}"], repo).stdout.strip()
            head = git(["rev-parse", f"origin/{branch}"], repo).stdout.strip()
            local_head = current_head(repo)
            pr, checks_error = wait_for_review_unit_checks(repo, branch)
            identity_error = review_pr_identity_error(pr, integration_branch, branch, head)
            if checks_error:
                fail("review_unit_checks_missing", checks_error)
            elif local_head != head:
                fail("review_unit_local_head_drift", "Local HEAD must equal the exact remote review branch head before checks are accepted.")
            elif identity_error:
                fail("review_unit_pr_identity_mismatch", identity_error)
            else:
                check_state, check_message = checks_state(pr.get("statusCheckRollup", []))
                if check_state != "passing":
                    fail(f"review_unit_checks_{check_state}", check_message)
                else:
                    result = gh(["pr", "checks", str(pr["number"]), "--watch"], repo)
                    if result.returncode != 0:
                        fail("review_unit_checks_failed", result.stderr.strip() or result.stdout.strip())
                    else:
                        executed.append({"type": "gh_pr_checks_watch", "prNumber": pr["number"]})
                        fetch = git(["fetch", "origin", integration_branch, branch], repo)
                        refreshed_pr, pr_error = review_unit_pr(repo, branch)
                        refreshed_base = git(["rev-parse", f"origin/{integration_branch}"], repo).stdout.strip() if fetch.returncode == 0 else ""
                        refreshed_head = git(["rev-parse", f"origin/{branch}"], repo).stdout.strip() if fetch.returncode == 0 else ""
                        identity_error = review_pr_identity_error(refreshed_pr, integration_branch, branch, head)
                        if fetch.returncode != 0:
                            fail("review_unit_refresh_failed", fetch.stderr.strip() or fetch.stdout.strip())
                        elif pr_error:
                            fail("review_unit_pr_refresh_failed", pr_error)
                        elif refreshed_base != base or refreshed_head != head or current_head(repo) != head:
                            fail("review_unit_head_changed_after_checks", "Review or integration branch changed while checks were running; recheck the new tuple.")
                        elif identity_error:
                            fail("review_unit_pr_identity_mismatch", identity_error)
                        else:
                            tree, tree_error = synthetic_merge_tree(repo, base, head)
                            if tree_error:
                                fail("review_unit_synthetic_merge_failed", tree_error)
                            else:
                                evidence = review_unit_evidence_path(run_path, args.unit, "check", base + head)
                                evidence.write_text(
                                    "# Review unit check\n\n"
                                    f"Unit: {args.unit}\n\nHead: {head}\n\nTested base: {base}\n\n"
                                    f"Synthetic merge tree: {tree}\n\nGitHub checks: pass\n",
                                    encoding="utf-8",
                                )
                                error = update_review_unit(
                                    repo, run_path, args.unit, "checked", head_sha=head,
                                    tested_base_sha=base, tested_tree_sha=tree,
                                    proof_command=f"gh pr checks {pr['number']} --watch", proof_result="pass",
                                    proof_evidence=evidence,
                                )
                                if error:
                                    fail("record_review_checked_failed", error)
                                else:
                                    executed.append({"type": "record_review_checked", "testedBaseSha": base, "testedTreeSha": tree})
                                    error = update_review_unit(repo, run_path, args.unit, "merge-locked", current_base_sha=base)
                                    if error:
                                        fail("record_review_merge_lock_failed", error)
                                    else:
                                        executed.append({"type": "record_review_merge_lock"})
                                        status, _ = review_unit_status(repo, run_path, args.unit)
                                        unit = status["unit"]

    if payload["status"] in {"pass", "warn"} and unit.get("state") == "merge-locked":
        fetch = git(["fetch", "origin", integration_branch], repo)
        current_base = git(["rev-parse", f"origin/{integration_branch}"], repo).stdout.strip() if fetch.returncode == 0 else ""
        locked_base = unit.get("merge_lock", {}).get("base_sha")
        head = unit.get("check", {}).get("head_sha")
        tested_tree = unit.get("check", {}).get("tested_tree_sha")
        merge_commit = None
        if fetch.returncode == 0 and current_base != locked_base:
            merge_commit = find_review_merge(repo, f"origin/{integration_branch}", locked_base, head, tested_tree)
            if merge_commit is None:
                fail("review_unit_base_changed_after_lock", "Integration branch advanced after merge lock; rerun execute to recheck against the new base.")
        elif fetch.returncode != 0:
            fail("review_unit_base_refresh_failed", fetch.stderr.strip() or fetch.stdout.strip())
        if payload["status"] in {"pass", "warn"} and merge_commit is None:
            commit = run_cmd([
                "git", "commit-tree", tested_tree, "-p", locked_base, "-p", head,
                "-m", f"Merge review unit {args.unit} into {integration_branch}",
            ], cwd=repo)
            if commit.returncode != 0:
                fail("review_unit_merge_commit_failed", commit.stderr.strip() or commit.stdout.strip())
            else:
                merge_commit = commit.stdout.strip()
                push = git([
                    "push", "origin", f"{merge_commit}:refs/heads/{integration_branch}",
                    f"--force-with-lease=refs/heads/{integration_branch}:{locked_base}",
                ], repo)
                if push.returncode != 0:
                    fail("review_unit_integration_push_failed", push.stderr.strip() or push.stdout.strip())
                else:
                    executed.append({"type": "git_push_integration_with_lease", "mergeSha": merge_commit})
        if payload["status"] in {"pass", "warn"} and merge_commit:
            refreshed = git(["fetch", "origin", integration_branch], repo)
            tree_result = git(["rev-parse", f"{merge_commit}^{{tree}}"], repo)
            reachable = git(["merge-base", "--is-ancestor", merge_commit, f"origin/{integration_branch}"], repo) if refreshed.returncode == 0 else refreshed
            if refreshed.returncode != 0:
                fail("review_unit_base_refresh_failed", refreshed.stderr.strip() or refreshed.stdout.strip())
            elif tree_result.returncode != 0:
                fail("review_unit_merge_tree_missing", tree_result.stderr.strip() or tree_result.stdout.strip())
            elif reachable.returncode != 0:
                fail("review_unit_merge_not_on_integration", "Recorded review merge is not reachable from the remote integration branch.")
            else:
                merged_tree = tree_result.stdout.strip()
                error = update_review_unit(
                    repo, run_path, args.unit, "merged", merge_sha=merge_commit,
                    merged_tree_sha=merged_tree,
                )
                if error:
                    fail("record_review_merged_failed", error)
                else:
                    executed.append({"type": "record_review_merged", "mergeSha": merge_commit})
                    status, _ = review_unit_status(repo, run_path, args.unit)
                    unit = status["unit"]

    if payload["status"] in {"pass", "warn"} and unit.get("state") == "merged":
        head = unit.get("check", {}).get("head_sha")
        merge_sha = unit.get("merge_sha")
        refreshed = git(["fetch", "origin", integration_branch], repo)
        ancestor = git(["merge-base", "--is-ancestor", head, merge_sha], repo)
        remote_ancestor = git(["merge-base", "--is-ancestor", merge_sha, f"origin/{integration_branch}"], repo) if refreshed.returncode == 0 else refreshed
        if refreshed.returncode != 0:
            fail("review_unit_verification_refresh_failed", refreshed.stderr.strip() or refreshed.stdout.strip())
        elif ancestor.returncode != 0:
            fail("review_unit_merge_not_verified", "Reviewed head is not reachable from the recorded merge commit.")
        elif remote_ancestor.returncode != 0:
            fail("review_unit_merge_not_on_integration", "Recorded review merge is absent from the remote integration branch.")
        else:
            evidence = review_unit_evidence_path(run_path, args.unit, "verified", merge_sha)
            evidence.write_text(
                f"# Review unit verification\n\nUnit: {args.unit}\n\nHead: {head}\n\nMerge commit: {merge_sha}\n\nReachability: pass\n",
                encoding="utf-8",
            )
            error = update_review_unit(
                repo, run_path, args.unit, "verified", evidence=evidence,
                summary="The reviewed head is reachable from the recorded integration merge commit and its tree matches the tested synthetic merge.",
            )
            if error:
                fail("record_review_verified_failed", error)
            else:
                executed.append({"type": "record_review_verified"})
                status, _ = review_unit_status(repo, run_path, args.unit)
                unit = status["unit"]

    if payload["status"] in {"pass", "warn"} and unit.get("state") == "verified":
        error = update_review_unit(repo, run_path, args.unit, "cleanup-eligible")
        if error:
            fail("record_review_cleanup_eligible_failed", error)
        else:
            executed.append({"type": "record_review_cleanup_eligible"})
            status, _ = review_unit_status(repo, run_path, args.unit)
            unit = status["unit"]

    if payload["status"] in {"pass", "warn"} and unit.get("state") == "cleanup-eligible":
        deletion = delete_remote_branch(repo, branch, expected_sha=unit.get("check", {}).get("head_sha"))
        if deletion.returncode != 0:
            fail("review_unit_remote_cleanup_failed", deletion.stderr.strip() or deletion.stdout.strip())
        else:
            error = update_review_unit(repo, run_path, args.unit, "cleaned")
            if error:
                fail("record_review_cleaned_failed", error)
            else:
                executed.append({"type": "cleanup_review_branch", "branch": branch})

    payload["executedActions"] = executed
    payload["status"] = status_for(payload)
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def run_binding_findings(repo, run_path, data):
    findings = []
    binding = data.get("binding") if isinstance(data, dict) else None
    if not isinstance(binding, dict):
        return findings
    expected_run = Path(run_path).resolve().name
    if binding.get("runId") != expected_run:
        findings.append(handoff_finding("run_id_drift", f"Run projection is bound to {binding.get('runId')}, not {expected_run}; run merge prepare again."))
    expected_repository = repository_identity(repo)
    projected_repository = binding.get("repository")
    if isinstance(projected_repository, dict):
        projected_repository = projected_repository.get("identity")
    if projected_repository != expected_repository:
        findings.append(handoff_finding("repository_drift", "Run projection repository identity does not match --git-root; run merge prepare again."))
    if (data.get("completion") or {}).get("merged") is True:
        if git(["cat-file", "-e", f"{binding.get('headSha')}^{{commit}}"], repo).returncode != 0:
            findings.append(handoff_finding("integration_head_missing", "The exact verified Epic head is no longer available in the repository."))
    else:
        current_branch = branch_name(repo)
        if binding.get("branch") != current_branch:
            findings.append(handoff_finding("integration_branch_drift", f"Run projection is bound to branch {binding.get('branch')}, not {current_branch}; run merge prepare again."))
        head = current_head(repo)
        if binding.get("headSha") != head:
            findings.append(handoff_finding("integration_head_drift", f"Run projection is bound to HEAD {binding.get('headSha')}, not {head}; run merge prepare again."))
    return findings


def primary_worktree(repo):
    result = git(["worktree", "list", "--porcelain"], repo)
    if result.returncode != 0:
        return Path(repo).resolve()
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            return Path(line.removeprefix("worktree ")).resolve()
    return Path(repo).resolve()


def branch_bound_run(repo, branch):
    if not branch:
        return None
    common = git(["rev-parse", "--git-common-dir"], repo)
    if common.returncode == 0:
        raw = Path(common.stdout.strip())
        common_path = raw if raw.is_absolute() else (Path(repo).resolve() / raw).resolve()
        registry = common_path / "gauntlet" / "run-bindings.json"
        if registry.is_file():
            try:
                records = json.loads(registry.read_text(encoding="utf-8"))
                record = records.get(branch) if isinstance(records, dict) else None
                candidate = Path(record.get("run", "")).resolve() if isinstance(record, dict) else None
                if candidate and (candidate / "manifest.json").is_file():
                    return candidate
            except (json.JSONDecodeError, OSError):
                return Path("/__gauntlet_invalid_run_binding_registry__")
    roots = []
    for root in [primary_worktree(repo), Path(repo).resolve()]:
        for relative in [Path("local-docs/executions"), Path(".gauntlet/executions"), Path("executions")]:
            candidate = root / relative
            if candidate not in roots:
                roots.append(candidate)
    for root in roots:
        if not root.is_dir():
            continue
        for manifest_path in sorted(root.glob("*/manifest.json")):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            integration = manifest.get("integration") or {}
            if integration.get("branch") == branch and integration.get("pr_strategy") in {"single-final-pr", "review-prs-plus-final"}:
                return manifest_path.parent
    return None


def command_merge_prepare(args):
    repo = Path(args.git_root).resolve()
    handoff_path = merge_input_path(repo, args.handoff) if args.handoff else None
    run_path = merge_input_path(repo, args.run) if args.run else None
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
        "runPath": str(run_path) if run_path else None,
    }
    data = None
    if run_path and handoff_path:
        add_finding(payload, "run_handoff_downgrade_rejected", "fail", "A PRD Execution Run must use the controller's schema 3.0 projection; do not supply a caller-authored handoff.")
    elif run_path:
        data, error = run_project_pr(repo, run_path)
        if error:
            add_finding(payload, "project_pr_projection_failed", "fail", error)
        elif data is not None:
            payload["findings"].extend(validate_run_merge_handoff(data))
            payload["findings"].extend(run_binding_findings(repo, run_path, data))
    elif not handoff_path or not handoff_path.is_file():
        add_finding(payload, "missing_handoff_file", "fail", f"Merge handoff does not exist: {handoff_path}")
    else:
        try:
            data = load_merge_handoff(handoff_path)
        except (json.JSONDecodeError, OSError) as error:
            add_finding(payload, "invalid_handoff_file", "fail", str(error))
            data = None
        if data is not None:
            if data.get("schemaVersion") == "3.0":
                add_finding(payload, "run_projection_requires_run", "fail", "Schema 3.0 is accepted only from `project-pr --run`; use --run instead of --handoff.")
            bound_run = branch_bound_run(repo, branch_name(repo))
            if bound_run:
                add_finding(payload, "run_handoff_downgrade_rejected", "fail", f"Branch {branch_name(repo)} is bound to Execution Run {bound_run}; use --run and schema 3.0.")
            payload["findings"].extend(validate_merge_handoff(data))
    if data is not None:
        payload["title"] = data.get("title")
        if not payload["findings"]:
            payload["changelogEntry"] = projection_changelog_entry(data)
            body_path.parent.mkdir(parents=True, exist_ok=True)
            body_path.write_text(render_pr_body(data), encoding="utf-8")
            payload["changelogChanged"] = ensure_unreleased_changelog(changelog_path, projection_changelog_entry(data))
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
    handoff_arg = getattr(args, "handoff", None)
    run_arg = getattr(args, "run", None)
    handoff_path = merge_input_path(repo, handoff_arg) if handoff_arg else None
    run_path = merge_input_path(repo, run_arg) if run_arg else None
    body_path = merge_input_path(repo, args.body)
    data = None
    body = ""
    if git(["rev-parse", "--is-inside-work-tree"], repo).returncode != 0:
        add_finding(payload, "git_root_not_repo", "fail", f"Not a git repository: {repo}")
    if run_path and handoff_path:
        add_finding(payload, "run_handoff_downgrade_rejected", "fail", "A PRD Execution Run must use the controller's schema 3.0 projection; do not supply a caller-authored handoff.")
    elif run_path:
        data, error = run_project_pr(repo, run_path)
        if error:
            add_finding(payload, "project_pr_projection_failed", "fail", error)
        elif data is not None:
            payload["findings"].extend(validate_run_merge_handoff(data))
            payload["findings"].extend(run_binding_findings(repo, run_path, data))
    elif not handoff_path or not handoff_path.is_file():
        add_finding(payload, "missing_handoff_file", "fail", f"Merge handoff does not exist: {handoff_path}")
    else:
        try:
            data = load_merge_handoff(handoff_path)
        except (json.JSONDecodeError, OSError) as error:
            add_finding(payload, "invalid_handoff_file", "fail", str(error))
        if data is not None:
            if data.get("schemaVersion") == "3.0":
                add_finding(payload, "run_projection_requires_run", "fail", "Schema 3.0 is accepted only from `project-pr --run`; use --run instead of --handoff.")
            bound_run = branch_bound_run(repo, branch_name(repo))
            if bound_run:
                add_finding(payload, "run_handoff_downgrade_rejected", "fail", f"Branch {branch_name(repo)} is bound to Execution Run {bound_run}; use --run and schema 3.0.")
            payload["findings"].extend(validate_merge_handoff(data))
    if not body_path.is_file():
        add_finding(payload, "missing_pr_body", "fail", f"PR body does not exist: {body_path}")
    else:
        body = body_path.read_text(encoding="utf-8")
    payload["handoffPath"] = str(handoff_path) if handoff_path else None
    payload["runPath"] = str(run_path) if run_path else None
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
        "runBacked": handoff.get("schemaVersion") == "3.0" if isinstance(handoff, dict) else False,
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
        "runBinding": (state.get("handoff") or {}).get("binding") if state.get("runBacked") else None,
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
        bullet = f"- {projection_changelog_entry(handoff).strip()}"
        changelog_path = Path(state["repo"]) / "CHANGELOG.md"
        changelog = changelog_path.read_text(encoding="utf-8") if changelog_path.is_file() else ""
        if not bullet.strip("- ") or sum(line.rstrip() == bullet for line in changelog.splitlines()) != 1:
            add_finding(payload, "changelog_mismatch", "fail", "CHANGELOG.md must contain the exact PR changelog entry once.")

    counts = state.get("defaultCounts")
    if counts and counts.get("behind"):
        severity = "fail" if state.get("runBacked") else "review"
        code = "stale_tested_base" if state.get("runBacked") else "branch_behind_default"
        add_finding(payload, code, severity, f"Task branch is behind origin/{state['defaultBranch']} by {counts['behind']} commit(s); update and verify again before merge.")

    if state.get("settingsError"):
        add_finding(payload, "merge_settings_unverified", "warn", "Could not verify repository merge settings; using merge-commit fallback.")
    merge_method = merge_method_from_settings(state.get("settings"))
    if not merge_method:
        add_finding(payload, "no_allowed_merge_method", "fail", "Repository reports no allowed pull-request merge method.")
    add_existing_pr_blockers(payload, state.get("pr"))
    if state.get("pr"):
        if state["pr"].get("headRefName") != branch:
            add_finding(payload, "pull_request_head_mismatch", "fail", "The existing pull request head does not match the bound integration branch.")
        if state["pr"].get("baseRefName") != state.get("defaultBranch"):
            add_finding(payload, "pull_request_base_mismatch", "fail", "The existing pull request base does not match the repository default branch.")

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
        {"type": "verify_default_branch", "branch": state.get("defaultBranch")},
        {"type": "delete_remote_branch", "branch": branch},
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


def refreshed_pr_is_mergeable(payload, pr, expected_head=None):
    if not pr:
        add_finding(payload, "pull_request_missing_after_publish", "fail", "Could not find the pull request after publishing it.")
        return False
    before = len(payload["findings"])
    add_existing_pr_blockers(payload, pr)
    if expected_head and pr.get("headRefOid") != expected_head:
        add_finding(payload, "pull_request_head_drift", "fail", "Pull request head no longer matches the revision bound during merge preparation.")
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


def delete_remote_branch(repo, branch, expected_sha=None, git_runner=None):
    git_runner = git_runner or git
    probe = git_runner(["ls-remote", "--exit-code", "--heads", "origin", branch], repo)
    if probe.returncode == 2:
        return subprocess.CompletedProcess(probe.args, 0, probe.stdout, probe.stderr)
    if probe.returncode != 0:
        return probe
    remote_values = probe.stdout.split()
    remote_sha = remote_values[0] if remote_values else ""
    if expected_sha and remote_sha != expected_sha:
        return subprocess.CompletedProcess(
            probe.args, 1, probe.stdout,
            f"remote branch {branch} changed from expected {expected_sha} to {remote_sha}; refusing cleanup",
        )

    deletion_args = ["push", "origin", f":refs/heads/{branch}"]
    if expected_sha:
        deletion_args.append(f"--force-with-lease=refs/heads/{branch}:{expected_sha}")
    deletion = git_runner(deletion_args, repo)
    if deletion.returncode == 0:
        return deletion

    confirmation = git_runner(["ls-remote", "--exit-code", "--heads", "origin", branch], repo)
    if confirmation.returncode == 2:
        return subprocess.CompletedProcess(deletion.args, 0, deletion.stdout, deletion.stderr)
    return deletion


def execute_merge_plan(payload, git_root, handoff_source, body_path, run_path=None, merge_lease=None):
    repo = Path(git_root).resolve()
    executed = []
    branch = payload.get("branch")
    default_branch = payload.get("defaultBranch") or "main"
    handoff = handoff_source if isinstance(handoff_source, dict) else load_merge_handoff(handoff_source)
    pr = payload.get("pr")
    expected_head = (payload.get("runBinding") or {}).get("headSha") or current_head(repo)
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
            if pr.get("headRefOid") != expected_head:
                add_finding(payload, "pull_request_head_drift", "fail", "Pull request head changed before checks were accepted.")
                break
            action["prNumber"] = pr.get("number")
            result = gh(["pr", "checks", str(pr.get("number")), "--watch"], repo)
        elif action_type == "gh_pr_merge":
            if run_path:
                if not merge_lease:
                    add_finding(payload, "epic_merge_lease_missing", "fail", "Run-backed merge requires the launch-set merge lease.")
                    break
                try:
                    validate_run_merge_lease(repo, merge_lease[0], merge_lease[1])
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    add_finding(payload, "epic_merge_lease_invalid", "fail", str(exc))
                    break
            pr, _ = current_pr(repo)
            if not refreshed_pr_is_mergeable(payload, pr, expected_head):
                break
            if run_path:
                granted, authority_error = run_authority_granted(repo, run_path, "merge-to-default")
                if not granted:
                    add_finding(payload, "merge_to_default_authority_missing", "fail", authority_error)
                    break
            action["prNumber"] = pr.get("number")
            method = action.get("mergeMethod") or "merge"
            result = gh([
                "pr", "merge", str(pr.get("number")), f"--{method}",
                "--match-head-commit", expected_head,
            ], repo)
        elif action_type == "delete_remote_branch":
            result = delete_remote_branch(repo, branch, expected_sha=expected_head)
        elif action_type == "verify_default_branch":
            fetch = git(["fetch", "origin", default_branch], repo)
            if fetch.returncode != 0:
                result = fetch
            else:
                ancestor = git(["merge-base", "--is-ancestor", expected_head, f"origin/{default_branch}"], repo)
                if ancestor.returncode == 0:
                    result = ancestor
                else:
                    candidate_tree = git(["rev-parse", f"{expected_head}^{{tree}}"], repo)
                    default_tree = git(["rev-parse", f"origin/{default_branch}^{{tree}}"], repo)
                    if candidate_tree.returncode == 0 and default_tree.returncode == 0 and candidate_tree.stdout.strip() == default_tree.stdout.strip():
                        result = subprocess.CompletedProcess(ancestor.args, 0, "tree-equivalent\n", "")
                    else:
                        result = ancestor
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
    body_path = merge_input_path(repo, args.body)
    if getattr(args, "run", None):
        run_path = merge_input_path(repo, args.run)
        handoff, error = run_project_pr(repo, run_path)
        if error:
            add_finding(payload, "project_pr_projection_failed", "fail", error)
            payload["status"] = status_for(payload)
            print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]
        payload["findings"].extend(validate_run_merge_handoff(handoff))
        payload["findings"].extend(run_binding_findings(repo, run_path, handoff))
        if handoff.get("binding") != payload.get("runBinding") or render_pr_body(handoff) != body_path.read_text(encoding="utf-8"):
            add_finding(payload, "run_projection_changed_during_execute", "fail", "Execution Run projection changed after planning; run merge prepare again.")
        pending_merge_gates = pending_run_merge_gates(handoff)
        if pending_merge_gates:
            add_finding(
                payload, "run_merge_safeguard_pending", "fail",
                "Run-backed merge has pending controller safeguards: " + ", ".join(gate.get("id", "unknown") for gate in pending_merge_gates),
            )
        payload["status"] = status_for(payload)
        if payload["status"] not in {"pass", "warn"}:
            payload["mergePlan"]["canMerge"] = False
            payload["mergePlan"]["actions"] = []
            print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]
        granted, authority_error = run_authority_granted(repo, run_path, "merge-to-default")
        if not granted:
            add_finding(payload, "merge_to_default_authority_missing", "fail", authority_error)
            payload["mergePlan"]["canMerge"] = False
            payload["mergePlan"]["actions"] = []
            payload["status"] = status_for(payload)
            print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]
        try:
            merge_lease = acquire_run_merge_lease(repo, run_path, handoff)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            add_finding(payload, "epic_merge_lease_failed", "fail", str(exc))
            payload["mergePlan"]["canMerge"] = False
            payload["mergePlan"]["actions"] = []
            payload["status"] = status_for(payload)
            print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]
    else:
        handoff = merge_input_path(repo, args.handoff)
        run_path = None
        merge_lease = None
    payload = execute_merge_plan(payload, repo, handoff, body_path, run_path=run_path, merge_lease=merge_lease)
    if run_path and payload["status"] in {"pass", "warn"} and any(
        action.get("type") == "verify_default_branch" for action in payload.get("executedActions", [])
    ):
        default_branch = payload.get("defaultBranch") or "main"
        main_result = git(["rev-parse", f"origin/{default_branch}"], repo)
        pr = payload.get("pr") or {}
        pr_reference = str(pr.get("url") or pr.get("number") or "run-backed-project-pr")
        if main_result.returncode != 0:
            add_finding(payload, "record_merge_head_failed", "fail", main_result.stderr.strip() or main_result.stdout.strip())
        else:
            main_sha = main_result.stdout.strip()
            _, record_error = run_prd_controller(repo, [
                "record-merge", "--run", str(run_path), "--pr", pr_reference,
                "--merged-sha", main_sha, "--main-sha", main_sha,
                "--evidence", f"origin/{default_branch} contains verified head {handoff['binding']['headSha']}",
            ])
            if record_error:
                add_finding(payload, "record_merge_failed", "fail", record_error)
            else:
                _, transition_error = run_prd_controller(repo, ["transition", "--run", str(run_path), "--to", "merged"])
                if transition_error:
                    add_finding(payload, "record_merge_transition_failed", "fail", transition_error)
                else:
                    payload["runMergeRecorded"] = {"mainSha": main_sha, "pr": pr_reference}
                    try:
                        release_run_merge_lease(repo, merge_lease[0], merge_lease[1], main_sha)
                        payload["mergeLeaseReleased"] = True
                    except (OSError, ValueError, json.JSONDecodeError) as exc:
                        add_finding(payload, "epic_merge_lease_release_failed", "fail", str(exc))
        payload["status"] = status_for(payload)
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_merge_reconcile(args):
    repo = Path(args.git_root).resolve()
    run_path = merge_input_path(repo, args.run)
    payload = {"schemaVersion": "1.0", "status": "pass", "findings": [], "runPath": str(run_path), "reconciled": False}
    handoff, error = run_project_pr(repo, run_path)
    if error:
        add_finding(payload, "project_pr_projection_failed", "fail", error)
    elif validate_run_merge_handoff(handoff):
        payload["findings"].extend(validate_run_merge_handoff(handoff))
    else:
        completion_output, completion_error = run_prd_controller(repo, ["completion", "--run", str(run_path)])
        if not completion_error:
            try:
                if json.loads(completion_output).get("merged") is True:
                    persisted = persisted_run_merge_lease(run_path, handoff)
                    if persisted:
                        release_run_merge_lease(repo, persisted[0], persisted[1], recorded_run_merge_head(run_path))
                        payload["mergeLeaseReleased"] = True
                    payload["reconciled"] = True
                    payload["alreadyRecorded"] = True
                    print_payload(payload, args.json)
                    return EXIT_CODES[payload["status"]]
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                add_finding(payload, "merge_reconcile_lease_failed", "fail", str(exc))
                payload["status"] = status_for(payload)
                print_payload(payload, args.json)
                return EXIT_CODES[payload["status"]]
        binding = handoff["binding"]
        default_result = git(["fetch", "origin"], repo)
        if default_result.returncode != 0:
            add_finding(payload, "merge_reconcile_fetch_failed", "fail", default_result.stderr.strip() or default_result.stdout.strip())
        else:
            settings, settings_error = repository_merge_settings(repo)
            if settings_error:
                add_finding(payload, "merge_reconcile_settings_failed", "fail", settings_error)
            else:
                default_branch = ((settings or {}).get("defaultBranchRef") or {}).get("name") or "main"
                main_result = git(["rev-parse", f"origin/{default_branch}"], repo)
                represented = default_represents_candidate(repo, binding["headSha"], f"origin/{default_branch}")
                merged_pr = gh([
                    "pr", "list", "--head", binding["branch"], "--state", "merged", "--limit", "1",
                    "--json", "number,url,headRefOid,baseRefName",
                ], repo)
                if main_result.returncode != 0 or not represented:
                    add_finding(payload, "merge_not_observed", "fail", "The remote default branch preserves neither verified-head ancestry nor the exact verified candidate tree.")
                elif merged_pr.returncode != 0:
                    add_finding(payload, "merged_pr_lookup_failed", "fail", merged_pr.stderr.strip() or merged_pr.stdout.strip())
                else:
                    records = json.loads(merged_pr.stdout or "[]")
                    pr = records[0] if records else None
                    if not pr or pr.get("headRefOid") != binding["headSha"] or pr.get("baseRefName") != default_branch:
                        add_finding(payload, "merged_pr_identity_mismatch", "fail", "No merged PR matches the verified Epic head and default branch.")
                    else:
                        main_sha = main_result.stdout.strip()
                        pr_reference = str(pr.get("url") or pr.get("number"))
                        try:
                            persisted = persisted_run_merge_lease(run_path, handoff)
                        except (OSError, ValueError, json.JSONDecodeError) as exc:
                            add_finding(payload, "merge_reconcile_lease_failed", "fail", str(exc))
                            persisted = None
                        if persisted is None and not payload["findings"]:
                            add_finding(
                                payload, "merge_lease_not_observed", "review",
                                "The merge is independently observable, but no controller merge lease survived to prove serialized execution.",
                            )
                        _, record_error = run_prd_controller(repo, [
                            "record-merge", "--run", str(run_path), "--pr", pr_reference,
                            "--merged-sha", main_sha, "--main-sha", main_sha,
                            "--evidence", f"origin/{default_branch} contains verified head {binding['headSha']}",
                        ])
                        if record_error:
                            add_finding(payload, "record_merge_failed", "fail", record_error)
                        else:
                            _, transition_error = run_prd_controller(repo, ["transition", "--run", str(run_path), "--to", "merged"])
                            if transition_error:
                                add_finding(payload, "record_merge_transition_failed", "fail", transition_error)
                            else:
                                payload.update({"reconciled": True, "mainSha": main_sha, "pr": pr_reference})
                                if persisted:
                                    try:
                                        release_run_merge_lease(repo, persisted[0], persisted[1], main_sha)
                                        payload["mergeLeaseReleased"] = True
                                    except (OSError, ValueError, json.JSONDecodeError) as exc:
                                        add_finding(payload, "merge_reconcile_lease_release_failed", "fail", str(exc))
    payload["status"] = status_for(payload)
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


def advance_run_release_state(repo, run_path):
    """Close only controller-provable release state; never invent live evidence."""
    transitions = []
    while True:
        manifest_path = Path(run_path) / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        state = manifest.get("state")
        release = manifest.get("release", {})
        applicability = release.get("applicability", {})
        if state == "merged":
            expected = "pass" if applicability.get("deployment") else "skipped"
            record = release.get("deployment", {})
            if expected == "skipped" and record.get("result") != "skipped":
                _, error = run_prd_controller(repo, [
                    "record-release", "--run", str(run_path), "--stage", "deployment",
                    "--result", "skipped", "--summary", "Deployment is not applicable to this Epic.",
                    "--evidence", "locked release applicability excludes deployment",
                ])
                if error:
                    return transitions, error
                transitions.append("deployment:not-applicable")
                continue
            if record.get("result") != expected:
                return transitions, None
            _, error = run_prd_controller(repo, ["transition", "--run", str(run_path), "--to", "deployed"])
            if error:
                return transitions, error
            transitions.append("deployed")
            continue
        if state == "deployed":
            expected = "pass" if applicability.get("production-verification") else "skipped"
            record = release.get("production-verification", {})
            if expected == "skipped" and record.get("result") != "skipped":
                _, error = run_prd_controller(repo, [
                    "record-release", "--run", str(run_path), "--stage", "production-verification",
                    "--result", "skipped", "--summary", "Production verification is not applicable to this Epic.",
                    "--evidence", "locked release applicability excludes production verification",
                ])
                if error:
                    return transitions, error
                transitions.append("production-verification:not-applicable")
                continue
            if record.get("result") != expected:
                return transitions, None
            _, error = run_prd_controller(repo, ["transition", "--run", str(run_path), "--to", "production_verified"])
            if error:
                return transitions, error
            transitions.append("production_verified")
            continue
        if state == "production_verified":
            _, error = run_prd_controller(repo, ["transition", "--run", str(run_path), "--to", "complete"])
            if error:
                return transitions, error
            transitions.append("complete")
            continue
        return transitions, None


def finalize_run_closeout(args, repo, payload, run_path, install_env):
    transitions, transition_error = advance_run_release_state(repo, run_path)
    payload["releaseTransitions"] = transitions
    if transition_error:
        closeout_fail(payload, "run_release_transition_failed", transition_error)
        print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    completion_output, completion_error = run_prd_controller(repo, ["completion", "--run", str(run_path)])
    try:
        completion = json.loads(completion_output) if not completion_error else None
    except json.JSONDecodeError:
        completion = None
    if not completion_allows_archive(completion):
        payload["releasePending"] = completion or {"error": completion_error or "completion projection unavailable"}
        payload["remainingAppActions"] = []
        payload["localCleanup"] = {"branch": branch_name(repo), "safeAfterTaskExit": False}
        add_finding(payload, "run_release_stages_pending", "review", "The Epic merged, but required release stages remain open; closeout will not install or archive the task.")
        payload["status"] = status_for(payload)
        print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]

    if args.install_target != "none":
        install_result = subprocess.run(
            closeout_install_command(repo, args), cwd=repo, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=install_env,
        )
        payload["install"] = {"target": args.install_target, "applied": install_result.returncode == 0, "preflight": True}
        if install_result.returncode != 0:
            closeout_fail(payload, "local_install_failed", install_result.stderr.strip() or install_result.stdout.strip())
            print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]
    else:
        payload["install"] = {"target": "none", "applied": False}

    archive_args = argparse.Namespace(
        title=args.title, suggested_title=args.suggested_title, content=None, run=run_path,
        git_root=repo, require_kickoff=False, require_assumptions=False,
        archive_anyway=False, confirm_git_risk=False, allow_dirty=[], json=True,
    )
    archive_payload = build_archive_payload(archive_args)
    if archive_payload["status"] in {"pass", "warn"}:
        archive_payload = execute_archive_actions(archive_payload, repo)
    payload["archive"] = archive_payload
    payload["archiveSummary"] = archive_payload.get("archiveSummary")
    payload["findings"].extend(archive_payload.get("findings", []))
    payload["status"] = status_for(payload)
    payload["remainingAppActions"] = archive_payload.get("remainingAppActions", []) if payload["status"] in {"pass", "warn"} else []
    payload["localCleanup"] = {"branch": branch_name(repo), "safeAfterTaskExit": True}
    print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def command_run_closeout_execute(args, repo, payload):
    run_path = merge_input_path(repo, args.run)
    handoff, error = run_project_pr(repo, run_path)
    if error:
        closeout_fail(payload, "project_pr_projection_failed", error)
        print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    payload["findings"].extend(validate_run_merge_handoff(handoff))
    payload["findings"].extend(run_binding_findings(repo, run_path, handoff))
    pending_merge_gates = pending_run_merge_gates(handoff)
    if pending_merge_gates:
        add_finding(
            payload, "run_merge_safeguard_pending", "fail",
            "Run-backed merge has pending controller safeguards: " + ", ".join(gate.get("id", "unknown") for gate in pending_merge_gates),
        )
    if payload["findings"]:
        payload["status"] = status_for(payload)
        print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    parsed_title = parse_thread_title(args.title)
    parsed_suggestion = parse_thread_title(args.suggested_title) if args.suggested_title else None
    if parsed_title["format"] != "current" and (not parsed_suggestion or parsed_suggestion["format"] != "current"):
        closeout_fail(payload, "invalid_archive_title", "Provide a current 'p#: four word goal' title or a valid --suggested-title before closeout begins.")
        print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    if dirty_paths(repo):
        closeout_fail(payload, "uncommitted_merge_work", "Run-backed closeout requires a clean, exactly verified Epic branch.")
        print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    changelog_entry = projection_changelog_entry(handoff)
    changelog_bullet = f"- {changelog_entry}"
    changelog_text = (repo / "CHANGELOG.md").read_text(encoding="utf-8") if (repo / "CHANGELOG.md").is_file() else ""
    if changelog_bullet not in changelog_text.splitlines():
        closeout_fail(payload, "run_changelog_not_prepared", "Prepare and commit the deterministic run changelog entry before final Epic verification.")
        print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]

    install_env = os.environ.copy()
    if args.agent_home:
        install_env["GAUNTLET_AGENT_HOME"] = str(Path(args.agent_home).expanduser())
    if args.install_target != "none":
        preflight = subprocess.run(
            closeout_install_command(repo, args, check=True), cwd=repo, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=install_env,
        )
        payload["install"] = {"target": args.install_target, "applied": False, "preflight": preflight.returncode == 0}
        if preflight.returncode != 0:
            closeout_fail(payload, "local_install_preflight_failed", preflight.stderr.strip() or preflight.stdout.strip())
            print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]

    if handoff.get("completion", {}).get("merged") is True:
        try:
            persisted = persisted_run_merge_lease(run_path, handoff)
            if persisted:
                release_run_merge_lease(repo, persisted[0], persisted[1], recorded_run_merge_head(run_path))
                payload["mergeLeaseReleased"] = True
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            closeout_fail(payload, "epic_merge_lease_recovery_failed", str(exc))
            print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]
        payload["merge"] = {
            "schemaVersion": "1.0", "status": "pass", "findings": [],
            "alreadyRecorded": True, "runBinding": handoff.get("binding"),
        }
        return finalize_run_closeout(args, repo, payload, run_path, install_env)

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix="-gauntlet-epic-pr.md") as handle:
        handle.write(render_pr_body(handoff))
        body_path = Path(handle.name)
    try:
        merge_args = argparse.Namespace(git_root=repo, handoff=None, run=run_path, body=body_path, json=True)
        merge_payload = build_merge_payload(merge_args)
        if merge_payload["status"] in {"pass", "warn"}:
            granted, authority_error = run_authority_granted(repo, run_path, "merge-to-default")
            if not granted:
                add_finding(merge_payload, "merge_to_default_authority_missing", "fail", authority_error)
                merge_payload["status"] = status_for(merge_payload)
            else:
                try:
                    merge_lease = acquire_run_merge_lease(repo, run_path, handoff)
                    merge_payload = execute_merge_plan(
                        merge_payload, repo, handoff, body_path,
                        run_path=run_path, merge_lease=merge_lease,
                    )
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    add_finding(merge_payload, "epic_merge_lease_failed", "fail", str(exc))
                    merge_payload["status"] = status_for(merge_payload)
        payload["merge"] = merge_payload
        payload["findings"].extend(merge_payload.get("findings", []))
        payload["status"] = status_for(payload)
        if payload["status"] not in {"pass", "warn"}:
            print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]
        default_branch = merge_payload.get("defaultBranch") or "main"
        main_result = git(["rev-parse", f"origin/{default_branch}"], repo)
        if main_result.returncode != 0:
            closeout_fail(payload, "record_merge_head_failed", main_result.stderr.strip() or main_result.stdout.strip())
            print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]
        main_sha = main_result.stdout.strip()
        pr = merge_payload.get("pr") or {}
        pr_reference = str(pr.get("url") or pr.get("number") or "run-backed-project-pr")
        _, record_error = run_prd_controller(repo, [
            "record-merge", "--run", str(run_path), "--pr", pr_reference,
            "--merged-sha", main_sha, "--main-sha", main_sha,
            "--evidence", f"origin/{default_branch} contains verified head {handoff['binding']['headSha']}",
        ])
        _, transition_error = run_prd_controller(repo, ["transition", "--run", str(run_path), "--to", "merged"]) if not record_error else (None, None)
        if record_error or transition_error:
            closeout_fail(payload, "record_merge_failed", record_error or transition_error)
            print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]
        payload["runMergeRecorded"] = {"mainSha": main_sha, "pr": pr_reference}
        try:
            release_run_merge_lease(repo, merge_lease[0], merge_lease[1], main_sha)
            payload["mergeLeaseReleased"] = True
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            closeout_fail(payload, "epic_merge_lease_release_failed", str(exc))
            print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]

        return finalize_run_closeout(args, repo, payload, run_path, install_env)
    finally:
        body_path.unlink(missing_ok=True)


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

    if getattr(args, "run", None):
        if getattr(args, "handoff", None):
            closeout_fail(payload, "run_handoff_downgrade_rejected", "Run-backed closeout accepts --run only, not a caller-authored handoff.")
            print_payload(payload, args.json)
            return EXIT_CODES[payload["status"]]
        return command_run_closeout_execute(args, repo, payload)

    if not getattr(args, "handoff", None):
        closeout_fail(payload, "missing_handoff_file", "Non-run Patch closeout requires --handoff.")
        print_payload(payload, args.json)
        return EXIT_CODES[payload["status"]]
    if not args.stage:
        closeout_fail(payload, "missing_stage_scope", "Non-run Patch closeout requires at least one --stage path.")
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
    if isinstance(handoff, dict) and handoff.get("schemaVersion") == "3.0":
        add_finding(payload, "run_projection_requires_run", "fail", "Schema 3.0 must be projected by merge --run and cannot be supplied to closeout as a file.")
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
        "number,state,isDraft,mergeable,mergedAt,statusCheckRollup,url,baseRefName,headRefName,headRefOid,reviewDecision",
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
        if getattr(args, "run", None):
            summary, findings = archive_summary_from_run(args.git_root, args.run)
        else:
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
    parser.add_argument("--run", type=Path, default=None, help="Use a deterministic Epic completion projection instead of an authored Archive Summary.")
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
    merge_prepare.add_argument("--handoff", type=Path, default=None)
    merge_prepare.add_argument("--run", type=Path, default=None)
    merge_prepare.add_argument("--body-output", type=Path, default=Path(".gauntlet/pr-body.md"))
    merge_prepare.add_argument("--json", action="store_true")
    merge_prepare.set_defaults(func=command_merge_prepare)
    for name, func in [("plan", command_merge_plan), ("execute", command_merge_execute)]:
        merge_command = merge_subcommands.add_parser(name)
        merge_command.add_argument("--git-root", type=Path, default=Path.cwd())
        merge_command.add_argument("--handoff", type=Path, default=None)
        merge_command.add_argument("--run", type=Path, default=None)
        merge_command.add_argument("--body", type=Path, default=Path(".gauntlet/pr-body.md"))
        merge_command.add_argument("--json", action="store_true")
        merge_command.set_defaults(func=func)
    merge_reconcile = merge_subcommands.add_parser("reconcile", help="Record an already-observed run-backed merge idempotently.")
    merge_reconcile.add_argument("--git-root", type=Path, default=Path.cwd())
    merge_reconcile.add_argument("--run", type=Path, required=True)
    merge_reconcile.add_argument("--json", action="store_true")
    merge_reconcile.set_defaults(func=command_merge_reconcile)

    review_unit = subcommands.add_parser("review-unit", help="Prepare or execute a parent-owned review-unit PR into an Execution Run integration branch.")
    review_unit_subcommands = review_unit.add_subparsers(dest="review_unit_command", required=True)
    for name, func in [
        ("prepare", command_review_unit_prepare),
        ("plan", command_review_unit_plan),
        ("execute", command_review_unit_execute),
    ]:
        review_command = review_unit_subcommands.add_parser(name)
        review_command.add_argument("--git-root", type=Path, default=Path.cwd())
        review_command.add_argument("--run", type=Path, required=True)
        review_command.add_argument("--unit", required=True)
        if name == "prepare":
            review_command.add_argument("--body-output", type=Path, default=None)
        else:
            review_command.add_argument("--body", type=Path, default=None)
        review_command.add_argument("--json", action="store_true")
        review_command.set_defaults(func=func)

    closeout = subcommands.add_parser("closeout", help="Commit scoped work, merge it through a PR, install it locally, and plan task archival.")
    closeout_subcommands = closeout.add_subparsers(dest="closeout_command", required=True)
    closeout_execute = closeout_subcommands.add_parser("execute")
    closeout_execute.add_argument("--git-root", type=Path, default=Path.cwd())
    closeout_execute.add_argument("--handoff", type=Path, default=None)
    closeout_execute.add_argument("--run", type=Path, default=None)
    closeout_execute.add_argument("--stage", action="append", default=[])
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
    closeout_execute.add_argument("--content", type=Path, default=None)
    closeout_execute.add_argument("--json", action="store_true")
    closeout_execute.set_defaults(func=command_closeout_execute)

    install = subcommands.add_parser("install", help="Installed-layout helpers.")
    install_subcommands = install.add_subparsers(dest="install_command", required=True)
    install_verify = install_subcommands.add_parser("verify")
    install_verify.add_argument("--target", choices=["codex", "claude"], required=True)
    install_verify.add_argument("--agent-home", required=True)
    install_verify.add_argument("--json", action="store_true")
    install_verify.set_defaults(func=command_install_verify)

    epic_tasks = subcommands.add_parser("epic-tasks", help="Plan and reconcile one visible implementation task per build-ready Epic.")
    epic_task_subcommands = epic_tasks.add_subparsers(dest="epic_tasks_command", required=True)
    epic_init = epic_task_subcommands.add_parser("init", help="Freeze one complete PRD target into an Epic launch set.")
    epic_init.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_init.add_argument("--source", type=Path, required=True)
    epic_init.add_argument("--target", action="append", default=[])
    epic_init.add_argument("--launch-set", type=Path, required=True)
    epic_init.add_argument("--priority", choices=["p0", "p1", "p2", "p3", "p4"], default="p1")
    epic_init.add_argument("--json", action="store_true")
    epic_init.set_defaults(func=command_epic_tasks_init)
    epic_plan = epic_task_subcommands.add_parser("plan", help="Emit only missing dependency-ready task actions.")
    epic_plan.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_plan.add_argument("--launch-set", type=Path, required=True)
    epic_plan.add_argument("--json", action="store_true")
    epic_plan.set_defaults(func=command_epic_tasks_plan)
    epic_record_task = epic_task_subcommands.add_parser("record-task", help="Persist a proven native task ID for an Epic.")
    epic_record_task.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_record_task.add_argument("--launch-set", type=Path, required=True)
    epic_record_task.add_argument("--epic", required=True)
    epic_record_task.add_argument("--task-key", required=True)
    epic_record_task.add_argument("--task-id", required=True)
    epic_record_task.add_argument("--json", action="store_true")
    epic_record_task.set_defaults(func=command_epic_tasks_record_task)
    epic_release = epic_task_subcommands.add_parser("release-start", help="Release an ambiguous task action only after native reconciliation proves no task exists.")
    epic_release.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_release.add_argument("--launch-set", type=Path, required=True)
    epic_release.add_argument("--epic", required=True)
    epic_release.add_argument("--task-key", required=True)
    epic_release.add_argument("--native-index", type=Path, required=True)
    epic_release.add_argument("--json", action="store_true")
    epic_release.set_defaults(func=command_epic_tasks_release_start)
    epic_record_run = epic_task_subcommands.add_parser("record-run", help="Bind an Epic task to its single-Epic Execution Run.")
    epic_record_run.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_record_run.add_argument("--launch-set", type=Path, required=True)
    epic_record_run.add_argument("--epic", required=True)
    epic_record_run.add_argument("--run", type=Path, required=True)
    epic_record_run.add_argument("--json", action="store_true")
    epic_record_run.set_defaults(func=command_epic_tasks_record_run)
    epic_status = epic_task_subcommands.add_parser("status", help="Read current Epic task and completion projections without changing state.")
    epic_status.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_status.add_argument("--launch-set", type=Path, required=True)
    epic_status.add_argument("--json", action="store_true")
    epic_status.set_defaults(func=command_epic_tasks_status)
    epic_reconcile = epic_task_subcommands.add_parser("reconcile", help="Refresh completion facts, finish copy, and newly ready task actions.")
    epic_reconcile.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_reconcile.add_argument("--launch-set", type=Path, required=True)
    epic_reconcile.add_argument("--json", action="store_true")
    epic_reconcile.set_defaults(func=command_epic_tasks_reconcile)
    epic_blocker = epic_task_subcommands.add_parser("blocker", help="Record a structured Epic blocker and emit a user question only when required.")
    epic_blocker.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_blocker.add_argument("--launch-set", type=Path, required=True)
    epic_blocker.add_argument("--epic", required=True)
    epic_blocker.add_argument("--blocker", type=Path, required=True)
    epic_blocker.add_argument("--json", action="store_true")
    epic_blocker.set_defaults(func=command_epic_tasks_blocker)
    epic_resolve = epic_task_subcommands.add_parser("resolve-blocker", help="Apply the product task's accepted blocker disposition.")
    epic_resolve.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_resolve.add_argument("--launch-set", type=Path, required=True)
    epic_resolve.add_argument("--epic", required=True)
    epic_resolve.add_argument("--disposition", choices=["continue", "stop"], required=True)
    epic_resolve.add_argument("--reason", default=None)
    epic_resolve.add_argument("--json", action="store_true")
    epic_resolve.set_defaults(func=command_epic_tasks_resolve_blocker)
    epic_docs = epic_task_subcommands.add_parser("reconcile-docs", help="Project one implemented Epic back into its canonical PRD and index.")
    epic_docs.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_docs.add_argument("--launch-set", type=Path, required=True)
    epic_docs.add_argument("--epic", required=True)
    epic_docs.add_argument("--json", action="store_true")
    epic_docs.set_defaults(func=command_epic_tasks_reconcile_docs)
    epic_lease = epic_task_subcommands.add_parser("merge-lease", help="Serialize default-branch mutation across ready Epic PRs.")
    epic_lease_subcommands = epic_lease.add_subparsers(dest="epic_merge_lease_command", required=True)
    epic_lease_acquire = epic_lease_subcommands.add_parser("acquire")
    epic_lease_acquire.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_lease_acquire.add_argument("--launch-set", type=Path, required=True)
    epic_lease_acquire.add_argument("--epic", required=True)
    epic_lease_acquire.add_argument("--candidate-head", required=True)
    epic_lease_acquire.add_argument("--verified-base", required=True)
    epic_lease_acquire.add_argument("--json", action="store_true")
    epic_lease_acquire.set_defaults(func=command_epic_tasks_merge_lease_acquire)
    epic_lease_release = epic_lease_subcommands.add_parser("release")
    epic_lease_release.add_argument("--git-root", type=Path, default=Path.cwd())
    epic_lease_release.add_argument("--launch-set", type=Path, required=True)
    epic_lease_release.add_argument("--epic", required=True)
    epic_lease_release.add_argument("--candidate-head", required=True)
    epic_lease_release.add_argument("--merged-head", required=True)
    epic_lease_release.add_argument("--json", action="store_true")
    epic_lease_release.set_defaults(func=command_epic_tasks_merge_lease_release)

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
    docs_draft = docs_subcommands.add_parser("draft", help="Create and explicitly promote user-owned product drafts.")
    docs_draft_subcommands = docs_draft.add_subparsers(dest="docs_draft_command", required=True)
    docs_draft_create = docs_draft_subcommands.add_parser("create", help="Create one guided, unanswered product draft.")
    docs_draft_create.add_argument("--project-root", type=Path, default=Path.cwd())
    docs_draft_create.add_argument("--template", choices=["founding-hypothesis", "peter-yang"], required=True)
    docs_draft_create.add_argument("--dry-run", action="store_true")
    docs_draft_create.add_argument("--json", action="store_true")
    docs_draft_create.set_defaults(func=command_docs_draft_create)
    docs_draft_promote = docs_draft_subcommands.add_parser("promote", help="Allocate an Epic and atomically move an existing draft into its canonical path.")
    docs_draft_promote.add_argument("--project-root", type=Path, default=Path.cwd())
    docs_draft_promote.add_argument("--draft", required=True, help="Draft filename or path below local-docs/drafts.")
    docs_draft_promote.add_argument("--title", required=True)
    docs_draft_promote.add_argument("--number", type=int, default=None)
    docs_draft_promote.add_argument("--dry-run", action="store_true")
    docs_draft_promote.add_argument("--json", action="store_true")
    docs_draft_promote.set_defaults(func=command_docs_draft_promote)

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
