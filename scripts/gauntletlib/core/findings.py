"""Shared finding construction and severity aggregation."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def finding(code: str, severity: str, message: str, **details: Any) -> dict[str, Any]:
    value = {
        "code": code,
        "severity": severity,
        "message": message,
    }
    value.update(details)
    return value


def status_for_findings(
    findings: Iterable[Mapping[str, Any]],
    status_order: Mapping[str, int],
) -> str:
    status = "pass"
    for item in findings:
        severity = item.get("severity", "warn")
        if status_order[severity] > status_order[status]:
            status = severity
    return status
