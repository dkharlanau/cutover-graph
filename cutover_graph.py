#!/usr/bin/env python3
"""Dependency-aware cutover planner with zero runtime dependencies."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DONE_STATES = {"done", "completed", "verified"}
RUNNING_STATES = {"running", "in_progress", "in-progress"}


def load_plan(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        plan = json.load(handle)
    if not isinstance(plan, dict):
        raise ValueError("plan must be a JSON object")
    return plan


def _status(task: dict[str, Any]) -> str:
    return str(task.get("status", "pending")).strip().lower()


def _record_key(record: Any, field: str) -> str:
    if isinstance(record, str):
        return record.strip()
    if isinstance(record, dict):
        return str(record.get(field) or record.get("id") or record.get("name") or "").strip()
    return ""


def checkpoint_status(task: dict[str, Any]) -> dict[str, Any]:
    """Evaluate optional approval/evidence gate attached to a task."""
    checkpoint = task.get("checkpoint")
    if not isinstance(checkpoint, dict):
        return {
            "required": False,
            "passed": True,
            "missing_approvals": [],
            "missing_evidence": [],
            "duplicate_approvals": [],
            "duplicate_evidence": [],
        }

    required_approvals = sorted({str(value).strip() for value in checkpoint.get("required_approvals", []) if str(value).strip()})
    approval_values = [_record_key(record, "role") for record in checkpoint.get("approvals", [])]
    approval_values = [value for value in approval_values if value]
    approval_set = set(approval_values)

    required_evidence = sorted({str(value).strip() for value in checkpoint.get("required_evidence", []) if str(value).strip()})
    evidence_values = [_record_key(record, "type") for record in checkpoint.get("evidence", [])]
    evidence_values = [value for value in evidence_values if value]
    evidence_set = set(evidence_values)

    duplicate_approvals = sorted(value for value, count in Counter(approval_values).items() if count > 1)
    duplicate_evidence = sorted(value for value, count in Counter(evidence_values).items() if count > 1)
    missing_approvals = sorted(set(required_approvals) - approval_set)
    missing_evidence = sorted(set(required_evidence) - evidence_set)

    return {
        "required": True,
        "passed": not missing_approvals and not missing_evidence,
        "missing_approvals": missing_approvals,
        "missing_evidence": missing_evidence,
        "duplicate_approvals": duplicate_approvals,
        "duplicate_evidence": duplicate_evidence,
    }


def task_complete(task: dict[str, Any]) -> bool:
    return _status(task) in DONE_STATES and checkpoint_status(task)["passed"]


def _task_index(plan: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    tasks = plan.get("tasks", [])
    index: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for task in tasks:
        task_id = str(task.get("id", ""))
        if not task_id:
            continue
        if task_id in index:
            duplicates.append(task_id)
        index[task_id] = task
    return index, sorted(set(duplicates))


def validate(plan: dict[str, Any]) -> dict[str, Any]:
    tasks, duplicates = _task_index(plan)
    missing_dependencies = []
    for task_id, task in tasks.items():
        for dep in task.get("depends_on", []):
            dep_id = str(dep)
            if dep_id not in tasks:
                missing_dependencies.append({"task": task_id, "missing": dep_id})

    cycles = find_cycles(plan) if not missing_dependencies else []
    return {
        "task_count": len(plan.get("tasks", [])),
        "duplicate_tasks": duplicates,
        "missing_dependencies": missing_dependencies,
        "cycles": cycles,
        "valid": not duplicates and not missing_dependencies and not cycles,
    }


def find_cycles(plan: dict[str, Any]) -> list[list[str]]:
    tasks, _ = _task_index(plan)
    state: dict[str, int] = {task_id: 0 for task_id in tasks}
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


def execution_waves(plan: dict[str, Any]) -> list[list[str]]:
    tasks, _ = _task_index(plan)
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
        next_ready: list[str] = []
        for task_id in wave:
            for child in children[task_id]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    next_ready.append(child)
        ready = sorted(next_ready)

    if processed != len(tasks):
        return []
    return waves


def critical_path(plan: dict[str, Any]) -> dict[str, Any]:
    tasks, _ = _task_index(plan)
    waves = execution_waves(plan)
    if tasks and not waves:
        return {"tasks": [], "duration_minutes": None}

    best_duration: dict[str, int] = {}
    best_path: dict[str, list[str]] = {}
    for wave in waves:
        for task_id in wave:
            task = tasks[task_id]
            duration = int(task.get("duration_minutes", 0) or 0)
            deps = [str(dep) for dep in task.get("depends_on", []) if str(dep) in tasks]
            if not deps:
                best_duration[task_id] = duration
                best_path[task_id] = [task_id]
                continue
            parent = max(deps, key=lambda dep: best_duration[dep])
            best_duration[task_id] = best_duration[parent] + duration
            best_path[task_id] = best_path[parent] + [task_id]

    if not best_duration:
        return {"tasks": [], "duration_minutes": 0}
    end = max(best_duration, key=best_duration.get)
    return {"tasks": best_path[end], "duration_minutes": best_duration[end]}


def checkpoint_report(plan: dict[str, Any]) -> list[dict[str, Any]]:
    tasks, _ = _task_index(plan)
    result = []
    for task_id in sorted(tasks):
        status = checkpoint_status(tasks[task_id])
        if status["required"]:
            result.append({"task": task_id, **status})
    return result


def blockers(plan: dict[str, Any]) -> list[dict[str, Any]]:
    tasks, _ = _task_index(plan)
    blocked = []
    for task_id, task in tasks.items():
        if task_complete(task):
            continue
        unresolved = [
            str(dep)
            for dep in task.get("depends_on", [])
            if str(dep) in tasks and not task_complete(tasks[str(dep)])
        ]
        if unresolved:
            blocked.append({"task": task_id, "blocked_by": unresolved})
    return blocked


def executable_now(plan: dict[str, Any]) -> list[str]:
    """Return not-started tasks whose dependencies are all checkpoint-complete."""
    tasks, _ = _task_index(plan)
    ready = []
    for task_id, task in tasks.items():
        status = _status(task)
        if status in DONE_STATES or status in RUNNING_STATES:
            continue
        deps = [str(dep) for dep in task.get("depends_on", [])]
        if all(dep in tasks and task_complete(tasks[dep]) for dep in deps):
            ready.append(task_id)
    return sorted(ready)


def progress(plan: dict[str, Any]) -> dict[str, Any]:
    tasks, _ = _task_index(plan)
    completed = sorted(task_id for task_id, task in tasks.items() if task_complete(task))
    status_done_but_checkpoint_blocked = sorted(
        task_id
        for task_id, task in tasks.items()
        if _status(task) in DONE_STATES and not task_complete(task)
    )
    running = sorted(task_id for task_id, task in tasks.items() if _status(task) in RUNNING_STATES)
    total = len(tasks)
    return {
        "total": total,
        "completed": completed,
        "status_done_but_checkpoint_blocked": status_done_but_checkpoint_blocked,
        "running": running,
        "completed_count": len(completed),
        "running_count": len(running),
        "completion_ratio": 1.0 if total == 0 else len(completed) / total,
    }


def build_report(plan: dict[str, Any]) -> dict[str, Any]:
    validation = validate(plan)
    valid_dependencies = not validation["missing_dependencies"]
    return {
        "validation": validation,
        "waves": execution_waves(plan) if validation["valid"] else [],
        "critical_path": critical_path(plan) if validation["valid"] else {"tasks": [], "duration_minutes": None},
        "progress": progress(plan),
        "checkpoints": checkpoint_report(plan),
        "executable_now": executable_now(plan) if valid_dependencies else [],
        "blockers": blockers(plan) if valid_dependencies else [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and plan an enterprise cutover graph")
    parser.add_argument("plan", help="Path to cutover plan JSON")
    parser.add_argument("command", nargs="?", default="plan", choices=["validate", "plan"])
    args = parser.parse_args()

    plan = load_plan(args.plan)
    result = validate(plan) if args.command == "validate" else build_report(plan)
    print(json.dumps(result, indent=2))
    valid = result["valid"] if args.command == "validate" else result["validation"]["valid"]
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
