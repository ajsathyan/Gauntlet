"""Shared construction and dispatch for the Gauntlet command-line entrypoint."""

import argparse
import json


EXIT_CODES = {"pass": 0, "warn": 0, "review": 2, "fail": 1}


def build_parser(register):
    parser = argparse.ArgumentParser(description="Gauntlet workflow helper CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    register(subparsers)
    return parser


def dispatch(parser, argv=None, error_printer=None):
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except RuntimeError as error:
        payload = {
            "schemaVersion": "1.0",
            "status": "fail",
            "findings": [{"code": "command_failed", "severity": "fail", "message": str(error)}],
        }
        if error_printer is None:
            if getattr(args, "json", False):
                print(json.dumps(payload, indent=2))
            else:
                print("Gauntlet: fail")
                print(f"- [fail] command_failed: {error}")
        else:
            error_printer(payload, getattr(args, "json", False))
        return 1


def print_json_or_brief(payload, as_json, brief):
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        print(brief)
