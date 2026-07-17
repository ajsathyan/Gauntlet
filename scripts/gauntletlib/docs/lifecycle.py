"""Canonical local product-document lifecycle and command handlers."""

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from gauntletlib.cli import EXIT_CODES
from gauntletlib.core.fsio import atomic_write_text as _core_atomic_write_text
from gauntletlib.core.fsio import write_new_file
from gauntletlib.core.findings import status_for
from gauntletlib.core.hashing import sha256
from gauntletlib.core.proc import git


ROOT = Path(__file__).resolve().parents[3]
LOCAL_DOC_TEMPLATES = ROOT / "templates" / "local-docs"
LOCAL_DOC_OPT_OUT = Path(".gauntlet") / "doc-org.disabled"
DOC_EXECUTION_BLOCK_BEGIN = "<!-- BEGIN GAUNTLET EXECUTION CONTRACT v2 -->"
DOC_EXECUTION_BLOCK_END = "<!-- END GAUNTLET EXECUTION CONTRACT v2 -->"
DOC_EXECUTION_LEGACY_HASHES = {
    "5315292c4648aaa6bc04bd810730c7f480a79efb01e81cc882966a63407538e8",
}

_atomic_write_text = _core_atomic_write_text
_parse_dependency_list = None
_parse_release_stages = None
_parse_consequence_triggers = None


def _default_legacy_hashes():
    return DOC_EXECUTION_LEGACY_HASHES


_legacy_hashes = _default_legacy_hashes


def configure(
    *,
    atomic_write_text=None,
    parse_dependency_list=None,
    parse_release_stages=None,
    parse_consequence_triggers=None,
    legacy_hashes=None,
):
    global _atomic_write_text
    global _parse_dependency_list
    global _parse_release_stages
    global _parse_consequence_triggers
    global _legacy_hashes
    if atomic_write_text is not None:
        _atomic_write_text = atomic_write_text
    if parse_dependency_list is not None:
        _parse_dependency_list = parse_dependency_list
    if parse_release_stages is not None:
        _parse_release_stages = parse_release_stages
    if parse_consequence_triggers is not None:
        _parse_consequence_triggers = parse_consequence_triggers
    if legacy_hashes is not None:
        _legacy_hashes = legacy_hashes


def _git_root(repo):
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
    repository = _git_root(supplied)
    if not repository:
        raise RuntimeError(f"Not a Git worktree: {supplied}")
    worktrees = parse_worktree_roots(repository)
    primary = worktrees[0]
    exclude_result = git(["rev-parse", "--git-path", "info/exclude"], primary)
    if exclude_result.returncode != 0:
        raise RuntimeError(
            f"Cannot resolve the local Git exclude file:\n{exclude_result.stderr.strip()}"
        )
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
        raise RuntimeError(
            f"Cannot inspect tracked local-document paths:\n{result.stderr.strip()}"
        )
    return [line for line in result.stdout.splitlines() if line.strip()]


def local_docs_path_findings(context):
    findings = []
    for path in [context["policyPath"], context["docsRoot"], context["indexPath"]]:
        if path.is_symlink():
            findings.append(
                {
                    "code": "local_document_symlink",
                    "severity": "fail",
                    "message": f"Canonical local-document paths must not be symlinks: {path}",
                }
            )
    if context["policyPath"].exists() and not context["policyPath"].is_file():
        findings.append(
            {
                "code": "invalid_doc_org_path",
                "severity": "fail",
                "message": f"Policy path is not a file: {context['policyPath']}",
            }
        )
    if context["docsRoot"].exists() and not context["docsRoot"].is_dir():
        findings.append(
            {
                "code": "invalid_local_docs_path",
                "severity": "fail",
                "message": f"Local document root is not a directory: {context['docsRoot']}",
            }
        )
    if context["indexPath"].exists() and not context["indexPath"].is_file():
        findings.append(
            {
                "code": "invalid_local_docs_index",
                "severity": "fail",
                "message": f"Local document index is not a file: {context['indexPath']}",
            }
        )
    if context["optOutPath"].is_symlink():
        findings.append(
            {
                "code": "local_document_opt_out_symlink",
                "severity": "fail",
                "message": (
                    "Local-document opt-out marker must not be a symlink: "
                    f"{context['optOutPath']}"
                ),
            }
        )
    if context["optOutPath"].exists() and not context["optOutPath"].is_file():
        findings.append(
            {
                "code": "invalid_local_document_opt_out",
                "severity": "fail",
                "message": (
                    "Local-document opt-out marker is not a file: "
                    f"{context['optOutPath']}"
                ),
            }
        )
    for name in ["drafts", "epics", "research"]:
        path = context["docsRoot"] / name
        if path.is_symlink():
            findings.append(
                {
                    "code": "local_document_symlink",
                    "severity": "fail",
                    "message": f"Canonical local-document paths must not be symlinks: {path}",
                }
            )
        elif path.exists() and not path.is_dir():
            findings.append(
                {
                    "code": "invalid_local_document_directory",
                    "severity": "fail",
                    "message": f"Local-document path is not a directory: {path}",
                }
            )
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
        findings.append(
            {
                "code": "tracked_local_document_collision",
                "severity": "fail",
                "message": "Local-document paths must not be tracked.",
                "paths": tracked,
            }
        )
    if local_docs_opted_out(context):
        return findings
    materialized = any(
        path.exists()
        for path in [context["policyPath"], context["docsRoot"], context["indexPath"]]
    )
    if require_profile or materialized:
        for key, code in [
            ("policyPath", "missing_doc_org"),
            ("indexPath", "missing_local_docs_index"),
        ]:
            if not context[key].is_file():
                findings.append(
                    {
                        "code": code,
                        "severity": "fail",
                        "message": f"Missing {context[key]}",
                    }
                )
        for relative in ["doc_org.md", "local-docs/INDEX.md"]:
            ignored = git(["check-ignore", "-q", "--", relative], context["primaryRoot"])
            if ignored.returncode != 0:
                findings.append(
                    {
                        "code": "local_document_not_ignored",
                        "severity": "fail",
                        "message": f"Canonical local path is not ignored: {relative}",
                    }
                )
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
        raise RuntimeError(
            f"Template {name} has unresolved placeholders: "
            + ", ".join(sorted(set(unresolved)))
        )
    return rendered


