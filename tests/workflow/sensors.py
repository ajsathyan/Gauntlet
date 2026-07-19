"""Adaptive code-quality sensor workflow case."""

from tests.workflow.fixtures import SCRIPTS, run


def test_adaptive_code_quality_sensor_contracts():
    for test in ("test_sensors.py", "test_sensor_tools.py"):
        result = run(
            ["python3", str(SCRIPTS.parent / "tests" / test)],
            check=False,
        )
        if result.returncode != 0 or "OK" not in result.stderr:
            raise AssertionError(
                f"Adaptive sensor behavior failed ({test}):\n"
                f"{result.stdout}\n{result.stderr}"
            )
