#!/usr/bin/env python3
"""Emit stable Enterprise-as-Code artifact references from a Cutover Graph plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

from cutover_contingency import branch_active, validate as validate_contingencies
from cutover_graph import checkpoint_status, load_plan, task_complete, validate


def artifact_ref(kind: str, *segments: str) -> str:
    local = "/".join(quote(str(segment), safe="._-:@") for segment in segments)
    return f"eac://dkharlanau/cutover-graph/{quote(kind, safe='._-')}/{local}"


def _evidence_refs(checkpoint: dict[str, Any]) -> list[str]:
    refs = []
    for record in checkpoint.get("evidence", []):
        if isinstance(record, str):
            value = record.strip()
        elif isinstance(record, dict):
            value = str(record.get("ref", "")).strip()
        else:
            value = ""
        if value:
            refs.append(value)
    return sorted(set(refs))


def _task_artifact(task: dict[str, Any], task_ref: str, task_refs: dict[str, str]) -> dict[str, Any]:
    task_id = str(task.get("id", "")).strip()
    result: dict[str, Any] = {
        "id": task_id,
        "artifact_ref": task_ref,
        "status": str(task.get("status", "pending")).strip().lower(),
        "complete": task_complete(task),
        "depends_on_refs": [task_refs[str(dep)] for dep in task.get("depends_on", []) if str(dep) in task_refs],
    }
    for field in ("owner", "workstream", "risk", "duration_minutes", "actual_start", "actual_end", "remaining_minutes"):
        if task.get(field) is not None:
            result[field] = task[field]
    if isinstance(task.get("checkpoint"), dict):
        checkpoint = task["checkpoint"]
        state = checkpoint_status(task)
        result["checkpoint"] = {
            "artifact_ref": artifact_ref("checkpoint", task_id),
            "passed": state["passed"],
            "missing_approvals": state["missing_approvals"],
            "missing_evidence": state["missing_evidence"],
            "duplicate_approvals": state["duplicate_approvals"],
            "duplicate_evidence": state["duplicate_evidence"],
            "required_approvals": sorted({str(value).strip() for value in checkpoint.get("required_approvals", []) if str(value).strip()}),
            "required_evidence": sorted({str(value).strip() for value in checkpoint.get("required_evidence", []) if str(value).strip()}),
            "evidence_refs": _evidence_refs(checkpoint),
        }
    return result


def build_index(plan: dict[str, Any]) -> dict[str, Any]:
    main_validation = validate(plan)
    contingency_validation = validate_contingencies(plan)
    tasks = {
        str(task.get("id")): task
        for task in plan.get("tasks", [])
        if str(task.get("id", "")).strip()
    }
    task_refs = {task_id: artifact_ref("task", task_id) for task_id in tasks}
    task_artifacts = [
        _task_artifact(tasks[task_id], task_refs[task_id], task_refs)
        for task_id in sorted(tasks)
    ]

    contingencies = []
    for branch in sorted(plan.get("contingencies", []), key=lambda item: str(item.get("id", ""))):
        branch_id = str(branch.get("id", "")).strip()
        if not branch_id:
            continue
        branch_tasks = {
            str(task.get("id")): task
            for task in branch.get("tasks", [])
            if str(task.get("id", "")).strip()
        }
        branch_task_refs = {
            task_id: artifact_ref("contingency", branch_id, "task", task_id)
            for task_id in branch_tasks
        }
        activation = branch_active(plan, branch)
        artifacts = []
        for task_id in sorted(branch_tasks):
            task = branch_tasks[task_id]
            item: dict[str, Any] = {
                "id": task_id,
                "artifact_ref": branch_task_refs[task_id],
                "status": str(task.get("status", "pending")).strip().lower(),
                "depends_on_refs": [
                    branch_task_refs[str(dep)]
                    for dep in task.get("depends_on", [])
                    if str(dep) in branch_task_refs
                ],
            }
            for field in ("owner", "workstream", "risk", "duration_minutes"):
                if task.get(field) is not None:
                    item[field] = task[field]
            artifacts.append(item)
        contingencies.append({
            "id": branch_id,
            "artifact_ref": artifact_ref("contingency", branch_id),
            "active": activation["active"],
            "activation": activation,
            "tasks": artifacts,
        })

    return {
        "schema_version": "0.1",
        "repository": "dkharlanau/cutover-graph",
        "valid": bool(main_validation["valid"] and contingency_validation["valid"]),
        "validation": {
            "plan": main_validation,
            "contingencies": contingency_validation,
        },
        "tasks": task_artifacts,
        "contingencies": contingencies,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit stable eac:// artifact index from Cutover Graph")
    parser.add_argument("plan")
    parser.add_argument("--output", "-o")
    args = parser.parse_args()
    index = build_index(load_plan(args.plan))
    payload = json.dumps(index, indent=2)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0 if index["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
