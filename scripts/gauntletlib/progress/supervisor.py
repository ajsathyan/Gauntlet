"""Live Epic progress supervisor and dashboard lifecycle."""

import fcntl
import json
import os
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from gauntletlib.core.fsio import atomic_write_text
from gauntletlib.core.hashing import sha256
from gauntletlib.core.timefmt import utc_timestamp

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
PROGRESS_SOURCE_SCHEMA = "gauntlet/live-progress-source/v1"
PROGRESS_STATE_SCHEMA = "gauntlet.progress-dashboard-state/v1"
PROGRESS_HEALTH_SCHEMA = "gauntlet.progress-dashboard-health/v1"
PROGRESS_REFRESH_SECONDS = 2.5
PROGRESS_TERMINAL_GRACE_SECONDS = 10.0
_load_launch_set = None
_launch_projections = None
_run_prd_controller = None
_print_payload = None

def configure(*, load_launch_set, launch_projections, run_prd_controller, print_payload):
    global _load_launch_set, _launch_projections, _run_prd_controller, _print_payload
    _load_launch_set = load_launch_set
    _launch_projections = launch_projections
    _run_prd_controller = run_prd_controller
    _print_payload = print_payload

def sha256_bytes(value):
    return sha256(value)

def progress_paths(launch_path):
    launch_path = Path(launch_path).resolve()
    stem = launch_path.stem
    return {
        "source": launch_path.with_name(stem + ".progress-source.json"),
        "state": launch_path.with_name(stem + ".progress-dashboard.json"),
        "supervisorLock": launch_path.with_name(stem + ".progress-supervisor.lock"),
    }


def progress_placeholder_facts(epic_id, epic):
    observed_at = utc_timestamp()
    return {
        "schemaVersion": "gauntlet/epic-run-facts/v1",
        "epicId": epic_id,
        "epicTitle": epic["title"],
        "time": {
            "protocolVersion": None, "elapsedCoverage": "unavailable", "createdAt": None,
            "startedAt": None, "updatedAt": observed_at, "terminalAt": None,
        },
        "progress": None,
        "operations": [],
        "owners": [],
        "release": {
            "applicability": {
                stage: stage in epic["releaseStages"]
                for stage in ("merge", "deployment", "production-verification")
            },
        },
    }


def run_facts_for_progress(repo, run_path):
    output, error = _run_prd_controller(repo, ["run-facts", "--run", str(Path(run_path).resolve())])
    if error:
        return None
    try:
        facts = json.loads(output)
    except json.JSONDecodeError:
        return None
    return facts if facts.get("schemaVersion") == "gauntlet/epic-run-facts/v1" else None


def telemetry_for_progress(facts):
    owners = facts.get("owners") if isinstance(facts, dict) else None
    if not isinstance(owners, list) or not owners:
        return None
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix="gauntlet-progress-facts-", suffix=".json")
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(facts, handle, sort_keys=True)
        command = [
            sys.executable, str(SCRIPTS / "subagent-audit.py"), "summary",
            "--run-facts", temporary, "--json",
        ]
        result = subprocess.run(command, text=True, capture_output=True, timeout=2.0)
        if result.returncode != 0:
            return None
        telemetry = json.loads(result.stdout)
        return telemetry if telemetry.get("schemaVersion") == "gauntlet/run-telemetry-summary/v1" else None
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None
    finally:
        if temporary and Path(temporary).exists():
            Path(temporary).unlink()


def refresh_progress_source(launch_path, launch, repo):
    paths = progress_paths(launch_path)
    previous = {}
    if paths["source"].is_file():
        try:
            previous = json.loads(paths["source"].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}
    previous_runs = previous.get("runs") if isinstance(previous.get("runs"), dict) else {}
    previous_telemetry = previous.get("telemetry") if isinstance(previous.get("telemetry"), dict) else {}
    runs = {}
    telemetry = {}
    for epic_id in launch["targetEpicIds"]:
        epic = launch["epics"][epic_id]
        facts = run_facts_for_progress(repo, epic.get("runPath")) if epic.get("runPath") else None
        if facts is None:
            preserved = previous_runs.get(epic_id)
            if isinstance(preserved, dict) and epic.get("runPath"):
                runs[epic_id] = preserved
            else:
                runs[epic_id] = {"runId": epic_id, "facts": progress_placeholder_facts(epic_id, epic)}
            if epic_id in previous_telemetry:
                telemetry[epic_id] = previous_telemetry[epic_id]
            continue
        runs[epic_id] = {"runId": Path(epic["runPath"]).name, "facts": facts}
        summary = telemetry_for_progress(facts)
        if summary is not None:
            telemetry[epic_id] = summary
        elif epic_id in previous_telemetry:
            telemetry[epic_id] = previous_telemetry[epic_id]
    source = {
        "schemaVersion": PROGRESS_SOURCE_SCHEMA,
        "launch": {
            "coverageSha256": launch["coverageSha256"],
            "targetEpicIds": launch["targetEpicIds"],
            "epics": {
                epic_id: {
                    "status": launch["epics"][epic_id]["status"],
                    "blocker": launch["epics"][epic_id].get("blocker"),
                    "stopDisposition": launch["epics"][epic_id].get("stopDisposition"),
                }
                for epic_id in launch["targetEpicIds"]
            },
        },
        "runs": runs,
        "telemetry": telemetry,
    }
    atomic_write_text(paths["source"], json.dumps(source, indent=2, sort_keys=True) + "\n", mode=0o600)
    return paths["source"]


