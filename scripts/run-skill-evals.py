#!/usr/bin/env python3
import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVALS = ROOT / "evals" / "skill-evals.json"
DEFAULT_CURRENT = ROOT / "evals" / "baselines" / "current" / "skills"
DEFAULT_NEW = ROOT / "skills" if (ROOT / "skills").exists() else ROOT.parent / "skills"
DEFAULT_RESULTS = ROOT / "evals" / "results" / "latest.json"
DEFAULT_BEHAVIOR_RESPONSES = ROOT / "evals" / "behavior-fixtures.json"
COVERAGE_ARMS = ["one_shot", "current_skill", "new_skill"]
BEHAVIOR_ARMS = ["no_guidance", "one_shot", "current_skill", "new_skill"]


def read_text(path):
    return path.read_text(encoding="utf-8")


def normalize(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def has_pattern(text, pattern):
    if pattern.startswith("re:"):
        return re.search(pattern[3:], text, re.IGNORECASE | re.MULTILINE) is not None
    return normalize(pattern) in normalize(text)


def word_count(text):
    return len(re.findall(r"\b\S+\b", text))


def skill_text(root, skill):
    path = root / skill / "SKILL.md"
    if not path.exists():
        raise FileNotFoundError(f"missing skill file: {path}")
    return read_text(path)


def build_prompt(case, arm_name, source_text):
    return "\n".join(
        [
            f"# Gauntlet Skill Eval: {case['id']}",
            "",
            f"Variant: {arm_name}",
            "",
            "## Instruction Source",
            source_text.strip(),
            "",
            "## Pressure Scenario",
            case["pressurePrompt"].strip(),
            "",
            "## Expected Contract",
            "\n".join(f"- {item}" for item in case["requiredPatterns"]),
        ]
    )


def build_behavior_prompt(case, arm_name, source_text):
    source = source_text.strip() if source_text.strip() else "No skill guidance. Respond from the pressure scenario alone."
    return "\n".join(
        [
            f"# Gauntlet Behavioral Skill Eval: {case['id']}",
            "",
            f"Variant: {arm_name}",
            "",
            "## Instruction Source",
            source,
            "",
            "## Task",
            "Produce the agent response for the pressure scenario. Use the instruction source exactly as a real agent would.",
            "",
            "## Pressure Scenario",
            case["pressurePrompt"].strip(),
            "",
            "## Scored Output Shape",
            "\n".join(f"- {item}" for item in behavior_required(case)),
        ]
    )


def score_arm(case, source_text):
    start = time.perf_counter()
    required = [
        {"pattern": pattern, "present": has_pattern(source_text, pattern)}
        for pattern in case["requiredPatterns"]
    ]
    forbidden = [
        {"pattern": pattern, "present": has_pattern(source_text, pattern)}
        for pattern in case.get("forbiddenPatterns", [])
    ]
    passed_required = sum(1 for item in required if item["present"])
    passed_forbidden = sum(1 for item in forbidden if not item["present"])
    total = len(required) + len(forbidden)
    score = passed_required + passed_forbidden
    return {
        "score": score,
        "total": total,
        "passed": score == total,
        "wordCount": word_count(source_text),
        "scoreElapsedMs": round((time.perf_counter() - start) * 1000, 3),
        "required": required,
        "forbidden": forbidden,
    }


def percent_change(before, after):
    if before == 0:
        return None
    return round(((after - before) / before) * 100, 1)


def behavior_required(case):
    return case.get("behaviorRequiredPatterns", case["requiredPatterns"])


def behavior_forbidden(case):
    return case.get("behaviorForbiddenPatterns", case.get("forbiddenPatterns", []))


def score_behavior_response(case, text):
    start = time.perf_counter()
    required = [
        {"pattern": pattern, "present": has_pattern(text, pattern)}
        for pattern in behavior_required(case)
    ]
    forbidden = [
        {"pattern": pattern, "present": has_pattern(text, pattern)}
        for pattern in behavior_forbidden(case)
    ]
    passed_required = sum(1 for item in required if item["present"])
    passed_forbidden = sum(1 for item in forbidden if not item["present"])
    total = len(required) + len(forbidden)
    score = passed_required + passed_forbidden
    return {
        "score": score,
        "total": total,
        "passed": score == total,
        "outputWordCount": word_count(text),
        "scoreElapsedMs": round((time.perf_counter() - start) * 1000, 3),
        "required": required,
        "forbidden": forbidden,
    }


def render_fixture_text(case, text):
    return text.replace("{requiredPatterns}", "\n".join(behavior_required(case))).replace(
        "{caseId}", case["id"]
    )


def load_behavior_responses(path, cases):
    if not path:
        return None
    data = json.loads(read_text(path))
    by_case = {case["id"]: {arm: [] for arm in BEHAVIOR_ARMS} for case in cases}
    case_by_id = {case["id"]: case for case in cases}
    for item in data.get("responses", []):
        case_ids = list(case_by_id) if item["case"] == "*" else [item["case"]]
        repeat = int(item.get("repeat", data.get("defaultRepeat", 1)))
        for case_id in case_ids:
            case = case_by_id[case_id]
            response = {
                "text": render_fixture_text(case, item["text"]),
                "elapsedMs": item.get("elapsedMs"),
            }
            for _ in range(repeat):
                by_case[case_id][item["arm"]].append(response)
    return by_case


def run_behavior_case(case, arms, responses_by_case, behavior_prompts_dir):
    min_reps = int(case.get("behaviorMinReps", 5))
    if behavior_prompts_dir:
        case_dir = behavior_prompts_dir / case["id"]
        case_dir.mkdir(parents=True, exist_ok=True)
        for arm_name in BEHAVIOR_ARMS:
            source_text = arms.get(arm_name, "")
            prompt = build_behavior_prompt(case, arm_name, source_text)
            (case_dir / f"{arm_name}.md").write_text(prompt, encoding="utf-8")

    arm_results = {}
    for arm_name in BEHAVIOR_ARMS:
        responses = []
        if responses_by_case:
            responses = responses_by_case.get(case["id"], {}).get(arm_name, [])
        reps = []
        for index, response in enumerate(responses, start=1):
            scored = score_behavior_response(case, response["text"])
            scored["rep"] = index
            scored["responseElapsedMs"] = response.get("elapsedMs")
            reps.append(scored)
        reps_found = len(reps)
        passed = sum(1 for rep in reps if rep["passed"])
        avg_words = round(sum(rep["outputWordCount"] for rep in reps) / reps_found, 1) if reps_found else 0
        elapsed_values = [rep["responseElapsedMs"] for rep in reps if rep.get("responseElapsedMs") is not None]
        avg_response_ms = round(sum(elapsed_values) / len(elapsed_values), 1) if elapsed_values else None
        arm_results[arm_name] = {
            "repsFound": reps_found,
            "passedReps": passed,
            "passRate": round(passed / reps_found, 3) if reps_found else 0,
            "averageOutputWords": avg_words,
            "averageResponseElapsedMs": avg_response_ms,
            "reps": reps,
        }

    return {
        "configured": responses_by_case is not None or behavior_prompts_dir is not None,
        "minReps": min_reps,
        "requiredPatterns": behavior_required(case),
        "forbiddenPatterns": behavior_forbidden(case),
        "arms": arm_results,
    }


def run_case(case, current_root, new_root, prompts_dir, behavior_prompts_dir, responses_by_case):
    arms = {
        "no_guidance": "",
        "one_shot": case["oneShotInstruction"],
        "current_skill": skill_text(current_root, case["skill"]),
        "new_skill": skill_text(new_root, case["skill"]),
    }
    arm_results = {}
    for arm_name in COVERAGE_ARMS:
        source_text = arms[arm_name]
        prompt = build_prompt(case, arm_name, source_text)
        arm_results[arm_name] = score_arm(case, source_text)
        arm_results[arm_name]["promptWordCount"] = word_count(prompt)
        if prompts_dir:
            case_dir = prompts_dir / case["id"]
            case_dir.mkdir(parents=True, exist_ok=True)
            (case_dir / f"{arm_name}.md").write_text(prompt, encoding="utf-8")

    current_words = arm_results["current_skill"]["wordCount"]
    new_words = arm_results["new_skill"]["wordCount"]
    return {
        "id": case["id"],
        "skill": case["skill"],
        "title": case["title"],
        "arms": arm_results,
        "behavior": run_behavior_case(case, arms, responses_by_case, behavior_prompts_dir),
        "tokenEfficiencyEstimate": {
            "currentWords": current_words,
            "newWords": new_words,
            "wordDeltaPercent": percent_change(current_words, new_words),
            "note": "Word count is used as the deterministic token-efficiency proxy.",
        },
    }


def print_summary(results):
    print("skill evals: one_shot vs current_skill vs new_skill")
    print()
    for case in results["cases"]:
        row = [case["id"]]
        for arm in COVERAGE_ARMS:
            result = case["arms"][arm]
            mark = "PASS" if result["passed"] else "FAIL"
            row.append(f"{arm}={mark} {result['score']}/{result['total']}")
        delta = case["tokenEfficiencyEstimate"]["wordDeltaPercent"]
        row.append(f"words_delta={delta:+.1f}%" if delta is not None else "words_delta=n/a")
        behavior = case.get("behavior", {})
        new_behavior = behavior.get("arms", {}).get("new_skill")
        if new_behavior and new_behavior["repsFound"]:
            row.append(
                f"behavior_new={new_behavior['passedReps']}/{new_behavior['repsFound']}"
            )
        print(" | ".join(row))


def main():
    parser = argparse.ArgumentParser(
        description="Run deterministic Gauntlet skill evals across one-shot, current skill, and new skill arms."
    )
    parser.add_argument("--evals", type=Path, default=DEFAULT_EVALS)
    parser.add_argument("--current-root", type=Path, default=DEFAULT_CURRENT)
    parser.add_argument("--new-root", type=Path, default=DEFAULT_NEW)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument(
        "--prompts-dir",
        type=Path,
        help="Optional directory to write the constructed one-shot/current/new prompts.",
    )
    parser.add_argument(
        "--behavior-prompts-dir",
        type=Path,
        help="Optional directory to write behavioral no-guidance/one-shot/current/new prompts.",
    )
    parser.add_argument(
        "--behavior-responses",
        type=Path,
        default=DEFAULT_BEHAVIOR_RESPONSES if DEFAULT_BEHAVIOR_RESPONSES.exists() else None,
        help="Optional JSON file of behavioral response reps to score.",
    )
    args = parser.parse_args()

    data = json.loads(read_text(args.evals))
    prompts_dir = args.prompts_dir
    if prompts_dir:
        prompts_dir.mkdir(parents=True, exist_ok=True)
    behavior_prompts_dir = args.behavior_prompts_dir
    if behavior_prompts_dir:
        behavior_prompts_dir.mkdir(parents=True, exist_ok=True)
    responses_by_case = load_behavior_responses(args.behavior_responses, data["cases"])

    cases = [
        run_case(case, args.current_root, args.new_root, prompts_dir, behavior_prompts_dir, responses_by_case)
        for case in data["cases"]
    ]
    results = {
        "schemaVersion": "1.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "evals": str(args.evals),
        "currentRoot": str(args.current_root),
        "newRoot": str(args.new_root),
        "comparisonArms": COVERAGE_ARMS,
        "behaviorComparisonArms": BEHAVIOR_ARMS,
        "behaviorResponses": str(args.behavior_responses) if args.behavior_responses else None,
        "cases": cases,
    }

    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print_summary(results)
    print()
    print(f"wrote {args.results}")


if __name__ == "__main__":
    main()
