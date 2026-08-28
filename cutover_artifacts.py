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
from external_evidence import load_registry, verify_checkpoint, verified_task_complete


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


def _unverified_external_result(task: dict[str, Any], external_refs: list[str]) -> dict[str, Any]:
    native = checkpoint_status(task)
    evidence_types = {}
    checkpoint = task.get("checkpoint") if isinstance(task.get("checkpoint"), dict) else {}
    for record in checkpoint.get("evidence", []):
        if isinstance(record, dict):
            ref = str(record.get("ref", "")).strip()
            if ref:
                evidence_types[ref] = str(record.get("type", "evidence")).strip() or "evidence"
    return {
        "task": str(task.get("id", "")),
        "native_checkpoint_passed": native["passed"],
        "external_refs_required": True,
        "external_evidence_passed": False,
        "passed": False,
        "registry_duplicate_refs": [],
        "verifications": [
            {
                "type": evidence_types.get(ref, "evidence"),
                "ref": ref,
                "verified": False,
                "reason": "verification_registry_not_supplied",
                "status": None,
                "document_sha256": None,
                "configuration_sha256": None,
                "observed_at": None,
            }
            for ref in external_refs
        ],
    }


def _task_artifact(
    task: dict[str, Any],
    task_ref: str,
    task_refs: dict[str, str],
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
        native = checkpoint_status(task)
        evidence_refs = _evidence_refs(checkpoint)
        external_refs = [ref for ref in evidence_refs if ref.startswith("eac://")]

        if external_refs and registry is None:
            verification = _unverified_external_result(task, external_refs)
            verification_mode = "unverified_external"
            result["complete"] = False
        elif external_refs:
            verification = verify_checkpoint(task, registry)
            verification_mode = "external_registry"
            result["complete"] = verified_task_complete(task, registry)
        else:
            verification = {
                "task": task_id,
                "native_checkpoint_passed": native["passed"],
                "external_refs_required": False,
                "external_evidence_passed": True,
                "passed": native["passed"],
                "registry_duplicate_refs": [],
                "verifications": [],
            }
            verification_mode = "local_only"

        result["checkpoint"] = {
            "artifact_ref": artifact_ref("checkpoint", task_id),
            "passed": verification["passed"],
            "native_passed": native["passed"],
            "verification_mode": verification_mode,
            "external_evidence_required": verification["external_refs_required"],
            "external_evidence_passed": verification["external_evidence_passed"],
            "verifications": verification["verifications"],
            "missing_approvals": native["missing_approvals"],
            "missing_evidence": native["missing_evidence"],
            "duplicate_approvals": native["duplicate_approvals"],
            "duplicate_evidence": native["duplicate_evidence"],
            "required_approvals": sorted({str(value).strip() for value in checkpoint.get("required_approvals", []) if str(value).strip()}),
            "required_evidence": sorted({str(value).strip() for value in checkpoint.get("required_evidence", []) if str(value).strip()}),
            "evidence_refs": evidence_refs,
        }
    return result


def build_index(plan: dict[str, Any], registry: dict[str, Any] | None = None) -> dict[str, Any]:
    main_validation = validate(plan)
    contingency_validation = validate_contingencies(plan)
    tasks = {
        str(task.get("id")): task
        for task in plan.get("tasks", [])
        if str(task.get("id", "")).strip()
    }
    task_refs = {task_id: artifact_ref("task", task_id) for task_id in tasks}
    task_artifacts = [
        _task_artifact(tasks[task_id], task_refs[task_id], task_refs, registry)
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

    external_checkpoints = [
        item["checkpoint"]
        for item in task_artifacts
        if isinstance(item.get("checkpoint"), dict) and item["checkpoint"]["external_evidence_required"]
    ]
    return {
        "schema_version": "0.1",
        "repository": "dkharlanau/cutover-graph",
        "valid": bool(main_validation["valid"] and contingency_validation["valid"]),
        "assurance": {
            "external_registry_supplied": registry is not None,
            "external_checkpoints": len(external_checkpoints),
            "external_checkpoints_verified": sum(
                1 for checkpoint in external_checkpoints if checkpoint["external_evidence_passed"]
            ),
            "passed": all(checkpoint["passed"] for checkpoint in external_checkpoints),
        },
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
    parser.add_argument("--registry", help="Verified external evidence registry. Required to export external eac:// checkpoints as passed.")
    parser.add_argument("--output", "-o")
    args = parser.parse_args()
    registry = load_registry(args.registry) if args.registry else None
    index = build_index(load_plan(args.plan), registry)
    payload = json.dumps(index, indent=2)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0 if index["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