def managed_execution_block():
    template = (LOCAL_DOC_TEMPLATES / "doc_org.md.tmpl").read_text(encoding="utf-8")
    start = template.index(DOC_EXECUTION_BLOCK_BEGIN)
    end = template.index(DOC_EXECUTION_BLOCK_END, start) + len(
        DOC_EXECUTION_BLOCK_END
    )
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
        end = text.index(DOC_EXECUTION_BLOCK_END, start) + len(
            DOC_EXECUTION_BLOCK_END
        )
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
    if sha256(legacy.encode("utf-8")) not in _legacy_hashes():
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
            _atomic_write_text(path, updated)
        findings.append(
            {
                "code": (
                    "local_execution_contract_migrated"
                    if not dry_run
                    else "local_execution_contract_migration_planned"
                ),
                "severity": "pass",
                "message": (
                    "Gauntlet updated only the versioned local execution contract "
                    "and preserved project-authored policy bytes."
                ),
            }
        )
        return findings, True
    if state in {"ambiguous", "customized"}:
        findings.append(
            {
                "code": "local_execution_contract_review",
                "severity": "review",
                "message": (
                    "The materialized doc_org.md execution contract is customized "
                    "or ambiguous; Gauntlet left it unchanged for human review."
                ),
            }
        )
    return findings, False


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
        _atomic_write_text(
            exclude_path,
            prefix + "\n".join(missing) + "\n",
            mode=0o644,
        )
    return missing


def _print_payload(payload, as_json):
    if as_json:
        print(json.dumps(payload, indent=2))
        return
    print(f"Gauntlet: {payload['status']}")
    for finding in payload.get("findings", []):
        print(f"- [{finding['severity']}] {finding['code']}: {finding['message']}")
    for action in payload.get("archivePlan", {}).get("actions", []):
        print(f"- action: {action.get('type')}")


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
    payload["status"] = status_for(payload["findings"])
    _print_payload(payload, args.json)
    return EXIT_CODES[payload["status"]]


