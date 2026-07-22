"""Construction and wiring for the Gauntlet Lite CLI."""

from gauntletlib.cli_support import build_parser as build_cli_parser
from gauntletlib.cli_support import dispatch
from gauntletlib.install.verify import command_verify as command_install_verify
from gauntletlib.install.verify import register as register_install
from gauntletlib.land import configure as configure_land
from gauntletlib.land import register as register_land
from gauntletlib.merge import configure as configure_merge
from gauntletlib.merge import register as register_merge

def print_payload(payload, as_json):
    import json

    if as_json:
        print(json.dumps(payload, indent=2))
        return
    print(f"Gauntlet: {payload.get('status', 'unknown')}")
    for finding in payload.get("findings", []):
        print(
            f"- [{finding.get('severity', 'unknown')}] "
            f"{finding.get('code', 'finding')}: {finding.get('message', '')}"
        )


def register(subcommands):
    configure_land(print_payload=print_payload)
    configure_merge(print_payload=print_payload)
    register_install(subcommands, command=command_install_verify)
    register_merge(subcommands)
    register_land(subcommands)


def build_parser():
    return build_cli_parser(register)


def main(argv=None):
    return dispatch(build_parser(), argv, error_printer=print_payload)


if __name__ == "__main__":
    raise SystemExit(main())
