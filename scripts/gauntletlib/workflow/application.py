"""Stateless application services for Design-to-Build-to-Verify gates."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .contracts import (
    ContractError,
    _validate_contract,
    accept_design,
    bind_candidate_revision,
    completion_status,
    record_verdict,
)


PREBUILD_LENSES = (
    "product-completeness",
    "engineering-shape",
    "proof-and-consequence",
)
TERMINAL_DISPOSITIONS = ("accepted", "rejected", "deferred", "omitted")


def _nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{label} must be a non-empty string")
    return value.strip()


def _review_design_binding(value):
    if not isinstance(value, Mapping):
        raise ContractError("review design binding must be an object")
    if {
        "designId",
        "sourcePath",
        "sourceSha256",
        "acceptanceSha256",
    }.issubset(value):
        return {
            "identity": value["designId"],
            "reference": value["sourcePath"],
            "sha256": value["sourceSha256"],
            "acceptanceSha256": value["acceptanceSha256"],
        }
    if {"epicId", "sourcePath", "sourceSha256"}.issubset(value):
        return {
            "identity": value["epicId"],
            "reference": value["sourcePath"],
            "sha256": value["sourceSha256"],
            "acceptanceSha256": value.get("acceptanceSha256"),
        }
    required = {"identity", "reference", "sha256", "acceptanceSha256"}
    if required.issubset(value):
        return {key: value[key] for key in required}
    raise ContractError("review design binding is incomplete")


def _same_digest(left, right):
    return str(left).removeprefix("sha256:") == str(right).removeprefix("sha256:")


def validate_prebuild_reviews(accepted_design, review_results):
    """Validate all three independent result sets without persisting review state."""

    if isinstance(review_results, (str, bytes)) or not isinstance(
        review_results, Sequence
    ):
        raise ContractError("pre-build reviews must be an array")
    if len(review_results) != len(PREBUILD_LENSES):
        raise ContractError("exactly three independent pre-build reviews are required")
    by_lens = {}
    reviewers = set()
    finding_ids = set()
    for result in review_results:
        if not isinstance(result, Mapping):
            raise ContractError("each pre-build review must be an object")
        lens = result.get("lens")
        if lens not in PREBUILD_LENSES or lens in by_lens:
            raise ContractError("pre-build review lenses must each appear exactly once")
        reviewer = _nonempty(result.get("reviewer"), f"{lens} reviewer")
        if reviewer in reviewers:
            raise ContractError("pre-build review lenses require independent reviewers")
        reviewers.add(reviewer)
        binding = _review_design_binding(result.get("design"))
        if (
            binding["identity"] != accepted_design["identity"]
            or binding["reference"] != accepted_design["reference"]
            or not _same_digest(binding["sha256"], accepted_design["sha256"])
            or (
                binding["acceptanceSha256"] is not None
                and not _same_digest(
                    binding["acceptanceSha256"],
                    accepted_design["acceptanceSha256"],
                )
            )
        ):
            raise ContractError(f"{lens} review is stale or bound to another design")
        findings = result.get("findings")
        if isinstance(findings, (str, bytes)) or not isinstance(findings, Sequence):
            raise ContractError(f"{lens} findings must be an array")
        material_count = result.get("materialFindingCount")
        observed_material = 0
        for finding in findings:
            if not isinstance(finding, Mapping):
                raise ContractError(f"{lens} finding must be an object")
            identity = _nonempty(finding.get("identity"), f"{lens} finding identity")
            if identity in finding_ids:
                raise ContractError(f"duplicate material finding identity: {identity}")
            finding_ids.add(identity)
            if not isinstance(finding.get("material"), bool):
                raise ContractError(f"{identity} must declare whether it is material")
            if not finding["material"]:
                continue
            observed_material += 1
            disposition = finding.get("disposition")
            if disposition not in TERMINAL_DISPOSITIONS:
                raise ContractError(
                    f"{identity} has an unresolved material disposition"
                )
            if disposition in {"deferred", "omitted"}:
                _nonempty(finding.get("reason"), f"{identity} disposition reason")
        if (
            not isinstance(material_count, int)
            or isinstance(material_count, bool)
            or material_count < 0
            or material_count != observed_material
        ):
            raise ContractError(
                f"{lens} materialFindingCount must cover every material finding"
            )
        by_lens[lens] = result
    return {
        "lenses": list(PREBUILD_LENSES),
        "reviewers": len(reviewers),
        "materialFindings": sum(
            item["materialFindingCount"] for item in by_lens.values()
        ),
    }


def build_entry(
    *,
    project_root,
    design,
    review_results,
    accepted_design_reader,
):
    """Open Build only for a current accepted design and resolved three-lens review."""

    accepted = accepted_design_reader(project_root, design)
    review_summary = validate_prebuild_reviews(accepted, review_results)
    contract = accept_design(
        identity=accepted["identity"],
        reference=accepted["reference"],
        design_sha256=accepted["sha256"],
        acceptance_sha256=accepted["acceptanceSha256"],
        outcomes=accepted["outcomes"],
    )
    return {"contract": contract, "prebuildReview": review_summary}


def authorize_candidate(
    *,
    project_root,
    design,
    review_results,
    contract,
    commit,
    tree,
    accepted_design_reader,
):
    """Re-run the ephemeral Build gate before binding an exact candidate."""

    authorized = build_entry(
        project_root=project_root,
        design=design,
        review_results=review_results,
        accepted_design_reader=accepted_design_reader,
    )["contract"]
    if contract != authorized:
        raise ContractError(
            "candidate contract does not match the current authorized Build entry"
        )
    return bind_candidate_revision(contract, commit=commit, tree=tree)


def verify_entry(
    *,
    project_root,
    design,
    contract,
    accepted_design_reader,
):
    """Validate the current accepted source and exact candidate before Verify."""

    _validate_contract(contract)
    accepted = accepted_design_reader(project_root, design)
    if contract["acceptedDesign"] != accepted:
        raise ContractError(
            "workflow contract is stale or bound to another accepted design"
        )
    if contract["candidateRevision"] is None:
        raise ContractError("Verify requires an exact candidate revision")
    return {
        "acceptedDesign": accepted,
        "candidateRevision": contract["candidateRevision"],
    }


def record_verification_verdict(
    *,
    project_root,
    design,
    contract,
    area,
    verdict,
    evidence,
    accepted_design_reader,
):
    """Record one source-validated exact-candidate verdict."""

    verify_entry(
        project_root=project_root,
        design=design,
        contract=contract,
        accepted_design_reader=accepted_design_reader,
    )
    if not isinstance(evidence, Mapping):
        raise ContractError("verdict evidence must be an object")
    accepted = contract["acceptedDesign"]
    revision = contract["candidateRevision"]
    return record_verdict(
        contract,
        area=area,
        verdict=verdict,
        design_identity=accepted["identity"],
        design_reference=accepted["reference"],
        design_sha256=accepted["sha256"],
        commit=revision["commit"],
        tree=revision["tree"],
        read_design_directly=True,
        direct_evidence=evidence.get("directEvidence", []),
        derivative_evidence=evidence.get("derivativeEvidence", []),
        outcome_evidence=evidence.get("outcomeEvidence", {}),
    )


def completion_check(
    *,
    project_root,
    design,
    contract,
    accepted_design_reader,
):
    """Evaluate the production completion path after revalidating its source."""

    verify_entry(
        project_root=project_root,
        design=design,
        contract=contract,
        accepted_design_reader=accepted_design_reader,
    )
    return completion_status(contract)
