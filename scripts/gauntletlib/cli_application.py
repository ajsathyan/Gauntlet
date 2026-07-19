"""Construction and wiring for the controller-free Gauntlet CLI."""

import json
from pathlib import Path

from gauntletlib.cli_registration import register_commands
from gauntletlib.cli_support import build_parser as build_cli_parser
from gauntletlib.cli_support import dispatch
from gauntletlib.closeout import (
    configure as configure_closeout,
    register_archive,
    register_changelog,
    register_closeout,
    register_followup,
)
from gauntletlib.diagram import command_find as command_diagram_find
from gauntletlib.diagram import register as register_diagram
from gauntletlib.docs import register as register_docs
from gauntletlib.install.verify import command_verify as command_install_verify
from gauntletlib.install.verify import register as register_install
from gauntletlib.land import configure as configure_land
from gauntletlib.land import register as register_land
from gauntletlib.merge import configure as configure_merge
from gauntletlib.merge import register as register_merge
from gauntletlib.sensors import register as register_sensors

try:
    from gauntletlib.workstreams import register as register_workstreams
except ImportError:
    register_workstreams = None


ROOT = Path(__file__).resolve().parents[2]


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
        if payload.get("status") in {"pass", "warn"}:
            return
        print()
    print(f"Gauntlet: {payload.get('status', 'unknown')}")
    for finding in payload.get("findings", []):
        print(
            f"- [{finding.get('severity', 'unknown')}] "
            f"{finding.get('code', 'finding')}: {finding.get('message', '')}"
        )
    for action in payload.get("archivePlan", {}).get("actions", []):
        print(f"- action: {action.get('type')}")


def _diagram_find(args):
    return command_diagram_find(args, root=ROOT)


def register(subcommands):
    configure_closeout(print_payload=print_payload)
    configure_land(print_payload=print_payload)
    configure_merge(print_payload=print_payload)
    register_commands(
        subcommands,
        register_archive=register_archive,
        register_land=register_land,
        register_merge=register_merge,
        register_closeout=register_closeout,
        register_install=register_install,
        register_docs=register_docs,
        register_followup=register_followup,
        register_changelog=register_changelog,
        register_sensors=register_sensors,
        register_diagram=register_diagram,
        register_workstreams=register_workstreams,
        command_install_verify=command_install_verify,
        command_diagram_find=_diagram_find,
    )


def build_parser():
    return build_cli_parser(register)


def main(argv=None, *, compatibility=None):
    del compatibility
    return dispatch(build_parser(), argv, error_printer=print_payload)


def install_compatibility_exports(namespace):
    """Keep the historical script entrypoint while exposing only the CLI facade."""

    namespace.update(
        {
            "build_parser": build_parser,
            "main": main,
            "print_payload": print_payload,
        }
    )


if __name__ == "__main__":
    raise SystemExit(main())
