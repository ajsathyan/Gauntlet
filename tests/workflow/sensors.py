"""Fast and integrated sensor workflow case."""

import sys

from tests.workflow.fixtures import ROOT, run


def test_sensor_execution_and_cadence():
    for test in (
        "test_sensors.py",
        "test_sensor_cadence.py",
        "test_sensor_tools.py",
    ):
        result = run(
            [sys.executable, str(ROOT / "tests" / test)],
            cwd=ROOT,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"Sensor behavior failed ({test}):\n"
                f"{result.stdout}\n{result.stderr}"
            )
