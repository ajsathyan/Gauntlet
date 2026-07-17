"""Declarative validation for contextual merge handoffs."""

import hashlib
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
}
REQUIRED_RUN_HANDOFF_FIELDS = {
    "schemaVersion", "title", "binding", "acceptedCriteria", "changedPaths",
    "completion", "deferrals", "epic", "releaseGates", "verificationReceipts",
}
RUN_BINDING_FIELDS = {
    "runId",
    "generation",
    "sourceLockSha256",
    "graphSha256",
    "repository",
    "branch",
    "headSha",
    "epicVerificationSha256",
}


def handoff_finding(code, message):
    return {"code": code, "severity": "fail", "message": message}


def nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def validate_string_list(
    findings, value, code, label, allow_empty=True
):
    if (
        not isinstance(value, list)
        or (not allow_empty and not value)
        or not all(nonempty_string(item) for item in value)
    ):
        findings.append(
            handoff_finding(
                code,
                f"{label} must be "
                f"{'a non-empty' if not allow_empty else 'a'} "
                "list of non-empty strings.",
            )
        )


def validate_accepted_criteria(findings, value):
    if isinstance(value, list):
        validate_string_list(
            findings,
            value,
            "invalid_accepted_criteria",
            "acceptedCriteria",
            allow_empty=False,
        )
        return
    if not isinstance(value, dict) or not value:
        findings.append(
            handoff_finding(
                "invalid_accepted_criteria",
                "acceptedCriteria must be a non-empty list or a non-empty "
                "object of named criteria lists.",
            )
        )
        return
    for group, criteria in value.items():
        if not nonempty_string(group):
            findings.append(
                handoff_finding(
                    "invalid_accepted_criteria",
                    "acceptedCriteria group names must be non-empty strings.",
                )
            )
            continue
        validate_string_list(
            findings,
            criteria,
            "invalid_accepted_criteria",
            f"acceptedCriteria.{group}",
            allow_empty=False,
        )


def validate_handoff_v1_fields(data, expected_schema="1.0"):
    findings = []
    if not isinstance(data, dict):
        return [
            handoff_finding(
                "invalid_handoff", "Merge handoff must be a JSON object."
            )
        ]
    missing = sorted(REQUIRED_HANDOFF_FIELDS - set(data))
    for field in missing:
        findings.append(
            handoff_finding(
                "missing_handoff_field", f"Merge handoff is missing: {field}."
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
        r"[^:\n]+: [^\n]+", title.strip()
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
                "invalid_handoff_problem", "problem must be an object."
            )
        )
    else:
        for field in ["context", "impact"]:
            if (
                not isinstance(problem.get(field), str)
                or not problem[field].strip()
            ):
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
                "invalid_handoff_solution", "solution must be an object."
            )
        )
    else:
        if (
            not isinstance(solution.get("outcome"), str)
            or not solution["outcome"].strip()
        ):
            findings.append(
                handoff_finding(
                    "missing_solution_outcome",
                    "solution.outcome must be non-empty.",
                )
            )
        for field in ["invariants", "preserved", "nonGoals"]:
            value = solution.get(field, [])
            if not isinstance(value, list) or not all(
                isinstance(item, str) and item.strip() for item in value
            ):
                findings.append(
                    handoff_finding(
                        "invalid_solution_list",
                        f"solution.{field} must be a list of non-empty strings.",
                    )
                )

    changelog = data.get("changelog")
    if not isinstance(changelog, str) or not changelog.strip():
        findings.append(
            handoff_finding(
                "missing_changelog_entry", "changelog must be non-empty."
            )
        )
    elif "\n" in changelog or "\r" in changelog:
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
            for field in ["command", "result", "proves"]:
                if (
                    not isinstance(item.get(field), str)
                    or not item[field].strip()
                ):
                    findings.append(
                        handoff_finding(
                            "invalid_testing_evidence",
                            f"testing item {index}.{field} must be non-empty.",
                        )
                    )

    security_risk = data.get("securityRisk")
    if security_risk is not None and (
        not isinstance(security_risk, str) or not security_risk.strip()
    ):
        findings.append(
            handoff_finding(
                "invalid_security_risk",
                "securityRisk must be null or a non-empty string.",
            )
        )
    if has_secret(json.dumps(data, sort_keys=True)):
        findings.append(
            handoff_finding(
                "secret_like_handoff",
                "Merge handoff contains secret-like content.",
            )
        )
    return findings


