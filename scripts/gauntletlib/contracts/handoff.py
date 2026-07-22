"""Declarative validation for generic contextual merge handoffs."""

import json
import re

from gauntletlib.core.redact import has_secret


REQUIRED_HANDOFF_FIELDS = {
    "schemaVersion",
    "title",
    "problem",
    "solution",
    "changelog",
    "testing",
    "securityRisk",
    "sourceBinding",
}
SOURCE_BINDING_FIELDS = {"repository", "commit", "tree", "base"}
OBJECT_ID = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?").fullmatch


def handoff_finding(code, message):
    return {"code": code, "severity": "fail", "message": message}


def nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def _validate_source_binding(findings, binding):
    if not isinstance(binding, dict) or set(binding) != SOURCE_BINDING_FIELDS:
        findings.append(
            handoff_finding(
                "invalid_source_binding",
                "sourceBinding must contain exactly repository, commit, tree, and base.",
            )
        )
        return
    if not nonempty_string(binding.get("repository")):
        findings.append(
            handoff_finding(
                "invalid_source_binding",
                "sourceBinding.repository must be non-empty.",
            )
        )
    for field in ("commit", "tree", "base"):
        if (
            not isinstance(binding.get(field), str)
            or OBJECT_ID(binding[field]) is None
        ):
            findings.append(
                handoff_finding(
                    "invalid_source_binding",
                    f"sourceBinding.{field} must be an exact Git object ID.",
                )
            )


def validate_handoff_v1_fields(data, expected_schema="1.0"):
    findings = []
    if not isinstance(data, dict):
        return [
            handoff_finding(
                "invalid_handoff",
                "Merge handoff must be a JSON object.",
            )
        ]
    missing = sorted(REQUIRED_HANDOFF_FIELDS - set(data))
    for field in missing:
        findings.append(
            handoff_finding(
                "missing_handoff_field",
                f"Merge handoff is missing: {field}.",
            )
        )
    if data.get("schemaVersion") != expected_schema:
        findings.append(
            handoff_finding(
                "unsupported_handoff_schema",
                f"Merge handoff schemaVersion must be {expected_schema}.",
            )
        )

    title = data.get("title")
    if not isinstance(title, str) or not re.fullmatch(
        r"[^:\n]+: [^\n]+",
        title.strip(),
    ):
        findings.append(
            handoff_finding(
                "invalid_handoff_title",
                "Title must use '<area>: <behavioral outcome>'.",
            )
        )

    problem = data.get("problem")
    if not isinstance(problem, dict):
        findings.append(
            handoff_finding(
                "invalid_handoff_problem",
                "problem must be an object.",
            )
        )
    else:
        for field in ("context", "impact"):
            if not nonempty_string(problem.get(field)):
                findings.append(
                    handoff_finding(
                        "missing_problem_framing",
                        f"problem.{field} must be non-empty.",
                    )
                )

    solution = data.get("solution")
    if not isinstance(solution, dict):
        findings.append(
            handoff_finding(
                "invalid_handoff_solution",
                "solution must be an object.",
            )
        )
    else:
        if not nonempty_string(solution.get("outcome")):
            findings.append(
                handoff_finding(
                    "missing_solution_outcome",
                    "solution.outcome must be non-empty.",
                )
            )
        for field in ("invariants", "preserved", "nonGoals"):
            value = solution.get(field, [])
            if not isinstance(value, list) or not all(
                nonempty_string(item) for item in value
            ):
                findings.append(
                    handoff_finding(
                        "invalid_solution_list",
                        f"solution.{field} must be a list of non-empty strings.",
                    )
                )

    changelog = data.get("changelog")
    if not nonempty_string(changelog):
        findings.append(
            handoff_finding(
                "missing_changelog_entry",
                "changelog must be non-empty.",
            )
        )
    elif isinstance(changelog, str) and ("\n" in changelog or "\r" in changelog):
        findings.append(
            handoff_finding(
                "multiline_changelog_entry",
                "changelog must be a single line.",
            )
        )

    testing = data.get("testing")
    if not isinstance(testing, list) or not testing:
        findings.append(
            handoff_finding(
                "missing_testing_evidence",
                "testing must contain at least one reported check.",
            )
        )
    else:
        for index, item in enumerate(testing, 1):
            if not isinstance(item, dict):
                findings.append(
                    handoff_finding(
                        "invalid_testing_evidence",
                        f"testing item {index} must be an object.",
                    )
                )
                continue
            for field in ("command", "result", "proves"):
                if not nonempty_string(item.get(field)):
                    findings.append(
                        handoff_finding(
                            "invalid_testing_evidence",
                            f"testing item {index}.{field} must be non-empty.",
                        )
                    )

    security_risk = data.get("securityRisk")
    if security_risk is not None and not nonempty_string(security_risk):
        findings.append(
            handoff_finding(
                "invalid_security_risk",
                "securityRisk must be null or a non-empty string.",
            )
        )
    _validate_source_binding(findings, data.get("sourceBinding"))
    if has_secret(json.dumps(data, sort_keys=True)):
        findings.append(
            handoff_finding(
                "secret_like_handoff",
                "Merge handoff contains secret-like content.",
            )
        )
    return findings


def validate_merge_handoff(data):
    return validate_handoff_v1_fields(data)
