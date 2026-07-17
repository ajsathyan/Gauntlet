"""Discovery adapter for the installed progress-projection compatibility test."""

from tests.support import load_script_test


_legacy = load_script_test("legacy_test_progress_projection", "test-progress-projection.py")
ProgressProjectionTests = _legacy.ProgressProjectionTests
source_fixture = _legacy.source_fixture