def _validate_run_identity(findings, data):
    if data.get("schemaVersion") != "3.0":
        findings.append(
            handoff_finding(
                "invalid_run_schema",
                "Run projection schemaVersion must be 3.0.",
            )
        )
    for field in sorted(REQUIRED_RUN_HANDOFF_FIELDS - set(data)):
        findings.append(
            handoff_finding(
                "missing_run_projection_field",
                f"Run projection is missing: {field}.",
            )
        )
    unknown = set(data) - REQUIRED_RUN_HANDOFF_FIELDS
    if unknown:
        findings.append(
            handoff_finding(
                "unknown_run_projection_field",
                "Run projection contains unsupported fields: "
                + ", ".join(sorted(unknown))
                + ".",
            )
        )
    if not nonempty_string(data.get("title")):
        findings.append(
            handoff_finding(
                "invalid_run_title", "title must be non-empty."
            )
        )


def _validate_run_binding(findings, binding):
    if not isinstance(binding, dict):
        findings.append(
            handoff_finding(
                "invalid_run_binding", "binding must be an object."
            )
        )
        return
    if set(binding) != RUN_BINDING_FIELDS:
        findings.append(
            handoff_finding(
                "invalid_run_binding",
                "binding must contain exactly the schema 3.0 binding fields.",
            )
        )
    if not nonempty_string(binding.get("runId")) or not nonempty_string(
        binding.get("repository")
    ):
        findings.append(
            handoff_finding(
                "invalid_run_binding",
                "binding.runId and binding.repository must be non-empty.",
            )
        )
    if (
        not isinstance(binding.get("generation"), int)
        or isinstance(binding.get("generation"), bool)
        or binding.get("generation", -1) < 0
    ):
        findings.append(
            handoff_finding(
                "invalid_run_binding",
                "binding.generation must be a non-negative integer.",
            )
        )
    for field in ["branch", "headSha"]:
        if not nonempty_string(binding.get(field)):
            findings.append(
                handoff_finding(
                    "invalid_run_binding",
                    f"binding.{field} must be non-empty.",
                )
            )
    for field in [
        "sourceLockSha256",
        "graphSha256",
        "epicVerificationSha256",
    ]:
        if not isinstance(binding.get(field), str) or not re.fullmatch(
            r"[0-9a-f]{64}", binding[field]
        ):
            findings.append(
                handoff_finding(
                    "invalid_run_binding_hash",
                    f"binding.{field} must be a lowercase SHA-256 digest.",
                )
            )


def _validate_epic(findings, epic):
    if not isinstance(epic, dict) or set(epic) != {
        "id",
        "title",
        "scopeAreas",
    }:
        findings.append(
            handoff_finding(
                "invalid_epic_projection",
                "epic must contain id, title, and scopeAreas.",
            )
        )
        return
    if not nonempty_string(epic.get("id")) or not nonempty_string(
        epic.get("title")
    ):
        findings.append(
            handoff_finding(
                "invalid_epic_projection",
                "epic.id and epic.title must be non-empty.",
            )
        )
    scopes = epic.get("scopeAreas")
    if not isinstance(scopes, list) or not scopes:
        findings.append(
            handoff_finding(
                "invalid_epic_projection",
                "epic.scopeAreas must be non-empty.",
            )
        )
        return
    for index, scope in enumerate(scopes, 1):
        if (
            not isinstance(scope, dict)
            or set(scope) != {"id", "responsibility"}
            or any(
                not nonempty_string(scope.get(key))
                for key in ["id", "responsibility"]
            )
        ):
            findings.append(
                handoff_finding(
                    "invalid_epic_scope",
                    f"epic.scopeAreas item {index} must contain id and "
                    "responsibility.",
                )
            )


