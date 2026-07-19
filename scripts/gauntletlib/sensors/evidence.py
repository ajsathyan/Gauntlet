"""Tool-neutral sensor evidence and readability receipt validation."""

import json


REWRITE_SCHEMA = "gauntlet.readability-rewrite-evidence/v1"


def command_normalize(args):
    if not args.raw_evidence_ref.strip():
        raise RuntimeError("--raw-evidence-ref must be a non-empty reference")
    payload = {
        "schema": "gauntlet.sensor-result/v1",
        "status": "pass",
        "sensor": args.sensor,
        "result": args.result,
        "rawEvidenceRef": args.raw_evidence_ref,
        "evidenceRefs": sorted(set(args.evidence_ref)),
    }
    if args.command is not None:
        payload["command"] = args.command
    if args.summary is not None:
        payload["summary"] = args.summary
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"{args.sensor}: {args.result}")
    return 0


def _nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def _evidence_refs(value):
    return (
        isinstance(value, list)
        and bool(value)
        and all(_nonempty_string(item) for item in value)
    )


def _validate_behavior_side(value, label, findings):
    if not isinstance(value, dict):
        findings.append(f"{label} must be an object.")
        return None
    identity = value.get("identity")
    if not _nonempty_string(identity):
        findings.append(f"{label}.identity must be a non-empty string.")
    if value.get("result") != "pass":
        findings.append(f"{label}.result must be pass.")
    if not _evidence_refs(value.get("evidenceRefs")):
        findings.append(f"{label}.evidenceRefs must contain at least one reference.")
    return identity


def _validate_rewrite(value):
    findings = []
    if not isinstance(value, dict):
        return ["The receipt must contain a JSON object."]
    if value.get("schema") != REWRITE_SCHEMA:
        findings.append(f"schema must be {REWRITE_SCHEMA}.")

    finding = value.get("finding")
    if not isinstance(finding, dict) or not _nonempty_string(finding.get("name")):
        findings.append("finding.name must be a non-empty string.")

    oracle = value.get("behaviorOracle")
    before_identity = None
    after_identity = None
    if not isinstance(oracle, dict):
        findings.append("behaviorOracle must contain before and after behavior proof.")
    else:
        before_identity = _validate_behavior_side(
            oracle.get("before"),
            "behaviorOracle.before",
            findings,
        )
        after_identity = _validate_behavior_side(
            oracle.get("after"),
            "behaviorOracle.after",
            findings,
        )
    if (
        _nonempty_string(before_identity)
        and _nonempty_string(after_identity)
        and before_identity != after_identity
    ):
        findings.append("The before and after behavior oracle identities must match.")
    if (
        isinstance(oracle, dict)
        and isinstance(oracle.get("before"), dict)
        and isinstance(oracle.get("after"), dict)
        and oracle["before"].get("evidenceRefs") == oracle["after"].get("evidenceRefs")
    ):
        findings.append("Before and after behavior proof must use distinct evidence.")

    inspection = value.get("structuralInspection")
    if not isinstance(inspection, dict):
        findings.append("structuralInspection is required.")
    else:
        if not _nonempty_string(inspection.get("inspector")):
            findings.append("structuralInspection.inspector must be a non-empty string.")
        if not _nonempty_string(inspection.get("summary")):
            findings.append("structuralInspection.summary must be a non-empty string.")
        if not _evidence_refs(inspection.get("evidenceRefs")):
            findings.append(
                "structuralInspection.evidenceRefs must contain at least one reference."
            )
    return findings


def command_validate_rewrite(args):
    findings = []
    try:
        value = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        findings.append(f"Unable to read rewrite evidence: {error}.")
    else:
        findings.extend(_validate_rewrite(value))

    payload = {
        "schema": REWRITE_SCHEMA,
        "status": "fail" if findings else "pass",
        "valid": not findings,
        "findings": findings,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("Rewrite evidence: " + ("valid" if not findings else "invalid"))
        for finding in findings:
            print(f"- {finding}")
    return 1 if findings else 0