def local_epic_prefix(index_path):
    if not index_path.is_file():
        raise RuntimeError(f"Local document index does not exist: {index_path}")
    match = re.search(
        r"^Epic prefix:\s*`([^`]+)`\s*$",
        index_path.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if not match:
        raise RuntimeError(
            f"Local document index does not declare an epic prefix: {index_path}"
        )
    return match.group(1)


def initialize_local_docs(args, context, prefix):
    dry_run = getattr(args, "dry_run", False)
    findings = local_docs_path_findings(context)
    tracked = tracked_local_doc_paths(context["primaryRoot"])
    if tracked:
        findings.append(
            {
                "code": "tracked_local_document_collision",
                "severity": "fail",
                "message": (
                    "Refusing to initialize because local-document paths are already tracked."
                ),
                "paths": tracked,
            }
        )
    if local_docs_opted_out(context):
        findings.append(
            {
                "code": "local_document_profile_opted_out",
                "severity": "fail",
                "message": (
                    "Project opted out of default local documents through "
                    f"{context['optOutPath']}; run docs enable before initialization."
                ),
            }
        )
    if findings:
        return findings, [], []

    prefix = prefix.upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9]{1,11}", prefix):
        findings.append(
            {
                "code": "invalid_epic_prefix",
                "severity": "fail",
                "message": (
                    "Epic prefix must be 2-12 uppercase letters or digits and begin "
                    "with a letter."
                ),
            }
        )
        return findings, [], []

    created = []
    preserved = []
    candidates = [
        (context["policyPath"], "doc_org.md.tmpl"),
        (context["indexPath"], "INDEX.md.tmpl"),
    ]
    rendered = {
        path: render_local_doc_template(template, {"EPIC_PREFIX": prefix})
        for path, template in candidates
        if not path.exists()
    }
    if context["indexPath"].exists():
        existing_prefix = local_epic_prefix(context["indexPath"])
        if existing_prefix != prefix:
            findings.append(
                {
                    "code": "epic_prefix_mismatch",
                    "severity": "fail",
                    "message": (
                        "Existing local document index uses epic prefix "
                        f"{existing_prefix}, not {prefix}."
                    ),
                }
            )
            return findings, [], []

    missing_excludes = ensure_local_excludes(context["excludePath"], dry_run=dry_run)
    for path, template in candidates:
        if path.exists():
            preserved.append(str(path))
            continue
        created.append(str(path))
        if not dry_run:
            write_new_file(path, rendered[path])
    for directory in [
        context["docsRoot"] / "drafts",
        context["docsRoot"] / "epics",
        context["docsRoot"] / "research",
    ]:
        if directory.exists():
            preserved.append(str(directory))
        else:
            created.append(str(directory))
            if not dry_run:
                directory.mkdir(parents=True, exist_ok=False)

    if missing_excludes:
        findings.append(
            {
                "code": (
                    "local_excludes_added"
                    if not dry_run
                    else "local_excludes_planned"
                ),
                "severity": "pass",
                "message": "Local Git exclusions protect the canonical local-document paths.",
                "patterns": missing_excludes,
            }
        )
    return findings, created, preserved


def local_product_document_paths(context):
    paths = []
    for root in [context["docsRoot"] / "drafts", context["docsRoot"] / "epics"]:
        if not root.is_dir() or root.is_symlink():
            continue
        paths.extend(
            path
            for path in root.rglob("*.md")
            if path.is_file() and not path.is_symlink()
        )
    return sorted(paths)


def guided_draft_destination(context, template):
    templates = {
        "founding-hypothesis": (
            "FOUNDING_HYPOTHESIS.md.tmpl",
            "FOUNDING_HYPOTHESIS.md",
        ),
        "peter-yang": ("PETER_YANG_PRD.md.tmpl", "PETER_YANG_PRD.md"),
    }
    template_name, filename = templates[template]
    return template_name, context["docsRoot"] / "drafts" / filename


def create_guided_draft(context, template, dry_run=False):
    template_name, draft_path = guided_draft_destination(context, template)
    drafts_root = context["docsRoot"] / "drafts"
    findings = []
    if drafts_root.is_symlink() or (
        drafts_root.exists() and not drafts_root.is_dir()
    ):
        findings.append(
            {
                "code": "invalid_drafts_directory",
                "severity": "fail",
                "message": f"Drafts path must be a real directory: {drafts_root}",
            }
        )
        return findings, draft_path
    if draft_path.exists() or draft_path.is_symlink():
        findings.append(
            {
                "code": "draft_exists",
                "severity": "fail",
                "message": f"Refusing to overwrite an existing product draft: {draft_path}",
            }
        )
        return findings, draft_path
    date = datetime.now().astimezone().date().isoformat()
    rendered = render_local_doc_template(template_name, {"DATE": date})
    if not dry_run:
        drafts_root.mkdir(parents=True, exist_ok=True)
        write_new_file(draft_path, rendered)
    findings.append(
        {
            "code": "guided_draft_planned" if dry_run else "guided_draft_created",
            "severity": "pass",
            "message": (
                f"Gauntlet {'would create' if dry_run else 'created'} an unanswered "
                f"{template} draft."
            ),
        }
    )
    return findings, draft_path