def _validate_completion(findings, completion):
    fields = {
        "implemented", "merged", "deployed", "productionProved", "complete",
        "epicId", "exactRevision", "exactState", "pendingGates",
        "sourceSha256", "verificationSummary",
    }
    if not isinstance(completion, dict) or set(completion) not in (
        fields,
        fields | {"gapReview"},
    ):
        findings.append(
            handoff_finding(
                "invalid_completion_projection",
                "completion has an unsupported shape.",
            )
        )
        return
    for field in [
        "implemented", "merged", "deployed", "productionProved", "complete",
    ]:
        if not isinstance(completion.get(field), bool):
            findings.append(
                handoff_finding(
                    "invalid_completion_projection",
                    f"completion.{field} must be boolean.",
                )
            )
    implemented = completion.get("implemented") is True
    merged = completion.get("merged") is True
    deployed = completion.get("deployed") is True
    production_proved = completion.get("productionProved") is True
    complete = completion.get("complete") is True
    if (
        (merged and not implemented)
        or (deployed and not merged)
        or (production_proved and not deployed)
        or (complete and not (implemented and merged))
    ):
        findings.append(
            handoff_finding(
                "contradictory_completion_projection",
                "Completion stages must be monotonic and complete requires "
                "implemented plus merged.",
            )
        )
    if implemented and not re.fullmatch(
        r"[0-9a-f]{40,64}", completion.get("exactRevision") or ""
    ):
        findings.append(
            handoff_finding(
                "invalid_completion_projection",
                "Implemented state requires an exact revision.",
            )
        )
    if not implemented and completion.get("exactRevision") is not None:
        findings.append(
            handoff_finding(
                "invalid_completion_projection",
                "An unimplemented state cannot claim an exact verified "
                "revision.",
            )
        )
    if implemented and not nonempty_string(
        completion.get("verificationSummary")
    ):
        findings.append(
            handoff_finding(
                "invalid_completion_projection",
                "Implemented state requires a final verification summary.",
            )
        )
    if not re.fullmatch(
        r"[0-9a-f]{64}", completion.get("sourceSha256") or ""
    ):
        findings.append(
            handoff_finding(
                "invalid_completion_projection",
                "completion.sourceSha256 must be a lowercase SHA-256 digest.",
            )
        )
    expected_state = (
        "complete" if complete else
        "production-proved" if production_proved else
        "deployed" if deployed else
        "merged" if merged else
        "implementation-complete" if implemented else
        "in-progress"
    )
    if completion.get("exactState") != expected_state:
        findings.append(
            handoff_finding(
                "contradictory_completion_projection",
                f"completion.exactState must be {expected_state} for the "
                "declared stage facts.",
            )
        )
    validate_string_list(
        findings,
        completion.get("pendingGates"),
        "invalid_completion_projection",
        "completion.pendingGates",
    )
    gap_review = completion.get("gapReview")
    if gap_review is not None and (
        not isinstance(gap_review, dict)
        or gap_review.get("schemaVersion")
        != "gauntlet.epic-gap-review-status.v1"
    ):
        findings.append(
            handoff_finding(
                "invalid_completion_projection",
                "completion.gapReview must be a controller gap-review "
                "projection.",
            )
        )


def _validate_deferrals(findings, deferrals):
    if not isinstance(deferrals, dict) or set(deferrals) != {
        "cannotVerify",
        "nonGoals",
    }:
        findings.append(
            handoff_finding(
                "invalid_deferrals",
                "deferrals must contain cannotVerify and nonGoals.",
            )
        )
        return
    validate_string_list(
        findings,
        deferrals.get("cannotVerify"),
        "invalid_deferrals",
        "deferrals.cannotVerify",
    )
    validate_string_list(
        findings,
        deferrals.get("nonGoals"),
        "invalid_deferrals",
        "deferrals.nonGoals",
    )


