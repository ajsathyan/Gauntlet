"""Controller-free local design-document commands."""

from pathlib import Path

from .lifecycle import accepted_record_path as accepted_record_path
from .lifecycle import acceptance_outcome_bindings as acceptance_outcome_bindings
from .lifecycle import command_docs_check
from .lifecycle import command_docs_design_accept
from .lifecycle import command_docs_design_create
from .lifecycle import command_docs_disable
from .lifecycle import command_docs_enable
from .lifecycle import command_docs_ensure
from .lifecycle import command_docs_init
from .lifecycle import configure as configure
from .lifecycle import exact_acceptance_section as exact_acceptance_section
from .lifecycle import load_accepted_design as load_accepted_design
from .lifecycle import valid_design_title as valid_design_title


def register(subparsers):
    docs = subparsers.add_parser(
        "docs",
        help="Manage private durable designs in the primary worktree.",
    )
    commands = docs.add_subparsers(dest="docs_command", required=True)

    init = commands.add_parser("init")
    init.add_argument("--project-root", type=Path, default=Path.cwd())
    init.add_argument("--prefix", required=True)
    init.add_argument("--dry-run", action="store_true")
    init.add_argument("--json", action="store_true")
    init.set_defaults(func=command_docs_init)

    ensure = commands.add_parser(
        "ensure",
        help="Materialize the default profile for a covered document action.",
    )
    ensure.add_argument("--project-root", type=Path, default=Path.cwd())
    ensure.add_argument("--prefix", default=None)
    ensure.add_argument("--dry-run", action="store_true")
    ensure.add_argument("--json", action="store_true")
    ensure.set_defaults(func=command_docs_ensure)

    disable = commands.add_parser(
        "disable",
        help="Opt this project out of the default local-document profile.",
    )
    disable.add_argument("--project-root", type=Path, default=Path.cwd())
    disable.add_argument("--json", action="store_true")
    disable.set_defaults(func=command_docs_disable)

    enable = commands.add_parser(
        "enable",
        help="Remove this project's local-document opt-out marker.",
    )
    enable.add_argument("--project-root", type=Path, default=Path.cwd())
    enable.add_argument("--json", action="store_true")
    enable.set_defaults(func=command_docs_enable)

    check = commands.add_parser("check")
    check.add_argument("--project-root", type=Path, default=Path.cwd())
    check.add_argument("--json", action="store_true")
    check.set_defaults(func=command_docs_check)

    design = commands.add_parser(
        "design",
        help="Create or accept one durable product design.",
    )
    design_commands = design.add_subparsers(
        dest="docs_design_command", required=True
    )
    create = design_commands.add_parser(
        "create",
        help="Create one durable guided design without an implementation plan.",
    )
    create.add_argument("--project-root", type=Path, default=Path.cwd())
    create.add_argument("--title", required=True)
    create.add_argument("--number", type=int, default=None)
    create.add_argument("--dry-run", action="store_true")
    create.add_argument("--json", action="store_true")
    create.set_defaults(func=command_docs_design_create)

    accept = design_commands.add_parser(
        "accept",
        help="Bind the exact design and its exact Acceptance section by digest.",
    )
    accept.add_argument("--project-root", type=Path, default=Path.cwd())
    accept.add_argument(
        "--design",
        required=True,
        help="Indexed design ID, local-docs-relative path, or absolute design path.",
    )
    accept.add_argument("--dry-run", action="store_true")
    accept.add_argument("--json", action="store_true")
    accept.set_defaults(func=command_docs_design_accept)
