"""Controller-free local design-document lifecycle."""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from gauntletlib.cli_support import EXIT_CODES
from gauntletlib.core.fsio import atomic_write_text as _core_atomic_write_text
from gauntletlib.core.fsio import write_new_file
from gauntletlib.core.findings import status_for
from gauntletlib.core.hashing import sha256
from gauntletlib.core.proc import git


ROOT = Path(__file__).resolve().parents[3]
LOCAL_DOC_TEMPLATES = ROOT / "templates" / "local-docs"
LOCAL_DOC_OPT_OUT = Path(".gauntlet") / "doc-org.disabled"

_atomic_write_text = _core_atomic_write_text


def configure(*, atomic_write_text=None, **_unused):
    """Allow the CLI facade and tests to provide the shared atomic writer."""
    global _atomic_write_text
    if atomic_write_text is not None:
        _atomic_write_text = atomic_write_text


def _git_root(repo):
    result = git(["rev-parse", "--show-toplevel"], repo)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def parse_worktree_roots(project_root):
    result = git(["worktree", "list", "--porcelain"], project_root)
    if result.returncode != 0:
        raise RuntimeError(f"Cannot list repository worktrees:\n{result.stderr.strip()}")
    roots = [
        Path(line.removeprefix("worktree ")).resolve()
        for line in result.stdout.splitlines()
        if line.startswith("worktree ")
    ]
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
    docs_root = primary / "local-docs"
    return {
        "requestedRoot": supplied,
        "primaryRoot": primary,
        "worktrees": worktrees,
        "policyPath": primary / "doc_org.md",
        "docsRoot": docs_root,
        "indexPath": docs_root / "INDEX.md",
        "designsRoot": docs_root / "designs",
        "researchRoot": docs_root / "research",
        "decisionsRoot": docs_root / "decisions",
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
    canonical = [
        context["policyPath"],
        context["docsRoot"],
        context["indexPath"],
        context["designsRoot"],
        context["researchRoot"],
        context["decisionsRoot"],
    ]
    for path in canonical:
        if path.is_symlink():
            findings.append(
                {
                    "code": "local_document_symlink",
                    "severity": "fail",
                    "message": f"Canonical local-document paths must not be symlinks: {path}",
                }
            )
    expected_files = [context["policyPath"], context["indexPath"]]
    expected_directories = [
        context["docsRoot"],
        context["designsRoot"],
        context["researchRoot"],
        context["decisionsRoot"],
    ]
    for path in expected_files:
        if path.exists() and not path.is_file():
            findings.append(
                {
                    "code": "invalid_local_document_file",
                    "severity": "fail",
                    "message": f"Canonical local-document path is not a file: {path}",
                }
            )
    for path in expected_directories:
        if path.exists() and not path.is_dir():
            findings.append(
                {
                    "code": "invalid_local_document_directory",
                    "severity": "fail",
                    "message": f"Canonical local-document path is not a directory: {path}",
                }
            )
    opt_out = context["optOutPath"]
    if opt_out.is_symlink():
        findings.append(
            {
                "code": "local_document_opt_out_symlink",
                "severity": "fail",
                "message": f"Local-document opt-out marker must not be a symlink: {opt_out}",
            }
        )
    elif opt_out.exists() and not opt_out.is_file():
        findings.append(
            {
                "code": "invalid_local_document_opt_out",
                "severity": "fail",
                "message": f"Local-document opt-out marker is not a file: {opt_out}",
            }
        )
    return findings


def local_docs_opted_out(context):
    return context["optOutPath"].is_file()


def inferred_design_prefix(context):
    raw = re.sub(r"[^A-Z0-9]", "", context["primaryRoot"].name.upper())
    if not raw or not raw[0].isalpha():
        raw = "PROJECT"
    if len(raw) == 1:
        raw += "D"
    return raw[:12]


def local_design_prefix(index_path):
    if not index_path.is_file():
        raise RuntimeError(f"Local document index does not exist: {index_path}")
    text = index_path.read_text(encoding="utf-8")
    match = re.search(r"^Design prefix:\s*`([^`]+)`\s*$", text, re.MULTILINE)
    if not match:
        raise RuntimeError(
            f"Local document index does not declare a design prefix: {index_path}"
        )
    return match.group(1)


def _valid_prefix(prefix):
    return bool(re.fullmatch(r"[A-Z][A-Z0-9]{1,11}", prefix))


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
        for path, code in [
            (context["policyPath"], "missing_doc_org"),
            (context["indexPath"], "missing_local_docs_index"),
        ]:
            if not path.is_file():
                findings.append(
                    {"code": code, "severity": "fail", "message": f"Missing {path}"}
                )
        for relative in [
            "doc_org.md",
            "local-docs/INDEX.md",
            ".gauntlet/doc-org.disabled",
        ]:
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


def ensure_local_excludes(exclude_path, dry_run=False):
    required = ["/doc_org.md", "/local-docs/", "/.gauntlet/doc-org.disabled"]
    existing = exclude_path.read_text(encoding="utf-8") if exclude_path.exists() else ""
    lines = {line.strip() for line in existing.splitlines()}
    missing = [entry for entry in required if entry not in lines]
    if missing and not dry_run:
        exclude_path.parent.mkdir(parents=True, exist_ok=True)
        prefix = existing
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        _atomic_write_text(exclude_path, prefix + "\n".join(missing) + "\n", mode=0o644)
    return missing


def _print_payload(payload, as_json):
    if as_json:
        print(json.dumps(payload, indent=2))
        return
    print(f"Gauntlet: {payload['status']}")
    for finding in payload.get("findings", []):
        print(f"- [{finding['severity']}] {finding['code']}: {finding['message']}")


def local_docs_payload(args, context, findings, **extra):
    payload = {
        "schemaVersion": "gauntlet.local-docs.v2",
        "status": "pass",
        "primaryRoot": str(context["primaryRoot"]),
        "policyPath": str(context["policyPath"]),
        "localDocsRoot": str(context["docsRoot"]),
        "findings": findings,
        **extra,
    }
    payload["status"] = status_for(payload["findings"])
    _print_payload(payload, getattr(args, "json", False))
    return EXIT_CODES[payload["status"]]


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
                    "Project opted out of default local documents; run docs enable "
                    "before initialization."
                ),
            }
        )
    prefix = prefix.upper()
    if not _valid_prefix(prefix):
        findings.append(
            {
                "code": "invalid_design_prefix",
                "severity": "fail",
                "message": (
                    "Design prefix must be 2-12 uppercase letters or digits and begin "
                    "with a letter."
                ),
            }
        )
    if findings:
        return findings, [], []

    if context["indexPath"].exists():
        existing_prefix = local_design_prefix(context["indexPath"])
        if existing_prefix != prefix:
            findings.append(
                {
                    "code": "design_prefix_mismatch",
                    "severity": "fail",
                    "message": (
                        f"Existing local document index uses prefix {existing_prefix}, "
                        f"not {prefix}."
                    ),
                }
            )
            return findings, [], []

    candidates = [
        (context["policyPath"], "doc_org.md.tmpl"),
        (context["indexPath"], "INDEX.md.tmpl"),
    ]
    rendered = {
        path: render_local_doc_template(template, {"DESIGN_PREFIX": prefix})
        for path, template in candidates
        if not path.exists()
    }
    created = []
    preserved = []
    missing_excludes = ensure_local_excludes(context["excludePath"], dry_run=dry_run)
    for path, _template in candidates:
        if path.exists():
            preserved.append(str(path))
        else:
            created.append(str(path))
            if not dry_run:
                write_new_file(path, rendered[path])
    for directory in [
        context["designsRoot"],
        context["researchRoot"],
        context["decisionsRoot"],
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
                    "local_excludes_planned" if dry_run else "local_excludes_added"
                ),
                "severity": "pass",
                "message": "Local Git exclusions protect the canonical document paths.",
                "patterns": missing_excludes,
            }
        )
    return findings, created, preserved


