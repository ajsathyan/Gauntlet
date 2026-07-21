"""Optional exact-design and exact-revision workflow contracts."""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping, Sequence

CONTRACT_SCHEMA = "gauntlet.workflow-contract.v2"
VERDICT_SCHEMA = "gauntlet.workflow-verdict.v2"
AREAS = ("build", "architecture")
OBJECT_ID = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?").fullmatch
SHA256 = re.compile(r"(?:sha256:)?[0-9a-f]{64}").fullmatch
REVISION_EVIDENCE = re.compile(
    r"revision:([0-9a-f]{40}(?:[0-9a-f]{24})?)#path:([^\s#]+)"
).fullmatch


class ContractError(ValueError):
    pass


def _closed(value, keys, label):
    if not isinstance(value, Mapping) or set(value) != set(keys):
        raise ContractError(f"{label} has an unsupported shape")
    return value


def _nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{label} must be a non-empty string")
    return value.strip()


def _object_id(value, label):
    if not isinstance(value, str) or OBJECT_ID(value) is None:
        raise ContractError(f"{label} must be an exact Git object ID")
    return value


def _digest(value, label="digest"):
    if not isinstance(value, str) or SHA256(value) is None:
        raise ContractError(f"{label} must be a SHA-256 digest")
    return value if value.startswith("sha256:") else "sha256:" + value


def _strings(value, label, *, allow_empty=True):
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ContractError(f"{label} must be a string array")
    result = [_nonempty(item, label) for item in value]
    if not allow_empty and not result:
        raise ContractError(f"{label} must not be empty")
    return result


def parse_revision_evidence(reference):
    if not isinstance(reference, str):
        return None
    match = REVISION_EVIDENCE(reference.strip())
    return (match.group(1), match.group(2)) if match else None


def _outcomes(value):
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ContractError("accepted outcomes must be an array")
    result = []
    seen = set()
    for item in value:
        item = _closed(item, ("identity", "sha256"), "accepted outcome")
        identity = _nonempty(item["identity"], "accepted outcome identity")
        if identity in seen:
            raise ContractError("accepted outcome identities must be unique")
        seen.add(identity)
        result.append({"identity": identity, "sha256": _digest(item["sha256"])})
    if not result:
        raise ContractError("accepted outcomes must not be empty")
    return result


def _applicability(value):
    value = _closed(value, ("architecture",), "contract applicability")
    binding = _closed(
        value["architecture"], ("applicable", "sha256"), "architecture binding"
    )
    if not isinstance(binding["applicable"], bool):
        raise ContractError("architecture applicable must be boolean")
    digest = binding["sha256"]
    if binding["applicable"]:
        digest = _digest(digest, "architecture digest")
    elif digest is not None:
        raise ContractError("architecture digest must be null when not applicable")
    return {"architecture": {"applicable": binding["applicable"], "sha256": digest}}


def _design(value):
    value = _closed(
        value,
        (
            "identity",
            "reference",
            "sha256",
            "acceptanceSha256",
            "outcomes",
            "contractApplicability",
        ),
        "accepted design",
    )
    return {
        "identity": _nonempty(value["identity"], "design identity"),
        "reference": _nonempty(value["reference"], "design reference"),
        "sha256": _digest(value["sha256"], "design digest"),
        "acceptanceSha256": _digest(value["acceptanceSha256"], "acceptance digest"),
        "outcomes": _outcomes(value["outcomes"]),
        "contractApplicability": _applicability(value["contractApplicability"]),
    }


def _revision(value):
    value = _closed(value, ("commit", "tree", "base"), "candidate revision")
    return {
        "commit": _object_id(value["commit"], "candidate commit"),
        "tree": _object_id(value["tree"], "candidate tree"),
        "base": _object_id(value["base"], "checked base"),
    }


