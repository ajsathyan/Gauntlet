"""Public CLI facade."""

from gauntletlib.cli_application import build_parser, main
from gauntletlib.cli_support import EXIT_CODES, dispatch, print_json_or_brief

__all__ = ["EXIT_CODES", "build_parser", "dispatch", "main", "print_json_or_brief"]
