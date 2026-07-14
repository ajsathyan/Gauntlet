#!/usr/bin/env python3
"""Measure physical LOC with explicit, reproducible category rules.

"nonblankLines" is the canonical LOC measure. Exit codes: 0 success/comparable,
1 incomparable measurements, 2 invalid input or runtime error.
"""

import argparse
import fnmatch
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SCHEMA_VERSION = 1
CATEGORIES = ("production", "test", "generated", "config", "fixture", "migration")
DEFAULT_RULES: Dict[str, Any] = {
    "extensions": [
        ".c", ".cc", ".clj", ".cljs", ".cpp", ".cs", ".css", ".dart", ".ex", ".exs",
        ".go", ".graphql", ".h", ".hpp", ".html", ".java", ".js", ".jsx", ".json", ".kt",
        ".kts", ".lua", ".mdx", ".mjs", ".php", ".proto", ".py", ".rb", ".rs", ".scala",
        ".scss", ".sh", ".sql", ".svelte", ".swift", ".toml", ".ts", ".tsx", ".vue", ".yaml",
        ".yml", ".zig",
    ],
    "include": ["**"],
    "exclude": [
        ".git/**", "**/.git/**", ".hg/**", "**/.hg/**", ".svn/**", "**/.svn/**",
        "node_modules/**", "**/node_modules/**", "vendor/**", "**/vendor/**",
        ".venv/**", "**/.venv/**", "venv/**", "**/venv/**", "__pycache__/**", "**/__pycache__/**",
    ],
    "categoryOrder": ["generated", "fixture", "migration", "test", "config", "production"],
    "categories": {
        "generated": [
            "generated/**", "**/generated/**", "dist/**", "**/dist/**", "build/**", "**/build/**",
            "coverage/**", "**/coverage/**", "*.generated.*", "**/*.generated.*", "*.gen.*", "**/*.gen.*",
        ],
        "fixture": [
            "fixtures/**", "**/fixtures/**", "fixture/**", "**/fixture/**", "testdata/**", "**/testdata/**",
            "__snapshots__/**", "**/__snapshots__/**", "*.snap", "**/*.snap",
        ],
        "migration": ["migrations/**", "**/migrations/**", "migration/**", "**/migration/**"],
        "test": [
            "test/**", "**/test/**", "tests/**", "**/tests/**", "spec/**", "**/spec/**",
            "*_test.*", "**/*_test.*", "test_*.*", "**/test_*.*", "*.test.*", "**/*.test.*",
            "*.spec.*", "**/*.spec.*",
        ],
        "config": [
            "package.json", "tsconfig*.json", "*.config.*", "**/*.config.*", ".eslintrc*", "**/.eslintrc*",
            "pyproject.toml", "Cargo.toml", "go.mod", "Gemfile", "Dockerfile", "docker-compose*.yml",
            "docker-compose*.yaml",
        ],
        "production": ["**"],
    },
}


class LocError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def emit(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))


