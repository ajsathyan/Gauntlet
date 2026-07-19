#!/usr/bin/env python3
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from support import SCRIPTS


SCRIPT = SCRIPTS / "context-audit.py"
SPEC = importlib.util.spec_from_file_location("context_audit", SCRIPT)
context_audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(context_audit)


class ContextAuditTests(unittest.TestCase):
    def test_report_measures_design_build_verify_without_controller_telemetry(self):
        report = context_audit.build_report(context_audit.ROOT, [])
        router = report["stableSurfaces"][0]
        self.assertEqual(router["path"], "router/AGENTS.md")
        self.assertEqual(
            router["bytes"],
            (context_audit.ROOT / "router" / "AGENTS.md").stat().st_size,
        )
        self.assertEqual(
            [phase["phase"] for phase in report["phases"]],
            ["design", "build", "verify"],
        )
        self.assertEqual(
            report["stablePrefixSavingsBytes"],
            report["stableBytes"] * 2,
        )
        self.assertEqual(
            report["repeatedWithoutStablePrefixBytes"]
            - report["stablePrefixSavingsBytes"],
            report["uniqueBytes"],
        )
        serialized = json.dumps(report).lower()
        for obsolete in ("epicid", "controller", "launch", "ticket graph"):
            self.assertNotIn(obsolete, serialized)

    def test_trace_reader_ignores_non_token_events(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace = Path(temporary) / "trace.jsonl"
            trace.write_text("\n".join([
                json.dumps({"type": "message", "input_tokens": 999}),
                json.dumps({"type": "token_count", "usage": {"input_tokens": 20, "cached_input_tokens": 5, "output_tokens": 3}}),
                "not-json",
            ]) + "\n", encoding="utf-8")
            self.assertEqual(context_audit.trace_tokens(trace), {
                "input": 20,
                "cachedInput": 5,
                "output": 3,
                "events": 1,
            })


if __name__ == "__main__":
    unittest.main()