def command_docs_init(args):
    context = local_docs_context(args.project_root)
    findings, created, preserved = initialize_local_docs(
        args, context, args.epic_prefix
    )
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
        return local_docs_payload(
            args,
            context,
            path_findings,
            mode="default-on",
            materialized=False,
            created=[],
            preserved=[],
        )
    if local_docs_opted_out(context):
        return local_docs_payload(
            args,
            context,
            [
                {
                    "code": "local_document_profile_opted_out",
                    "severity": "pass",
                    "message": (
                        "Project opted out of default local documents through "
                        f"{context['optOutPath']}; no files were created."
                    ),
                }
            ],
            mode="opted-out",
            materialized=False,
            created=[],
            preserved=[],
        )

    all_paths_exist = all(
        path.exists()
        for path in [context["policyPath"], context["docsRoot"], context["indexPath"]]
    )
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
        migration_findings, migrated = ensure_doc_execution_contract(
            context, dry_run=args.dry_run
        )
        findings = migration_findings + local_docs_validation_findings(
            context, require_profile=True
        )
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
    if not had_product_document and (
        founding_candidate.exists() or founding_candidate.is_symlink()
    ):
        return local_docs_payload(
            args,
            context,
            [
                {
                    "code": "draft_exists",
                    "severity": "fail",
                    "message": (
                        "Refusing to overwrite an existing product draft path: "
                        f"{founding_candidate}"
                    ),
                }
            ],
            mode="default-on",
            materialized=False,
            created=[],
            preserved=[],
            dryRun=args.dry_run,
            foundingDraftPath=str(founding_candidate),
        )
    prefix = args.epic_prefix or (
        local_epic_prefix(context["indexPath"])
        if context["indexPath"].is_file()
        else inferred_epic_prefix(context)
    )
    findings, created, preserved = initialize_local_docs(args, context, prefix)
    founding_draft_path = None
    if not had_product_document and not any(
        finding.get("severity") == "fail" for finding in findings
    ):
        draft_findings, founding_draft_path = create_guided_draft(
            context, "founding-hypothesis", dry_run=args.dry_run
        )
        findings.extend(draft_findings)
        if not any(
            finding.get("severity") == "fail" for finding in draft_findings
        ):
            created.append(str(founding_draft_path))
    if not args.dry_run and not any(
        finding.get("severity") == "fail" for finding in findings
    ):
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
        findings.append(
            {
                "code": "tracked_local_document_collision",
                "severity": "fail",
                "message": (
                    "Refusing to change the local-document mode because "
                    "local-document paths are already tracked."
                ),
                "paths": tracked,
            }
        )
    if not findings and not context["optOutPath"].exists():
        write_new_file(
            context["optOutPath"],
            "# Gauntlet local-document profile disabled.\n",
        )
        changed = True
    if (
        context["optOutPath"].exists()
        and not context["optOutPath"].is_symlink()
        and context["optOutPath"].is_file()
    ):
        findings.append(
            {
                "code": "local_document_profile_disabled",
                "severity": "pass",
                "message": (
                    "Default local documents are disabled for this project through "
                    f"{context['optOutPath']}."
                ),
            }
        )
    return local_docs_payload(
        args, context, findings, mode="opted-out", changed=changed
    )


def command_docs_enable(args):
    context = local_docs_context(args.project_root)
    findings = local_docs_path_findings(context)
    changed = False
    if (
        not any(finding.get("severity") == "fail" for finding in findings)
        and context["optOutPath"].is_file()
    ):
        context["optOutPath"].unlink()
        changed = True
    if not any(finding.get("severity") == "fail" for finding in findings):
        findings.append(
            {
                "code": "local_document_profile_enabled",
                "severity": "pass",
                "message": (
                    "Default local documents are enabled for this project; files "
                    "will be materialized on first covered document task."
                ),
            }
        )
    return local_docs_payload(
        args, context, findings, mode="default-on", changed=changed
    )


def command_docs_check(args):
    context = local_docs_context(args.project_root)
    opted_out = local_docs_opted_out(context)
    findings = local_docs_validation_findings(context)
    materialized = any(
        path.exists()
        for path in [context["policyPath"], context["docsRoot"], context["indexPath"]]
    )
    if not opted_out and context["policyPath"].is_file():
        migration_findings, _ = ensure_doc_execution_contract(context, dry_run=True)
        findings.extend(migration_findings)
    if opted_out:
        findings.append(
            {
                "code": "local_document_profile_opted_out",
                "severity": "pass",
                "message": (
                    "Project opted out of default local documents through "
                    f"{context['optOutPath']}."
                ),
            }
        )
    elif materialized:
        findings.append(
            {
                "code": "local_document_profile_materialized",
                "severity": "pass",
                "message": (
                    "Default local documents are materialized in the primary worktree."
                ),
            }
        )
    else:
        findings.append(
            {
                "code": "local_document_profile_default_active",
                "severity": "pass",
                "message": (
                    "Default local documents are active and will be materialized "
                    "lazily on the first covered document task."
                ),
            }
        )
    duplicates = []
    if not opted_out and materialized:
        for worktree in context["worktrees"][1:]:
            for relative in ["doc_org.md", "local-docs"]:
                candidate = worktree / relative
                if candidate.exists():
                    duplicates.append(str(candidate))
    if duplicates:
        findings.append(
            {
                "code": "linked_worktree_canonical_copy",
                "severity": "fail",
                "message": (
                    "Linked worktrees contain alternate canonical local-document paths."
                ),
                "paths": duplicates,
            }
        )
    return local_docs_payload(
        args,
        context,
        findings,
        checked=True,
        mode="opted-out" if opted_out else "default-on",
        materialized=materialized,
    )


