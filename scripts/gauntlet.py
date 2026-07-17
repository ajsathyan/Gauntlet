#!/usr/bin/env python3
"""Compatibility entrypoint for the modular Gauntlet CLI."""

from gauntletlib import cli as _cli


_cli.install_compatibility_exports(globals())


def main(argv=None):
    return _cli.main(argv, compatibility=globals())


if __name__ == "__main__":
    raise SystemExit(main())
