"""Grouped Gauntlet Lite regression runner."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

from tests.workflow.fixtures import ROOT, run
from tests.workflow.install import (
    test_install_preserves_personal_state_and_is_idempotent,
    test_install_rejects_malformed_and_modified_owned_state,
    test_install_transfers_personal_skills_and_retires_stale_payload,
)
from tests.workflow.lifecycle import test_design_document_lifecycle_behavior
from tests.workflow.policy import (
    test_lifecycle_authority_and_six_lenses,
    test_normal_requests_and_research_use_minimum_scope,
    test_plugin_manifests_bundle_shared_skills,
)
from tests.workflow.quality import test_skill_changes_are_guarded_by_pre_commit
from tests.test_land import test_land_workflow_behavior


def _modules(name, *modules):
    def test():
        result = run([sys.executable, "-m", "unittest", *modules], cwd=ROOT, check=False)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
    test.__name__ = name
    return test


def _files(name, *files):
    paths = tuple(Path(value) for value in files)
    def test():
        for path in paths:
            result = run([sys.executable, str(ROOT / path)], cwd=ROOT, check=False)
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
    test.__name__ = name
    return test


test_cli_policy = _modules(
    "test_cli_policy", "tests.test_workflow_policy", "tests.test_controller_free_cli"
)
test_contracts = _modules("test_contracts", "tests.test_workflow_contracts")
test_security = _modules("test_security", "tests.test_security_review_cli")
test_evals = _files(
    "test_evals",
    "tests/test_eval_task.py",
    "tests/test_eval_run.py",
    "tests/test_eval_harness.py",
    "tests/test_skill_evals.py",
)

GROUP_CASES = {
    "policy": (
        test_plugin_manifests_bundle_shared_skills,
        test_normal_requests_and_research_use_minimum_scope,
        test_lifecycle_authority_and_six_lenses,
        test_skill_changes_are_guarded_by_pre_commit,
        test_land_workflow_behavior,
        test_cli_policy,
    ),
    "install": (
        test_install_preserves_personal_state_and_is_idempotent,
        test_install_transfers_personal_skills_and_retires_stale_payload,
        test_install_rejects_malformed_and_modified_owned_state,
    ),
    "design": (test_design_document_lifecycle_behavior,),
    "contracts": (test_contracts, test_security),
    "evals": (test_evals,),
}
FULL_CASES = tuple(case for name in GROUP_CASES for case in GROUP_CASES[name])
SMOKE_CASES = (
    test_normal_requests_and_research_use_minimum_scope,
    test_cli_policy,
    test_contracts,
)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--group", choices=sorted(GROUP_CASES))
    args = parser.parse_args(argv)
    if args.smoke and args.group:
        parser.error("--smoke and --group cannot be combined")
    cases = GROUP_CASES[args.group] if args.group else SMOKE_CASES if args.smoke else FULL_CASES
    started = time.monotonic()
    try:
        for case in cases:
            case()
            print(f"PASS {case.__name__}")
    except AssertionError as error:
        parser.exit(1, f"FAIL {error}\n")
    print(f"SUMMARY {args.group or ('smoke' if args.smoke else 'full')}: {len(cases)} cases in {time.monotonic() - started:.1f}s")


if __name__ == "__main__":
    main()