def _outcome_results(value, accepted, revision):
    if not isinstance(value, Mapping) or set(value) != accepted:
        raise ContractError("Build outcomeResults must cover every accepted outcome exactly")
    result = {}
    evidence_seen = set()
    for identity, item in value.items():
        item = _closed(
            item,
            ("behavior", "proofAvailability", "evidence", "remainingCheck"),
            f"outcomeResults[{identity}]",
        )
        behavior = item["behavior"]
        availability = item["proofAvailability"]
        if behavior not in {"passed", "failed", "unknown"}:
            raise ContractError(f"{identity} behavior is unsupported")
        if availability not in {"available", "unavailable"}:
            raise ContractError(f"{identity} proofAvailability is unsupported")
        evidence = _strings(item["evidence"], f"{identity} evidence")
        for reference in evidence:
            parsed = parse_revision_evidence(reference)
            if parsed is None or parsed[0] != revision["commit"]:
                raise ContractError(f"{identity} evidence must bind the candidate commit")
            if reference in evidence_seen:
                raise ContractError("Build evidence references must be unique per outcome")
            evidence_seen.add(reference)
        remaining = item["remainingCheck"]
        if behavior == "passed" and availability == "available" and not evidence:
            raise ContractError(f"{identity} passed outcome requires evidence")
        unresolved = behavior == "unknown" or availability == "unavailable"
        if unresolved:
            remaining = _nonempty(remaining, f"{identity} remainingCheck")
        elif remaining is not None:
            raise ContractError(f"{identity} remainingCheck must be null when resolved")
        result[identity] = {
            "behavior": behavior,
            "proofAvailability": availability,
            "evidence": evidence,
            "remainingCheck": remaining,
        }
    return result


def derive_build_verdict(outcome_results):
    if any(item["behavior"] == "failed" for item in outcome_results.values()):
        return "failed"
    if any(
        item["behavior"] == "unknown" or item["proofAvailability"] == "unavailable"
        for item in outcome_results.values()
    ):
        return "blocked"
    return "passed"


def _validate_receipt(receipt, design, revision, area):
    if area == "build":
        receipt = _closed(
            receipt,
            (
                "schemaVersion",
                "area",
                "verdict",
                "designIdentity",
                "designReference",
                "designSha256",
                "acceptanceSha256",
                "commit",
                "tree",
                "base",
                "acceptedDesignReadDirectly",
                "outcomeResults",
            ),
            "Build verdict",
        )
    else:
        receipt = _closed(
            receipt,
            (
                "schemaVersion",
                "area",
                "verdict",
                "designIdentity",
                "designReference",
                "designSha256",
                "acceptanceSha256",
                "commit",
                "tree",
                "base",
                "acceptedDesignReadDirectly",
                "evidence",
                "remainingCheck",
            ),
            "Architecture verdict",
        )
    if receipt["schemaVersion"] != VERDICT_SCHEMA or receipt["area"] != area:
        raise ContractError("verification verdict schema or area is unsupported")
    if {
        "identity": receipt["designIdentity"],
        "reference": receipt["designReference"],
        "sha256": receipt["designSha256"],
        "acceptanceSha256": receipt["acceptanceSha256"],
        "outcomes": design["outcomes"],
        "contractApplicability": design["contractApplicability"],
    } != design:
        raise ContractError("verification verdict does not match the accepted design")
    if receipt["acceptedDesignReadDirectly"] is not True:
        raise ContractError("Verify must read the accepted design directly")
    bound = _revision(
        {"commit": receipt["commit"], "tree": receipt["tree"], "base": receipt["base"]}
    )
    if bound != revision:
        raise ContractError("verification verdict does not match the candidate revision")

    if area == "build":
        accepted = {item["identity"] for item in design["outcomes"]}
        results = _outcome_results(receipt["outcomeResults"], accepted, revision)
        if receipt["verdict"] != derive_build_verdict(results):
            raise ContractError("Build verdict does not match its outcome results")
    else:
        verdict = receipt["verdict"]
        if verdict not in {"passed", "failed", "blocked", "not-applicable"}:
            raise ContractError("Architecture verdict is unsupported")
        applicable = design["contractApplicability"]["architecture"]["applicable"]
        if verdict == "not-applicable" and applicable:
            raise ContractError("Architecture is applicable to the accepted design")
        if verdict != "not-applicable" and not applicable:
            raise ContractError("Architecture must be not-applicable")
        evidence = _strings(receipt["evidence"], "Architecture evidence")
        remaining = receipt["remainingCheck"]
        if verdict in {"passed", "failed"} and not evidence:
            raise ContractError("resolved Architecture verdict requires evidence")
        if verdict == "blocked":
            _nonempty(remaining, "Architecture remainingCheck")
        elif remaining is not None:
            raise ContractError("Architecture remainingCheck must be null when resolved")
    return receipt


