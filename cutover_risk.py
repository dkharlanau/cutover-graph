#!/usr/bin/env python3
"""Deterministic open-risk concentration analysis for Cutover Graph."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from cutover_graph import DONE_STATES, RUNNING_STATES, checkpoint_status, critical_path, load_plan, task_complete


DEFAULT_RISK_WEIGHTS = {
    "r0": 0.5,
    "r1": 1.0,
    "r2": 2.0,
    "r3": 4.0,
    "r4": 8.0,
    "low": 1.0,
    "medium": 2.0,
    "high": 5.0,
    "critical": 10.0,
}

DEFAULT_STATE_FACTORS = {
    "pending": 1.0,
    "running": 1.25,
    "failed": 2.0,
    "checkpoint_blocked": 1.5,
    "done": 0.0,
    "cancelled": 0.0,
    "skipped": 0.0,
}

FAILED_STATES = {"failed", "error"}
CANCELLED_STATES = {"cancelled", "canceled"}
SKIPPED_STATES = {"skipped"}


def load_policy(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("risk policy must be a JSON object")
    return value


def execution_state(task: dict[str, Any]) -> str:
    raw = str(task.get("status", "pending")).strip().lower()
    if raw in DONE_STATES:
        if task_complete(task):
            return "done"
        return "checkpoint_blocked"
    if raw in RUNNING_STATES:
        return "running"
    if raw in FAILED_STATES:
        return "failed"
    if raw in CANCELLED_STATES:
        return "cancelled"
    if raw in SKIPPED_STATES:
        return "skipped"
    return "pending"


def _risk_weight(task: dict[str, Any], weights: dict[str, float], default_weight: float) -> tuple[str | None, float, bool]:
    raw = task.get("risk")
    risk = str(raw).strip() if raw is not None and str(raw).strip() else None
    if risk is None:
        return None, default_weight, False
    key = risk.lower()
    return risk, weights.get(key, default_weight), key in weights


def _aggregate(tasks: list[dict[str, Any]], field: str, total_score: float) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = defaultdict(lambda: {"score": 0.0, "tasks": []})
    missing_label = f"unassigned_{field}"
    for item in tasks:
        label = str(item.get(field) or "").strip() or missing_label
        groups[label]["score"] += float(item["open_risk_score"])
        groups[label]["tasks"].append(item["id"])
    rows = []
    for label, value in groups.items():
        score = value["score"]
        rows.append({
            field: label,
            "open_risk_score": score,
            "share": 0.0 if total_score == 0 else score / total_score,
            "open_task_count": sum(1 for item in tasks if (str(item.get(field) or "").strip() or missing_label) == label and item["open_risk_score"] > 0),
            "tasks": sorted(value["tasks"]),
        })
    rows.sort(key=lambda item: (-item["open_risk_score"], str(item[field])))
    return rows


def analyze(plan: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or {}
    weights = {key: float(value) for key, value in DEFAULT_RISK_WEIGHTS.items()}
    weights.update({str(key).lower(): float(value) for key, value in policy.get("risk_weights", {}).items()})
    factors = {key: float(value) for key, value in DEFAULT_STATE_FACTORS.items()}
    factors.update({str(key): float(value) for key, value in policy.get("state_factors", {}).items()})
    default_weight = float(policy.get("default_risk_weight", 1.0))
    critical_multiplier = float(policy.get("critical_path_multiplier", 1.5))

    critical = critical_path(plan)
    critical_tasks = set(critical.get("tasks", []))
    rows = []
    unknown_risks = []
    missing_risk_tasks = []

    for task in sorted(plan.get("tasks", []), key=lambda item: str(item.get("id", ""))):
        task_id = str(task.get("id", "")).strip()
        if not task_id:
            continue
        state = execution_state(task)
        risk, risk_weight, known = _risk_weight(task, weights, default_weight)
        if risk is None:
            missing_risk_tasks.append(task_id)
        elif not known:
            unknown_risks.append({"task": task_id, "risk": risk, "used_weight": risk_weight})
        state_factor = factors.get(state, factors.get("pending", 1.0))
        unresolved = not task_complete(task) and state not in {"cancelled", "skipped"}
        on_critical = task_id in critical_tasks and unresolved
        path_multiplier = critical_multiplier if on_critical else 1.0
        score = risk_weight * state_factor * path_multiplier
        checkpoint = checkpoint_status(task)
        rows.append({
            "id": task_id,
            "owner": task.get("owner"),
            "workstream": task.get("workstream"),
            "risk": risk,
            "risk_known": known if risk is not None else False,
            "risk_weight": risk_weight,
            "execution_state": state,
            "state_factor": state_factor,
            "on_unresolved_critical_path": on_critical,
            "critical_path_multiplier": path_multiplier,
            "checkpoint_required": checkpoint["required"],
            "checkpoint_passed": checkpoint["passed"],
            "open_risk_score": score,
        })

    total_score = sum(item["open_risk_score"] for item in rows)
    open_rows = [item for item in rows if item["open_risk_score"] > 0]
    return {
        "total_open_risk_score": total_score,
        "open_task_count": len(open_rows),
        "critical_path": critical,
        "configuration": {
            "default_risk_weight": default_weight,
            "critical_path_multiplier": critical_multiplier,
            "risk_weights": dict(sorted(weights.items())),
            "state_factors": dict(sorted(factors.items())),
        },
        "unknown_risks": unknown_risks,
        "missing_risk_tasks": missing_risk_tasks,
        "tasks": rows,
        "by_owner": _aggregate(rows, "owner", total_score),
        "by_workstream": _aggregate(rows, "workstream", total_score),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Cutover Graph operational risk concentration")
    parser.add_argument("plan")
    parser.add_argument("--policy")
    args = parser.parse_args()
    result = analyze(load_plan(args.plan), load_policy(args.policy) if args.policy else None)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
