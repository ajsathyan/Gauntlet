"""Controller-free local Design regression case."""

import sys

from tests.workflow.fixtures import ROOT, run


def test_design_document_lifecycle_behavior():
    for relative in [
        "tests/test_doc_lifecycle.py",
        "tests/test_flexible_prd.py",
    ]:
        result = run([sys.executable, str(ROOT / relative)], cwd=ROOT, check=False)
        if result.returncode != 0:
            raise AssertionError(
                f"Design lifecycle behavior failed ({relative}):\n"
                f"{result.stdout}\n{result.stderr}"
            )