def epic_title_slug(title):
    slug = re.sub(r"[^A-Z0-9]+", "_", title.upper()).strip("_")
    return slug[:64] or "UNTITLED"


def valid_epic_title(title):
    return (
        bool(title.strip())
        and len(title) <= 120
        and not any(character in title for character in "\n\r|[]()<>`\\")
    )


def allocated_epic_numbers(context, prefix):
    pattern = re.compile(rf"\b{re.escape(prefix)}-(\d{{3}})\b")
    numbers = {
        int(match)
        for match in pattern.findall(
            context["indexPath"].read_text(encoding="utf-8")
        )
    }
    epics_root = context["docsRoot"] / "epics"
    if epics_root.exists():
        for path in epics_root.rglob("*.md"):
            if path.is_file() and not path.is_symlink():
                numbers.update(
                    int(match)
                    for match in pattern.findall(path.read_text(encoding="utf-8"))
                )
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
            raise RuntimeError(
                f"An appended PRD path must not use symlinks: {candidate}"
            )
        current = current.parent
    if not candidate.is_file():
        raise RuntimeError(f"An appended PRD must already exist: {candidate}")
    return candidate


def command_docs_epic_create(args):
    context = local_docs_context(args.project_root)
    if local_docs_opted_out(context):
        findings = local_docs_path_findings(context) + [
            {
                "code": "local_document_profile_opted_out",
                "severity": "fail",
                "message": (
                    "Project opted out of default local documents through "
                    f"{context['optOutPath']}; run docs enable before creating an Epic."
                ),
            }
        ]
    elif all(
        path.exists()
        for path in [context["policyPath"], context["docsRoot"], context["indexPath"]]
    ):
        findings = local_docs_validation_findings(context, require_profile=True)
    else:
        findings, _, _ = initialize_local_docs(
            args, context, inferred_epic_prefix(context)
        )
        if not any(finding.get("severity") == "fail" for finding in findings):
            findings.extend(
                local_docs_validation_findings(context, require_profile=True)
            )
    if findings:
        return local_docs_payload(args, context, findings)
    if not valid_epic_title(args.title):
        findings.append(
            {
                "code": "invalid_epic_title",
                "severity": "fail",
                "message": (
                    "Epic title must be one non-empty line, at most 120 characters, "
                    "without Markdown link or control delimiters."
                ),
            }
        )
        return local_docs_payload(args, context, findings)
    prefix = local_epic_prefix(context["indexPath"])
    if not re.fullmatch(r"[A-Z][A-Z0-9]{1,11}", prefix):
        raise RuntimeError(f"Local document index has an invalid epic prefix: {prefix}")
    epics_root = context["docsRoot"] / "epics"
    existing = allocated_epic_numbers(context, prefix)
    number = args.number if args.number is not None else (
        (max(existing) + 1) if existing else 1
    )
    if number < 1 or number > 999:
        findings.append(
            {
                "code": "invalid_epic_number",
                "severity": "fail",
                "message": "Epic number must be between 001 and 999.",
            }
        )
        return local_docs_payload(args, context, findings)
    sequence = f"{number:03d}"
    if number in existing:
        findings.append(
            {
                "code": "epic_id_exists",
                "severity": "fail",
                "message": f"Epic ID already exists: {prefix}-{sequence}",
            }
        )
        return local_docs_payload(args, context, findings)
    epic_root = epics_root / sequence
    if not args.prd and epic_root.exists():
        findings.append(
            {
                "code": "epic_exists",
                "severity": "fail",
                "message": f"Epic folder already exists: {epic_root}",
            }
        )
        return local_docs_payload(args, context, findings)

    index_text = context["indexPath"].read_text(encoding="utf-8")
    marker = "<!-- EPICS -->"
    if marker not in index_text:
        raise RuntimeError(
            f"Local document index is missing its epic insertion marker: "
            f"{context['indexPath']}"
        )
    date = datetime.now().astimezone().date().isoformat()
    epic_id = f"{prefix}-{sequence}"
    section = render_local_doc_template(
        "EPIC_SECTION.md.tmpl",
        {"EPIC_ID": epic_id, "TITLE": args.title},
    )
    prd_path = (
        existing_prd_path(context, args.prd)
        if args.prd
        else epic_root / f"{sequence}_{epic_title_slug(args.title)}_PRD.md"
    )
    prd_before = prd_path.read_text(encoding="utf-8") if args.prd else None
    try:
        if args.prd:
            separator = (
                ""
                if prd_before.endswith("\n\n")
                else ("\n" if prd_before.endswith("\n") else "\n\n")
            )
            _atomic_write_text(
                prd_path, prd_before + separator + section.rstrip() + "\n"
            )
        else:
            epic_root.mkdir(parents=True)
            for child in ["prompts", "research", "decisions", "runs"]:
                (epic_root / child).mkdir()
            write_new_file(
                prd_path,
                render_local_doc_template(
                    "EPIC_PRD.md.tmpl",
                    {
                        "TITLE": args.title,
                        "DATE": date,
                        "EPIC_SECTION": section.rstrip(),
                    },
                ),
            )
        relative = prd_path.relative_to(context["docsRoot"])
        row = (
            f"| `{epic_id}` | [{args.title}]({relative.as_posix()}) | PRD | "
            f"Proposed | {date} | None | None | Not implemented | Not verified |\n"
        )
        _atomic_write_text(
            context["indexPath"], index_text.replace(marker, row + marker, 1)
        )
    except Exception:
        if args.prd and prd_before is not None:
            _atomic_write_text(prd_path, prd_before)
        elif epic_root.exists():
            shutil.rmtree(epic_root)
        raise
    return local_docs_payload(
        args,
        context,
        findings,
        epicId=epic_id,
        epicRoot=str(prd_path.parent),
        prdPath=str(prd_path),
        appended=bool(args.prd),
    )


