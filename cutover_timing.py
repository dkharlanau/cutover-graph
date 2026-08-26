#!/usr/bin/env python3
"""Time-aware cutover baseline, forecast, and delay propagation."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from cutover_graph import DONE_STATES, RUNNING_STATES, _status, _task_index, execution_waves, load_plan, validate


def parse_iso(value: str) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        result = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"invalid ISO-8601 timestamp: {value!r}") from exc
    if result.tzinfo is None:
        raise ValueError(f"timestamp must include timezone: {value!r}")
    return result


def format_iso(value: datetime) -> str:
    normalized = value.astimezone(timezone.utc).isoformat(timespec="seconds")
    return normalized.replace("+00:00", "Z")


def minutes(delta: timedelta) -> int:
    return int(round(delta.total_seconds() / 60))


def timing_report(plan: dict[str, Any]) -> dict[str, Any]:
    graph_validation = validate(plan)
    errors = []
    if not graph_validation["valid"]:
        errors.append("cutover dependency graph is invalid")

    anchor_text = plan.get("cutover_start")
    if not anchor_text:
        errors.append("cutover_start is required for time-aware planning")
        return {"timing_valid": False, "errors": errors, "tasks": []}

    try:
        anchor = parse_iso(str(anchor_text))
        as_of = parse_iso(str(plan.get("as_of"))) if plan.get("as_of") else None
    except ValueError as exc:
        errors.append(str(exc))
        return {"timing_valid": False, "errors": errors, "tasks": []}

    if errors:
        return {"timing_valid": False, "errors": errors, "tasks": []}

    tasks, _ = _task_index(plan)
    waves = execution_waves(plan)
    baseline: dict[str, tuple[datetime, datetime]] = {}
    forecast: dict[str, tuple[datetime, datetime]] = {}
    detail: dict[str, dict[str, Any]] = {}

    for wave in waves:
        for task_id in wave:
            task = tasks[task_id]
            duration = int(task.get("duration_minutes", 0) or 0)
            if duration < 0:
                errors.append(f"task {task_id}: duration_minutes must be >= 0")
                continue

            try:
                planned_floor = parse_iso(str(task["planned_start"])) if task.get("planned_start") else anchor
                actual_start = parse_iso(str(task["actual_start"])) if task.get("actual_start") else None
                actual_end = parse_iso(str(task["actual_end"])) if task.get("actual_end") else None
            except ValueError as exc:
                errors.append(f"task {task_id}: {exc}")
                continue

            deps = [str(dep) for dep in task.get("depends_on", [])]
            baseline_dep_end = max((baseline[dep][1] for dep in deps), default=anchor)
            baseline_start = max(planned_floor, baseline_dep_end)
            baseline_end = baseline_start + timedelta(minutes=duration)
            baseline[task_id] = (baseline_start, baseline_end)

            forecast_dep_end = max((forecast[dep][1] for dep in deps), default=anchor)
            earliest_start = max(planned_floor, forecast_dep_end)
            status = _status(task)

            if status in DONE_STATES:
                start = actual_start or earliest_start
                end = actual_end or (start + timedelta(minutes=duration))
            elif status in RUNNING_STATES:
                start = actual_start or earliest_start
                if task.get("remaining_minutes") is not None and as_of is not None:
                    end = as_of + timedelta(minutes=int(task.get("remaining_minutes") or 0))
                else:
                    end = start + timedelta(minutes=duration)
                    if as_of is not None and end < as_of:
                        end = as_of
            else:
                start = earliest_start
                end = start + timedelta(minutes=duration)

            if end < start:
                errors.append(f"task {task_id}: forecast/actual end precedes start")
                continue

            forecast[task_id] = (start, end)
            upstream_delay = max(0, minutes(earliest_start - baseline_start))
            total_variance = minutes(end - baseline_end)
            own_delay = max(0, total_variance - upstream_delay)

            detail[task_id] = {
                "task": task_id,
                "status": status,
                "baseline_start": format_iso(baseline_start),
                "baseline_end": format_iso(baseline_end),
                "forecast_start": format_iso(start),
                "forecast_end": format_iso(end),
                "variance_minutes": total_variance,
                "upstream_delay_minutes": upstream_delay,
                "own_delay_minutes": own_delay,
            }

    if errors or len(forecast) != len(tasks):
        return {"timing_valid": False, "errors": errors or ["could not schedule every task"], "tasks": list(detail.values())}

    baseline_completion = max((end for _, end in baseline.values()), default=anchor)
    forecast_completion = max((end for _, end in forecast.values()), default=anchor)
    affected = [
        {"task": task_id, "variance_minutes": item["variance_minutes"]}
        for task_id, item in sorted(detail.items())
        if item["variance_minutes"] > 0
    ]
    origins = [
        {"task": task_id, "own_delay_minutes": item["own_delay_minutes"]}
        for task_id, item in sorted(detail.items())
        if item["own_delay_minutes"] > 0
    ]

    return {
        "timing_valid": True,
        "errors": [],
        "cutover_start": format_iso(anchor),
        "as_of": format_iso(as_of) if as_of else None,
        "baseline_completion": format_iso(baseline_completion),
        "forecast_completion": format_iso(forecast_completion),
        "completion_variance_minutes": minutes(forecast_completion - baseline_completion),
        "origin_delays": origins,
        "affected_tasks": affected,
        "tasks": [detail[task_id] for task_id in sorted(detail)],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Calculate time-aware cutover forecast and delay propagation")
    parser.add_argument("plan")
    args = parser.parse_args()
    result = timing_report(load_plan(args.plan))
    print(json.dumps(result, indent=2))
    return 0 if result["timing_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
