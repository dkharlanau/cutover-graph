#!/usr/bin/env python3
"""Evaluate a cutover plan against machine-readable readiness policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from cutover_graph import DONE_STATES, build_report, load_plan


def load_policy(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        policy = json.load(handle)
    if not isinstance(policy, dict):
        raise ValueError("policy must be a JSON object")
    return policy


def evaluate(plan: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    report = build_report(plan)
    tasks = {str(task.get("id")): task for task in plan.get("tasks", []) if task.get("id")}
    checks = []

    def add(name: str, passed: bool, actual: Any, expected: Any) -> None:
        checks.append({"name": name, "passed": passed, "actual": actual, "expected": expected})

    if policy.get("require_valid_plan", True):
        add("valid_plan", report["validation"]["valid"], report["validation"]["valid"], True)

    if policy.get("require_owners", False):
        missing = sorted(task_id for task_id, task in tasks.items() if not str(task.get("owner", "")).strip())
        add("owners", not missing, missing, [])

    required_complete = [str(task_id) for task_id in policy.get("required_complete", [])]
    incomplete = sorted(
        task_id
        for task_id in required_complete
        if task_id not in tasks or str(tasks[task_id].get("status", "pending")).lower() not in DONE_STATES
    )
    if required_complete:
        add("required_complete", not incomplete, incomplete, [])

    if policy.get("require_evidence_for_completed", False):
        missing_evidence = sorted(
            task_id
            for task_id, task in tasks.items()
            if str(task.get("status", "pending")).lower() in DONE_STATES and not task.get("evidence")
        )
        add("completed_task_evidence", not missing_evidence, missing_evidence, [])

    max_blocked = policy.get("max_blocked_tasks")
    if max_blocked is not None:
        actual = len(report["blockers"])
        add("blocked_tasks", actual <= int(max_blocked), actual, f"<={int(max_blocked)}")

    max_critical = policy.get("max_critical_path_minutes")
    if max_critical is not None:
        actual = report["critical_path"]["duration_minutes"]
        passed = actual is not None and actual <= int(max_critical)
        add("critical_path_minutes", passed, actual, f"<={int(max_critical)}")

    return {
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
        "failed_checks": [check["name"] for check in checks if not check["passed"]],
        "active_blockers": report["blockers"],
        "critical_path": report["critical_path"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate cutover readiness policy")
    parser.add_argument("plan")
    parser.add_argument("policy")
    args = parser.parse_args()

    result = evaluate(load_plan(args.plan), load_policy(args.policy))
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