def load_json(path: Path, code: str) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LocError(code, f"Could not read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LocError(code, f"Expected a JSON object in {path}")
    return value


def validate_rules(rules: Dict[str, Any]) -> Dict[str, Any]:
    required = {"extensions", "include", "exclude", "categoryOrder", "categories"}
    if set(rules) != required:
        raise LocError("invalid-rules", f"Rules must contain exactly: {', '.join(sorted(required))}")
    for key in ("extensions", "include", "exclude", "categoryOrder"):
        if not isinstance(rules[key], list) or not all(isinstance(item, str) and item for item in rules[key]):
            raise LocError("invalid-rules", f"rules.{key} must be a non-empty string array")
    if set(rules["categoryOrder"]) != set(CATEGORIES) or len(rules["categoryOrder"]) != len(CATEGORIES):
        raise LocError("invalid-rules", "categoryOrder must name each required category exactly once")
    categories = rules["categories"]
    if not isinstance(categories, dict) or set(categories) != set(CATEGORIES):
        raise LocError("invalid-rules", "categories must define production, test, generated, config, fixture, and migration")
    for category, patterns in categories.items():
        if not isinstance(patterns, list) or not all(isinstance(item, str) and item for item in patterns):
            raise LocError("invalid-rules", f"categories.{category} must be a non-empty string array")
    normalized = json.loads(canonical(rules))
    normalized["extensions"] = sorted(set(normalized["extensions"]))
    return normalized


def matches(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def classify(path: str, rules: Dict[str, Any]) -> Optional[str]:
    if not matches(path, rules["include"]) or matches(path, rules["exclude"]):
        return None
    has_measured_extension = Path(path).suffix.lower() in rules["extensions"]
    is_named_config = matches(path, rules["categories"]["config"])
    if not has_measured_extension and not is_named_config:
        return None
    for category in rules["categoryOrder"]:
        if matches(path, rules["categories"][category]):
            return category
    return None


def line_counts(path: Path) -> Tuple[int, int]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise LocError("file-read-failed", f"Could not read {path}: {exc}") from exc
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    return len(lines), sum(1 for line in lines if line.strip())


def measure(root: Path, rules: Dict[str, Any]) -> Dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise LocError("root-not-directory", f"Project root is not a directory: {root}")
    category_files: Dict[str, List[Dict[str, Any]]] = {category: [] for category in CATEGORIES}
    for path in sorted((item for item in root.rglob("*") if item.is_file() or item.is_symlink()), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        category = classify(relative, rules)
        if category is None or path.is_symlink():
            continue
        total, nonblank = line_counts(path)
        category_files[category].append({"path": relative, "totalLines": total, "nonblankLines": nonblank})

    summaries: Dict[str, Any] = {}
    for category in CATEGORIES:
        files = category_files[category]
        summaries[category] = {
            "files": len(files),
            "totalLines": sum(item["totalLines"] for item in files),
            "nonblankLines": sum(item["nonblankLines"] for item in files),
            "entries": files,
        }
    production_test = summaries["production"]["nonblankLines"] + summaries["test"]["nonblankLines"]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "root": str(root),
        "metric": "physical nonblank lines",
        "rulesHash": hashlib.sha256(canonical(rules).encode("utf-8")).hexdigest(),
        "rules": rules,
        "categories": summaries,
        "productionTestNonblankLines": production_test,
        "allMeasuredNonblankLines": sum(summaries[item]["nonblankLines"] for item in CATEGORIES),
    }


def write_output(path: Optional[Path], payload: Dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def command_measure(args: argparse.Namespace) -> int:
    rules = validate_rules(load_json(Path(args.rules), "invalid-rules") if args.rules else DEFAULT_RULES)
    payload = measure(Path(args.root), rules)
    write_output(Path(args.output) if args.output else None, payload)
    emit(payload)
    return 0


def command_compare(args: argparse.Namespace) -> int:
    baseline = load_json(Path(args.baseline), "invalid-measurement")
    current = load_json(Path(args.current), "invalid-measurement")
    for label, value in (("baseline", baseline), ("current", current)):
        if value.get("schemaVersion") != SCHEMA_VERSION or not isinstance(value.get("productionTestNonblankLines"), int):
            raise LocError("invalid-measurement", f"{label} is not a schemaVersion {SCHEMA_VERSION} LOC measurement")
    comparable = baseline.get("rulesHash") == current.get("rulesHash") and baseline.get("metric") == current.get("metric")
    report: Dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "comparable": comparable,
        "baselineRulesHash": baseline.get("rulesHash"),
        "currentRulesHash": current.get("rulesHash"),
        "metric": baseline.get("metric"),
    }
    if not comparable:
        report["reason"] = "LOC rules or metric differ; remeasure both trees with the same explicit rules."
        emit(report)
        return 1
    before = baseline["productionTestNonblankLines"]
    after = current["productionTestNonblankLines"]
    reduction = 0.0 if before == 0 and after == 0 else (None if before == 0 else round((before - after) / before * 100, 6))
    report.update({
        "baselineProductionTestNonblankLines": before,
        "currentProductionTestNonblankLines": after,
        "productionTestReductionPercent": reduction,
    })
    emit(report)
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Measure and compare physical nonblank LOC with explicit category rules.")
    subparsers = root.add_subparsers(dest="command", required=True)
    measure_parser = subparsers.add_parser("measure", help="Measure one project tree.")
    measure_parser.add_argument("root", help="Project root to measure.")
    measure_parser.add_argument("--rules", help="Optional JSON rule set; defaults are emitted in the result.")
    measure_parser.add_argument("--output", help="Optional JSON output file.")
    measure_parser.set_defaults(handler=command_measure)
    compare_parser = subparsers.add_parser("compare", help="Compare two saved measurements.")
    compare_parser.add_argument("baseline", help="Baseline measurement JSON.")
    compare_parser.add_argument("current", help="Current measurement JSON.")
    compare_parser.set_defaults(handler=command_compare)
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        return int(args.handler(args))
    except LocError as exc:
        emit({"error": {"code": exc.code, "message": str(exc)}})
        return 2
    except OSError as exc:
        emit({"error": {"code": "io-error", "message": str(exc)}})
        return 2


if __name__ == "__main__":
    sys.exit(main())