def command_docs_draft_create(args):
    context = local_docs_context(args.project_root)
    _, draft_candidate = guided_draft_destination(context, args.template)
    if draft_candidate.exists() or draft_candidate.is_symlink():
        return local_docs_payload(
            args,
            context,
            [
                {
                    "code": "draft_exists",
                    "severity": "fail",
                    "message": (
                        "Refusing to overwrite an existing product draft: "
                        f"{draft_candidate}"
                    ),
                }
            ],
            template=args.template,
            draftPath=str(draft_candidate),
            dryRun=args.dry_run,
        )
    if local_docs_opted_out(context):
        findings = local_docs_path_findings(context) + [
            {
                "code": "local_document_profile_opted_out",
                "severity": "fail",
                "message": (
                    "Project opted out of default local documents through "
                    f"{context['optOutPath']}; run docs enable before creating a draft."
                ),
            }
        ]
    elif all(
        path.exists()
        for path in [context["policyPath"], context["docsRoot"], context["indexPath"]]
    ):
        findings = local_docs_validation_findings(context, require_profile=True)
    else:
        findings, _, _ = initialize_local_docs(
            args, context, inferred_epic_prefix(context)
        )
        if not args.dry_run and not any(
            finding.get("severity") == "fail" for finding in findings
        ):
            findings.extend(
                local_docs_validation_findings(context, require_profile=True)
            )
    if any(finding.get("severity") == "fail" for finding in findings):
        return local_docs_payload(
            args, context, findings, template=args.template, dryRun=args.dry_run
        )
    draft_findings, draft_path = create_guided_draft(
        context, args.template, dry_run=args.dry_run
    )
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
        raise RuntimeError(
            "A promoted draft must be inside local-docs/drafts."
        ) from exc
    current = candidate.parent
    resolved_docs_root = context["docsRoot"].resolve()
    while current.resolve() != resolved_docs_root:
        if current.is_symlink():
            raise RuntimeError(
                f"A promoted draft path must not use symlinks: {candidate}"
            )
        if current == current.parent:
            raise RuntimeError(
                "A promoted draft must be inside local-docs/drafts."
            )
        current = current.parent
    if candidate.parent.resolve() != resolved_root:
        raise RuntimeError(
            "A promoted draft must be directly inside local-docs/drafts."
        )
    if not resolved.is_file():
        raise RuntimeError(f"A promoted draft must already exist: {candidate}")
    return resolved