def _validate_contract(contract):
    contract = _closed(
        contract, ("schemaVersion", "acceptedDesign", "candidateRevision", "verdicts"),
        "workflow contract"
    )
    if contract["schemaVersion"] != CONTRACT_SCHEMA:
        raise ContractError("workflow contract schema is unsupported")
    design = _design(contract["acceptedDesign"])
    revision = None if contract["candidateRevision"] is None else _revision(contract["candidateRevision"])
    verdicts = _closed(contract["verdicts"], AREAS, "workflow verdicts")
    for area, receipt in verdicts.items():
        if receipt is not None:
            if revision is None:
                raise ContractError("verdict exists without a candidate revision")
            _validate_receipt(receipt, design, revision, area)
    return contract


def accept_design(*, identity, reference, design_sha256, acceptance_sha256, outcomes, contract_applicability):
    contract = {
        "schemaVersion": CONTRACT_SCHEMA,
        "acceptedDesign": {
            "identity": _nonempty(identity, "design identity"),
            "reference": _nonempty(reference, "design reference"),
            "sha256": _digest(design_sha256, "design digest"),
            "acceptanceSha256": _digest(acceptance_sha256, "acceptance digest"),
            "outcomes": _outcomes(outcomes),
            "contractApplicability": _applicability(contract_applicability),
        },
        "candidateRevision": None,
        "verdicts": {area: None for area in AREAS},
    }
    _validate_contract(contract)
    return contract


def bind_candidate_revision(contract, *, commit, tree, base):
    _validate_contract(contract)
    if any(contract["verdicts"].values()):
        raise ContractError("candidate cannot change after verification")
    revision = _revision({"commit": commit, "tree": tree, "base": base})
    if contract["candidateRevision"] is not None and contract["candidateRevision"] != revision:
        raise ContractError("contract is already bound to another candidate")
    updated = copy.deepcopy(contract)
    updated["candidateRevision"] = revision
    return updated


def record_verdict(contract, *, area, verdict, outcome_results=None, evidence=(), remaining_check=None):
    _validate_contract(contract)
    if area not in AREAS or contract["candidateRevision"] is None:
        raise ContractError("verdict requires a supported area and bound candidate")
    design = contract["acceptedDesign"]
    revision = contract["candidateRevision"]
    common = {
        "schemaVersion": VERDICT_SCHEMA,
        "area": area,
        "verdict": verdict,
        "designIdentity": design["identity"],
        "designReference": design["reference"],
        "designSha256": design["sha256"],
        "acceptanceSha256": design["acceptanceSha256"],
        **revision,
        "acceptedDesignReadDirectly": True,
    }
    if area == "build":
        common["outcomeResults"] = outcome_results or {}
    else:
        common["evidence"] = list(evidence)
        common["remainingCheck"] = remaining_check
    _validate_receipt(common, design, revision, area)
    updated = copy.deepcopy(contract)
    updated["verdicts"][area] = common
    return updated


def completion_status(contract):
    _validate_contract(contract)
    states = {}
    reasons = []
    for area in AREAS:
        receipt = contract["verdicts"][area]
        if receipt is None:
            states[area] = "absent"
            reasons.append(f"{area} verdict is absent")
            continue
        states[area] = receipt["verdict"]
        if receipt["verdict"] not in {"passed", "not-applicable"}:
            reasons.append(f"{area} verdict is {receipt['verdict']}")
    return {
        "complete": not reasons,
        "status": "complete" if not reasons else "incomplete",
        "verdicts": states,
        "reasons": reasons,
    }
