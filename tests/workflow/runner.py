"""Ordered controller-free workflow regression runner."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

from tests.workflow.install import (
    test_codex_install_merges_preferences_without_silent_overwrite,
    test_codex_hook_install_preserves_user_state_and_fails_closed,
    test_install_migrates_exact_legacy_layout_and_rejects_malformed_blocks,
)
from tests.workflow.lifecycle import test_design_document_lifecycle_behavior
from tests.workflow.policy import (
    test_merge_and_archive_authority_requires_complete_safe_closeout,
    test_normal_requests_use_minimum_scope_before_design,
    test_plugin_manifests_bundle_shared_skills,
)
from tests.workflow.quality import test_skill_changes_are_guarded_by_pre_commit
from tests.workflow.fixtures import ROOT, run
from tests.test_land import test_land_workflow_behavior


def _test_files(name, *relative_paths):
    paths = tuple(Path(relative) for relative in relative_paths)

    def test():
        for relative in paths:
            result = run(
                [sys.executable, str(ROOT / relative)],
                cwd=ROOT,
                check=False,
            )
            if result.returncode:
                raise AssertionError(
                    f"{relative} failed:\n{result.stdout}\n{result.stderr}"
                )

    test.__name__ = name
    return test


def _test_modules(name, *modules):
    def test():
        result = run(
            [sys.executable, "-m", "unittest", *modules],
            cwd=ROOT,
            check=False,
        )
        if result.returncode:
            raise AssertionError(
                f"{', '.join(modules)} failed:\n"
                f"{result.stdout}\n{result.stderr}"
            )

    test.__name__ = name
    return test


test_plain_title_and_controller_free_cli = _test_modules(
    "test_plain_title_and_controller_free_cli",
    "tests.test_workflow_policy",
    "tests.test_controller_free_cli",
)
test_exact_revision_contracts = _test_modules(
    "test_exact_revision_contracts",
    "tests.test_workflow_contracts",
)
test_dedicated_security_runner = _test_modules(
    "test_dedicated_security_runner",
    "tests.test_security_review_cli",
)
test_generated_context_and_size_audit = _test_files(
    "test_generated_context_and_size_audit",
    "tests/test_generated_context.py",
    "tests/test_context_audit.py",
)
test_retained_evaluation_runtime = _test_files(
    "test_retained_evaluation_runtime",
    "tests/test_eval_task.py",
    "tests/test_eval_run.py",
    "tests/test_eval_harness.py",
)
test_workflow_skill_evaluations = _test_files(
    "test_workflow_skill_evaluations",
    "tests/test_skill_evals.py",
)


POLICY_CASES = (
    test_plugin_manifests_bundle_shared_skills,
    test_normal_requests_use_minimum_scope_before_design,
    test_merge_and_archive_authority_requires_complete_safe_closeout,
    test_skill_changes_are_guarded_by_pre_commit,
    test_land_workflow_behavior,
    test_plain_title_and_controller_free_cli,
)

INSTALL_CASES = (
    test_install_migrates_exact_legacy_layout_and_rejects_malformed_blocks,
    test_codex_install_merges_preferences_without_silent_overwrite,
    test_codex_hook_install_preserves_user_state_and_fails_closed,
)

DESIGN_CASES = (test_design_document_lifecycle_behavior,)

CONTRACT_CASES = (
    test_exact_revision_contracts,
    test_dedicated_security_runner,
)

EVAL_CASES = (
    test_generated_context_and_size_audit,
    test_retained_evaluation_runtime,
    test_workflow_skill_evaluations,
)

GROUP_CASES = {
    "policy": POLICY_CASES,
    "install": INSTALL_CASES,
    "design": DESIGN_CASES,
    "contracts": CONTRACT_CASES,
    "evals": EVAL_CASES,
}

FULL_CASES = tuple(
    case
    for group in ("policy", "install", "design", "contracts", "evals")
    for case in GROUP_CASES[group]
)
if len(FULL_CASES) != len(set(FULL_CASES)):
    raise RuntimeError("full workflow cases must appear exactly once")

SMOKE_CASES = (
    test_normal_requests_use_minimum_scope_before_design,
    test_plain_title_and_controller_free_cli,
    test_exact_revision_contracts,
)


def run_cases(cases):
    for test in cases:
        test()
        print(f"PASS {test.__name__}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run Gauntlet workflow regression checks.")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="run the fast structural subset instead of all workflow cases",
    )
    parser.add_argument(
        "--group",
        choices=sorted(GROUP_CASES),
        help="run one independent CI group instead of the full workflow suite",
    )
    args = parser.parse_args(argv)
    if args.smoke and args.group:
        parser.error("--smoke and --group cannot be combined")
    cases = (
        GROUP_CASES[args.group]
        if args.group
        else SMOKE_CASES
        if args.smoke
        else FULL_CASES
    )
    label = args.group or ("smoke" if args.smoke else "full")
    started = time.monotonic()
    try:
        run_cases(cases)
    except AssertionError as error:
        parser.exit(1, f"FAIL {error}\n")
    elapsed = time.monotonic() - started
    print(f"SUMMARY {label}: {len(cases)} cases in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