def command_docs_draft_promote(args):
    context = local_docs_context(args.project_root)
    if local_docs_opted_out(context):
        findings = local_docs_path_findings(context) + [
            {
                "code": "local_document_profile_opted_out",
                "severity": "fail",
                "message": (
                    "Project opted out of default local documents through "
                    f"{context['optOutPath']}; run docs enable before promoting a draft."
                ),
            }
        ]
    elif all(
        path.exists()
        for path in [context["policyPath"], context["docsRoot"], context["indexPath"]]
    ):
        findings = local_docs_validation_findings(context, require_profile=True)
    else:
        findings = local_docs_path_findings(context) + [
            {
                "code": "local_document_profile_missing",
                "severity": "fail",
                "message": "Create a local product draft before promoting it.",
            }
        ]
    if any(finding.get("severity") == "fail" for finding in findings):
        return local_docs_payload(args, context, findings, dryRun=args.dry_run)
    if not valid_epic_title(args.title):
        findings.append(
            {
                "code": "invalid_epic_title",
                "severity": "fail",
                "message": (
                    "Epic title must be one non-empty line, at most 120 characters, "
                    "without Markdown link or control delimiters."
                ),
            }
        )
        return local_docs_payload(args, context, findings, dryRun=args.dry_run)

    draft_path = local_draft_path(context, args.draft)
    prefix = local_epic_prefix(context["indexPath"])
    if not re.fullmatch(r"[A-Z][A-Z0-9]{1,11}", prefix):
        raise RuntimeError(f"Local document index has an invalid epic prefix: {prefix}")
    existing = allocated_epic_numbers(context, prefix)
    number = args.number if args.number is not None else (
        (max(existing) + 1) if existing else 1
    )
    if number < 1 or number > 999:
        findings.append(
            {
                "code": "invalid_epic_number",
                "severity": "fail",
                "message": "Epic number must be between 001 and 999.",
            }
        )
        return local_docs_payload(
            args,
            context,
            findings,
            draftPath=str(draft_path),
            dryRun=args.dry_run,
        )
    sequence = f"{number:03d}"
    epic_id = f"{prefix}-{sequence}"
    if number in existing:
        findings.append(
            {
                "code": "epic_id_exists",
                "severity": "fail",
                "message": f"Epic ID already exists: {epic_id}",
            }
        )
        return local_docs_payload(
            args,
            context,
            findings,
            draftPath=str(draft_path),
            dryRun=args.dry_run,
        )

    epics_root = context["docsRoot"] / "epics"
    epic_root = epics_root / sequence
    prd_path = epic_root / f"{sequence}_{epic_title_slug(args.title)}_PRD.md"
    if epic_root.exists() or epic_root.is_symlink() or prd_path.exists():
        findings.append(
            {
                "code": "epic_exists",
                "severity": "fail",
                "message": f"Epic destination already exists: {epic_root}",
            }
        )
        return local_docs_payload(
            args,
            context,
            findings,
            draftPath=str(draft_path),
            dryRun=args.dry_run,
        )

    index_path = context["indexPath"]
    index_text = index_path.read_text(encoding="utf-8")
    marker = "<!-- EPICS -->"
    if index_text.count(marker) != 1:
        raise RuntimeError(
            f"Local document index must contain exactly one epic insertion marker: "
            f"{index_path}"
        )
    date = datetime.now().astimezone().date().isoformat()
    relative = prd_path.relative_to(context["docsRoot"])
    row = (
        f"| `{epic_id}` | [{args.title}]({relative.as_posix()}) | PRD | "
        f"Proposed | {date} | None | None | Not implemented | Not verified |\n"
    )
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
        _atomic_write_text(index_path, updated_index)
    except Exception:
        if moved and prd_path.is_file() and not draft_path.exists():
            os.replace(prd_path, draft_path)
        if epic_root.exists() and not epic_root.is_symlink():
            shutil.rmtree(epic_root)
        if (
            index_path.is_file()
            and index_path.read_text(encoding="utf-8") != index_text
        ):
            _atomic_write_text(index_path, index_text)
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


def markdown_answer(text, headings):
    for heading in headings:
        match = re.search(
            rf"^(##|###) {re.escape(heading)}\s*$",
            text,
            re.MULTILINE | re.IGNORECASE,
        )
        if not match:
            continue
        level = len(match.group(1))
        following = re.search(
            rf"^#{{1,{level}}} ", text[match.end() :], re.MULTILINE
        )
        end = match.end() + following.start() if following else len(text)
        content = text[match.end() : end].strip()
        substantive = [
            line
            for line in content.splitlines()
            if line.strip()
            and not line.strip().lower().startswith(("*guidance:", "_guidance:"))
        ]
        if substantive:
            return content
    return ""


def accepted_record_path(prd_path):
    return prd_path.with_suffix(".accepted.json")