def progress_process_birth_sha(pid):
    result = subprocess.run(
        ["/bin/ps", "-o", "lstart=", "-p", str(pid)],
        text=True, capture_output=True, timeout=1.0,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return sha256_bytes(" ".join(result.stdout.split()).encode("utf-8"))


def read_progress_state(launch_path):
    state_path = progress_paths(launch_path)["state"]
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return state_path, None
    return state_path, state if isinstance(state, dict) else None


def progress_assets_sha():
    root = ROOT / "templates" / "progress-dashboard"
    parts = []
    for relative in ("assets/app.css", "assets/app.js", "index.html"):
        path = root / relative
        if not path.is_file():
            return None
        parts.append(relative.encode() + b"\0" + path.read_bytes())
    return sha256_bytes(b"\0".join(parts))


def authenticated_progress_state(launch_path):
    state_path, state = read_progress_state(launch_path)
    if not state or state.get("schemaVersion") != PROGRESS_STATE_SCHEMA:
        return state_path, None
    if state.get("status") == "stopped":
        return state_path, state
    if state.get("status") != "running" or not isinstance(state.get("pid"), int):
        return state_path, None
    capability = state.get("capability")
    origin = state.get("origin")
    if (
        not isinstance(capability, str)
        or not isinstance(origin, str)
        or not re.fullmatch(r"http://127\.0\.0\.1:\d{1,5}", origin)
        or state.get("processBirthSha256") != progress_process_birth_sha(state["pid"])
    ):
        return state_path, None
    request = urllib.request.Request(
        origin + "/healthz",
        headers={"Authorization": "Bearer " + capability},
        method="GET",
    )
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=1.0) as response:
            health = json.loads(response.read())
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return state_path, None
    if (
        health.get("schemaVersion") != PROGRESS_HEALTH_SCHEMA
        or health.get("processNonce") != state.get("processNonce")
        or health.get("executableSha256") != state.get("executableSha256")
        or health.get("launchId") != state.get("launchId")
    ):
        return state_path, None
    return state_path, state


def verified_progress_state(launch_path):
    state_path, state = authenticated_progress_state(launch_path)
    if not state or state.get("status") != "running":
        return state_path, state
    executable = SCRIPTS / "progress-dashboard.py"
    if (
        not executable.is_file()
        or state.get("executableSha256") != sha256_bytes(executable.read_bytes())
        or state.get("assetsSha256") != progress_assets_sha()
    ):
        return state_path, None
    return state_path, state


def progress_dashboard_status(launch_path):
    state_path, state = verified_progress_state(launch_path)
    if state and state.get("status") == "running":
        return {
            "status": "running", "stateFile": str(state_path), "pid": state["pid"],
            "launchId": state.get("launchId"), "sourceStatus": state.get("sourceStatus"),
        }
    if state and state.get("status") == "stopped":
        return {"status": "stopped", "stateFile": str(state_path), "launchId": state.get("launchId")}
    return {"status": "unavailable", "stateFile": str(state_path)}


def progress_launch_terminal(launch, projections):
    for epic_id in launch["targetEpicIds"]:
        epic = launch["epics"][epic_id]
        if epic["status"] in {"failed", "stopped"}:
            continue
        if (projections.get(epic_id) or {}).get("complete") is True:
            continue
        return False
    return True


def stop_progress_dashboard(launch_path):
    state_path, state = authenticated_progress_state(launch_path)
    if not state or state.get("status") != "running":
        return progress_dashboard_status(launch_path)
    status = {
        "status": "running", "stateFile": str(state_path), "pid": state["pid"],
        "launchId": state.get("launchId"), "sourceStatus": state.get("sourceStatus"),
    }
    try:
        os.kill(status["pid"], signal.SIGTERM)
    except (OSError, ProcessLookupError):
        return {**status, "status": "unavailable"}
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        _, current_state = read_progress_state(launch_path)
        if current_state and current_state.get("status") == "stopped":
            return {"status": "stopped", "stateFile": str(state_path), "launchId": current_state.get("launchId")}
        time.sleep(0.05)
    return {**status, "status": "unavailable"}


