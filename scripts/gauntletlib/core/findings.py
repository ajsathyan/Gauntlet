"""Shared finding construction and severity aggregation."""

from __future__ import annotations

from typing import Any


STATUS_ORDER = {"pass": 0, "warn": 1, "review": 2, "fail": 3}


def finding(code: str, severity: str, message: str, **details: Any) -> dict[str, Any]:
    value = {
        "code": code,
        "severity": severity,
        "message": message,
    }
    value.update(details)
    return value


def add_finding(findings, code, severity, message, **details):
    findings.append(finding(code, severity, message, **details))


def status_for(findings):
    status = "pass"
    for item in findings:
        severity = item.get("severity", "warn")
        if STATUS_ORDER[severity] > STATUS_ORDER[status]:
            status = severity
    return status
