#!/usr/bin/env python3
"""Measure physical LOC with explicit, reproducible category rules.

"nonblankLines" is the canonical LOC measure. Exit codes: 0 success/comparable,
1 incomparable measurements, 2 invalid input or runtime error.
"""

import argparse
import fnmatch
import hashlib
import json
import os
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
            "out/**", "**/out/**", "target/**", "**/target/**", ".next/**", "**/.next/**",
            ".nuxt/**", "**/.nuxt/**", ".svelte-kit/**", "**/.svelte-kit/**",
            ".turbo/**", "**/.turbo/**", ".vite/**", "**/.vite/**", ".cache/**", "**/.cache/**",
            ".gauntlet/**", "**/.gauntlet/**", "evals/results/**", "**/evals/results/**",
            "test-results/**", "**/test-results/**", "playwright-report/**", "**/playwright-report/**",
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
            "package.json", "**/package.json", "tsconfig*.json", "**/tsconfig*.json", "*.config.*", "**/*.config.*",
            ".eslintrc*", "**/.eslintrc*", "pyproject.toml", "**/pyproject.toml", "Cargo.toml", "**/Cargo.toml",
            "go.mod", "**/go.mod", "Gemfile", "**/Gemfile", "Dockerfile", "**/Dockerfile",
            "docker-compose*.yml", "**/docker-compose*.yml", "docker-compose*.yaml", "**/docker-compose*.yaml",
        ],
        "production": ["**"],
    },
}
HARD_IGNORED = (".git/**", "**/.git/**", ".hg/**", "**/.hg/**", ".svn/**", "**/.svn/**")


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


def content_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise LocError("file-read-failed", f"Could not read {path}: {exc}") from exc


def excluded_record(path: Path, relative: str, reason: str) -> Dict[str, Any]:
    if path.is_symlink():
        target = os.readlink(path)
        return {
            "path": relative,
            "kind": "symlink",
            "bytes": 0,
            "sha256": hashlib.sha256(target.encode("utf-8", errors="surrogateescape")).hexdigest(),
            "reason": reason,
        }
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise LocError("file-read-failed", f"Could not stat {path}: {exc}") from exc
    return {"path": relative, "kind": "file", "bytes": size, "sha256": content_sha256(path), "reason": reason}


def measure(root: Path, rules: Dict[str, Any], receipt_exclusions: Sequence[str] = ()) -> Dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise LocError("root-not-directory", f"Project root is not a directory: {root}")
    category_files: Dict[str, List[Dict[str, Any]]] = {category: [] for category in CATEGORIES}
    excluded_files: List[Dict[str, Any]] = []
    for path in sorted((item for item in root.rglob("*") if item.is_file() or item.is_symlink()), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        if relative in receipt_exclusions:
            continue
        category = classify(relative, rules)
        if matches(relative, HARD_IGNORED):
            continue
        if path.is_symlink():
            excluded_files.append(excluded_record(path, relative, "symlink"))
            continue
        if category is None:
            reason = "excluded-pattern" if matches(relative, rules["exclude"]) else "unmeasured-extension-or-include-rule"
            excluded_files.append(excluded_record(path, relative, reason))
            continue
        total, nonblank = line_counts(path)
        category_files[category].append({
            "path": relative,
            "totalLines": total,
            "nonblankLines": nonblank,
            "sha256": content_sha256(path),
        })

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
    tree_digest = hashlib.sha256(canonical(category_files).encode("utf-8")).hexdigest()
    excluded_digest = hashlib.sha256(canonical(excluded_files).encode("utf-8")).hexdigest()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "root": str(root),
        "metric": "physical nonblank lines",
        "rulesHash": hashlib.sha256(canonical(rules).encode("utf-8")).hexdigest(),
        "rules": rules,
        "receiptExclusions": sorted(set(receipt_exclusions)),
        "treeDigest": tree_digest,
        "excludedInventory": {
            "files": len(excluded_files),
            "bytes": sum(item["bytes"] for item in excluded_files),
            "digest": excluded_digest,
            "entries": excluded_files,
        },
        "categories": summaries,
        "productionTestNonblankLines": production_test,
        "allMeasuredNonblankLines": sum(summaries[item]["nonblankLines"] for item in CATEGORIES),
    }


def nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def validate_measurement(value: Dict[str, Any], label: str) -> Dict[str, Any]:
    if value.get("schemaVersion") != SCHEMA_VERSION or value.get("metric") != "physical nonblank lines":
        raise LocError("invalid-measurement", f"{label} is not a schemaVersion {SCHEMA_VERSION} LOC measurement")
    rules_value = value.get("rules")
    if not isinstance(rules_value, dict):
        raise LocError("invalid-measurement", f"{label}.rules must be an object")
    try:
        rules = validate_rules(rules_value)
    except LocError as exc:
        raise LocError("invalid-measurement", f"{label}.rules are invalid: {exc}") from exc
    expected_rules_hash = hashlib.sha256(canonical(rules).encode("utf-8")).hexdigest()
    if value.get("rulesHash") != expected_rules_hash:
        raise LocError("invalid-measurement", f"{label}.rulesHash does not match its embedded rules")
    categories = value.get("categories")
    if not isinstance(categories, dict) or set(categories) != set(CATEGORIES):
        raise LocError("invalid-measurement", f"{label}.categories must contain every required category exactly once")
    canonical_files: Dict[str, List[Dict[str, Any]]] = {}
    for category in CATEGORIES:
        summary = categories[category]
        if not isinstance(summary, dict) or set(summary) != {"files", "totalLines", "nonblankLines", "entries"}:
            raise LocError("invalid-measurement", f"{label}.categories.{category} has an invalid shape")
        entries = summary["entries"]
        if not isinstance(entries, list):
            raise LocError("invalid-measurement", f"{label}.categories.{category}.entries must be an array")
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"path", "totalLines", "nonblankLines", "sha256"}:
                raise LocError("invalid-measurement", f"{label} contains an invalid {category} entry")
            path = entry["path"]
            if not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts or path in seen:
                raise LocError("invalid-measurement", f"{label} contains an unsafe or duplicate {category} path")
            seen.add(path)
            if not nonnegative_int(entry["totalLines"]) or not nonnegative_int(entry["nonblankLines"]):
                raise LocError("invalid-measurement", f"{label} contains invalid line totals")
            if entry["nonblankLines"] > entry["totalLines"]:
                raise LocError("invalid-measurement", f"{label} contains nonblank lines greater than total lines")
            if not isinstance(entry["sha256"], str) or len(entry["sha256"]) != 64:
                raise LocError("invalid-measurement", f"{label} contains an invalid content hash")
        if entries != sorted(entries, key=lambda item: item["path"]):
            raise LocError("invalid-measurement", f"{label}.{category} entries must be path-sorted")
        expected = {
            "files": len(entries),
            "totalLines": sum(item["totalLines"] for item in entries),
            "nonblankLines": sum(item["nonblankLines"] for item in entries),
        }
        if any(not nonnegative_int(summary[field]) or summary[field] != expected[field] for field in expected):
            raise LocError("invalid-measurement", f"{label}.{category} summary does not match its entries")
        canonical_files[category] = entries
    production_test = categories["production"]["nonblankLines"] + categories["test"]["nonblankLines"]
    all_measured = sum(categories[item]["nonblankLines"] for item in CATEGORIES)
    if not nonnegative_int(value.get("productionTestNonblankLines")) or value["productionTestNonblankLines"] != production_test:
        raise LocError("invalid-measurement", f"{label}.productionTestNonblankLines is invalid")
    if not nonnegative_int(value.get("allMeasuredNonblankLines")) or value["allMeasuredNonblankLines"] != all_measured:
        raise LocError("invalid-measurement", f"{label}.allMeasuredNonblankLines is invalid")
    expected_tree_digest = hashlib.sha256(canonical(canonical_files).encode("utf-8")).hexdigest()
    if value.get("treeDigest") != expected_tree_digest:
        raise LocError("invalid-measurement", f"{label}.treeDigest does not match its entries")
    excluded = value.get("excludedInventory")
    if not isinstance(excluded, dict) or set(excluded) != {"files", "bytes", "digest", "entries"}:
        raise LocError("invalid-measurement", f"{label}.excludedInventory has an invalid shape")
    excluded_entries = excluded["entries"]
    if not isinstance(excluded_entries, list):
        raise LocError("invalid-measurement", f"{label}.excludedInventory.entries must be an array")
    for entry in excluded_entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "kind", "bytes", "sha256", "reason"}:
            raise LocError("invalid-measurement", f"{label} contains an invalid excluded entry")
        path = entry["path"]
        if not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts:
            raise LocError("invalid-measurement", f"{label} contains an unsafe excluded path")
        if not nonnegative_int(entry["bytes"]) or not isinstance(entry["sha256"], str) or len(entry["sha256"]) != 64:
            raise LocError("invalid-measurement", f"{label} contains invalid excluded metadata")
        if entry["kind"] not in {"file", "symlink"}:
            raise LocError("invalid-measurement", f"{label} contains an invalid excluded kind")
        if entry["reason"] not in {"excluded-pattern", "unmeasured-extension-or-include-rule", "symlink"}:
            raise LocError("invalid-measurement", f"{label} contains an invalid excluded reason")
    if excluded_entries != sorted(excluded_entries, key=lambda item: item["path"]):
        raise LocError("invalid-measurement", f"{label}.excludedInventory entries must be path-sorted")
    expected_excluded = {
        "files": len(excluded_entries),
        "bytes": sum(item["bytes"] for item in excluded_entries),
        "digest": hashlib.sha256(canonical(excluded_entries).encode("utf-8")).hexdigest(),
    }
    if any(excluded.get(field) != expected for field, expected in expected_excluded.items()):
        raise LocError("invalid-measurement", f"{label}.excludedInventory summary does not match its entries")
    root = value.get("root")
    if not isinstance(root, str) or not root:
        raise LocError("invalid-measurement", f"{label}.root must identify the measured tree")
    receipt_exclusions = value.get("receiptExclusions")
    if not isinstance(receipt_exclusions, list) or receipt_exclusions != sorted(set(receipt_exclusions)):
        raise LocError("invalid-measurement", f"{label}.receiptExclusions must be a sorted unique array")
    for path in receipt_exclusions:
        if not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts:
            raise LocError("invalid-measurement", f"{label} contains an unsafe receipt exclusion")
    return rules