def start_progress_dashboard(launch_path, launch, repo):
    source = refresh_progress_source(launch_path, launch, repo)
    paths = progress_paths(launch_path)
    command = [
        sys.executable, str(SCRIPTS / "progress-dashboard.py"), "serve",
        "--source", str(source),
        "--assets", str(ROOT / "templates" / "progress-dashboard"),
        "--state-file", str(paths["state"]),
        "--host", "127.0.0.1", "--port", "0", "--stale-after", "300",
    ]
    subprocess.Popen(
        command, cwd=Path(repo).resolve(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True, close_fds=True,
    )
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        status = progress_dashboard_status(launch_path)
        if status["status"] == "running":
            return {**status, "started": True}
        time.sleep(0.05)
    return {"status": "unavailable", "stateFile": str(paths["state"]), "started": False}


def ensure_progress_supervisor(launch_path, launch, repo):
    _, owned = authenticated_progress_state(launch_path)
    if owned and owned.get("status") == "running" and verified_progress_state(launch_path)[1] is None:
        stop_progress_dashboard(launch_path)
    existing = progress_dashboard_status(launch_path)
    command = [
        sys.executable, str(Path(__file__).resolve()), "epic-tasks", "progress-supervise",
        "--git-root", str(Path(repo).resolve()), "--launch-set", str(Path(launch_path).resolve()),
        "--interval", str(PROGRESS_REFRESH_SECONDS),
    ]
    subprocess.Popen(
        command, cwd=Path(repo).resolve(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True, close_fds=True,
    )
    if existing["status"] == "running":
        # The detached contender exits immediately when a supervisor already owns
        # the launch lock, and takes ownership when the dashboard outlived it.
        return {**existing, "started": False}
    deadline = time.monotonic() + 4.0
    while time.monotonic() < deadline:
        status = progress_dashboard_status(launch_path)
        if status["status"] == "running":
            return {**status, "started": True}
        time.sleep(0.05)
    return {"status": "unavailable", "stateFile": str(progress_paths(launch_path)["state"]), "started": False}


def unavailable_progress_dashboard(launch_path, *, started=False):
    return {
        "status": "unavailable",
        "stateFile": str(progress_paths(launch_path)["state"]),
        "started": started,
    }


def safely_ensure_progress_supervisor(launch_path, launch, repo):
    try:
        return ensure_progress_supervisor(launch_path, launch, repo)
    except (OSError, ValueError, TypeError, subprocess.SubprocessError, json.JSONDecodeError, TimeoutError):
        return unavailable_progress_dashboard(launch_path)


def safely_stop_progress_dashboard(launch_path):
    try:
        return stop_progress_dashboard(launch_path)
    except (OSError, ValueError, TypeError, subprocess.SubprocessError, json.JSONDecodeError, TimeoutError):
        return unavailable_progress_dashboard(launch_path)


def safely_progress_dashboard_status(launch_path):
    try:
        return progress_dashboard_status(launch_path)
    except (OSError, ValueError, TypeError, subprocess.SubprocessError, json.JSONDecodeError, TimeoutError):
        return unavailable_progress_dashboard(launch_path)


def progress_browser_action(launch, epic_id, dashboard):
    if dashboard.get("status") != "running":
        return None
    action = {
        "type": "open_browser",
        "surface": "codex-in-app-browser",
        "stateFile": dashboard["stateFile"],
        "route": "/",
        "credentialTransport": "fragment-from-state-file",
        "reuseKey": "gauntlet-progress:" + launch["coverageSha256"][:24],
    }
    if len(launch["targetEpicIds"]) == 1:
        action["epicId"] = epic_id
    return action


def command_epic_tasks_progress_supervise(args):
    paths = progress_paths(args.launch_set)
    paths["supervisorLock"].parent.mkdir(parents=True, exist_ok=True)
    if not hasattr(os, "O_NOFOLLOW") and paths["supervisorLock"].is_symlink():
        return 0
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(paths["supervisorLock"], flags, 0o600)
    except OSError:
        return 0
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        return 0
    os.fchmod(descriptor, 0o600)
    lock = os.fdopen(descriptor, "a+")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        return 0
    stopped = False
    terminal_since = None

    def stop(signum, frame):
        nonlocal stopped
        stopped = True

    previous = {
        signal.SIGTERM: signal.signal(signal.SIGTERM, stop),
        signal.SIGINT: signal.signal(signal.SIGINT, stop),
    }
    try:
        while not stopped:
            cycle_started = time.monotonic()
            try:
                launch_path, launch = _load_launch_set(args.launch_set)
                refresh_progress_source(launch_path, launch, args.git_root)
                projections = _launch_projections(args.git_root, launch)
                if progress_launch_terminal(launch, projections):
                    terminal_since = terminal_since or time.monotonic()
                    if time.monotonic() - terminal_since >= PROGRESS_TERMINAL_GRACE_SECONDS:
                        stop_progress_dashboard(launch_path)
                        break
                else:
                    terminal_since = None
                if progress_dashboard_status(launch_path)["status"] != "running":
                    start_progress_dashboard(launch_path, launch, args.git_root)
            except (OSError, ValueError, json.JSONDecodeError):
                pass
            deadline = cycle_started + max(0.5, args.interval)
            while not stopped and time.monotonic() < deadline:
                time.sleep(min(0.1, deadline - time.monotonic()))
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()
    return 0


def command_epic_tasks_progress_stop(args):
    payload = {"schemaVersion": PROGRESS_STATE_SCHEMA, **safely_stop_progress_dashboard(args.launch_set)}
    _print_payload(payload, args.json)
    return 0