def command_docs_epic_accept(args):
    context = local_docs_context(args.project_root)
    findings = local_docs_validation_findings(context, require_profile=True)
    if any(finding.get("severity") == "fail" for finding in findings):
        return local_docs_payload(args, context, findings, dryRun=args.dry_run)
    epic_id = args.epic.upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9]*-\d{3}", epic_id):
        findings.append(
            {
                "code": "invalid_epic_id",
                "severity": "fail",
                "message": "Acceptance requires a stable Epic ID.",
            }
        )
        return local_docs_payload(args, context, findings, dryRun=args.dry_run)
    prd_path = existing_prd_path(context, args.prd)
    source_bytes = prd_path.read_bytes()
    source_text = source_bytes.decode("utf-8")
    if not markdown_answer(
        source_text, ("Acceptance", "Done when", "Product Acceptance")
    ):
        findings.append(
            {
                "code": "missing_observable_acceptance",
                "severity": "fail",
                "message": (
                    "Add an answered Acceptance or Done when section before "
                    "accepting this Epic; Gauntlet will not invent it."
                ),
            }
        )
        return local_docs_payload(
            args,
            context,
            findings,
            epicId=epic_id,
            prdPath=str(prd_path),
            dryRun=args.dry_run,
        )
    index_path = context["indexPath"]
    index_text = index_path.read_text(encoding="utf-8")
    row_pattern = re.compile(
        rf"^\| `{re.escape(epic_id)}` \| \[([^\]]+)\]\(([^)]+)\) "
        rf"\| PRD \| ([^|]+) \|.*$",
        re.MULTILINE,
    )
    row_match = row_pattern.search(index_text)
    if not row_match:
        findings.append(
            {
                "code": "epic_not_indexed",
                "severity": "fail",
                "message": f"Epic {epic_id} is not indexed.",
            }
        )
        return local_docs_payload(
            args,
            context,
            findings,
            epicId=epic_id,
            prdPath=str(prd_path),
            dryRun=args.dry_run,
        )
    indexed_path = (context["docsRoot"] / row_match.group(2)).resolve()
    if indexed_path != prd_path.resolve():
        findings.append(
            {
                "code": "epic_path_mismatch",
                "severity": "fail",
                "message": f"Epic {epic_id} does not point to {prd_path}.",
            }
        )
        return local_docs_payload(
            args,
            context,
            findings,
            epicId=epic_id,
            prdPath=str(prd_path),
            dryRun=args.dry_run,
        )
    sidecar = accepted_record_path(prd_path)
    if sidecar.exists() or sidecar.is_symlink():
        findings.append(
            {
                "code": "accepted_record_exists",
                "severity": "fail",
                "message": f"Acceptance already exists: {sidecar}",
            }
        )
        return local_docs_payload(
            args,
            context,
            findings,
            epicId=epic_id,
            prdPath=str(prd_path),
            acceptedRecord=str(sidecar),
            dryRun=args.dry_run,
        )
    if not all(
        [
            _parse_dependency_list,
            _parse_release_stages,
            _parse_consequence_triggers,
        ]
    ):
        raise RuntimeError("Docs acceptance contracts are not configured.")
    record = {
        "schemaVersion": "gauntlet.accepted-epic.v1",
        "epicId": epic_id,
        "title": row_match.group(1),
        "sourcePath": str(prd_path.resolve()),
        "sourceSha256": sha256(source_bytes),
        "acceptedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "dependencies": _parse_dependency_list(args.depends_on),
        "releaseStages": _parse_release_stages(args.release_stages),
        "consequenceTriggers": _parse_consequence_triggers(
            args.consequence_triggers
        ),
    }
    updated_index = (
        index_text[: row_match.start()]
        + row_match.group(0).replace("| Proposed |", "| Accepted |", 1)
        + index_text[row_match.end() :]
    )
    if updated_index == index_text:
        findings.append(
            {
                "code": "epic_not_proposed",
                "severity": "fail",
                "message": f"Epic {epic_id} must be Proposed before acceptance.",
            }
        )
        return local_docs_payload(
            args,
            context,
            findings,
            epicId=epic_id,
            prdPath=str(prd_path),
            dryRun=args.dry_run,
        )
    if not args.dry_run:
        try:
            write_new_file(
                sidecar, json.dumps(record, indent=2, sort_keys=True) + "\n"
            )
            _atomic_write_text(index_path, updated_index)
        except Exception:
            if sidecar.is_file() and not sidecar.is_symlink():
                sidecar.unlink()
            if index_path.read_text(encoding="utf-8") != index_text:
                _atomic_write_text(index_path, index_text)
            raise
    return local_docs_payload(
        args,
        context,
        findings,
        epicId=epic_id,
        prdPath=str(prd_path),
        acceptedRecord=str(sidecar),
        sourceSha256=record["sourceSha256"],
        dryRun=args.dry_run,
    )