def verify_live(value: Dict[str, Any], label: str, rules: Dict[str, Any]) -> None:
    live = measure(Path(value["root"]), rules, value["receiptExclusions"])
    if live["treeDigest"] != value["treeDigest"] or live["excludedInventory"]["digest"] != value["excludedInventory"]["digest"]:
        raise LocError("stale-measurement", f"{label} no longer matches the live tree at its recorded root")


def write_output(path: Optional[Path], payload: Dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def command_measure(args: argparse.Namespace) -> int:
    rules = validate_rules(load_json(Path(args.rules), "invalid-rules") if args.rules else DEFAULT_RULES)
    root = Path(args.root).resolve()
    receipt_exclusions: List[str] = []
    if args.output:
        try:
            receipt_exclusions.append(Path(args.output).resolve().relative_to(root).as_posix())
        except ValueError:
            pass
    payload = measure(root, rules, receipt_exclusions)
    write_output(Path(args.output) if args.output else None, payload)
    emit(payload)
    return 0


def command_compare(args: argparse.Namespace) -> int:
    baseline = load_json(Path(args.baseline), "invalid-measurement")
    current = load_json(Path(args.current), "invalid-measurement")
    baseline_rules = validate_measurement(baseline, "baseline")
    current_rules = validate_measurement(current, "current")
    if args.verify_live:
        verify_live(baseline, "baseline", baseline_rules)
        verify_live(current, "current", current_rules)
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
    category_deltas = {
        category: current["categories"][category]["nonblankLines"] - baseline["categories"][category]["nonblankLines"]
        for category in CATEGORIES
    }
    reduction_lines = max(0, before - after)
    displaced_lines = sum(max(0, category_deltas[item]) for item in ("generated", "config", "fixture", "migration"))
    excluded_changed = baseline["excludedInventory"]["digest"] != current["excludedInventory"]["digest"]
    changed_nonproduction = [
        category for category in ("generated", "config", "fixture", "migration")
        if baseline["categories"][category]["entries"] != current["categories"][category]["entries"]
    ]
    displaced = reduction_lines > 0 and (bool(changed_nonproduction) or excluded_changed)
    report.update({
        "categoryNonblankLineDeltas": category_deltas,
        "displacedComplexity": displaced,
        "displacedIntoNonProductionLines": displaced_lines,
        "excludedInventoryChanged": excluded_changed,
        "excludedFileDelta": current["excludedInventory"]["files"] - baseline["excludedInventory"]["files"],
        "excludedByteDelta": current["excludedInventory"]["bytes"] - baseline["excludedInventory"]["bytes"],
        "nonProductionContentChangedCategories": changed_nonproduction,
    })
    if displaced:
        report["reason"] = "Production/test LOC fell while excluded content changed or non-production categories grew; inspect and account for displaced complexity before certifying the reduction."
    emit(report)
    return 1 if displaced else 0


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
    compare_parser.add_argument("--verify-live", action="store_true", help="Also require each recorded root to exist and still match its receipt.")
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