def _profile_ready(args, context):
    if local_docs_opted_out(context):
        return [
            {
                "code": "local_document_profile_opted_out",
                "severity": "fail",
                "message": (
                    "Project opted out of default local documents; run docs enable "
                    "before creating or accepting a design."
                ),
            }
        ]
    materialized = all(
        path.exists()
        for path in [context["policyPath"], context["docsRoot"], context["indexPath"]]
    )
    if materialized:
        findings = local_docs_validation_findings(context, require_profile=True)
        if not any(finding["severity"] == "fail" for finding in findings):
            for directory in [
                context["designsRoot"],
                context["researchRoot"],
                context["decisionsRoot"],
            ]:
                if not directory.exists():
                    if getattr(args, "dry_run", False):
                        continue
                    directory.mkdir(parents=True, exist_ok=False)
        return findings
    prefix = getattr(args, "prefix", None) or inferred_design_prefix(context)
    findings, _, _ = initialize_local_docs(args, context, prefix)
    if not getattr(args, "dry_run", False) and not any(
        finding["severity"] == "fail" for finding in findings
    ):
        findings.extend(local_docs_validation_findings(context, require_profile=True))
    return findings


def command_docs_init(args):
    context = local_docs_context(args.project_root)
    findings, created, preserved = initialize_local_docs(args, context, args.prefix)
    return local_docs_payload(
        args,
        context,
        findings,
        designPrefix=args.prefix.upper(),
        dryRun=args.dry_run,
        created=created,
        preserved=preserved,
        excludePath=str(context["excludePath"]),
    )


