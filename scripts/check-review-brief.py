#!/usr/bin/env python3
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
TEMPLATES = ROOT / "templates"


def read_first_existing(paths):
    for path in paths:
        if path.exists():
            return path.read_text()
    raise AssertionError(f"missing expected file; checked: {', '.join(str(path) for path in paths)}")


def read_optional(path):
    return path.read_text() if path.exists() else ""


def run(args, cwd=None, check=True, env=None):
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    result = subprocess.run(
        args,
        cwd=cwd,
        env=merged_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"{args} failed with {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def extract_embedded_data(html_path):
    html = html_path.read_text()
    match = re.search(
        r'(<script\b[^>]*\bid=["\']review-brief-data["\'][^>]*>)(.*?)(</script>)',
        html,
        re.S,
    )
    if not match:
        raise AssertionError("review-brief.html is missing the embedded data script")
    raw = match.group(2).strip()
    if not raw:
        raise AssertionError("embedded review data is empty")
    return json.loads(raw)


def mutate_data(data_path):
    data = json.loads(data_path.read_text())
    data["brief"]["summary"] = "Updated summary for embedded snapshot check."
    data_path.write_text(json.dumps(data, indent=2) + "\n")
    return data


def stop_server(project):
    pid_file = project / ".gauntlet-review-server.pid"
    if not pid_file.exists():
        return
    try:
        pid = int(pid_file.read_text().strip())
    except ValueError:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    for _ in range(20):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)


def fetch_bytes(url):
    with urllib.request.urlopen(url, timeout=3) as response:
        if response.status != 200:
            raise AssertionError(f"{url} returned HTTP {response.status}")
        return response.read()


def test_init_embeds_and_refreshes_snapshot():
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        run([str(SCRIPTS / "init-review-brief.sh"), str(project)])

        embedded = extract_embedded_data(project / "review-brief.html")
        sidecar = json.loads((project / "review-brief-data.json").read_text())
        if embedded != sidecar:
            raise AssertionError("embedded snapshot does not match sidecar JSON after init")

        updated = mutate_data(project / "review-brief-data.json")
        run([str(SCRIPTS / "init-review-brief.sh"), str(project)])
        refreshed = extract_embedded_data(project / "review-brief.html")
        if refreshed != updated:
            raise AssertionError("embedded snapshot did not refresh after sidecar JSON changed")


def test_serve_rejects_invalid_data():
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        shutil.copy(TEMPLATES / "review-brief.html", project / "review-brief.html")
        (project / "review-brief-data.json").write_text('{"schemaVersion":"1.0"}\n')
        result = run([str(SCRIPTS / "serve-review-brief.sh"), str(project)], check=False)
        stop_server(project)
        if result.returncode == 0:
            raise AssertionError(f"serve-review-brief.sh accepted invalid data: {result.stdout}")
        if "review-brief-data invalid" not in result.stderr:
            raise AssertionError(f"invalid data failure was not explicit:\n{result.stderr}")


def test_refresh_template_option_updates_existing_shell():
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        run([str(SCRIPTS / "init-review-brief.sh"), str(project)])
        (project / "review-brief.html").write_text("<!doctype html><title>stale</title>\n")
        run(
            [str(SCRIPTS / "init-review-brief.sh"), str(project)],
            env={"GAUNTLET_REVIEW_REFRESH_TEMPLATE": "1"},
        )
        extract_embedded_data(project / "review-brief.html")


def test_start_prints_only_healthy_project_url():
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        env = {
            "GAUNTLET_REVIEW_PORT": "8910",
            "GAUNTLET_REVIEW_PORT_MAX": "8930",
        }
        result = run([str(SCRIPTS / "start-review-brief.sh"), str(project)], env=env)
        try:
            lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            if len(lines) != 1 or not lines[0].startswith("Review brief: http://"):
                raise AssertionError(f"unexpected start output:\n{result.stdout}")
            url = lines[0].split("Review brief: ", 1)[1]
            parsed = urllib.parse.urlparse(url)
            if parsed.path != "/review-brief.html":
                raise AssertionError(f"unexpected review brief path: {url}")
            pid = int((project / ".gauntlet-review-server.pid").read_text().strip())
            if hasattr(os, "getsid") and os.getsid(pid) == os.getsid(0):
                raise AssertionError("review brief server was not detached into its own session")

            time.sleep(1)
            html = fetch_bytes(url)
            data_url = urllib.parse.urlunparse(parsed._replace(path="/review-brief-data.json"))
            data = fetch_bytes(data_url)
            if html != (project / "review-brief.html").read_bytes():
                raise AssertionError("served HTML does not match the project review-brief.html")
            if data != (project / "review-brief-data.json").read_bytes():
                raise AssertionError("served JSON does not match the project review-brief-data.json")
            json.loads(data)
        finally:
            stop_server(project)


def test_no_legacy_fixed_review_port():
    offenders = []
    for path in SCRIPTS.glob("*.sh"):
        if path.name == "check-review-brief.sh":
            continue
        text = path.read_text()
        for fixed_port in ("4173", "8770"):
            if fixed_port in text:
                offenders.append(f"{path}:{fixed_port}")
    if offenders:
        raise AssertionError(f"fixed review port found in {offenders}")


