#!/usr/bin/env python3
"""Pure, privacy-allowlisted projection for live Epic implementation progress."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import statistics
from typing import Any

from gauntletlib.core.serialization import canonical_json


SOURCE_SCHEMA = "gauntlet/live-progress-source/v1"
PROJECTION_SCHEMA = "gauntlet/live-epic-progress/v1"
RUN_SCHEMA = "gauntlet/epic-run-facts/v1"
TELEMETRY_SCHEMA = "gauntlet/run-telemetry-summary/v1"
PHASE_POLICY = {
    "prepare": 0.05,
    "build": 0.35,
    "integrate": 0.25,
    "final_verify": 0.20,
    "ship": 0.15,
}
PHASE_LABELS = {
    "prepare": "Prepare",
    "build": "Build",
    "integrate": "Integrate",
    "final_verify": "Final verify",
    "ship": "Ship",
}
PRESENTATION_STATES = (
    "starting", "healthy_build", "parallel_work", "return_update", "recovering",
    "needs_user", "ready_to_merge", "ready_to_deploy", "shipped",
)
PRICING_DISCLAIMER = "comparison only — not your bill or savings"
OPAQUE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")
REASON_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class ProjectionError(Exception):
    pass


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def now_value(value: str | None) -> tuple[str, datetime]:
    if value is None:
        current = datetime.now(timezone.utc)
        return current.isoformat(timespec="seconds").replace("+00:00", "Z"), current
    parsed = parse_time(value)
    if parsed is None:
        raise ProjectionError("now must be an RFC 3339 UTC timestamp")
    return value, parsed


def format_clock(value: str | None) -> str:
    parsed = parse_time(value)
    if parsed is None:
        return "Unavailable"
    return parsed.strftime("%b %-d, %-I:%M %p UTC")


def format_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "Unavailable"
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, _ = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def phase_key(value: str) -> str:
    return value.replace("-", "_")


def unit_label(unit: dict[str, Any]) -> str:
    kind = unit.get("kind")
    identifier = str(unit.get("id", "unit"))
    suffix = identifier.rsplit(":", 1)[-1]
    labels = {
        "prepare": "Prepare run",
        "ticket-build": f"Build {suffix}",
        "ticket-integration": f"Integrate {suffix}",
        "cohort-verification": f"Verify shared check {suffix}",
        "epic-gap-review": "Review implementation gaps",
        "consequence-review": f"Review {suffix.replace('-', ' ')}",
        "final-epic-verification": "Final Epic verification",
        "release-safeguard": f"Check {suffix.replace('-', ' ')}",
        "release-gate": suffix.replace("-", " ").title(),
    }
    return labels.get(kind, "Execution unit")


def current_units(facts: dict[str, Any]) -> list[dict[str, Any]]:
    progress = facts.get("progress")
    if not isinstance(progress, dict) or not isinstance(progress.get("units"), list):
        return []
    operations = {
        item.get("id"): item
        for item in facts.get("operations", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    projected = []
    for raw in progress["units"]:
        if (
            not isinstance(raw, dict)
            or not isinstance(raw.get("id"), str)
            or not OPAQUE_ID_RE.fullmatch(raw["id"])
        ):
            raise ProjectionError("progress units must have stable IDs")
        phase = phase_key(str(raw.get("phase")))
        if phase not in PHASE_POLICY:
            raise ProjectionError("progress unit has an unsupported phase")
        dependencies = raw.get("dependencies", [])
        if not isinstance(dependencies, list) or any(
            not isinstance(item, str) or not OPAQUE_ID_RE.fullmatch(item) for item in dependencies
        ):
            raise ProjectionError("progress unit dependencies must use stable IDs")
        operation = operations.get(raw["id"])
        status = operation.get("status") if operation else raw.get("status", "queued")
        attempts = operation.get("attempts", []) if operation else []
        previously_passed = any(item.get("status") == "pass" for item in attempts if isinstance(item, dict))
        if previously_passed and status in {"queued", "running"}:
            display_status = "invalidated"
        else:
            display_status = {
                "queued": "waiting", "running": "running", "pass": "passed", "fail": "failed",
                "invalidated": "invalidated",
            }.get(status, "waiting")
        projected.append({
            "id": raw["id"],
            "kind": raw.get("kind"),
            "label": unit_label(raw),
            "phase": phase,
            "status": display_status,
            "dependencies": dependencies,
        })
    return projected


def phase_projection(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not units:
        return [{
            "key": phase,
            "label": PHASE_LABELS[phase],
            "status": "waiting",
            "policyShare": policy_share,
            "provedShare": 0.0,
            "accessibleLabel": f"{PHASE_LABELS[phase]}: waiting",
        } for phase, policy_share in PHASE_POLICY.items()]
    phase_items: dict[str, list[dict[str, Any]]] = {key: [] for key in PHASE_POLICY}
    for unit in units:
        phase_items[unit["phase"]].append(unit)
    first_unfinished = next((
        phase for phase in PHASE_POLICY
        if phase_items[phase] and not all(item["status"] == "passed" for item in phase_items[phase])
    ), None)
    output = []
    for phase, policy_share in PHASE_POLICY.items():
        items = phase_items[phase]
        passed = sum(item["status"] == "passed" for item in items)
        proved = passed / len(items) if items else 1.0
        if not items or passed == len(items):
            status = "complete"
        elif any(item["status"] == "invalidated" for item in items):
            status = "invalidated"
        elif any(item["status"] in {"running", "failed"} for item in items) or phase == first_unfinished:
            status = "active"
        else:
            status = "waiting"
        label = PHASE_LABELS[phase]
        output.append({
            "key": phase,
            "label": label,
            "status": status,
            "policyShare": policy_share,
            "provedShare": round(proved, 6),
            "accessibleLabel": f"{label}: {status}",
        })
    return output


def source_freshness(
    facts: dict[str, Any], telemetry: dict[str, Any] | None, current: datetime, stale_after: int,
) -> dict[str, Any]:
    run_observed = (facts.get("time") or {}).get("updatedAt")
    telemetry_observed = (((telemetry or {}).get("coverage") or {}).get("freshness") or {}).get("observedThrough")
    observations = [(value, parse_time(value)) for value in (run_observed, telemetry_observed)]
    valid = [(value, parsed) for value, parsed in observations if parsed is not None]
    observed_at, observed = max(valid, key=lambda item: item[1]) if valid else (None, None)
    stale = observed is None or (current - observed).total_seconds() > stale_after
    run_complete = (facts.get("time") or {}).get("protocolVersion") == "gauntlet.rfc3339-utc.v1"
    telemetry_status = ((telemetry or {}).get("coverage") or {}).get("status")
    coverage = "complete" if run_complete and telemetry_status == "complete" else "partial" if observed else "unavailable"
    if observed is None:
        label = "Update time unavailable"
    elif stale:
        label = "Update is stale"
    else:
        age = max(0, int((current - observed).total_seconds()))
        label = "Updated just now" if age < 60 else f"Updated {age // 60}m ago"
    return {"observedAt": observed_at, "coverage": coverage, "stale": stale, "label": label}


def health_projection(
    launch_epic: dict[str, Any], facts: dict[str, Any], units: list[dict[str, Any]], stale: bool,
) -> dict[str, Any]:
    gap_review = facts.get("gapReview") if isinstance(facts.get("gapReview"), dict) else {}
    review_blocked = gap_review.get("status") == "blocked" or bool(gap_review.get("blockedWork"))
    needs_user = launch_epic.get("status") == "needs-decision" or bool(launch_epic.get("blocker")) or review_blocked
    if needs_user:
        reason = "review-decision-required" if review_blocked else "owner-decision-required"
        return {"status": "needs_user", "reason": reason, "actionRequired": True}
    if stale:
        return {"status": "recovering", "reason": "source-stale", "actionRequired": False}
    if any(item["status"] == "failed" for item in units):
        return {"status": "recovering", "reason": "operation-failed", "actionRequired": False}
    return {"status": "healthy", "reason": "execution-advancing", "actionRequired": False}


def presentation_state(
    health: dict[str, Any], phases: list[dict[str, Any]], units: list[dict[str, Any]], terminal_at: str | None,
) -> str:
    if health["status"] == "needs_user":
        return "needs_user"
    if health["status"] == "recovering":
        return "recovering"
    if terminal_at and units and all(item["status"] == "passed" for item in units):
        return "shipped"
    merge = next((item for item in units if item["id"] == "ship:merge"), None)
    final = next((item for item in units if item["id"] == "verify:final-epic"), None)
    if merge and merge["status"] == "passed" and any(
        item["phase"] == "ship" and item["status"] != "passed" for item in units
    ):
        return "ready_to_deploy"
    if final and final["status"] == "passed" and merge and merge["status"] != "passed":
        return "ready_to_merge"
    active = [item["key"] for item in phases if item["status"] in {"active", "invalidated"}]
    work_active = [item for item in active if item in {"build", "integrate", "final_verify"}]
    if len(work_active) >= 2:
        return "parallel_work"
    if any(item["status"] == "running" and item["phase"] == "build" for item in units):
        return "healthy_build"
    return "starting"


def representative_copy(
    state: str,
    phases: list[dict[str, Any]],
    units: list[dict[str, Any]],
    terminal_outcome: str | None,
) -> tuple[dict[str, str], dict[str, str] | None]:
    if terminal_outcome == "failed":
        return (
            {"reason": "failed", "label": "Implementation failed", "actionId": None},
            {"reason": "review-failure", "label": "Review the failure in the main task", "actionId": None},
        )
    if terminal_outcome == "stopped":
        return (
            {"reason": "stopped", "label": "Implementation stopped", "actionId": None},
            {"reason": "resume-stopped", "label": "Resume from the main task when ready", "actionId": None},
        )
    if terminal_outcome == "succeeded":
        return ({"reason": "shipped", "label": "Live and verified", "actionId": None}, None)
    copy_map = {
        "starting": ("Preparing the run", "Start the first ready build unit"),
        "healthy_build": ("Building", "Integrate the next completed unit"),
        "parallel_work": ("Building + integrating + verifying", "Advance the nearest unfinished gate"),
        "recovering": ("Recovering execution facts", "Resume the interrupted operation"),
        "needs_user": ("Waiting on your decision", "Resolve the required decision"),
        "ready_to_merge": ("Implementation verified", "Merge to main"),
        "ready_to_deploy": ("Merged to main", "Deploy to production"),
        "shipped": ("Live and verified", None),
    }
    now_label, next_label = copy_map.get(state, copy_map["starting"])
    active_phases = [phase["label"] for phase in phases if phase["status"] in {"active", "invalidated"}]
    if active_phases and state not in {"needs_user", "ready_to_merge", "ready_to_deploy"}:
        now_label = " + ".join(active_phases) + " in progress"
    phase_order = {key: index for index, key in enumerate(PHASE_POLICY)}
    passed_ids = {unit["id"] for unit in units if unit["status"] == "passed"}
    unfinished = [unit for unit in units if unit["status"] != "passed"]
    dependency_ready = [
        unit for unit in unfinished
        if all(dependency in passed_ids for dependency in unit["dependencies"])
    ]
    queued_ready = [unit for unit in dependency_ready if unit["status"] != "running"]
    candidates = sorted(
        queued_ready or dependency_ready,
        key=lambda unit: (phase_order[unit["phase"]], unit["id"]),
    )
    if candidates and state not in {"needs_user", "ready_to_merge", "ready_to_deploy"}:
        candidate = candidates[0]
        verb = "Retry" if candidate["status"] == "failed" else "Next gate"
        next_label = f"{verb}: {PHASE_LABELS[candidate['phase']]} — {candidate['label']}"
    elif unfinished and state not in {"needs_user", "ready_to_merge", "ready_to_deploy"}:
        next_label = "Waiting for the current dependency chain"
    return (
        {"reason": state, "label": now_label, "actionId": None},
        {"reason": f"next-{state}", "label": next_label, "actionId": None} if next_label else None,
    )


def time_projection(facts: dict[str, Any], now: str, current: datetime) -> dict[str, Any]:
    time_facts = facts.get("time") if isinstance(facts.get("time"), dict) else {}
    started_at = time_facts.get("startedAt")
    terminal_at = time_facts.get("terminalAt")
    started = parse_time(started_at)
    terminal = parse_time(terminal_at)
    elapsed = None if started is None else ((terminal or current) - started).total_seconds()
    return {
        "startedAt": started_at if started else None,
        "currentAt": now,
        "updatedAt": time_facts.get("updatedAt"),
        "terminalAt": terminal_at if terminal else None,
        "started": format_clock(started_at),
        "current": format_clock(now),
        "elapsed": format_duration(elapsed),
        "updated": format_clock(time_facts.get("updatedAt")),
    }


def eta_projection(
    facts: dict[str, Any], units: list[dict[str, Any]], health: dict[str, Any], now: str, current: datetime,
) -> dict[str, Any]:
    if health["status"] == "needs_user":
        return {"status": "waiting_on_user", "likelyFinishAt": None, "remainingSeconds": None,
                "confidence": None, "estimatorVersion": "gauntlet-eta/v1", "label": "Waiting on you",
                "detail": "A decision is required before scheduling can continue.", "reason": "needs-user"}
    time_facts = facts.get("time") or {}
    started = parse_time(time_facts.get("startedAt"))
    updated = parse_time(time_facts.get("updatedAt"))
    terminal = parse_time(time_facts.get("terminalAt"))
    inconsistent = (
        started is None
        or (updated is not None and updated < started)
        or (terminal is not None and terminal < started)
        or (updated is not None and (updated - current).total_seconds() > 5)
    )
    if time_facts.get("elapsedCoverage") != "complete" or inconsistent:
        return {"status": "unavailable", "likelyFinishAt": None, "remainingSeconds": None,
                "confidence": None, "estimatorVersion": "gauntlet-eta/v1", "label": "Cannot estimate yet",
                "detail": "The run has no consistent timestamp sequence.", "reason": "timestamp-unavailable"}
    unfinished = [item for item in units if item["status"] != "passed"]
    if not unfinished:
        return {"status": "available", "likelyFinishAt": now, "remainingSeconds": 0,
                "confidence": "high", "estimatorVersion": "gauntlet-eta/v1", "label": "Complete",
                "detail": "No execution units remain.", "reason": None}
    durations = []
    for operation in facts.get("operations", []):
        for attempt in operation.get("attempts", []):
            start, finish = parse_time(attempt.get("startedAt")), parse_time(attempt.get("finishedAt"))
            if start and finish and finish >= start:
                durations.append((finish - start).total_seconds())
    if not durations:
        return {"status": "settling", "likelyFinishAt": None, "remainingSeconds": None,
                "confidence": "low", "estimatorVersion": "gauntlet-eta/v1", "label": "Estimate settling",
                "detail": "Waiting for timestamped operation durations.", "reason": "insufficient-priors"}
    typical = max(60.0, statistics.median(durations))
    active = max(1, sum(item["status"] == "running" for item in unfinished))
    serial = sum(item["phase"] in {"integrate", "final_verify", "ship"} for item in unfinished)
    parallel = len(unfinished) - serial
    remaining = int(serial * typical + (parallel * typical / active))
    finish = current.timestamp() + remaining
    likely = datetime.fromtimestamp(finish, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {"status": "available", "likelyFinishAt": likely, "remainingSeconds": remaining,
            "confidence": "low", "estimatorVersion": "gauntlet-eta/v1",
            "label": f"Likely done {format_clock(likely)}",
            "detail": f"About {format_duration(remaining)} remaining · Low confidence", "reason": None}


def usage_projection(telemetry: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    coverage = (telemetry or {}).get("coverage") if isinstance((telemetry or {}).get("coverage"), dict) else {}
    coverage_status = coverage.get("status") if coverage.get("status") in {"complete", "partial"} else "unavailable"
    tokens = (telemetry or {}).get("tokens") if isinstance((telemetry or {}).get("tokens"), dict) else None
    total = tokens.get("total_tokens") if tokens and isinstance(tokens.get("total_tokens"), int) else 0
    freshness = (coverage.get("freshness") or {}).get("observedThrough") or "Unavailable"
    usage = {
        "totalTokens": total,
        "totalLabel": f"{total:,}" if tokens else "Unavailable",
        "observedThrough": (coverage.get("freshness") or {}).get("observedThrough"),
        "freshness": freshness,
        "coverage": coverage_status,
        "models": [],
    }
    raw_pricing = (telemetry or {}).get("pricing") if isinstance((telemetry or {}).get("pricing"), dict) else {}
    for model, values in sorted((raw_pricing.get("byModel") or {}).items()):
        if model not in {"gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-terra"} or not isinstance(values, dict):
            continue
        model_total = values.get("totalTokens")
        if not isinstance(model_total, int) or model_total < 0:
            continue
        usage["models"].append({
            "model": model,
            "tokens": model_total,
            "label": f"{model_total:,}",
            "inputTokens": values.get("inputTokens"),
            "cachedInputTokens": values.get("cachedInputTokens"),
            "outputTokens": values.get("outputTokens"),
            "reasoningOutputTokens": values.get("reasoningOutputTokens"),
        })
    raw_status = raw_pricing.get("status")
    status = "complete" if raw_status == "complete" else "lower_bound" if raw_status == "partial" else "unavailable"
    amount = raw_pricing.get("estimatedUsd") if status == "complete" else raw_pricing.get("lowerBoundUsd") if status == "lower_bound" else None
    components = []
    for key, label in (("inputUsd", "Input"), ("cachedInputUsd", "Cached input"), ("outputUsd", "Output")):
        value = (raw_pricing.get("components") or {}).get(key)
        if isinstance(value, (int, float)):
            components.append({"label": label, "value": f"${value:.4f}"})
    for model, values in sorted((raw_pricing.get("byModel") or {}).items()):
        total_usd = values.get("totalUsd") if isinstance(values, dict) else None
        if model in {"gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-terra"} and isinstance(total_usd, (int, float)):
            components.append({"label": f"{model} subtotal", "value": f"${total_usd:.4f}"})
    limitations = [
        item for item in raw_pricing.get("limitations", [])
        if isinstance(item, str) and REASON_RE.fullmatch(item)
    ]
    if len(limitations) != len(raw_pricing.get("limitations", [])):
        limitations.append("pricing-coverage-unavailable")
    registry_version = raw_pricing.get("registryVersion")
    if registry_version != "gauntlet.model-api-pricing.v1":
        registry_version = None
    effective_at = raw_pricing.get("effectiveAt")
    if isinstance(effective_at, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}T.+Z", effective_at):
        effective_at = effective_at[:10]
    if not isinstance(effective_at, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", effective_at):
        effective_at = None
    pricing = {
        "status": status,
        "registryVersion": registry_version,
        "effectiveDate": effective_at,
        "amountUsd": amount,
        "amountLabel": "Unavailable" if amount is None else f"${amount:.2f}",
        "disclaimer": PRICING_DISCLAIMER,
        "components": components,
        "unpricedReasons": sorted(set(limitations)),
    }
    return usage, pricing


def agents_projection(facts: dict[str, Any], units: list[dict[str, Any]]) -> dict[str, Any]:
    active = []
    for index, owner in enumerate(facts.get("owners", []), 1):
        if not isinstance(owner, dict) or owner.get("ownerKind") != "delegated":
            continue
        window = owner.get("requestWindow") or {}
        if window.get("endedAt") is not None:
            continue
        owner_id = str(owner.get("ownerId", f"owner-{index}"))
        ticket = owner_id.split(":")[1] if owner_id.startswith("ticket:") and len(owner_id.split(":")) > 1 else None
        ticket_unit = next((item for item in units if item["id"] == f"build:ticket:{ticket}"), None)
        phase = ticket_unit["phase"] if ticket_unit else "build"
        active.append({
            "id": digest({"owner": owner_id})[:12],
            "label": f"Agent {len(active) + 1}",
            "phase": phase,
            "phaseLabel": PHASE_LABELS[phase],
            "status": "active",
            "elapsed": None,
            "modelUsage": None,
        })
    counts = [{"phase": phase, "count": sum(item["phase"] == phase for item in active)} for phase in PHASE_POLICY]
    counts = [item for item in counts if item["count"]]
    summary = " · ".join(f"{item['count']} {PHASE_LABELS[item['phase']].lower()}" for item in counts) or "No delegated agents active"
    return {"activeCount": len(active), "summary": summary, "byPhase": counts, "details": active}


def epic_projection(
    launch_id: str,
    epic_id: str,
    launch_epic: dict[str, Any],
    run_value: dict[str, Any],
    telemetry: dict[str, Any] | None,
    now: str,
    current: datetime,
    stale_after: int,
) -> dict[str, Any]:
    facts = run_value.get("facts") if isinstance(run_value.get("facts"), dict) else run_value
    if facts.get("schemaVersion") != RUN_SCHEMA or facts.get("epicId") != epic_id:
        raise ProjectionError(f"Epic {epic_id} has invalid run facts")
    if telemetry is not None and telemetry.get("schemaVersion") != TELEMETRY_SCHEMA:
        raise ProjectionError(f"Epic {epic_id} has invalid telemetry")
    units = current_units(facts)
    phases = phase_projection(units)
    time_facts = time_projection(facts, now, current)
    launch_status = launch_epic.get("status")
    terminal_outcome = (
        "failed" if launch_status == "failed" else
        "stopped" if launch_status == "stopped" else
        None
    )
    if terminal_outcome:
        for unit in units:
            if unit["status"] == "running":
                unit["status"] = "failed" if terminal_outcome == "failed" else "waiting"
        phases = phase_projection(units)
        for phase in phases:
            if phase["status"] == "active":
                phase["status"] = "invalidated" if terminal_outcome == "failed" else "waiting"
                phase["accessibleLabel"] = f"{phase['label']}: {phase['status']}"
    freshness = source_freshness(facts, telemetry, current, stale_after)
    completion = facts.get("completion") if isinstance(facts.get("completion"), dict) else {}
    release_complete = completion.get("complete") is True
    if release_complete and not units:
        phases = [{
            **phase,
            "status": "complete",
            "provedShare": 1.0,
            "accessibleLabel": f"{phase['label']}: complete",
        } for phase in phases]
    if time_facts["terminalAt"] or terminal_outcome or release_complete:
        # A terminal run no longer produces active-work heartbeats. Its final
        # controller facts remain authoritative instead of aging into recovery.
        freshness["stale"] = False
        freshness["label"] = "Final"
    health = health_projection(launch_epic, facts, units, freshness["stale"])
    if release_complete:
        health = {"status": "healthy", "reason": "release-complete", "actionRequired": False}
    if terminal_outcome:
        health = {
            "status": "recovering",
            "reason": f"implementation-{terminal_outcome}",
            "actionRequired": False,
        }
    elif launch_status == "implementation-complete":
        health = {
            "status": "healthy",
            "reason": "implementation-verified",
            "actionRequired": False,
        }
    # Legacy runs may have no progress units, so launch state remains their
    # compatibility signal. Instrumented runs carry the more precise merge,
    # release, and terminal facts and must not be pinned at ready-to-merge.
    state = (
        "shipped" if release_complete
        else "ready_to_merge" if launch_status == "implementation-complete" and not units
        else presentation_state(health, phases, units, time_facts["terminalAt"])
    )
    if state == "shipped":
        terminal_outcome = "succeeded"
    now_copy, next_copy = representative_copy(state, phases, units, terminal_outcome)
    usage, pricing = usage_projection(telemetry)
    progress = facts.get("progress") if isinstance(facts.get("progress"), dict) else {}
    policy_version = progress.get("policyVersion")
    if policy_version != "gauntlet.progress-policy.v1":
        policy_version = "unavailable"
    denominator = progress.get("denominatorSha256")
    if not isinstance(denominator, str) or not re.fullmatch(r"[0-9a-f]{64}", denominator):
        denominator = None
    raw_run_id = str(run_value.get("runId") or facts.get("runId") or epic_id)
    safe_run_id = raw_run_id if OPAQUE_ID_RE.fullmatch(raw_run_id) else "run-" + digest({"run": raw_run_id})[:20]
    planned = sum(
        phase["policyShare"] * phase["provedShare"]
        for phase in phases
    )
    transition = digest({
        "health": health["status"], "phases": [(item["key"], item["status"], item["provedShare"]) for item in phases],
        "state": state, "terminal": time_facts["terminalAt"], "terminalOutcome": terminal_outcome,
    })[:16]
    eta = eta_projection(facts, units, health, now, current)
    if state == "ready_to_merge":
        eta = {
            "status": "available", "likelyFinishAt": now, "remainingSeconds": 0,
            "confidence": "high", "estimatorVersion": "gauntlet-eta/v1",
            "label": "Implementation complete", "detail": "Merge remains.", "reason": None,
        }
    elif state == "shipped":
        eta = {
            "status": "available", "likelyFinishAt": now, "remainingSeconds": 0,
            "confidence": "high", "estimatorVersion": "gauntlet-eta/v1",
            "label": "Complete", "detail": "The accepted release path is complete.", "reason": None,
        }
    if terminal_outcome in {"failed", "stopped"}:
        eta = {
            "status": "unavailable", "likelyFinishAt": None, "remainingSeconds": None,
            "confidence": None, "estimatorVersion": "gauntlet-eta/v1",
            "label": "No completion estimate", "detail": "This implementation run is terminal.",
            "reason": terminal_outcome,
        }
    agents = agents_projection(facts, units)
    if terminal_outcome in {"failed", "stopped"}:
        agents = {
            "activeCount": 0,
            "summary": "No delegated agents active — run ended",
            "byPhase": [],
            "details": [],
        }
    return {
        "identity": {
            "launchId": launch_id,
            "epicId": epic_id,
            "runId": safe_run_id,
            "title": str(facts.get("epicTitle") or epic_id)[:256],
            "terminalOutcome": terminal_outcome,
        },
        "time": time_facts,
        "presentation": {"state": state, "transitionId": transition},
        "health": health,
        "freshness": freshness,
        "phases": phases,
        "now": now_copy,
        "next": next_copy,
        "agents": agents,
        "eta": eta,
        "usage": usage,
        "pricing": pricing,
        "details": {
            "progressPolicy": policy_version,
            "denominatorDigest": denominator,
            "plannedProgress": f"{planned * 100:.1f}%" if units else None,
            "units": units,
            "timing": [
                {"label": "Started", "value": time_facts["started"]},
                {"label": "Updated", "value": time_facts["updated"]},
            ],
            "coverage": [
                {"label": "Freshness", "value": freshness["coverage"]},
                {"label": "Usage", "value": usage["coverage"]},
            ],
            "recovery": ([{"label": "Status", "value": health["reason"]}] if health["status"] != "healthy" else []),
        },
        "actions": [],
    }


def build_projection(source: dict[str, Any], *, now: str | None = None, stale_after: int = 300) -> dict[str, Any]:
    if not isinstance(source, dict) or source.get("schemaVersion") != SOURCE_SCHEMA:
        raise ProjectionError(f"source schema must be {SOURCE_SCHEMA}")
    launch = source.get("launch")
    runs = source.get("runs")
    telemetry = source.get("telemetry", {})
    if not isinstance(launch, dict) or not isinstance(runs, dict) or not isinstance(telemetry, dict):
        raise ProjectionError("source launch, runs, and telemetry must be objects")
    epic_ids = launch.get("targetEpicIds")
    launch_epics = launch.get("epics")
    if not isinstance(epic_ids, list) or not epic_ids or not isinstance(launch_epics, dict):
        raise ProjectionError("launch must declare target Epic membership")
    if set(epic_ids) != set(launch_epics) or not set(epic_ids).issubset(runs):
        raise ProjectionError("launch and run Epic membership disagree")
    now, current = now_value(now)
    launch_id = str(launch.get("coverageSha256") or digest({"epics": sorted(epic_ids)}))[:64]
    epics = [
        epic_projection(
            launch_id, epic_id, launch_epics[epic_id], runs[epic_id], telemetry.get(epic_id),
            now, current, stale_after,
        )
        for epic_id in epic_ids
    ]
    return {"schema": PROJECTION_SCHEMA, "generatedAt": now, "launch": {"id": launch_id}, "epics": epics}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--now")
    parser.add_argument("--stale-after", type=int, default=300)
    args = parser.parse_args()
    try:
        source = json.loads(args.source.read_text(encoding="utf-8"))
        print(json.dumps(build_projection(source, now=args.now, stale_after=args.stale_after), sort_keys=True, indent=2))
    except (OSError, json.JSONDecodeError, ProjectionError) as exc:
        print(f"error: {exc}", file=__import__("sys").stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
