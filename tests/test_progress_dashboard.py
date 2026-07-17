"""Discovery adapter for the installed progress-dashboard compatibility test."""

from tests.support import load_script_test


_legacy = load_script_test("legacy_test_progress_dashboard", "test-progress-dashboard.py")
DashboardTests = _legacy.DashboardTests
DashboardLockTests = _legacy.DashboardLockTests
