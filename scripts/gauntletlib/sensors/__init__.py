"""Adaptive code-quality sensor CLI commands."""

from pathlib import Path

from .evidence import command_normalize, command_validate_rewrite
from .planner import SENSOR_IDS, command_plan


def register(subparsers):
    sensors = subparsers.add_parser(
        "sensors",
        help="Plan and normalize deterministic code-quality evidence.",
    )
    commands = sensors.add_subparsers(dest="sensors_command", required=True)

    plan = commands.add_parser("plan")
    plan.add_argument("--project-root", type=Path, required=True)
    plan.add_argument(
        "--workflow-mode",
        choices=["scratch", "research", "patch", "feature", "release"],
        required=True,
    )
    plan.add_argument("--changed-path", action="append", default=[])
    plan.add_argument("--repo-command", action="append", default=[])
    plan.add_argument("--app-surface", action="store_true")
    plan.add_argument("--frontend-surface", action="store_true")
    plan.add_argument("--consequence", action="append", default=[])
    plan.add_argument("--durable-change", action="store_true")
    plan.add_argument("--architecture-change", action="store_true")
    plan.add_argument("--request-sensor", action="append", choices=SENSOR_IDS, default=[])
    plan.add_argument("--json", action="store_true")
    plan.set_defaults(func=command_plan)

    normalize = commands.add_parser("normalize")
    normalize.add_argument("--sensor", choices=SENSOR_IDS, required=True)
    normalize.add_argument(
        "--result",
        choices=["pass", "fail", "not-run", "unavailable"],
        required=True,
    )
    normalize.add_argument("--raw-evidence-ref", required=True)
    normalize.add_argument("--evidence-ref", action="append", default=[])
    normalize.add_argument("--command", default=None)
    normalize.add_argument("--summary", default=None)
    normalize.add_argument("--json", action="store_true")
    normalize.set_defaults(func=command_normalize)

    rewrite = commands.add_parser("validate-rewrite")
    rewrite.add_argument("--input", type=Path, required=True)
    rewrite.add_argument("--json", action="store_true")
    rewrite.set_defaults(func=command_validate_rewrite)