def test_template_uses_embedded_only_for_file_protocol():
    html = (TEMPLATES / "review-brief.html").read_text()
    required = [
        "async function loadReviewData()",
        "window.location.protocol",
        "protocol === 'file:'",
        "return await loadSidecarData();",
        "const loaded = await loadReviewData();",
        "state.data = loaded.data;",
        "state.dataFingerprint = loaded.fingerprint;",
    ]
    for needle in required:
        if needle not in html:
            raise AssertionError(f"template is missing protocol-aware data loading marker: {needle}")


def test_template_polls_for_fresh_sidecar_data_without_reload():
    html = (TEMPLATES / "review-brief.html").read_text()
    required = [
        "function reviewDataFingerprint(",
        "function renderFreshnessBanner()",
        "async function pollForFreshReviewData()",
        "state.pendingFreshData",
        "state.ignoredFreshnessFingerprint",
        "window.setInterval(pollForFreshReviewData",
        "window.location.protocol === 'file:'",
        "New review data available",
        "Update view",
        "Waiting for valid review data update",
    ]
    for needle in required:
        if needle not in html:
            raise AssertionError(f"template is missing live freshness marker: {needle}")
    if "window.location.reload" in html or ".reload()" in html:
        raise AssertionError("freshness flow must update the view without a hard reload")


def test_require_review_brief_gate_opens_and_records_sentinel():
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "project"
        project.mkdir()
        opener_log = Path(tmp) / "opened-url.txt"
        opener = Path(tmp) / "open-review-url.sh"
        opener.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "printf '%s\\n' \"$1\" > \"$GAUNTLET_REVIEW_OPEN_LOG\"\n"
        )
        opener.chmod(0o755)
        env = {
            "GAUNTLET_REVIEW_OPEN": "default",
            "GAUNTLET_REVIEW_OPEN_COMMAND": str(opener),
            "GAUNTLET_REVIEW_OPEN_LOG": str(opener_log),
        }

        result = run([str(SCRIPTS / "require-review-brief-started.sh"), str(project)], env=env)
        try:
            lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            if len(lines) != 1 or not lines[0].startswith("Review brief: http://"):
                raise AssertionError(f"unexpected gate output:\n{result.stdout}")
            url = lines[0].split("Review brief: ", 1)[1]
            if opener_log.read_text().strip() != url:
                raise AssertionError("review brief gate did not invoke the configured opener")

            sentinel = json.loads((project / ".gauntlet-review-brief-started.json").read_text())
            if sentinel.get("url") != url:
                raise AssertionError("sentinel URL does not match the printed review brief URL")
            if sentinel.get("projectRoot") != str(project):
                raise AssertionError("sentinel project root does not match the requested project")
            if sentinel.get("openMode") != "default":
                raise AssertionError("sentinel did not record the browser open mode")
            pid = int(sentinel.get("serverPid", 0))
            if pid <= 0:
                raise AssertionError("sentinel did not record a server PID")
            if hasattr(os, "getsid") and os.getsid(pid) == os.getsid(0):
                raise AssertionError("review brief gate server was not detached into its own session")
            fetch_bytes(url)
        finally:
            stop_server(project)


def test_workflow_instructions_require_gate_command():
    agents = read_first_existing([ROOT / "AGENTS.md", ROOT.parent / "AGENTS.md"])
    skill = read_first_existing(
        [
            ROOT / "skills" / "review-brief-builder" / "SKILL.md",
            ROOT.parent / "skills" / "review-brief-builder" / "SKILL.md",
        ]
    )
    readme = read_optional(ROOT / "README.md")
    required = [
        'scripts/require-review-brief-started.sh "$PROJECT_ROOT"',
        "GAUNTLET_REVIEW_OPEN=chrome",
        "Feature and Release",
    ]
    combined = "\n".join([agents, skill, readme])
    for needle in required:
        if needle not in combined:
            raise AssertionError(f"workflow instructions are missing required gate marker: {needle}")
    if "review brief startup gate" not in combined.lower():
        raise AssertionError("workflow instructions are missing the review brief startup gate marker")
    if "For Patch and Deep Patch, do not start a review brief by default" in agents:
        raise AssertionError("workflow still tells agents not to start review briefs for all Deep Patch work")
    if "For Slice and Release work" in agents or "For Slice and Release work" in skill:
        raise AssertionError("workflow still refers to Slice as the review brief mode")


def main():
    tests = [
        test_init_embeds_and_refreshes_snapshot,
        test_serve_rejects_invalid_data,
        test_refresh_template_option_updates_existing_shell,
        test_start_prints_only_healthy_project_url,
        test_no_legacy_fixed_review_port,
        test_template_uses_embedded_only_for_file_protocol,
        test_template_polls_for_fresh_sidecar_data_without_reload,
        test_require_review_brief_gate_opens_and_records_sentinel,
        test_workflow_instructions_require_gate_command,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        print(f"FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
