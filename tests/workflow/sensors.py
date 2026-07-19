"""Adaptive code-quality sensor workflow case."""

from tests.workflow.fixtures import SCRIPTS, run


def test_adaptive_code_quality_sensor_contracts():
    result = run(["python3", str(SCRIPTS.parent / "tests" / "test_sensors.py")], check=False)
    if result.returncode != 0 or "OK" not in result.stderr:
        raise AssertionError(
            f"Adaptive sensor behavior failed:\n{result.stdout}\n{result.stderr}"
        )
