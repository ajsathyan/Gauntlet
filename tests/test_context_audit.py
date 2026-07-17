#!/usr/bin/env python3
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from tests.support import SCRIPTS


SCRIPT = SCRIPTS / "context-audit.py"
SPEC = importlib.util.spec_from_file_location("context_audit", SCRIPT)
context_audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(context_audit)


class ContextAuditTests(unittest.TestCase):
    def test_report_uses_real_surface_bytes_and_fixed_representative_fixtures(self):
        report = context_audit.build_report(context_audit.ROOT, context_audit.DEFAULT_FIXTURES, [])
        router = next(item for item in report["surfaces"] if item["path"] == "router/AGENTS.md")
        self.assertEqual(router["bytes"], (context_audit.ROOT / "router" / "AGENTS.md").stat().st_size)
        self.assertLess(report["modelVisibleBytes"], report["baselineModelVisibleBytes"])
        self.assertLess(report["modelVisibleDeltaBytes"], 0)
        agora = next(item for item in report["representativeLaunches"] if item["epicId"] == "AGORARUNPOD-014")
        self.assertEqual(agora["epicBytes"], 61897)
        self.assertEqual(agora["candidateTaskBytes"], 850)

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
