"""Local-document workflow support."""

from pathlib import Path

from .lifecycle import DOC_EXECUTION_BLOCK_BEGIN as DOC_EXECUTION_BLOCK_BEGIN
from .lifecycle import DOC_EXECUTION_BLOCK_END as DOC_EXECUTION_BLOCK_END
from .lifecycle import DOC_EXECUTION_LEGACY_HASHES as DOC_EXECUTION_LEGACY_HASHES
from .lifecycle import accepted_record_path as accepted_record_path
from .lifecycle import command_docs_check
from .lifecycle import command_docs_disable
from .lifecycle import command_docs_draft_create
from .lifecycle import command_docs_draft_promote
from .lifecycle import command_docs_enable
from .lifecycle import command_docs_ensure
from .lifecycle import command_docs_epic_accept
from .lifecycle import command_docs_epic_create
from .lifecycle import command_docs_init
from .lifecycle import configure as configure
from .lifecycle import ensure_doc_execution_contract as ensure_doc_execution_contract
from .lifecycle import migrate_doc_execution_contract as migrate_doc_execution_contract
from .lifecycle import valid_epic_title as valid_epic_title


def register(subparsers):
    docs = subparsers.add_parser(
        "docs",
        help="Manage the default-on canonical local product-document profile.",
    )
    docs_subcommands = docs.add_subparsers(dest="docs_command", required=True)
    docs_init = docs_subcommands.add_parser("init")
    docs_init.add_argument("--project-root", type=Path, default=Path.cwd())
    docs_init.add_argument("--epic-prefix", required=True)
    docs_init.add_argument("--dry-run", action="store_true")
    docs_init.add_argument("--json", action="store_true")
    docs_init.set_defaults(func=command_docs_init)
    docs_ensure = docs_subcommands.add_parser(
        "ensure",
        help="Materialize the default profile when a covered document task needs it.",
    )
    docs_ensure.add_argument("--project-root", type=Path, default=Path.cwd())
    docs_ensure.add_argument("--epic-prefix", default=None)
    docs_ensure.add_argument("--dry-run", action="store_true")
    docs_ensure.add_argument("--json", action="store_true")
    docs_ensure.set_defaults(func=command_docs_ensure)
    docs_disable = docs_subcommands.add_parser(
        "disable",
        help="Opt this project out of the default local-document profile.",
    )
    docs_disable.add_argument("--project-root", type=Path, default=Path.cwd())
    docs_disable.add_argument("--json", action="store_true")
    docs_disable.set_defaults(func=command_docs_disable)
    docs_enable = docs_subcommands.add_parser(
        "enable",
        help="Remove this project's local-document opt-out marker.",
    )
    docs_enable.add_argument("--project-root", type=Path, default=Path.cwd())
    docs_enable.add_argument("--json", action="store_true")
    docs_enable.set_defaults(func=command_docs_enable)
    docs_check = docs_subcommands.add_parser("check")
    docs_check.add_argument("--project-root", type=Path, default=Path.cwd())
    docs_check.add_argument("--json", action="store_true")
    docs_check.set_defaults(func=command_docs_check)
    docs_epic = docs_subcommands.add_parser("epic")
    docs_epic_subcommands = docs_epic.add_subparsers(
        dest="docs_epic_command", required=True
    )
    docs_epic_create = docs_epic_subcommands.add_parser("create")
    docs_epic_create.add_argument("--project-root", type=Path, default=Path.cwd())
    docs_epic_create.add_argument("--title", required=True)
    docs_epic_create.add_argument("--number", type=int, default=None)
    docs_epic_create.add_argument(
        "--prd",
        default=None,
        help="Append the new Epic to an existing PRD under local-docs/epics.",
    )
    docs_epic_create.add_argument("--json", action="store_true")
    docs_epic_create.set_defaults(func=command_docs_epic_create)
    docs_epic_accept = docs_epic_subcommands.add_parser(
        "accept",
        help=(
            "Bind the exact promoted document version for implementation without "
            "editing its product content."
        ),
    )
    docs_epic_accept.add_argument("--project-root", type=Path, default=Path.cwd())
    docs_epic_accept.add_argument("--epic", required=True)
    docs_epic_accept.add_argument(
        "--prd",
        required=True,
        help="Promoted PRD path below local-docs/epics.",
    )
    docs_epic_accept.add_argument("--depends-on", default="None")
    docs_epic_accept.add_argument("--release-stages", default="merge")
    docs_epic_accept.add_argument("--consequence-triggers", default="none")
    docs_epic_accept.add_argument("--dry-run", action="store_true")
    docs_epic_accept.add_argument("--json", action="store_true")
    docs_epic_accept.set_defaults(func=command_docs_epic_accept)
    docs_draft = docs_subcommands.add_parser(
        "draft",
        help="Create and explicitly promote user-owned product drafts.",
    )
    docs_draft_subcommands = docs_draft.add_subparsers(
        dest="docs_draft_command", required=True
    )
    docs_draft_create = docs_draft_subcommands.add_parser(
        "create",
        help="Create one guided, unanswered product draft.",
    )
    docs_draft_create.add_argument("--project-root", type=Path, default=Path.cwd())
    docs_draft_create.add_argument(
        "--template",
        choices=["founding-hypothesis", "peter-yang"],
        required=True,
    )
    docs_draft_create.add_argument(
        "--title",
        help=(
            "Feature title used to name Peter Yang PRD drafts; required with "
            "--template peter-yang."
        ),
    )
    docs_draft_create.add_argument("--dry-run", action="store_true")
    docs_draft_create.add_argument("--json", action="store_true")
    docs_draft_create.set_defaults(func=command_docs_draft_create)
    docs_draft_promote = docs_draft_subcommands.add_parser(
        "promote",
        help=(
            "Allocate an Epic and atomically move an existing draft into its "
            "canonical path."
        ),
    )
    docs_draft_promote.add_argument("--project-root", type=Path, default=Path.cwd())
    docs_draft_promote.add_argument(
        "--draft",
        required=True,
        help="Draft filename or path below local-docs/drafts.",
    )
    docs_draft_promote.add_argument("--title", required=True)
    docs_draft_promote.add_argument("--number", type=int, default=None)
    docs_draft_promote.add_argument("--dry-run", action="store_true")
    docs_draft_promote.add_argument("--json", action="store_true")
    docs_draft_promote.set_defaults(func=command_docs_draft_promote)
