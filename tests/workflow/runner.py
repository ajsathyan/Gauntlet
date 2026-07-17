"""Ordered full and smoke runners for the legacy workflow-check command."""

from __future__ import annotations

import argparse

from tests.workflow.install import (
    test_codex_install_merges_preferences_without_silent_overwrite,
    test_install_migrates_exact_legacy_layout_and_rejects_malformed_blocks,
)
from tests.workflow.lifecycle import (
    test_document_draft_lifecycle_behavior,
    test_live_progress_projection_dashboard_and_production_assets,
    test_local_document_profile_preserves_tracked_docs_and_primary_canonical_copy,
    test_prd_execution_run_controller_behavior,
    test_subagent_orchestration_v2_behavior,
)
from tests.workflow.policy import (
    test_merge_and_archive_authority_requires_complete_safe_closeout,
    test_normal_requests_use_minimum_scope_before_lifecycle_routing,
    test_plugin_manifests_bundle_shared_skills,
)
from tests.workflow.quality import test_skill_changes_are_guarded_by_pre_commit


FULL_CASES = (
    test_plugin_manifests_bundle_shared_skills,
    test_normal_requests_use_minimum_scope_before_lifecycle_routing,
    test_merge_and_archive_authority_requires_complete_safe_closeout,
    test_skill_changes_are_guarded_by_pre_commit,
    test_install_migrates_exact_legacy_layout_and_rejects_malformed_blocks,
    test_codex_install_merges_preferences_without_silent_overwrite,
    test_local_document_profile_preserves_tracked_docs_and_primary_canonical_copy,
    test_document_draft_lifecycle_behavior,
    test_prd_execution_run_controller_behavior,
    test_live_progress_projection_dashboard_and_production_assets,
    test_subagent_orchestration_v2_behavior,
)

SMOKE_CASES = (
    test_plugin_manifests_bundle_shared_skills,
    test_normal_requests_use_minimum_scope_before_lifecycle_routing,
    test_merge_and_archive_authority_requires_complete_safe_closeout,
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
    args = parser.parse_args(argv)
    try:
        run_cases(SMOKE_CASES if args.smoke else FULL_CASES)
    except AssertionError as error:
        parser.exit(1, f"FAIL {error}\n")


if __name__ == "__main__":
    main()
