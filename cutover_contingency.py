#!/usr/bin/env python3
"""Evaluate deterministic rollback/contingency branches for Cutover Graph."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from cutover_graph import DONE_STATES, RUNNING_STATES, load_plan


def _status(task: dict[str, Any]) -> str:
    return str(task.get("status", "pending")).strip().lower()


def _main_tasks(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(task.get("id")): task for task in plan.get("tasks", []) if str(task.get("id", "")).strip()}


def _branch_tasks(branch: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    result: dict[str, dict[str, Any]] = {}
    duplicates = []
    for task in branch.get("tasks", []):
        task_id = str(task.get("id", "")).strip()
        if not task_id:
            continue
        if task_id in result:
            duplicates.append(task_id)
        result[task_id] = task
    return result, sorted(set(duplicates))


def _condition_result(plan: dict[str, Any], condition: dict[str, Any]) -> dict[str, Any]:
    if "task" in condition:
        task_id = str(condition["task"])
        tasks = _main_tasks(plan)
        allowed = sorted({str(value).strip().lower() for value in condition.get("status_in", [])})
        actual = _status(tasks[task_id]) if task_id in tasks else None
        return {
            "kind": "task_status",
            "task": task_id,
            "actual": actual,
            "expected": allowed,
            "passed": actual in allowed if actual is not None else False,
        }
    if "signal" in condition:
        signal = str(condition["signal"])
        expected = condition.get("equals", True)
        actual = plan.get("signals", {}).get(signal)
        return {
            "kind": "signal",
            "signal": signal,
            "actual": actual,
            "expected": expected,
            "passed": actual == expected,
        }
    return {"kind": "invalid", "passed": False, "error": "condition must contain task or signal"}


def _cycles(tasks: dict[str, dict[str, Any]]) -> list[list[str]]:
    state = {task_id: 0 for task_id in tasks}
    stack: list[str] = []
    cycles: list[list[str]] = []

    def visit(task_id: str) -> None:
        state[task_id] = 1
        stack.append(task_id)
        for dep in tasks[task_id].get("depends_on", []):
            dep_id = str(dep)
            if dep_id not in tasks:
                continue
            if state[dep_id] == 0:
                visit(dep_id)
            elif state[dep_id] == 1:
                start = stack.index(dep_id)
                cycle = stack[start:] + [dep_id]
                if cycle not in cycles:
                    cycles.append(cycle)
        stack.pop()
        state[task_id] = 2

    for task_id in tasks:
        if state[task_id] == 0:
            visit(task_id)
    return cycles


def validate(plan: dict[str, Any]) -> dict[str, Any]:
    main_tasks = _main_tasks(plan)
    branches = plan.get("contingencies", [])
    branch_ids: set[str] = set()
    duplicate_branches = []
    findings = []

    for index, branch in enumerate(branches):
        branch_id = str(branch.get("id", "")).strip()
        if not branch_id:
            findings.append({"contingency_index": index, "error": "missing contingency id"})
            continue
        if branch_id in branch_ids:
            duplicate_branches.append(branch_id)
        branch_ids.add(branch_id)

        mode = str(branch.get("mode", "all")).lower()
        if mode not in {"all", "any"}:
            findings.append({"contingency": branch_id, "error": "mode must be all or any"})

        for condition in branch.get("activate_when", []):
            if "task" in condition and str(condition["task"]) not in main_tasks:
                findings.append({"contingency": branch_id, "error": "unknown trigger task", "task": str(condition["task"])})
            elif "task" in condition and not condition.get("status_in"):
                findings.append({"contingency": branch_id, "error": "task condition requires status_in", "task": str(condition["task"])})
            elif "signal" not in condition and "task" not in condition:
                findings.append({"contingency": branch_id, "error": "invalid activation condition"})

        tasks, duplicates = _branch_tasks(branch)
        if duplicates:
            findings.append({"contingency": branch_id, "error": "duplicate branch tasks", "tasks": duplicates})
        missing = []
        for task_id, task in tasks.items():
            for dep in task.get("depends_on", []):
                if str(dep) not in tasks:
                    missing.append({"task": task_id, "missing": str(dep)})
        if missing:
            findings.append({"contingency": branch_id, "error": "missing branch dependencies", "details": missing})
        cycles = _cycles(tasks)
        if cycles:
            findings.append({"contingency": branch_id, "error": "branch cycles", "cycles": cycles})

    return {
        "contingency_count": len(branches),
        "duplicate_contingencies": sorted(set(duplicate_branches)),
        "findings": findings,
        "valid": not duplicate_branches and not findings,
    }


def branch_active(plan: dict[str, Any], branch: dict[str, Any]) -> dict[str, Any]:
    conditions = [_condition_result(plan, condition) for condition in branch.get("activate_when", [])]
    mode = str(branch.get("mode", "all")).lower()
    if not conditions:
        active = False
    elif mode == "any":
        active = any(item["passed"] for item in conditions)
    else:
        active = all(item["passed"] for item in conditions)
    return {"active": active, "mode": mode, "conditions": conditions}


def branch_waves(branch: dict[str, Any]) -> list[list[str]]:
    tasks, _ = _branch_tasks(branch)
    indegree = {task_id: 0 for task_id in tasks}
    children: dict[str, list[str]] = defaultdict(list)
    for task_id, task in tasks.items():
        for dep in task.get("depends_on", []):
            dep_id = str(dep)
            if dep_id in tasks:
                indegree[task_id] += 1
                children[dep_id].append(task_id)
    ready = sorted(task_id for task_id, degree in indegree.items() if degree == 0)
    waves: list[list[str]] = []
    processed = 0
    while ready:
        wave = ready
        waves.append(wave)
        processed += len(wave)
        next_ready = []
        for task_id in wave:
            for child in children[task_id]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    next_ready.append(child)
        ready = sorted(next_ready)
    return waves if processed == len(tasks) else []


def branch_report(branch: dict[str, Any]) -> dict[str, Any]:
    tasks, _ = _branch_tasks(branch)
    completed = sorted(task_id for task_id, task in tasks.items() if _status(task) in DONE_STATES)
    running = sorted(task_id for task_id, task in tasks.items() if _status(task) in RUNNING_STATES)
    executable = []
    blocked = []
    for task_id, task in tasks.items():
        if _status(task) in DONE_STATES or _status(task) in RUNNING_STATES:
            continue
        unresolved = [str(dep) for dep in task.get("depends_on", []) if str(dep) in tasks and _status(tasks[str(dep)]) not in DONE_STATES]
        if unresolved:
            blocked.append({"task": task_id, "blocked_by": unresolved})
        else:
            executable.append(task_id)
    total = len(tasks)
    return {
        "waves": branch_waves(branch),
        "completed": completed,
        "running": running,
        "executable_now": sorted(executable),
        "blockers": blocked,
        "completion_ratio": 1.0 if total == 0 else len(completed) / total,
    }


def build_report(plan: dict[str, Any]) -> dict[str, Any]:
    validation = validate(plan)
    contingencies = []
    for branch in plan.get("contingencies", []):
        activation = branch_active(plan, branch)
        contingencies.append({
            "id": branch.get("id"),
            "activation": activation,
            "execution": branch_report(branch) if activation["active"] else None,
        })
    return {
        "validation": validation,
        "active_contingencies": [item["id"] for item in contingencies if item["activation"]["active"]],
        "contingencies": contingencies,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Cutover Graph contingency branches")
    parser.add_argument("plan")
    args = parser.parse_args()
    report = build_report(load_plan(args.plan))
    print(json.dumps(report, indent=2))
    return 0 if report["validation"]["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
