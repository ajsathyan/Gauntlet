#!/usr/bin/env python3
"""Black-box safety and recovery tests for the loopback progress dashboard."""

from __future__ import annotations

import http.client
import json
from pathlib import Path
import stat
import subprocess
import tempfile
import time
import unittest

from importlib.util import module_from_spec, spec_from_file_location


SCRIPT = Path(__file__).with_name("progress-dashboard.py")
PROJECTION_TEST = Path(__file__).with_name("test-progress-projection.py")
FIXTURE_SPEC = spec_from_file_location("projection_fixture", PROJECTION_TEST)
fixture_module = module_from_spec(FIXTURE_SPEC)
assert FIXTURE_SPEC.loader is not None
FIXTURE_SPEC.loader.exec_module(fixture_module)
ASSETS = SCRIPT.parents[1] / "templates" / "progress-dashboard"


class DashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source.json"
        self.source.write_text(json.dumps(fixture_module.source_fixture()))
        self.state = self.root / "dashboard-state.json"
        self.process: subprocess.Popen[str] | None = None
        self.start()

    def tearDown(self) -> None:
        self.stop()
        self.temporary.cleanup()

    def start(self) -> None:
        self.process = subprocess.Popen(
            [
                "python3", str(SCRIPT), "serve", "--source", str(self.source),
                "--assets", str(ASSETS), "--state-file", str(self.state),
                "--host", "127.0.0.1", "--port", "0", "--stale-after", "120",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        deadline = time.time() + 5
        while time.time() < deadline:
            if self.process.poll() is not None:
                out, err = self.process.communicate()
                self.fail(f"dashboard exited early: stdout={out!r} stderr={err!r}")
            if self.state.is_file():
                state = json.loads(self.state.read_text())
                if state.get("status") == "running":
                    self.server = state
                    return
            time.sleep(0.02)
        self.fail("dashboard did not publish running state")

    def stop(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        self.process.terminate()
        self.process.wait(timeout=5)
        self.process.communicate(timeout=1)
        state = json.loads(self.state.read_text())
        self.assertEqual("stopped", state["status"])
        self.assertIsNotNone(state["terminalAt"])

    def request(
        self,
        method: str,
        path: str,
        *,
        capability: bool = True,
        host: str | None = None,
        origin: str | None = None,
        extra: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        connection = http.client.HTTPConnection("127.0.0.1", self.server["port"], timeout=3)
        headers = {"Host": host or self.server["authority"]}
        if capability:
            headers["Authorization"] = "Bearer " + self.server["capability"]
        if origin is not None:
            headers["Origin"] = origin
        headers.update(extra or {})
        connection.request(method, path, headers=headers)
        response = connection.getresponse()
        body = response.read()
        result = response.status, {key.lower(): value for key, value in response.getheaders()}, body
        connection.close()
        return result

    def test_projection_requires_header_capability_and_supports_etag_head(self) -> None:
        unauthorized = self.request("GET", "/api/progress", capability=False)
        self.assertEqual(401, unauthorized[0])
        self.assertNotIn(self.server["capability"].encode(), unauthorized[2])

        status, headers, body = self.request("GET", "/api/progress")
        self.assertEqual(200, status)
        self.assertEqual("no-store", headers["cache-control"])
        self.assertEqual("nosniff", headers["x-content-type-options"])
        payload = json.loads(body)
        self.assertEqual("gauntlet/live-epic-progress/v1", payload["schema"])
        etag = headers["etag"]

        unchanged = self.request("GET", "/api/progress", extra={"If-None-Match": etag})
        self.assertEqual(304, unchanged[0])
        self.assertEqual(b"", unchanged[2])
        head = self.request("HEAD", "/api/progress")
        self.assertEqual(200, head[0])
        self.assertEqual(b"", head[2])

    def test_static_page_has_no_capability_and_state_secret_is_private(self) -> None:
        status, headers, body = self.request("GET", "/", capability=False)
        self.assertEqual(200, status)
        self.assertIn("default-src 'none'", headers["content-security-policy"])
        self.assertNotIn(self.server["capability"].encode(), body)
        self.assertNotIn(self.server["capability"], " ".join(self.process.args))
        self.assertEqual(0o600, stat.S_IMODE(self.state.stat().st_mode))
        self.assertNotIn("capability=", body.decode())

    def test_host_origin_method_path_and_query_capability_fail_closed(self) -> None:
        self.assertEqual(421, self.request("GET", "/api/progress", host="evil.example")[0])
        self.assertEqual(403, self.request("GET", "/api/progress", origin="https://evil.example")[0])
        self.assertEqual(405, self.request("POST", "/api/progress")[0])
        self.assertEqual(404, self.request("GET", "/unknown")[0])
        self.assertEqual(400, self.request("GET", "/assets/%2e%2e/index.html", capability=False)[0])
        self.assertEqual(401, self.request(
            "GET", "/api/progress?capability=" + self.server["capability"], capability=False,
        )[0])

    def test_malformed_refresh_retains_last_valid_stale_projection(self) -> None:
        good = json.loads(self.request("GET", "/api/progress")[2])
        self.source.write_text("{partial")
        status, _, body = self.request("GET", "/api/progress")
        self.assertEqual(200, status)
        degraded = json.loads(body)
        self.assertEqual(good["epics"][0]["identity"], degraded["epics"][0]["identity"])
        self.assertTrue(degraded["epics"][0]["freshness"]["stale"])
        self.assertEqual("recovering", degraded["epics"][0]["health"]["status"])
        self.assertEqual("recovering", degraded["epics"][0]["presentation"]["state"])

    def test_restart_replaces_process_identity_and_terminal_projection_remains_readable(self) -> None:
        first_pid = self.server["pid"]
        first_capability = self.server["capability"]
        self.stop()
        value = fixture_module.source_fixture()
        facts = value["runs"]["E1"]["facts"]
        for unit in facts["progress"]["units"]:
            unit["status"] = "pass"
        for operation in facts["operations"]:
            operation["status"] = "pass"
        facts["time"]["terminalAt"] = fixture_module.NOW
        self.source.write_text(json.dumps(value))
        self.start()
        self.assertNotEqual(first_pid, self.server["pid"])
        self.assertNotEqual(first_capability, self.server["capability"])
        payload = json.loads(self.request("GET", "/api/progress")[2])
        self.assertEqual("shipped", payload["epics"][0]["presentation"]["state"])


class DashboardLockTests(unittest.TestCase):
    def test_state_lock_rejects_symlinks_without_chmodding_the_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.json"
            source.write_text(json.dumps(fixture_module.source_fixture()))
            state = root / "state.json"
            target = root / "unmanaged.txt"
            target.write_text("keep")
            target.chmod(0o644)
            (root / "state.json.lock").symlink_to(target)
            result = subprocess.run([
                "python3", str(SCRIPT), "serve", "--source", str(source),
                "--assets", str(ASSETS), "--state-file", str(state),
                "--host", "127.0.0.1", "--port", "0",
            ], text=True, capture_output=True, timeout=5)
            self.assertNotEqual(0, result.returncode)
            self.assertEqual(0o644, stat.S_IMODE(target.stat().st_mode))


if __name__ == "__main__":
    unittest.main()
