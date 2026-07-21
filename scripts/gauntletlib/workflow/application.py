"""Stateless services for optional exact-design proof contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .contracts import (
    ContractError,
    _validate_contract,
    accept_design,
    bind_candidate_revision,
    completion_status,
    parse_revision_evidence,
    record_verdict,
)

PREBUILD_LENSES = (
    "product",
    "engineering",
    "design",
    "analytics",
    "qa",
    "performance",
)
TERMINAL_DISPOSITIONS = ("accepted", "rejected", "deferred", "omitted")


def _nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{label} must be a non-empty string")
    return value.strip()


def _review_design_binding(value):
    if not isinstance(value, Mapping):
        raise ContractError("review design binding must be an object")
    if {"designId", "sourcePath", "sourceSha256", "acceptanceSha256"}.issubset(value):
        return {
            "identity": value["designId"],
            "reference": value["sourcePath"],
            "sha256": value["sourceSha256"],
            "acceptanceSha256": value["acceptanceSha256"],
        }
    required = {"identity", "reference", "sha256", "acceptanceSha256"}
    if required.issubset(value):
        return {key: value[key] for key in required}
    raise ContractError("review design binding is incomplete")


def _same_digest(left, right):
    return str(left).removeprefix("sha256:") == str(right).removeprefix("sha256:")


def validate_prebuild_reviews(accepted_design, review_results):
    if isinstance(review_results, (str, bytes)) or not isinstance(review_results, Sequence):
        raise ContractError("pre-build reviews must be an array")
    if len(review_results) != len(PREBUILD_LENSES):
        raise ContractError("exactly six pre-build lens results are required")
    by_lens = {}
    finding_ids = set()
    for result in review_results:
        if not isinstance(result, Mapping):
            raise ContractError("each lens result must be an object")
        lens = result.get("lens")
        if lens not in PREBUILD_LENSES or lens in by_lens:
            raise ContractError("all six lenses must appear exactly once")
        _nonempty(result.get("reviewer"), f"{lens} reviewer")
        binding = _review_design_binding(result.get("design"))
        if (
            binding["identity"] != accepted_design["identity"]
            or binding["reference"] != accepted_design["reference"]
            or not _same_digest(binding["sha256"], accepted_design["sha256"])
            or not _same_digest(
                binding["acceptanceSha256"], accepted_design["acceptanceSha256"]
            )
        ):
            raise ContractError(f"{lens} review is stale or bound to another design")
        applicability = result.get("applicability")
        if applicability not in {"applicable", "not-applicable"}:
            raise ContractError(f"{lens} applicability is unsupported")
        reason = result.get("applicabilityReason")
        if applicability == "not-applicable":
            _nonempty(reason, f"{lens} applicability reason")
        elif reason is not None:
            raise ContractError(f"{lens} applicabilityReason must be null when applicable")
        findings = result.get("findings")
        if isinstance(findings, (str, bytes)) or not isinstance(findings, Sequence):
            raise ContractError(f"{lens} findings must be an array")
        material = 0
        for finding in findings:
            if not isinstance(finding, Mapping):
                raise ContractError(f"{lens} finding must be an object")
            identity = _nonempty(finding.get("identity"), f"{lens} finding identity")
            if identity in finding_ids:
                raise ContractError(f"duplicate finding identity: {identity}")
            finding_ids.add(identity)
            if not isinstance(finding.get("material"), bool):
                raise ContractError(f"{identity} must declare material")
            if not finding["material"]:
                continue
            material += 1
            disposition = finding.get("disposition")
            if disposition not in TERMINAL_DISPOSITIONS:
                raise ContractError(f"{identity} has unresolved disposition")
            if disposition in {"deferred", "omitted", "rejected"}:
                _nonempty(finding.get("reason"), f"{identity} disposition reason")
        if result.get("materialFindingCount") != material:
            raise ContractError(f"{lens} materialFindingCount is inaccurate")
        by_lens[lens] = result
    return {
        "lenses": list(PREBUILD_LENSES),
        "reviewerMode": "main-agent",
        "materialFindings": sum(item["materialFindingCount"] for item in by_lens.values()),
    }


def build_entry(*, project_root, design, review_results, accepted_design_reader):
    accepted = accepted_design_reader(project_root, design)
    summary = validate_prebuild_reviews(accepted, review_results)
    contract = accept_design(
        identity=accepted["identity"],
        reference=accepted["reference"],
        design_sha256=accepted["sha256"],
        acceptance_sha256=accepted["acceptanceSha256"],
        outcomes=accepted["outcomes"],
        contract_applicability=accepted["contractApplicability"],
    )
    return {"contract": contract, "prebuildReview": summary}


def authorize_candidate(
    *, project_root, design, review_results, contract, commit, tree, base,
    accepted_design_reader, git_repository
):
    authorized = build_entry(
        project_root=project_root,
        design=design,
        review_results=review_results,
        accepted_design_reader=accepted_design_reader,
    )["contract"]
    if contract != authorized:
        raise ContractError("candidate contract does not match the current proof entry")
    resolved = git_repository.resolve_candidate(project_root, commit, tree, base)
    return bind_candidate_revision(contract, **resolved)


def verify_entry(*, project_root, design, contract, accepted_design_reader):
    _validate_contract(contract)
    accepted = accepted_design_reader(project_root, design)
    if contract["acceptedDesign"] != accepted:
        raise ContractError("workflow contract is stale or bound to another design")
    if contract["candidateRevision"] is None:
        raise ContractError("Verify requires an exact candidate revision")
    return {
        "acceptedDesign": accepted,
        "candidateRevision": contract["candidateRevision"],
    }


def _resolve_references(project_root, revision, references, git_repository):
    for reference in references:
        parsed = parse_revision_evidence(reference)
        if parsed is None or parsed[0] != revision["commit"]:
            raise ContractError("evidence reference does not bind the candidate commit")
        git_repository.resolve_evidence(
            project_root, parsed[0], "path:" + parsed[1]
        )


def record_verification_verdict(
    *, project_root, design, contract, area, verdict, evidence,
    accepted_design_reader, git_repository
):
    verify_entry(
        project_root=project_root,
        design=design,
        contract=contract,
        accepted_design_reader=accepted_design_reader,
    )
    if not isinstance(evidence, Mapping):
        raise ContractError("verdict evidence must be an object")
    revision = contract["candidateRevision"]
    if area == "build":
        results = evidence.get("outcomeResults")
        if not isinstance(results, Mapping):
            raise ContractError("Build evidence requires outcomeResults")
        for result in results.values():
            if isinstance(result, Mapping):
                _resolve_references(
                    project_root, revision, result.get("evidence", []), git_repository
                )
        return record_verdict(
            contract, area=area, verdict=verdict, outcome_results=results
        )
    references = evidence.get("evidence", [])
    _resolve_references(project_root, revision, references, git_repository)
    return record_verdict(
        contract,
        area=area,
        verdict=verdict,
        evidence=references,
        remaining_check=evidence.get("remainingCheck"),
    )


def completion_check(*, project_root, design, contract, accepted_design_reader):
    verify_entry(
        project_root=project_root,
        design=design,
        contract=contract,
        accepted_design_reader=accepted_design_reader,
    )
    return completion_status(contract)
