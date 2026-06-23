#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKILLS = ROOT / "skills" if (ROOT / "skills").exists() else ROOT.parent / "skills"


def read_text(path):
    return path.read_text(encoding="utf-8")


def word_count(text):
    return len(re.findall(r"\b\S+\b", text))


def parse_frontmatter(text, path):
    if not text.startswith("---\n"):
        raise ValueError(f"{path} missing YAML frontmatter")
    end = text.find("\n---", 4)
    if end == -1:
        raise ValueError(f"{path} has unterminated YAML frontmatter")
    raw = text[4:end].strip()
    data = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data, text[end + 4 :]


def lint_skill(path, max_words):
    text = read_text(path)
    frontmatter, body = parse_frontmatter(text, path)
    name = frontmatter.get("name", path.parent.name)
    description = frontmatter.get("description", "")
    examples = sorted(str(p.relative_to(path.parent)) for p in (path.parent / "examples").glob("*.md"))
    failures = []
    warnings = []

    if not re.fullmatch(r"[a-z0-9-]+", name):
        failures.append("frontmatter name must use lowercase letters, numbers, and hyphens")
    if not description.startswith("Use when"):
        failures.append("description must start with 'Use when'")
    if len("\n".join(f"{k}: {v}" for k, v in frontmatter.items())) > 1024:
        failures.append("frontmatter exceeds 1024 characters")

    words = word_count(text)
    if words > max_words:
        failures.append(f"word count {words} exceeds budget {max_words}")

    if "Cannot verify" not in body:
        failures.append("missing Cannot verify slot")
    if not any(marker in body for marker in ["Output Contract", "Intake Packet", "Product Packet", "Gauntlet Task Packet", "Ready Item", "Implementation Packet"]):
        failures.append("missing explicit packet or output contract")
    if "Not relevant because" not in body:
        failures.append("missing Not relevant because default")
    if "Optional example:" not in body:
        failures.append("missing Optional example reference")
    if not examples:
        failures.append("missing optional example file")

    lower = body.lower()
    parallel_subagent_guidance = any(
        marker in lower
        for marker in ["parallel subagent", "subagent-ready", "go to subagents", "use subagents"]
    )
    if parallel_subagent_guidance and not all(marker in lower for marker in ["independent", "proof"]):
        failures.append("subagent guidance must be bounded by independence and proof")

    soft_matches = sorted(set(re.findall(r"\b(consider|prefer|maybe)\b", body, flags=re.IGNORECASE)))
    if soft_matches:
        warnings.append(f"soft guidance terms present: {', '.join(soft_matches)}")

    return {
        "name": name,
        "path": str(path),
        "wordCount": words,
        "description": description,
        "optionalExamples": examples,
        "hasNotRelevantDefault": "Not relevant because" in body,
        "failures": failures,
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser(description="Lint Gauntlet skill contracts.")
    parser.add_argument("--skills-root", type=Path, default=DEFAULT_SKILLS)
    parser.add_argument("--max-words", type=int, default=500)
    parser.add_argument(
        "--only",
        help="Comma-separated skill names to lint. Defaults to every SKILL.md under --skills-root.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable results.")
    args = parser.parse_args()

    skills = []
    failures = []
    warnings = []
    only = set(filter(None, (args.only or "").split(",")))
    seen = set()
    for path in sorted(args.skills_root.glob("*/SKILL.md")):
        if only and path.parent.name not in only:
            continue
        try:
            result = lint_skill(path, args.max_words)
        except ValueError as error:
            result = {
                "name": path.parent.name,
                "path": str(path),
                "wordCount": 0,
                "description": "",
                "optionalExamples": [],
                "hasNotRelevantDefault": False,
                "failures": [str(error)],
                "warnings": [],
            }
        seen.add(result["name"])
        skills.append(result)
        for failure in result["failures"]:
            failures.append({"skill": result["name"], "message": failure})
        for warning in result["warnings"]:
            warnings.append({"skill": result["name"], "message": warning})
    for missing in sorted(only - seen):
        failures.append({"skill": missing, "message": "requested skill was not found"})

    output = {"schemaVersion": "1.0", "skills": skills, "failures": failures, "warnings": warnings}
    if args.json:
        print(json.dumps(output, indent=2))
    else:
        for skill in skills:
            status = "FAIL" if skill["failures"] else "PASS"
            print(f"{status} {skill['name']} words={skill['wordCount']} examples={len(skill['optionalExamples'])}")
            for failure in skill["failures"]:
                print(f"  failure: {failure}")
            for warning in skill["warnings"]:
                print(f"  warning: {warning}")

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