def _validate_release_gates(findings, gates):
    if not isinstance(gates, list) or not gates:
        findings.append(
            handoff_finding(
                "missing_release_gate", "releaseGates must be non-empty."
            )
        )
        return
    seen = set()
    fields = {
        "id", "stage", "status", "summary", "evidenceRefs", "blocksPr",
        "blocksOverallCompletion",
    }
    for index, gate in enumerate(gates, 1):
        if not isinstance(gate, dict) or set(gate) != fields:
            findings.append(
                handoff_finding(
                    "invalid_release_gate",
                    f"releaseGates item {index} has an unsupported shape.",
                )
            )
            continue
        for field in ["id", "stage", "status", "summary"]:
            if not nonempty_string(gate.get(field)):
                findings.append(
                    handoff_finding(
                        "invalid_release_gate",
                        f"releaseGates item {index}.{field} must be non-empty.",
                    )
                )
        if gate.get("status") not in {
            "pass", "fail", "pending", "stale", "not-required",
            "not-applicable",
        }:
            findings.append(
                handoff_finding(
                    "invalid_release_gate",
                    f"releaseGates item {index}.status is unsupported.",
                )
            )
        if gate.get("id") in seen:
            findings.append(
                handoff_finding(
                    "duplicate_release_gate",
                    f"Release gate {gate.get('id')} appears more than once.",
                )
            )
        seen.add(gate.get("id"))
        for field in ["blocksPr", "blocksOverallCompletion"]:
            if not isinstance(gate.get(field), bool):
                findings.append(
                    handoff_finding(
                        "invalid_release_gate",
                        f"releaseGates item {index}.{field} must be boolean.",
                    )
                )
        validate_string_list(
            findings,
            gate.get("evidenceRefs"),
            "invalid_release_gate_evidence",
            f"releaseGates item {index}.evidenceRefs",
        )


def _validate_cross_fields(findings, binding, epic, completion, gates):
    if isinstance(epic, dict) and isinstance(completion, dict):
        if epic.get("id") != completion.get("epicId"):
            findings.append(
                handoff_finding(
                    "completion_epic_mismatch",
                    "completion.epicId must equal epic.id.",
                )
            )
    if (
        isinstance(binding, dict)
        and isinstance(completion, dict)
        and completion.get("implemented") is True
        and binding.get("headSha") != completion.get("exactRevision")
    ):
        findings.append(
            handoff_finding(
                "completion_revision_mismatch",
                "The implemented revision must equal binding.headSha.",
            )
        )
    if not isinstance(gates, list) or not isinstance(completion, dict):
        return
    open_overall = [
        gate for gate in gates
        if isinstance(gate, dict)
        and gate.get("blocksOverallCompletion") is True
        and gate.get("status") not in {"pass", "not-applicable"}
    ]
    if completion.get("complete") is True and open_overall:
        findings.append(
            handoff_finding(
                "contradictory_completion_projection",
                "Complete state cannot retain an open overall-completion "
                "release gate.",
            )
        )
    if completion.get("complete") is True and completion.get("pendingGates"):
        findings.append(
            handoff_finding(
                "contradictory_completion_projection",
                "Complete state cannot retain pending gates.",
            )
        )
    if (
        completion.get("complete") is not True
        and not completion.get("pendingGates")
    ):
        findings.append(
            handoff_finding(
                "contradictory_completion_projection",
                "An incomplete state must name at least one pending gate.",
            )
        )


def validate_run_merge_handoff(data):
    findings = []
    if not isinstance(data, dict):
        return [
            handoff_finding(
                "invalid_run_projection",
                "Run projection must be a JSON object.",
            )
        ]
    _validate_run_identity(findings, data)
    binding = data.get("binding")
    epic = data.get("epic")
    completion = data.get("completion")
    gates = data.get("releaseGates")
    _validate_run_binding(findings, binding)
    _validate_epic(findings, epic)
    validate_accepted_criteria(findings, data.get("acceptedCriteria"))
    validate_string_list(
        findings, data.get("changedPaths"), "invalid_changed_paths",
        "changedPaths",
    )
    validate_string_list(
        findings, data.get("verificationReceipts"),
        "invalid_verification_receipts", "verificationReceipts",
        allow_empty=False,
    )
    _validate_completion(findings, completion)
    _validate_deferrals(findings, data.get("deferrals"))
    _validate_release_gates(findings, gates)
    _validate_cross_fields(findings, binding, epic, completion, gates)
    if has_secret(json.dumps(data, sort_keys=True)):
        findings.append(
            handoff_finding(
                "secret_like_run_projection",
                "Run projection contains secret-like content.",
            )
        )
    return findings


def validate_merge_handoff(data):
    if isinstance(data, dict) and data.get("schemaVersion") == "3.0":
        return validate_run_merge_handoff(data)
    return validate_handoff_v1_fields(data)


def merge_binding_digest(data):
    return hashlib.sha256(
        json.dumps(
            data["binding"], sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