def command_docs_ensure(args):
    context = local_docs_context(args.project_root)
    path_findings = local_docs_path_findings(context)
    if any(finding["severity"] == "fail" for finding in path_findings):
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
                    "message": "Project opted out; no local documents were created.",
                }
            ],
            mode="opted-out",
            materialized=False,
            created=[],
            preserved=[],
        )
    prefix = args.prefix or (
        local_design_prefix(context["indexPath"])
        if context["indexPath"].is_file()
        else inferred_design_prefix(context)
    )
    findings, created, preserved = initialize_local_docs(args, context, prefix)
    if not args.dry_run and not any(
        finding["severity"] == "fail" for finding in findings
    ):
        findings.extend(local_docs_validation_findings(context, require_profile=True))
    return local_docs_payload(
        args,
        context,
        findings,
        mode="default-on",
        materialized=not args.dry_run,
        designPrefix=prefix.upper(),
        dryRun=args.dry_run,
        created=created,
        preserved=preserved,
        excludePath=str(context["excludePath"]),
    )


def command_docs_disable(args):
    context = local_docs_context(args.project_root)
    findings = local_docs_path_findings(context)
    tracked = tracked_local_doc_paths(context["primaryRoot"])
    if tracked:
        findings.append(
            {
                "code": "tracked_local_document_collision",
                "severity": "fail",
                "message": (
                    "Refusing to change the local-document mode because canonical "
                    "local paths are tracked."
                ),
                "paths": tracked,
            }
        )
    changed = False
    if not findings and not context["optOutPath"].exists():
        ensure_local_excludes(context["excludePath"])
        write_new_file(
            context["optOutPath"],
            "# Gauntlet local-document profile disabled.\n",
        )
        changed = True
    if context["optOutPath"].is_file() and not context["optOutPath"].is_symlink():
        findings.append(
            {
                "code": "local_document_profile_disabled",
                "severity": "pass",
                "message": "Default local documents are disabled for this project.",
            }
        )
    return local_docs_payload(
        args, context, findings, mode="opted-out", changed=changed
    )


