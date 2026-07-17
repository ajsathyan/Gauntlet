#!/usr/bin/env python3
"""Read-only loopback server for the live Epic progress projection and static UI."""

from __future__ import annotations

import argparse
import copy
import fcntl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import signal
import stat
import subprocess
import sys
import threading
import time
from urllib.parse import unquote, urlsplit

from gauntletlib.core.fsio import atomic_write_private_json as atomic_private_json
from gauntletlib.core.hashing import sha256_bytes as sha_bytes
from gauntletlib.core.timefmt import utc_now_seconds as utc_now
from progress_projection import ProjectionError, build_projection


STATE_SCHEMA = "gauntlet.progress-dashboard-state/v1"
HEALTH_SCHEMA = "gauntlet.progress-dashboard-health/v1"
CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
    "img-src 'self' data:; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
STATIC_ROUTES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/assets/app.js": ("assets/app.js", "text/javascript; charset=utf-8"),
    "/assets/app.css": ("assets/app.css", "text/css; charset=utf-8"),
}
MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_CONCURRENT_REQUESTS = 16


class DashboardError(Exception):
    pass


def executable_digest() -> str:
    return sha_bytes(Path(__file__).read_bytes())


def process_birth_digest(pid: int) -> str:
    result = subprocess.run(
        ["/bin/ps", "-o", "lstart=", "-p", str(pid)],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise DashboardError("cannot establish process birth identity")
    return sha_bytes(" ".join(result.stdout.split()).encode())


def load_assets(root: Path) -> tuple[dict[str, tuple[bytes, str, str]], str]:
    parts = []
    loaded = {}
    for route, (relative, _) in sorted(STATIC_ROUTES.items()):
        if route == "/":
            continue
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise DashboardError("static asset escapes the configured asset root") from exc
        if not path.is_file():
            raise DashboardError(f"required static asset is missing: {relative}")
        body = path.read_bytes()
        parts.append(relative.encode() + b"\0" + body)
        loaded[route] = (body, STATIC_ROUTES[route][1], '"' + sha_bytes(body) + '"')
    loaded["/"] = loaded["/index.html"]
    return loaded, sha_bytes(b"\0".join(parts))


class ProjectionStore:
    """Keep the last valid allowlisted projection when a source refresh is malformed."""

    def __init__(self, source: Path, stale_after: int):
        self.source = source
        self.stale_after = stale_after
        self.last_source_sha: str | None = None
        self.last_valid: dict | None = None
        self.last_response: dict | None = None
        self.last_response_bytes: bytes | None = None
        self.last_etag: str | None = None
        self.last_refresh_monotonic = 0.0
        self.degraded = False
        self.lock = threading.Lock()

    @staticmethod
    def serialize(value: dict) -> tuple[bytes, str]:
        body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        return body, '"' + sha_bytes(body) + '"'

    def degraded_projection(self, now: str) -> dict:
        if self.last_valid is None:
            raise ProjectionError("no valid progress source is available")
        value = copy.deepcopy(self.last_valid)
        value["generatedAt"] = now
        for epic in value["epics"]:
            epic["freshness"].update({
                "coverage": "partial",
                "stale": True,
                "label": "Source refresh unavailable",
            })
            if epic["health"]["status"] != "needs_user":
                epic["health"] = {
                    "status": "recovering",
                    "reason": "source-refresh-invalid",
                    "actionRequired": False,
                }
                epic["presentation"]["state"] = "recovering"
            epic["eta"] = {
                "status": "unavailable",
                "likelyFinishAt": None,
                "remainingSeconds": None,
                "confidence": None,
                "estimatorVersion": "gauntlet-eta/v1",
                "label": "Cannot estimate yet",
                "detail": "The latest source refresh is invalid; showing last valid progress.",
                "reason": "source-refresh-invalid",
            }
            epic["presentation"]["transitionId"] = sha_bytes(
                (epic["presentation"]["transitionId"] + ":source-refresh-invalid").encode()
            )[:16]
            epic["details"]["recovery"] = [{"label": "Status", "value": "source-refresh-invalid"}]
        return value

    def refresh(self) -> tuple[bytes, str, bool]:
        with self.lock:
            now_monotonic = time.monotonic()
            try:
                if self.source.stat().st_size > MAX_SOURCE_BYTES:
                    raise ProjectionError("progress source exceeds the bounded input size")
                source_bytes = self.source.read_bytes()
                if len(source_bytes) > MAX_SOURCE_BYTES:
                    raise ProjectionError("progress source exceeds the bounded input size")
                source_sha = sha_bytes(source_bytes)
                should_rebuild = (
                    source_sha != self.last_source_sha
                    or now_monotonic - self.last_refresh_monotonic >= 5.0
                    or self.last_response is None
                )
                if should_rebuild:
                    source = json.loads(source_bytes)
                    projection = build_projection(source, stale_after=self.stale_after)
                    self.last_source_sha = source_sha
                    self.last_valid = projection
                    self.last_response = projection
                    self.last_response_bytes, self.last_etag = self.serialize(projection)
                    self.last_refresh_monotonic = now_monotonic
                    self.degraded = False
                return self.last_response_bytes, self.last_etag, self.degraded
            except (OSError, json.JSONDecodeError, ProjectionError, TypeError, ValueError):
                if self.last_valid is None:
                    raise ProjectionError("no valid progress source is available")
                if not self.degraded:
                    projection = self.degraded_projection(utc_now())
                    self.last_response = projection
                    self.last_response_bytes, self.last_etag = self.serialize(projection)
                    self.last_refresh_monotonic = now_monotonic
                    self.degraded = True
                return self.last_response_bytes, self.last_etag, True


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    request_queue_size = MAX_CONCURRENT_REQUESTS

    def server_activate(self) -> None:
        self.request_slots = threading.BoundedSemaphore(MAX_CONCURRENT_REQUESTS)
        super().server_activate()

    def process_request(self, request, client_address) -> None:
        if not self.request_slots.acquire(blocking=False):
            request.close()
            return
        super().process_request(request, client_address)

    def process_request_thread(self, request, client_address) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.request_slots.release()


class Handler(BaseHTTPRequestHandler):
    server_version = "GauntletProgress/1"
    sys_version = ""

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - required BaseHTTPRequestHandler API
        return

    def common_headers(self, content_type: str, content_length: int, etag: str | None = None) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(content_length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        if etag:
            self.send_header("ETag", etag)

    def fixed_error(self, status: int) -> None:
        body = json.dumps({"error": "request-rejected", "status": status}, separators=(",", ":")).encode() + b"\n"
        self.send_response(status)
        self.common_headers("application/json; charset=utf-8", len(body))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def validated_path(self) -> str | None:
        try:
            parsed = urlsplit(self.path)
            decoded = unquote(parsed.path, errors="strict")
        except (UnicodeDecodeError, ValueError):
            self.fixed_error(400)
            return None
        if (
            "\x00" in decoded
            or ".." in decoded.split("/")
            or "\\" in decoded
            or decoded.startswith("//")
            or "%2f" in parsed.path.lower()
            or "%5c" in parsed.path.lower()
            or "%2e" in parsed.path.lower()
        ):
            self.fixed_error(400)
            return None
        return decoded

    def request_guard(self) -> bool:
        if self.headers.get("Host") != self.server.authority:
            self.fixed_error(421)
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin != self.server.origin:
            self.fixed_error(403)
            return False
        return True

    def authorized(self) -> bool:
        value = self.headers.get("Authorization", "")
        expected = "Bearer " + self.server.capability
        return secrets.compare_digest(value, expected)

    def send_bytes(self, body: bytes, content_type: str, etag: str) -> None:
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.common_headers(content_type, 0, etag)
            self.end_headers()
            return
        self.send_response(200)
        self.common_headers(content_type, len(body), etag)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def serve_static(self, path: str) -> None:
        body, content_type, etag = self.server.static_assets[path]
        self.send_bytes(body, content_type, etag)

    def serve_progress(self) -> None:
        if not self.authorized():
            self.fixed_error(401)
            return
        try:
            body, etag, degraded = self.server.store.refresh()
        except ProjectionError:
            self.fixed_error(503)
            return
        self.server.source_status = "stale" if degraded else "valid"
        self.send_bytes(body, "application/json; charset=utf-8", etag)

    def serve_health(self) -> None:
        if not self.authorized():
            self.fixed_error(401)
            return
        body = json.dumps({
            "schemaVersion": HEALTH_SCHEMA,
            "status": "running",
            "launchId": self.server.launch_id,
            "sourceStatus": self.server.source_status,
            "processNonce": self.server.process_nonce,
            "executableSha256": self.server.executable_sha256,
        }, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        self.send_bytes(body, "application/json; charset=utf-8", '"' + sha_bytes(body) + '"')

    def handle_read(self) -> None:
        if not self.request_guard():
            return
        path = self.validated_path()
        if path is None:
            return
        if path in STATIC_ROUTES:
            self.serve_static(path)
        elif path == "/api/progress":
            self.serve_progress()
        elif path == "/healthz":
            self.serve_health()
        else:
            self.fixed_error(404)

    def do_GET(self) -> None:
        self.handle_read()

    def do_HEAD(self) -> None:
        self.handle_read()

    def method_not_allowed(self) -> None:
        if not self.request_guard():
            return
        self.send_response(405)
        self.send_header("Allow", "GET, HEAD")
        self.common_headers("application/json; charset=utf-8", 0)
        self.end_headers()

    do_POST = method_not_allowed
    do_PUT = method_not_allowed
    do_PATCH = method_not_allowed
    do_DELETE = method_not_allowed
    do_OPTIONS = method_not_allowed


def lock_state(path: Path):
    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if not hasattr(os, "O_NOFOLLOW") and lock_path.is_symlink():
        raise DashboardError("dashboard state lock is unsafe")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise DashboardError("dashboard state lock is unsafe") from exc
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise DashboardError("dashboard state lock must be a regular file")
    os.fchmod(descriptor, 0o600)
    handle = os.fdopen(descriptor, "a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        handle.close()
        raise DashboardError("dashboard state is already owned by a running process") from exc
    return handle


def serve(args: argparse.Namespace) -> int:
    if args.host != "127.0.0.1":
        raise DashboardError("dashboard host must be exactly 127.0.0.1")
    if args.port < 0 or args.port > 65535:
        raise DashboardError("dashboard port must be between 0 and 65535")
    source = args.source.resolve()
    assets = args.assets.resolve()
    state_path = args.state_file.resolve()
    if not source.is_file():
        raise DashboardError("progress source does not exist")
    static_assets, assets_sha = load_assets(assets)
    state_lock = lock_state(state_path)
    capability = secrets.token_urlsafe(32)
    process_nonce = secrets.token_hex(16)
    store = ProjectionStore(source, args.stale_after)
    initial_launch_id = None
    source_status = "unavailable"
    try:
        body, _, degraded = store.refresh()
        initial_launch_id = json.loads(body)["launch"]["id"]
        source_status = "stale" if degraded else "valid"
    except ProjectionError:
        pass
    server = DashboardServer((args.host, args.port), Handler)
    port = server.server_address[1]
    authority = f"{args.host}:{port}"
    origin = f"http://{authority}"
    server.static_assets = static_assets
    server.authority = authority
    server.origin = origin
    server.capability = capability
    server.process_nonce = process_nonce
    server.executable_sha256 = executable_digest()
    server.launch_id = initial_launch_id
    server.source_status = source_status
    server.store = store
    started_at = utc_now()
    state = {
        "schemaVersion": STATE_SCHEMA,
        "status": "running",
        "pid": os.getpid(),
        "processNonce": process_nonce,
        "processBirthSha256": process_birth_digest(os.getpid()),
        "processStartedAt": started_at,
        "serverStartedAt": started_at,
        "terminalAt": None,
        "host": args.host,
        "port": port,
        "authority": authority,
        "origin": origin,
        "launchId": initial_launch_id,
        "sourceStatus": source_status,
        "capability": capability,
        "capabilitySha256": sha_bytes(capability.encode()),
        "executableSha256": server.executable_sha256,
        "assetsSha256": assets_sha,
    }
    atomic_private_json(state_path, state)

    stopping = threading.Event()

    def stop_handler(signum, frame) -> None:
        if stopping.is_set():
            return
        stopping.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    previous = {
        signal.SIGTERM: signal.signal(signal.SIGTERM, stop_handler),
        signal.SIGINT: signal.signal(signal.SIGINT, stop_handler),
    }
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()
        state.update({
            "status": "stopped",
            "terminalAt": utc_now(),
            "sourceStatus": server.source_status,
            "capability": None,
        })
        atomic_private_json(state_path, state)
        for signum, handler in previous.items():
            signal.signal(signum, handler)
        fcntl.flock(state_lock.fileno(), fcntl.LOCK_UN)
        state_lock.close()
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    serve_command = commands.add_parser("serve")
    serve_command.add_argument("--source", type=Path, required=True)
    serve_command.add_argument("--assets", type=Path, required=True)
    serve_command.add_argument("--state-file", type=Path, required=True)
    serve_command.add_argument("--host", default="127.0.0.1")
    serve_command.add_argument("--port", type=int, default=0)
    serve_command.add_argument("--stale-after", type=int, default=300)
    serve_command.set_defaults(func=serve)
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        return args.func(args)
    except DashboardError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
