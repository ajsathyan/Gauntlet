"""Bind accepted design intent and independent proof to one candidate revision.

The public values are plain JSON-compatible dictionaries.  The module does not
own execution or persistence; it only establishes and evaluates the contract.
The accepted source and candidate revision remain separate bindings.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping, Sequence


CONTRACT_SCHEMA = "gauntlet.workflow-contract.v1"
VERDICT_SCHEMA = "gauntlet.workflow-verdict.v1"
VERDICT_AREAS = ("build", "architecture", "sensor")
VERDICTS_BY_AREA = {
    "build": ("pass", "fail", "cannot-verify"),
    "architecture": ("pass", "fail", "not-applicable", "cannot-verify"),
    "sensor": ("pass", "fail", "not-applicable", "cannot-verify"),
}
_OBJECT_ID = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?").fullmatch
_SHA256 = re.compile(r"(?:sha256:)?[0-9a-f]{64}").fullmatch
_REVISION_EVIDENCE = re.compile(
    r"revision:([0-9a-f]{40}(?:[0-9a-f]{24})?)#([^\s#]+)"
).fullmatch


class ContractError(ValueError):
    """The design or verification value violates the workflow contract."""


def parse_revision_evidence(reference):
    """Return the exact commit and locator from a mechanical evidence reference."""

    if not isinstance(reference, str):
        return None
    match = _REVISION_EVIDENCE(reference.strip())
    return (match.group(1), match.group(2)) if match else None


def _object_id(value, label):
    if not isinstance(value, str) or _OBJECT_ID(value) is None:
        raise ContractError(f"{label} must be an exact 40- or 64-character Git object ID")
    return value


def _design_sha256(value):
    if not isinstance(value, str) or _SHA256(value) is None:
        raise ContractError("design_sha256 must be a SHA-256 digest")
    return value if value.startswith("sha256:") else "sha256:" + value


def _outcome_bindings(value):
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ContractError("accepted design outcomes must be an array")
    result = []
    identities = set()
    for item in value:
        item = _closed_object(
            item,
            ("identity", "sha256"),
            "accepted outcome binding",
        )
        identity = _nonempty(item["identity"], "accepted outcome identity")
        if identity in identities:
            raise ContractError("accepted outcome identities must be unique")
        identities.add(identity)
        result.append(
            {
                "identity": identity,
                "sha256": _design_sha256(item["sha256"]),
            }
        )
    if not result:
        raise ContractError("accepted design outcomes must not be empty")
    return result


def _contract_applicability(value):
    value = _closed_object(
        value,
        ("architecture", "sensor"),
        "contract applicability",
    )
    result = {}
    for area, binding in value.items():
        binding = _closed_object(
            binding,
            ("applicable", "sha256"),
            f"{area} contract binding",
        )
        if not isinstance(binding["applicable"], bool):
            raise ContractError(f"{area} contract applicable must be boolean")
        digest = binding["sha256"]
        if binding["applicable"]:
            digest = _design_sha256(digest)
        elif digest is not None:
            raise ContractError(
                f"{area} contract digest must be null when not applicable"
            )
        result[area] = {"applicable": binding["applicable"], "sha256": digest}
    return result


def _strings(value, label, *, allow_empty):
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ContractError(f"{label} must be a string array")
    result = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ContractError(f"{label} must contain only non-empty strings")
        result.append(item.strip())
    if not allow_empty and not result:
        raise ContractError(f"{label} must not be empty")
    return result


def _closed_object(value, keys, label):
    if not isinstance(value, Mapping) or set(value) != set(keys):
        raise ContractError(f"{label} has an unsupported shape")
    return value


def _validate_verdict(receipt, design):
    receipt = _closed_object(
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
            "acceptedDesignReadDirectly",
            "directEvidence",
            "derivativeEvidence",
            "outcomeEvidence",
        ),
        "verification verdict",
    )
    if receipt["schemaVersion"] != VERDICT_SCHEMA:
        raise ContractError("verification verdict schema is unsupported")
    if receipt["area"] not in VERDICT_AREAS:
        raise ContractError("verification verdict area is unsupported")
    if receipt["verdict"] not in VERDICTS_BY_AREA[receipt["area"]]:
        raise ContractError(
            f"{receipt['area']} verdict must be one of "
            + ", ".join(VERDICTS_BY_AREA[receipt["area"]])
        )
    if (
        receipt["area"] in {"architecture", "sensor"}
        and receipt["verdict"] == "not-applicable"
        and design["contractApplicability"][receipt["area"]]["applicable"]
    ):
        raise ContractError(
            f"{receipt['area']} verdict cannot be not-applicable because the "
            "accepted design contains that contract"
        )
    design_binding = {
        "identity": _nonempty(receipt["designIdentity"], "verification design identity"),
        "reference": _nonempty(
            receipt["designReference"],
            "verification design reference",
        ),
        "sha256": _design_sha256(receipt["designSha256"]),
        "acceptanceSha256": _design_sha256(receipt["acceptanceSha256"]),
        "outcomes": design["outcomes"],
        "contractApplicability": design["contractApplicability"],
    }
    if design_binding != design:
        raise ContractError(
            "verification verdict does not match the accepted design"
        )
    if receipt["acceptedDesignReadDirectly"] is not True:
        raise ContractError(
            "verification verdict must attest that it read the accepted design directly"
        )
    revision_binding = {
        "commit": _object_id(receipt["commit"], "verification commit"),
        "tree": _object_id(receipt["tree"], "verification tree"),
    }
    _strings(receipt["directEvidence"], "directEvidence", allow_empty=True)
    _strings(receipt["derivativeEvidence"], "derivativeEvidence", allow_empty=True)
    evidence = receipt["outcomeEvidence"]
    if not isinstance(evidence, Mapping):
        raise ContractError("outcomeEvidence must be an object")
    accepted_identities = {item["identity"] for item in design["outcomes"]}
    if not set(evidence).issubset(accepted_identities):
        raise ContractError("outcomeEvidence identifies an unaccepted outcome")
    evidence_references = []
    for identity, observations in evidence.items():
        references = _strings(
            observations,
            f"outcomeEvidence[{identity}]",
            allow_empty=False,
        )
        for reference in references:
            parsed = parse_revision_evidence(reference)
            if parsed is None or parsed[0] != revision_binding["commit"]:
                raise ContractError(
                    f"outcomeEvidence[{identity}] must contain resolvable "
                    "exact-revision evidence references"
                )
            evidence_references.append(reference)
    if receipt["area"] != "build" and evidence:
        raise ContractError("only the Build verdict may contain outcomeEvidence")
    if (
        receipt["area"] == "build"
        and receipt["verdict"] == "pass"
        and set(evidence) != accepted_identities
    ):
        raise ContractError(
            "a passing Build verdict requires direct evidence for every accepted outcome"
        )
    if (
        receipt["area"] == "build"
        and receipt["verdict"] == "pass"
        and len(evidence_references) != len(set(evidence_references))
    ):
        raise ContractError(
            "a passing Build verdict requires unique evidence references per outcome"
        )
    return revision_binding


def _nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{label} must be a non-empty string")
    return value.strip()


def _validate_contract(contract):
    contract = _closed_object(
        contract,
        (
            "schemaVersion",
            "acceptedDesign",
            "candidateRevision",
            "verdicts",
        ),
        "workflow contract",
    )
    if contract["schemaVersion"] != CONTRACT_SCHEMA:
        raise ContractError("workflow contract schema is unsupported")
    design = _closed_object(
        contract["acceptedDesign"],
        (
            "identity",
            "reference",
            "sha256",
            "acceptanceSha256",
            "outcomes",
            "contractApplicability",
        ),
        "accepted design binding",
    )
    normalized_design = {
        "identity": _nonempty(design["identity"], "accepted design identity"),
        "reference": _nonempty(design["reference"], "accepted design reference"),
        "sha256": _design_sha256(design["sha256"]),
        "acceptanceSha256": _design_sha256(design["acceptanceSha256"]),
        "outcomes": _outcome_bindings(design["outcomes"]),
        "contractApplicability": _contract_applicability(
            design["contractApplicability"]
        ),
    }
    revision = contract["candidateRevision"]
    if revision is not None:
        revision = _closed_object(
            revision,
            ("commit", "tree"),
            "candidate revision binding",
        )
        normalized_revision = {
            "commit": _object_id(revision["commit"], "candidate commit"),
            "tree": _object_id(revision["tree"], "candidate tree"),
        }
    else:
        normalized_revision = None
    verdicts = _closed_object(
        contract["verdicts"],
        VERDICT_AREAS,
        "workflow verdicts",
    )
    for area, receipt in verdicts.items():
        if receipt is None:
            continue
        receipt_revision = _validate_verdict(receipt, normalized_design)
        if receipt["area"] != area:
            raise ContractError("verification verdict is stored under the wrong area")
        if normalized_revision is None or receipt_revision != normalized_revision:
            raise ContractError(
                "verification verdict does not match the exact candidate revision"
            )
    return contract


def accept_design(
    *,
    identity,
    reference,
    design_sha256,
    acceptance_sha256,
    outcomes,
    contract_applicability,
):
    """Create a contract pointing directly to one accepted design source."""

    contract = {
        "schemaVersion": CONTRACT_SCHEMA,
        "acceptedDesign": {
            "identity": _nonempty(identity, "accepted design identity"),
            "reference": _nonempty(reference, "accepted design reference"),
            "sha256": _design_sha256(design_sha256),
            "acceptanceSha256": _design_sha256(acceptance_sha256),
            "outcomes": _outcome_bindings(outcomes),
            "contractApplicability": _contract_applicability(
                contract_applicability
            ),
        },
        "candidateRevision": None,
        "verdicts": {area: None for area in VERDICT_AREAS},
    }
    _validate_contract(contract)
    return contract


def bind_candidate_revision(contract, *, commit, tree):
    """Return a copy bound to the exact candidate revision under verification."""

    _validate_contract(contract)
    if any(receipt is not None for receipt in contract["verdicts"].values()):
        raise ContractError(
            "candidate revision cannot change after verification has been recorded"
        )
    revision = {
        "commit": _object_id(commit, "candidate commit"),
        "tree": _object_id(tree, "candidate tree"),
    }
    if contract["candidateRevision"] is not None:
        if contract["candidateRevision"] == revision:
            return copy.deepcopy(contract)
        raise ContractError("workflow contract is already bound to another candidate")
    updated = copy.deepcopy(contract)
    updated["candidateRevision"] = revision
    return updated


def record_verdict(
    contract,
    *,
    area,
    verdict,
    design_identity,
    design_reference,
    design_sha256,
    commit,
    tree,
    read_design_directly,
    direct_evidence,
    derivative_evidence=(),
    outcome_evidence=None,
):
    """Return a copy with one independently bound verification verdict.

    Derived summaries may accompany proof but cannot stand in for a direct
    observation of the applicable oracle.
    """

    _validate_contract(contract)
    if area not in VERDICT_AREAS:
        raise ContractError("area must be build, architecture, or sensor")
    if verdict not in VERDICTS_BY_AREA[area]:
        raise ContractError(
            f"{area} verdict must be one of "
            + ", ".join(VERDICTS_BY_AREA[area])
        )
    if contract["candidateRevision"] is None:
        raise ContractError(
            "candidate revision must be bound before verification is recorded"
        )
    direct = _strings(direct_evidence, "direct_evidence", allow_empty=True)
    derivative = _strings(
        derivative_evidence,
        "derivative_evidence",
        allow_empty=True,
    )
    if not direct:
        raise ContractError(
            "a verification verdict requires direct evidence; derivative-only "
            "evidence is insufficient"
        )
    if outcome_evidence is None:
        outcome_evidence = {}
    if not isinstance(outcome_evidence, Mapping):
        raise ContractError("outcome_evidence must be an object")
    normalized_outcome_evidence = {
        _nonempty(identity, "outcome evidence identity"): _strings(
            observations,
            f"outcome_evidence[{identity}]",
            allow_empty=False,
        )
        for identity, observations in outcome_evidence.items()
    }
    receipt = {
        "schemaVersion": VERDICT_SCHEMA,
        "area": area,
        "verdict": verdict,
        "designIdentity": _nonempty(
            design_identity,
            "verification design identity",
        ),
        "designReference": _nonempty(
            design_reference,
            "verification design reference",
        ),
        "designSha256": _design_sha256(design_sha256),
        "acceptanceSha256": contract["acceptedDesign"]["acceptanceSha256"],
        "commit": _object_id(commit, "verification commit"),
        "tree": _object_id(tree, "verification tree"),
        "acceptedDesignReadDirectly": read_design_directly,
        "directEvidence": direct,
        "derivativeEvidence": derivative,
        "outcomeEvidence": normalized_outcome_evidence,
    }
    receipt_revision = _validate_verdict(receipt, contract["acceptedDesign"])
    if receipt_revision != contract["candidateRevision"]:
        raise ContractError(
            "verification verdict does not match the exact candidate revision"
        )
    updated = copy.deepcopy(contract)
    updated["verdicts"][area] = receipt
    return updated


def completion_status(contract):
    """Evaluate completion without allowing Sensor proof to imply Build proof."""

    _validate_contract(contract)
    reasons = []
    states = {}
    for area in VERDICT_AREAS:
        receipt = contract["verdicts"][area]
        if receipt is None:
            states[area] = "absent"
            reasons.append(f"{area} verdict is absent")
        elif not receipt["directEvidence"]:
            states[area] = "unproved"
            reasons.append(f"{area} verdict is unproved")
        elif receipt["verdict"] == "cannot-verify":
            states[area] = "cannot-verify"
            reasons.append(f"{area} could not be verified")
        elif receipt["verdict"] == "fail":
            states[area] = "fail"
            reasons.append(f"{area} verdict did not pass")
        else:
            states[area] = receipt["verdict"]
    return {
        "complete": not reasons,
        "status": "complete" if not reasons else "incomplete",
        "verdicts": states,
        "reasons": reasons,
    }
