"""Public CLI facade with lazy application loading."""

from gauntletlib.cli_support import EXIT_CODES as EXIT_CODES
from gauntletlib.cli_support import build_parser as build_parser
from gauntletlib.cli_support import dispatch as dispatch
from gauntletlib.cli_support import print_json_or_brief as print_json_or_brief


def _application():
    from gauntletlib import cli_application

    return cli_application


def main(argv=None, *, compatibility=None):
    return _application().main(argv, compatibility=compatibility)


def install_compatibility_exports(namespace):
    return _application().install_compatibility_exports(namespace)


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    return getattr(_application(), name)