def command_docs_enable(args):
    context = local_docs_context(args.project_root)
    findings = local_docs_path_findings(context)
    changed = False
    if not any(finding["severity"] == "fail" for finding in findings):
        if context["optOutPath"].is_file():
            context["optOutPath"].unlink()
            changed = True
        findings.append(
            {
                "code": "local_document_profile_enabled",
                "severity": "pass",
                "message": (
                    "Default local documents are enabled and will materialize on "
                    "the first covered document action."
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
    if opted_out:
        findings.append(
            {
                "code": "local_document_profile_opted_out",
                "severity": "pass",
                "message": "Project opted out of the default local-document profile.",
            }
        )
    elif materialized:
        findings.append(
            {
                "code": "local_document_profile_materialized",
                "severity": "pass",
                "message": "Local designs are materialized in the primary worktree.",
            }
        )
    else:
        findings.append(
            {
                "code": "local_document_profile_default_active",
                "severity": "pass",
                "message": (
                    "Default local documents are active and will materialize lazily."
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
                "message": "Linked worktrees contain alternate canonical local documents.",
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


def design_title_slug(title):
    slug = re.sub(r"[^A-Z0-9]+", "_", title.upper()).strip("_")
    return slug[:64] or "UNTITLED"


def valid_design_title(title):
    return (
        bool(title.strip())
        and len(title) <= 120
        and not any(character in title for character in "\n\r|[]()<>`\\")
    )


def allocated_design_numbers(context, prefix):
    pattern = re.compile(rf"\b{re.escape(prefix)}-(\d{{3}})\b")
    numbers = set()
    if context["indexPath"].is_file():
        numbers.update(
            int(match)
            for match in pattern.findall(
                context["indexPath"].read_text(encoding="utf-8")
            )
        )
    for root in [context["designsRoot"]]:
        if not root.is_dir() or root.is_symlink():
            continue
        for path in root.rglob("*.md"):
            if path.is_file() and not path.is_symlink():
                numbers.update(
                    int(match)
                    for match in pattern.findall(path.read_text(encoding="utf-8"))
                )
    return numbers


def _index_marker(index_text):
    if index_text.count("<!-- DESIGNS -->") == 1:
        return "<!-- DESIGNS -->"
    raise RuntimeError(
        "Local document index must contain exactly one design insertion marker."
    )


def command_docs_design_create(args):
    context = local_docs_context(args.project_root)
    findings = _profile_ready(args, context)
    if any(finding["severity"] == "fail" for finding in findings):
        return local_docs_payload(args, context, findings, dryRun=args.dry_run)
    if not valid_design_title(args.title):
        findings.append(
            {
                "code": "invalid_design_title",
                "severity": "fail",
                "message": (
                    "Design title must be one non-empty line, at most 120 characters, "
                    "without Markdown link or table delimiters."
                ),
            }
        )
        return local_docs_payload(args, context, findings, dryRun=args.dry_run)

    prefix = (
        local_design_prefix(context["indexPath"])
        if context["indexPath"].is_file()
        else (getattr(args, "prefix", None) or inferred_design_prefix(context))
    )
    if not _valid_prefix(prefix):
        raise RuntimeError(f"Local document index has an invalid prefix: {prefix}")
    allocated = allocated_design_numbers(context, prefix)
    number = args.number if args.number is not None else (
        max(allocated) + 1 if allocated else 1
    )
    if number < 1 or number > 999:
        findings.append(
            {
                "code": "invalid_design_number",
                "severity": "fail",
                "message": "Design number must be between 001 and 999.",
            }
        )
        return local_docs_payload(args, context, findings, dryRun=args.dry_run)
    sequence = f"{number:03d}"
    design_id = f"{prefix}-{sequence}"
    if number in allocated:
        findings.append(
            {
                "code": "design_id_exists",
                "severity": "fail",
                "message": f"Design ID already exists: {design_id}",
            }
        )
        return local_docs_payload(args, context, findings, dryRun=args.dry_run)

    design_path = (
        context["designsRoot"]
        / f"{sequence}_{design_title_slug(args.title)}_DESIGN.md"
    )
    if design_path.exists() or design_path.is_symlink():
        findings.append(
            {
                "code": "design_exists",
                "severity": "fail",
                "message": f"Refusing to overwrite an existing design: {design_path}",
            }
        )
        return local_docs_payload(args, context, findings, dryRun=args.dry_run)
    date = datetime.now().astimezone().date().isoformat()
    rendered = render_local_doc_template(
        "DESIGN.md.tmpl",
        {
            "DESIGN_ID": design_id,
            "TITLE": args.title,
            "DATE": date,
        },
    )
    index_path = context["indexPath"]
    if index_path.is_file():
        index_text = index_path.read_text(encoding="utf-8")
    else:
        index_text = render_local_doc_template(
            "INDEX.md.tmpl", {"DESIGN_PREFIX": prefix}
        )
    marker = _index_marker(index_text)
    relative = design_path.relative_to(context["docsRoot"])
    row = (
        f"| `{design_id}` | [{args.title}]({relative.as_posix()}) "
        f"| Proposed | {date} |\n"
    )
    if not args.dry_run:
        try:
            write_new_file(design_path, rendered)
            _atomic_write_text(index_path, index_text.replace(marker, row + marker, 1))
        except Exception:
            if design_path.is_file() and not design_path.is_symlink():
                design_path.unlink()
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
        designId=design_id,
        designPath=str(design_path),
        dryRun=args.dry_run,
    )


def _safe_local_document_path(context, supplied):
    candidate = Path(supplied).expanduser()
    if not candidate.is_absolute():
        candidate = context["docsRoot"] / candidate
    candidate = Path(os.path.abspath(str(candidate)))
    resolved_root = context["docsRoot"].resolve()
    try:
        relative = candidate.relative_to(context["docsRoot"])
    except ValueError as exc:
        raise RuntimeError("A design must be inside local-docs.") from exc
    current = context["docsRoot"]
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise RuntimeError(f"A design path must not use symlinks: {candidate}")
    try:
        candidate.resolve().relative_to(resolved_root)
    except ValueError as exc:
        raise RuntimeError("A design must be inside local-docs.") from exc
    if not candidate.is_file():
        raise RuntimeError(f"A design must already exist: {candidate}")
    return candidate.resolve()


def _indexed_design(context, supplied):
    index_text = context["indexPath"].read_text(encoding="utf-8")
    row_pattern = re.compile(
        r"^\| `([A-Z][A-Z0-9]*-\d{3})` \| \[([^\]]+)\]\(([^)]+)\) "
        r"\| ([^|]+) \|.*$",
        re.MULTILINE,
    )
    rows = list(row_pattern.finditer(index_text))
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*-\d{3}", supplied):
        design_id = supplied.upper()
        row = next((item for item in rows if item.group(1) == design_id), None)
        if row is None:
            raise RuntimeError(f"Design {design_id} is not indexed.")
        design_path = _safe_local_document_path(context, row.group(3))
        return index_text, row, design_path

    design_path = _safe_local_document_path(context, supplied)
    row = next(
        (
            item
            for item in rows
            if (context["docsRoot"] / item.group(3)).resolve() == design_path
        ),
        None,
    )
    if row is None:
        raise RuntimeError(f"Design is not indexed: {design_path}")
    return index_text, row, design_path


def exact_acceptance_section(source_text):
    return exact_named_section(source_text, "Acceptance")


def exact_named_section(source_text, title):
    matches = list(
        re.finditer(
            rf"^## {re.escape(title)}[ \t]*\r?$",
            source_text,
            re.MULTILINE,
        )
    )
    if len(matches) != 1:
        return ""
    start = matches[0].start()
    following = re.search(r"^#{1,2} ", source_text[matches[0].end() :], re.MULTILINE)
    end = matches[0].end() + following.start() if following else len(source_text)
    section = source_text[start:end]
    body = source_text[matches[0].end() : end]
    visible = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    visible_lines = [
        line.strip()
        for line in visible.splitlines()
        if line.strip()
        and not line.strip().lower().startswith(("*guidance:", "_guidance:"))
    ]
    return section if visible_lines else ""


def _optional_contract_binding(source_text, title):
    headings = re.findall(
        rf"^## {re.escape(title)}[ \t]*\r?$",
        source_text,
        re.MULTILINE,
    )
    if len(headings) > 1:
        raise RuntimeError(f"Accepted design has multiple exact '{title}' sections.")
    section = exact_named_section(source_text, title)
    return {
        "applicable": bool(section),
        "sha256": "sha256:" + sha256(section.encode("utf-8")) if section else None,
    }


def acceptance_outcome_bindings(acceptance):
    """Return stable identities and digests for each exact accepted outcome.

    The contract retains only mechanical bindings.  Build and Verify continue
    to read the human-owned Acceptance section for meaning.
    """

    heading = re.match(r"^## Acceptance[ \t]*\r?\n?", acceptance)
    body = acceptance[heading.end() :] if heading else acceptance
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    lines = body.splitlines()
    item_candidates = [
        (index, len(match.group(1).expandtabs(4)))
        for index, line in enumerate(lines)
        if (
            match := re.match(
                r"^([ \t]*)(?:[-+*]|\d+[.)])[ \t]+\S",
                line,
            )
        )
    ]
    minimum_indent = min((indent for _index, indent in item_candidates), default=0)
    item_starts = {index for index, indent in item_candidates if indent == minimum_indent}
    outcomes = []
    index = 0
    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        start = index
        if index in item_starts:
            index += 1
            while index < len(lines):
                if index in item_starts:
                    break
                if not lines[index].strip():
                    following = index + 1
                    while following < len(lines) and not lines[following].strip():
                        following += 1
                    if following >= len(lines) or following in item_starts:
                        break
                    indent = len(lines[following]) - len(lines[following].lstrip())
                    if indent <= minimum_indent:
                        break
                index += 1
        else:
            index += 1
            while (
                index < len(lines)
                and lines[index].strip()
                and index not in item_starts
            ):
                index += 1
        outcome = "\n".join(lines[start:index]).strip()
        if outcome and not outcome.lower().startswith(("*guidance:", "_guidance:")):
            outcomes.append(outcome)
    return [
        {
            "identity": f"acceptance-{index:03d}",
            "sha256": "sha256:" + sha256(outcome.encode("utf-8")),
        }
        for index, outcome in enumerate(outcomes, start=1)
    ]


def accepted_record_path(design_path):
    return design_path.with_suffix(".accepted.json")


def load_accepted_design(project_root, supplied):
    """Read and validate the exact accepted source for Build or Verify entry."""

    context = local_docs_context(project_root)
    findings = local_docs_validation_findings(context, require_profile=True)
    failures = [item["message"] for item in findings if item["severity"] == "fail"]
    if failures:
        raise RuntimeError("Accepted design is unavailable: " + "; ".join(failures))
    _index_text, row, design_path = _indexed_design(context, supplied)
    sidecar = accepted_record_path(design_path)
    if sidecar.is_symlink() or not sidecar.is_file():
        raise RuntimeError(f"Accepted design record is unavailable: {sidecar}")
    try:
        record = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Accepted design record is invalid: {sidecar}") from exc
    design_keys = {
        "schemaVersion",
        "designId",
        "sourcePath",
        "sourceSha256",
        "acceptanceSha256",
        "acceptedAt",
    }
    if not isinstance(record, dict):
        raise RuntimeError(f"Accepted design record has an unsupported shape: {sidecar}")
    relative = str(design_path.relative_to(context["docsRoot"]))
    if record.get("schemaVersion") != "gauntlet.accepted-design.v1":
        raise RuntimeError(f"Accepted design record schema is unsupported: {sidecar}")
    if set(record) != design_keys:
        raise RuntimeError(
            f"Accepted design record has an unsupported shape: {sidecar}"
        )
    identity = record.get("designId")
    reference = relative
    indexed_status = row.group(4).strip()
    source_matches = record.get("sourcePath") == relative
    if identity != row.group(1) or not source_matches:
        raise RuntimeError("Accepted design record does not identify the indexed design.")
    if indexed_status != "Accepted":
        raise RuntimeError(f"Design {row.group(1)} is not accepted.")
    source_bytes = design_path.read_bytes()
    try:
        source_text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError("Accepted design source must be UTF-8.") from exc
    acceptance = exact_acceptance_section(source_text)
    if not acceptance:
        raise RuntimeError("Accepted design no longer has one exact Acceptance section.")
    current_source = sha256(source_bytes)
    current_acceptance = sha256(acceptance.encode("utf-8"))
    if record["sourceSha256"] != current_source:
        raise RuntimeError(
            "Accepted design source is stale: its bytes changed after acceptance."
        )
    if record["acceptanceSha256"] != current_acceptance:
        raise RuntimeError(
            "Accepted design Acceptance section is stale: its bytes changed after acceptance."
        )
    outcomes = acceptance_outcome_bindings(acceptance)
    if not outcomes:
        raise RuntimeError("Accepted design has no observable Acceptance outcomes.")
    return {
        "identity": identity,
        "reference": reference,
        "sha256": "sha256:" + record["sourceSha256"],
        "acceptanceSha256": "sha256:" + current_acceptance,
        "outcomes": outcomes,
        "contractApplicability": {
            "architecture": _optional_contract_binding(
                source_text,
                "Architecture Contract",
            ),
        },
    }


def command_docs_design_accept(args):
    context = local_docs_context(args.project_root)
    findings = local_docs_validation_findings(context, require_profile=True)
    if any(finding["severity"] == "fail" for finding in findings):
        return local_docs_payload(args, context, findings, dryRun=args.dry_run)

    index_text, row, design_path = _indexed_design(context, args.design)
    source_bytes = design_path.read_bytes()
    source_text = source_bytes.decode("utf-8")
    acceptance = exact_acceptance_section(source_text)
    if not acceptance:
        findings.append(
            {
                "code": "missing_exact_acceptance",
                "severity": "fail",
                "message": (
                    "Add one answered exact '## Acceptance' section before accepting "
                    "this design; Gauntlet will not invent or broaden it."
                ),
            }
        )
        return local_docs_payload(
            args,
            context,
            findings,
            designId=row.group(1),
            designPath=str(design_path),
            dryRun=args.dry_run,
        )
    sidecar = accepted_record_path(design_path)
    if sidecar.is_symlink() or (sidecar.exists() and not sidecar.is_file()):
        findings.append(
            {
                "code": "invalid_accepted_record",
                "severity": "fail",
                "message": f"Acceptance record must be a regular file: {sidecar}",
            }
        )
        return local_docs_payload(
            args,
            context,
            findings,
            designId=row.group(1),
            designPath=str(design_path),
            acceptedRecord=str(sidecar),
            dryRun=args.dry_run,
        )
    current_status = row.group(4).strip()
    if current_status not in {"Proposed", "Accepted"}:
        findings.append(
            {
                "code": "design_not_acceptable",
                "severity": "fail",
                "message": (
                    f"Design {row.group(1)} must be Proposed or Accepted before "
                    "binding its current bytes."
                ),
            }
        )
        return local_docs_payload(args, context, findings, dryRun=args.dry_run)

    record = {
        "schemaVersion": "gauntlet.accepted-design.v1",
        "designId": row.group(1),
        "sourcePath": str(design_path.relative_to(context["docsRoot"])),
        "sourceSha256": sha256(source_bytes),
        "acceptanceSha256": sha256(acceptance.encode("utf-8")),
        "acceptedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    updated_index = index_text
    if current_status == "Proposed":
        updated_index = (
            index_text[: row.start()]
            + row.group(0).replace("| Proposed |", "| Accepted |", 1)
            + index_text[row.end() :]
        )
    previous_record = sidecar.read_text(encoding="utf-8") if sidecar.is_file() else None
    if not args.dry_run:
        try:
            serialized = json.dumps(record, indent=2, sort_keys=True) + "\n"
            if previous_record is None:
                write_new_file(sidecar, serialized)
            else:
                _atomic_write_text(sidecar, serialized)
            if updated_index != index_text:
                _atomic_write_text(context["indexPath"], updated_index)
        except Exception:
            if previous_record is not None:
                _atomic_write_text(sidecar, previous_record)
            elif sidecar.is_file() and not sidecar.is_symlink():
                sidecar.unlink()
            if context["indexPath"].read_text(encoding="utf-8") != index_text:
                _atomic_write_text(context["indexPath"], index_text)
            raise
    return local_docs_payload(
        args,
        context,
        findings,
        designId=row.group(1),
        designPath=str(design_path),
        acceptedRecord=str(sidecar),
        sourceSha256=record["sourceSha256"],
        acceptanceSha256=record["acceptanceSha256"],
        reaccepted=previous_record is not None,
        dryRun=args.dry_run,
    )
