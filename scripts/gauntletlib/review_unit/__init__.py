"""Review Unit support."""

from pathlib import Path

from .workflow import command_review_unit_execute
from .workflow import command_review_unit_plan
from .workflow import command_review_unit_prepare
from .workflow import configure as configure


def register(subparsers):
    review_unit = subparsers.add_parser(
        "review-unit",
        help=(
            "Prepare or execute a parent-owned review-unit PR into an "
            "Execution Run integration branch."
        ),
    )
    commands = review_unit.add_subparsers(
        dest="review_unit_command", required=True
    )
    for name, func in [
        ("prepare", command_review_unit_prepare),
        ("plan", command_review_unit_plan),
        ("execute", command_review_unit_execute),
    ]:
        command = commands.add_parser(name)
        command.add_argument(
            "--git-root", type=Path, default=Path.cwd()
        )
        command.add_argument("--run", type=Path, required=True)
        command.add_argument("--unit", required=True)
        if name == "prepare":
            command.add_argument("--body-output", type=Path, default=None)
        else:
            command.add_argument("--body", type=Path, default=None)
        command.add_argument("--json", action="store_true")
        command.set_defaults(func=func)
