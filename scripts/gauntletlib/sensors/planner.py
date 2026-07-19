"""Deterministic planning for repository-owned code-quality commands."""

import json
from pathlib import Path


SENSOR_IDS = (
    "formatter",
    "type-checker",
    "linter",
    "focused-tests",
    "coverage",
    "complexity",
    "dead-code-dependency",
    "semgrep",
    "gitleaks",
    "browser",
    "accessibility",
    "dependency-cruiser",
    "jscpd",
    "mutation",
)
PROOF_PHASES = ("fast", "integrated")

BASELINE_IDS = frozenset(SENSOR_IDS[:5])
OPTIONAL_PACKAGES = {
    "dependency-cruiser": "dependency-cruiser",
    "jscpd": "jscpd",
}
LANGUAGE_BY_SUFFIX = {
    ".cjs": "javascript",
    ".css": "css",
    ".cts": "typescript",
    ".html": "html",
    ".htm": "html",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".mts": "typescript",
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
}
SUPPORTED_LANGUAGES = frozenset({"css", "html", "javascript", "python", "typescript"})


def _commands(values):
    commands = {}
    for value in values:
        sensor, separator, command = value.partition("=")
        sensor = sensor.strip()
        command = command.strip()
        if not separator or sensor not in SENSOR_IDS or not command:
            raise RuntimeError(
                "--repo-command must use a known sensor ID in the form ID=COMMAND"
            )
        if sensor in commands and commands[sensor] != command:
            raise RuntimeError(f"conflicting repository commands for sensor: {sensor}")
        commands[sensor] = command
    return commands


def _package_facts(project_root):
    package_path = project_root / "package.json"
    if not package_path.is_file():
        return False, frozenset(), None
    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return True, frozenset(), "package.json could not be read as JSON"
    if not isinstance(package, dict):
        return True, frozenset(), "package.json must contain a JSON object"
    declared = set()
    for field in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        values = package.get(field, {})
        if isinstance(values, dict):
            declared.update(str(name) for name in values)
    return True, frozenset(declared), None


def _language_facts(changed_paths):
    languages = {
        language
        for path in changed_paths
        if (language := LANGUAGE_BY_SUFFIX.get(Path(path).suffix.lower()))
    }
    unsupported_extensions = sorted(
        {
            Path(path).suffix.lower()
            for path in changed_paths
            if Path(path).suffix and Path(path).suffix.lower() not in LANGUAGE_BY_SUFFIX
        }
    )
    return sorted(languages), unsupported_extensions


def _relevant(sensor, args):
    if sensor in BASELINE_IDS:
        return True, "baseline evidence for a supported changed language"
    if sensor in {"complexity", "dead-code-dependency"}:
        return args.app_surface, "changed application logic"
    if sensor == "semgrep":
        return (
            args.architecture_change or bool(args.consequence),
            "architecture, data-flow, or consequential logic changed",
        )
    if sensor == "gitleaks":
        return args.durable_change, "durable repository content changed"
    if sensor in {"browser", "accessibility"}:
        return args.frontend_surface, "frontend behavior changed"
    if sensor == "mutation":
        return bool(args.consequence), "consequential logic changed"
    if sensor == "dependency-cruiser":
        return (
            args.durable_change and args.architecture_change,
            "a durable JavaScript or TypeScript architecture changed",
        )
    if sensor == "jscpd":
        return (
            args.durable_change and args.app_surface,
            "durable application logic changed",
        )
    raise AssertionError(f"unknown sensor: {sensor}")


def _entry(sensor, args, commands, languages, declared_packages, package_error):
    requested = sensor in set(args.request_sensor)
    supported = bool(set(languages) & SUPPORTED_LANGUAGES)
    relevant, trigger = _relevant(sensor, args)

    if args.workflow_mode == "scratch" and not requested:
        return {
            "id": sensor,
            "disposition": "skipped",
            "reason": "Scratch mode requires an explicit request-scoped sensor opt-in.",
        }
    if requested:
        relevant = True
        trigger = "explicitly requested for this Scratch or Gauntlet request"
    if not supported:
        return {
            "id": sensor,
            "disposition": "not-configured",
            "reason": (
                "Unsupported changed language or no supported changed source path; "
                "no command was invented."
            ),
        }
    if not relevant:
        return {
            "id": sensor,
            "disposition": "skipped",
            "reason": f"Not needed because this change does not include {trigger}.",
        }
    if sensor == "dependency-cruiser" and not (
        {"javascript", "typescript"} & set(languages)
    ):
        return {
            "id": sensor,
            "disposition": "skipped",
            "reason": (
                "dependency-cruiser applies only to changed JavaScript or TypeScript "
                "sources."
            ),
        }

    command = commands.get(sensor)
    if not command:
        return {
            "id": sensor,
            "disposition": "not-configured",
            "reason": f"Relevant for {trigger}, but no repository-owned command was supplied.",
        }

    package = OPTIONAL_PACKAGES.get(sensor)
    if package is not None:
        if package_error:
            return {
                "id": sensor,
                "disposition": "unavailable",
                "reason": f"{package_error}; optional tool availability cannot be confirmed.",
            }
        if package not in declared_packages:
            return {
                "id": sensor,
                "disposition": "not-configured",
                "reason": (
                    f"Relevant for {trigger}, but optional package {package} is not "
                    "declared by the repository."
                ),
            }

    return {
        "id": sensor,
        "disposition": "selected",
        "reason": f"Selected because {trigger} and the repository supplies this command.",
        "command": command,
    }


def command_plan(args):
    project_root = args.project_root.expanduser().resolve()
    if not project_root.is_dir():
        raise RuntimeError(f"project root is not a directory: {project_root}")

    changed_paths = sorted(set(args.changed_path))
    languages, unsupported_extensions = _language_facts(changed_paths)
    has_package, declared_packages, package_error = _package_facts(project_root)
    commands = _commands(args.repo_command)
    consequences = sorted(set(args.consequence))
    proof_phase = getattr(args, "phase", None) or "integrated"

    payload = {
        "schema": "gauntlet.sensor-plan/v1",
        "status": "pass",
        "workflowMode": args.workflow_mode,
        "projectRoot": str(project_root),
        "changedPaths": changed_paths,
        "facts": {
            "languages": languages,
            "unsupportedExtensions": unsupported_extensions,
            "hasPackageJson": has_package,
            "declaredOptionalTools": sorted(
                package
                for package in OPTIONAL_PACKAGES.values()
                if package in declared_packages
            ),
            "appSurface": bool(args.app_surface),
            "frontendSurface": bool(args.frontend_surface),
            "architectureChange": bool(args.architecture_change),
            "durableChange": bool(args.durable_change),
            "consequences": consequences,
            "proofPhase": proof_phase,
        },
        "sensors": [
            _entry(
                sensor,
                args,
                commands,
                languages,
                declared_packages,
                package_error,
            )
            for sensor in SENSOR_IDS
        ],
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        selected = [item["id"] for item in payload["sensors"] if item["disposition"] == "selected"]
        print("Selected sensors: " + (", ".join(selected) if selected else "none"))
    return 0
