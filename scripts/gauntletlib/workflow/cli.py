"""Public stateless CLI adapters for workflow semantic gates."""

from __future__ import annotations

import json
from pathlib import Path

from .application import build_entry, completion_check, verify_entry
from .contracts import ContractError, bind_candidate_revision, record_verdict


def _read_json(path, label):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{label} is not valid JSON: {path}") from exc


def _print(payload, as_json):
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Gauntlet: {payload['status']}")
        for finding in payload.get("findings", []):
            print(
                f"- [{finding['severity']}] {finding['code']}: {finding['message']}"
            )


def _run(args, operation):
    try:
        payload = operation()
    except (ContractError, RuntimeError) as exc:
        _print(
            {
                "schemaVersion": "gauntlet.workflow-check.v1",
                "status": "fail",
                "findings": [
                    {
                        "code": "workflow_gate_failed",
                        "severity": "fail",
                        "message": str(exc),
                    }
                ],
            },
            args.json,
        )
        return 1
    status = payload.pop("status", "pass")
    payload = {
        "schemaVersion": "gauntlet.workflow-check.v1",
        "status": status,
        **payload,
    }
    _print(payload, args.json)
    return 0 if status == "pass" else 1


def command_build_entry(args):
    return _run(
        args,
        lambda: build_entry(
            project_root=args.project_root,
            design=args.design,
            review_results=_read_json(args.reviews, "pre-build reviews"),
        ),
    )


def command_bind_candidate(args):
    def operation():
        contract = _read_json(args.contract, "workflow contract")
        authorized = build_entry(
            project_root=args.project_root,
            design=args.design,
            review_results=_read_json(args.reviews, "pre-build reviews"),
        )["contract"]
        if contract != authorized:
            raise ContractError(
                "candidate contract does not match the current authorized Build entry"
            )
        return {
            "contract": bind_candidate_revision(
                contract,
                commit=args.commit,
                tree=args.tree,
            )
        }

    return _run(args, operation)


def command_verify_entry(args):
    return _run(
        args,
        lambda: verify_entry(
            project_root=args.project_root,
            design=args.design,
            contract=_read_json(args.contract, "workflow contract"),
        ),
    )


def command_record_verdict(args):
    def operation():
        contract = _read_json(args.contract, "workflow contract")
        verify_entry(
            project_root=args.project_root,
            design=args.design,
            contract=contract,
        )
        evidence = _read_json(args.evidence, "verdict evidence")
        if not isinstance(evidence, dict):
            raise ContractError("verdict evidence must be an object")
        accepted = contract["acceptedDesign"]
        revision = contract["candidateRevision"]
        return {
            "contract": record_verdict(
                contract,
                area=args.area,
                verdict=args.verdict,
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
        }

    return _run(args, operation)


def command_completion_check(args):
    def operation():
        result = completion_check(
            project_root=args.project_root,
            design=args.design,
            contract=_read_json(args.contract, "workflow contract"),
        )
        findings = [
            {
                "code": "workflow_incomplete",
                "severity": "fail",
                "message": reason,
            }
            for reason in result["reasons"]
        ]
        return {
            "status": "pass" if result["complete"] else "fail",
            "completion": result,
            "findings": findings,
        }

    return _run(args, operation)


def _common_design(parser):
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--design", required=True)
    parser.add_argument("--json", action="store_true")


def register(subparsers):
    workflow = subparsers.add_parser(
        "workflow",
        help="Run stateless Design, Build, and Verify semantic gates.",
    )
    commands = workflow.add_subparsers(dest="workflow_command", required=True)

    build = commands.add_parser("build-entry")
    _common_design(build)
    build.add_argument("--reviews", type=Path, required=True)
    build.set_defaults(func=command_build_entry)

    bind = commands.add_parser("bind-candidate")
    _common_design(bind)
    bind.add_argument("--contract", type=Path, required=True)
    bind.add_argument("--reviews", type=Path, required=True)
    bind.add_argument("--commit", required=True)
    bind.add_argument("--tree", required=True)
    bind.set_defaults(func=command_bind_candidate)

    verify = commands.add_parser("verify-entry")
    _common_design(verify)
    verify.add_argument("--contract", type=Path, required=True)
    verify.set_defaults(func=command_verify_entry)

    verdict = commands.add_parser("record-verdict")
    _common_design(verdict)
    verdict.add_argument("--contract", type=Path, required=True)
    verdict.add_argument("--area", choices=("build", "architecture", "sensor"), required=True)
    verdict.add_argument(
        "--verdict",
        choices=("pass", "fail", "not-applicable", "cannot-verify"),
        required=True,
    )
    verdict.add_argument("--evidence", type=Path, required=True)
    verdict.set_defaults(func=command_record_verdict)

    completion = commands.add_parser("completion-check")
    _common_design(completion)
    completion.add_argument("--contract", type=Path, required=True)
    completion.set_defaults(func=command_completion_check)
