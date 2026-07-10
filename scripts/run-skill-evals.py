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
DEFAULT_SCORER_SMOKE_RESPONSES = ROOT / "evals" / "scorer-smoke-fixtures.json"
COVERAGE_ARMS = ["one_shot", "current_skill", "new_skill"]
SCORER_SMOKE_ARMS = ["no_guidance", "one_shot", "current_skill", "new_skill"]


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


def build_scorer_smoke_prompt(case, arm_name, source_text):
    source = source_text.strip() if source_text.strip() else "No skill guidance. Respond from the pressure scenario alone."
    return "\n".join(
        [
            f"# Gauntlet Skill Scorer Smoke: {case['id']}",
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
            "\n".join(f"- {item}" for item in scorer_smoke_required(case)),
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


def scorer_smoke_required(case):
    return case.get(
        "scorerSmokeRequiredPatterns",
        case.get("behaviorRequiredPatterns", case["requiredPatterns"]),
    )


def scorer_smoke_forbidden(case):
    return case.get(
        "scorerSmokeForbiddenPatterns",
        case.get("behaviorForbiddenPatterns", case.get("forbiddenPatterns", [])),
    )


def score_scorer_smoke_response(case, text):
    start = time.perf_counter()
    required = [
        {"pattern": pattern, "present": has_pattern(text, pattern)}
        for pattern in scorer_smoke_required(case)
    ]
    forbidden = [
        {"pattern": pattern, "present": has_pattern(text, pattern)}
        for pattern in scorer_smoke_forbidden(case)
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
    return text.replace("{requiredPatterns}", "\n".join(scorer_smoke_required(case))).replace(
        "{caseId}", case["id"]
    )


def load_scorer_smoke_responses(path, cases):
    if not path:
        return None
    data = json.loads(read_text(path))
    by_case = {case["id"]: {arm: [] for arm in SCORER_SMOKE_ARMS} for case in cases}
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


def run_scorer_smoke_case(case, arms, responses_by_case, scorer_smoke_prompts_dir):
    min_reps = int(case.get("scorerSmokeMinReps", case.get("behaviorMinReps", 5)))
    if scorer_smoke_prompts_dir:
        case_dir = scorer_smoke_prompts_dir / case["id"]
        case_dir.mkdir(parents=True, exist_ok=True)
        for arm_name in SCORER_SMOKE_ARMS:
            source_text = arms.get(arm_name, "")
            prompt = build_scorer_smoke_prompt(case, arm_name, source_text)
            (case_dir / f"{arm_name}.md").write_text(prompt, encoding="utf-8")

    arm_results = {}
    for arm_name in SCORER_SMOKE_ARMS:
        responses = []
        if responses_by_case:
            responses = responses_by_case.get(case["id"], {}).get(arm_name, [])
        reps = []
        for index, response in enumerate(responses, start=1):
            scored = score_scorer_smoke_response(case, response["text"])
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
        "configured": responses_by_case is not None or scorer_smoke_prompts_dir is not None,
        "responsesConfigured": responses_by_case is not None,
        "promptsWritten": scorer_smoke_prompts_dir is not None,
        "minReps": min_reps,
        "requiredPatterns": scorer_smoke_required(case),
        "forbiddenPatterns": scorer_smoke_forbidden(case),
        "arms": arm_results,
    }


def run_case(
    case,
    current_root,
    new_root,
    prompts_dir,
    scorer_smoke_prompts_dir,
    responses_by_case,
):
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
        "scorerSmoke": run_scorer_smoke_case(
            case, arms, responses_by_case, scorer_smoke_prompts_dir
        ),
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
        scorer_smoke = case.get("scorerSmoke", {})
        new_scorer_smoke = scorer_smoke.get("arms", {}).get("new_skill")
        if new_scorer_smoke and new_scorer_smoke["repsFound"]:
            row.append(
                "scorer_smoke_new="
                f"{new_scorer_smoke['passedReps']}/{new_scorer_smoke['repsFound']}"
            )
        print(" | ".join(row))
    gate = "PASS" if results["summary"]["gatePassed"] else "FAIL"
    print(f"coverage_and_scorer_smoke={gate}")


def build_summary(cases):
    coverage_passed = all(case["arms"]["new_skill"]["passed"] for case in cases)
    configured_smoke = [
        case["scorerSmoke"]
        for case in cases
        if case["scorerSmoke"]["responsesConfigured"]
    ]
    scorer_smoke_passed = all(
        smoke["arms"]["new_skill"]["repsFound"] >= smoke["minReps"]
        and smoke["arms"]["new_skill"]["passedReps"]
        == smoke["arms"]["new_skill"]["repsFound"]
        for smoke in configured_smoke
    )
    return {
        "cases": len(cases),
        "newSkillCoveragePassed": coverage_passed,
        "newSkillScorerSmokePassed": scorer_smoke_passed if configured_smoke else None,
        "gatePassed": coverage_passed and scorer_smoke_passed,
    }


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
    prompt_group = parser.add_mutually_exclusive_group()
    prompt_group.add_argument(
        "--scorer-smoke-prompts-dir",
        type=Path,
        help="Optional directory to write scorer-smoke no-guidance/one-shot/current/new prompts.",
    )
    prompt_group.add_argument(
        "--behavior-prompts-dir",
        dest="scorer_smoke_prompts_dir",
        type=Path,
        help=argparse.SUPPRESS,
    )
    response_group = parser.add_mutually_exclusive_group()
    response_group.add_argument(
        "--scorer-smoke-responses",
        type=Path,
        default=(
            DEFAULT_SCORER_SMOKE_RESPONSES
            if DEFAULT_SCORER_SMOKE_RESPONSES.exists()
            else None
        ),
        help="Optional JSON file of deterministic response fixtures that exercise the phrase scorer.",
    )
    response_group.add_argument(
        "--behavior-responses",
        dest="scorer_smoke_responses",
        type=Path,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--only-skill",
        help="Comma-separated skill names to evaluate. Defaults to every configured case.",
    )
    args = parser.parse_args()

    data = json.loads(read_text(args.evals))
    requested_skills = set(filter(None, (args.only_skill or "").split(",")))
    all_cases = data["cases"]
    cases_to_run = [
        case for case in all_cases if not requested_skills or case["skill"] in requested_skills
    ]
    missing_skills = sorted(requested_skills - {case["skill"] for case in all_cases})
    if missing_skills:
        raise SystemExit(f"no eval cases for requested skills: {', '.join(missing_skills)}")
    prompts_dir = args.prompts_dir
    if prompts_dir:
        prompts_dir.mkdir(parents=True, exist_ok=True)
    scorer_smoke_prompts_dir = args.scorer_smoke_prompts_dir
    if scorer_smoke_prompts_dir:
        scorer_smoke_prompts_dir.mkdir(parents=True, exist_ok=True)
    responses_by_case = load_scorer_smoke_responses(
        args.scorer_smoke_responses, cases_to_run
    )

    cases = [
        run_case(
            case,
            args.current_root,
            args.new_root,
            prompts_dir,
            scorer_smoke_prompts_dir,
            responses_by_case,
        )
        for case in cases_to_run
    ]
    results = {
        "schemaVersion": "1.1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "evals": str(args.evals),
        "currentRoot": str(args.current_root),
        "newRoot": str(args.new_root),
        "comparisonArms": COVERAGE_ARMS,
        "scorerSmokeComparisonArms": SCORER_SMOKE_ARMS,
        "scorerSmokeResponses": (
            str(args.scorer_smoke_responses) if args.scorer_smoke_responses else None
        ),
        "onlySkill": sorted(requested_skills),
        "summary": build_summary(cases),
        "cases": cases,
    }

    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print_summary(results)
    print()
    print(f"wrote {args.results}")
    if not results["summary"]["gatePassed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
