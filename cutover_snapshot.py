#!/usr/bin/env python3
"""Create immutable cutover execution snapshots and validate state transitions."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cutover_contingency import branch_active
from cutover_graph import DONE_STATES, RUNNING_STATES, checkpoint_status, load_plan, task_complete, validate


PENDING_STATES = {"pending", "not_started", "not-started", "ready", "blocked"}
FAILED_STATES = {"failed", "error"}
CANCELLED_STATES = {"cancelled", "canceled"}
SKIPPED_STATES = {"skipped"}

DEFAULT_ALLOWED_TRANSITIONS = {
    "pending": ["pending", "running", "done", "failed", "cancelled", "skipped"],
    "running": ["running", "done", "failed", "cancelled"],
    "failed": ["failed", "running", "cancelled"],
    "done": ["done"],
    "cancelled": ["cancelled"],
    "skipped": ["skipped"],
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _parse_time(value: str) -> datetime:
    text = str(value).strip()
    if not text:
        raise ValueError("timestamp must not be empty")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"invalid ISO-8601 timestamp: {value!r}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return dt.astimezone(timezone.utc)


def _iso_utc(value: str) -> str:
    return _parse_time(value).isoformat().replace("+00:00", "Z")


def canonical_state(status: Any) -> str:
    value = str(status or "pending").strip().lower()
    if value in PENDING_STATES:
        return "pending"
    if value in RUNNING_STATES:
        return "running"
    if value in DONE_STATES:
        return "done"
    if value in FAILED_STATES:
        return "failed"
    if value in CANCELLED_STATES:
        return "cancelled"
    if value in SKIPPED_STATES:
        return "skipped"
    return value or "pending"


def _task_snapshot(task: dict[str, Any]) -> dict[str, Any]:
    checkpoint = checkpoint_status(task)
    item: dict[str, Any] = {
        "id": str(task.get("id", "")).strip(),
        "status": str(task.get("status", "pending")).strip().lower(),
        "state": canonical_state(task.get("status")),
        "complete": task_complete(task),
        "depends_on": sorted(str(dep) for dep in task.get("depends_on", [])),
        "checkpoint": {
            "required": checkpoint["required"],
            "passed": checkpoint["passed"],
            "missing_approvals": checkpoint["missing_approvals"],
            "missing_evidence": checkpoint["missing_evidence"],
        },
    }
    for field in (
        "owner", "workstream", "risk", "duration_minutes", "actual_start", "actual_end", "remaining_minutes"
    ):
        if task.get(field) is not None:
            item[field] = task[field]
    return item


def create_snapshot(
    plan: dict[str, Any],
    observed_at: str,
    parent_snapshot_id: str | None = None,
) -> dict[str, Any]:
    plan_validation = validate(plan)
    if not plan_validation["valid"]:
        raise ValueError("cannot snapshot an invalid cutover plan")

    observed = _iso_utc(observed_at)
    tasks = sorted(
        [_task_snapshot(task) for task in plan.get("tasks", []) if str(task.get("id", "")).strip()],
        key=lambda item: item["id"],
    )
    active_contingencies = []
    for branch in sorted(plan.get("contingencies", []), key=lambda item: str(item.get("id", ""))):
        branch_id = str(branch.get("id", "")).strip()
        if branch_id and branch_active(plan, branch)["active"]:
            active_contingencies.append(branch_id)

    state = {
        "tasks": tasks,
        "signals": {str(key): plan.get("signals", {})[key] for key in sorted(plan.get("signals", {}))},
        "active_contingencies": active_contingencies,
    }
    semantic = {
        "snapshot_version": "0.1",
        "observed_at": observed,
        "parent_snapshot_id": parent_snapshot_id,
        "plan_sha256": _sha256(plan),
        "state": state,
    }
    snapshot_id = "snap-" + _sha256(semantic)[:24]
    return {"snapshot_id": snapshot_id, **semantic}


def load_snapshot(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("snapshot must be a JSON object")
    return value


def load_policy(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("transition policy must be a JSON object")
    return value


def _snapshot_tasks(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    state = snapshot.get("state") if isinstance(snapshot.get("state"), dict) else {}
    return {
        str(task.get("id")): task
        for task in state.get("tasks", [])
        if isinstance(task, dict) and str(task.get("id", "")).strip()
    }


def validate_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    errors = []
    if snapshot.get("snapshot_version") != "0.1":
        errors.append("snapshot_version must be 0.1")
    snapshot_id = str(snapshot.get("snapshot_id", ""))
    if not snapshot_id.startswith("snap-"):
        errors.append("snapshot_id is missing or invalid")
    try:
        _parse_time(str(snapshot.get("observed_at", "")))
    except ValueError as exc:
        errors.append(str(exc))
    state = snapshot.get("state")
    if not isinstance(state, dict) or not isinstance(state.get("tasks"), list):
        errors.append("state.tasks must be an array")
    plan_sha = str(snapshot.get("plan_sha256", ""))
    if len(plan_sha) != 64 or any(char not in "0123456789abcdef" for char in plan_sha):
        errors.append("plan_sha256 must be lowercase SHA-256")
    if not errors:
        semantic = {
            "snapshot_version": snapshot["snapshot_version"],
            "observed_at": snapshot["observed_at"],
            "parent_snapshot_id": snapshot.get("parent_snapshot_id"),
            "plan_sha256": snapshot["plan_sha256"],
            "state": snapshot["state"],
        }
        expected_id = "snap-" + _sha256(semantic)[:24]
        if expected_id != snapshot_id:
            errors.append("snapshot_id does not match snapshot content")
    return {"valid": not errors, "errors": errors}


def validate_transition(
    previous: dict[str, Any],
    current: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or {}
    previous_validation = validate_snapshot(previous)
    current_validation = validate_snapshot(current)
    findings: list[dict[str, Any]] = []

    if not previous_validation["valid"]:
        findings.append({"type": "invalid_previous_snapshot", "errors": previous_validation["errors"]})
    if not current_validation["valid"]:
        findings.append({"type": "invalid_current_snapshot", "errors": current_validation["errors"]})
    if findings:
        return {
            "valid": False,
            "previous_snapshot_id": previous.get("snapshot_id"),
            "current_snapshot_id": current.get("snapshot_id"),
            "findings": findings,
            "added_tasks": [],
            "removed_tasks": [],
            "state_changes": [],
        }

    previous_time = _parse_time(previous["observed_at"])
    current_time = _parse_time(current["observed_at"])
    if current_time <= previous_time:
        findings.append({
            "type": "non_forward_timestamp",
            "previous": previous["observed_at"],
            "current": current["observed_at"],
        })

    parent = current.get("parent_snapshot_id")
    if parent is not None and parent != previous.get("snapshot_id"):
        findings.append({
            "type": "parent_mismatch",
            "expected": previous.get("snapshot_id"),
            "actual": parent,
        })
    if policy.get("require_parent", False) and parent != previous.get("snapshot_id"):
        findings.append({
            "type": "required_parent_missing_or_mismatched",
            "expected": previous.get("snapshot_id"),
            "actual": parent,
        })

    before = _snapshot_tasks(previous)
    after = _snapshot_tasks(current)
    before_ids = set(before)
    after_ids = set(after)
    added = sorted(after_ids - before_ids)
    removed = sorted(before_ids - after_ids)
    if added and not policy.get("allow_added_tasks", False):
        findings.append({"type": "tasks_added", "tasks": added})
    if removed and not policy.get("allow_removed_tasks", False):
        findings.append({"type": "tasks_removed", "tasks": removed})

    allowed = {
        str(source): [str(target) for target in targets]
        for source, targets in policy.get("allowed_transitions", DEFAULT_ALLOWED_TRANSITIONS).items()
    }
    changes = []
    for task_id in sorted(before_ids & after_ids):
        old_state = str(before[task_id].get("state", canonical_state(before[task_id].get("status"))))
        new_state = str(after[task_id].get("state", canonical_state(after[task_id].get("status"))))
        if old_state != new_state:
            changes.append({"task": task_id, "from": old_state, "to": new_state})
        legal_targets = allowed.get(old_state, [old_state])
        if new_state not in legal_targets:
            findings.append({
                "type": "illegal_task_transition",
                "task": task_id,
                "from": old_state,
                "to": new_state,
                "allowed": legal_targets,
            })

        old_checkpoint = before[task_id].get("checkpoint", {})
        new_checkpoint = after[task_id].get("checkpoint", {})
        if old_checkpoint.get("required") and old_checkpoint.get("passed"):
            if not new_checkpoint.get("required") or not new_checkpoint.get("passed"):
                findings.append({
                    "type": "checkpoint_regression",
                    "task": task_id,
                    "previous": old_checkpoint,
                    "current": new_checkpoint,
                })

    return {
        "valid": not findings,
        "previous_snapshot_id": previous["snapshot_id"],
        "current_snapshot_id": current["snapshot_id"],
        "previous_observed_at": previous["observed_at"],
        "current_observed_at": current["observed_at"],
        "added_tasks": added,
        "removed_tasks": removed,
        "state_changes": changes,
        "findings": findings,
    }


def _write(path: str | Path, value: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and validate immutable Cutover Graph snapshots")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("plan")
    create.add_argument("--observed-at")
    create.add_argument("--parent-snapshot-id")
    create.add_argument("--output", "-o", required=True)

    transition = sub.add_parser("transition")
    transition.add_argument("previous")
    transition.add_argument("current")
    transition.add_argument("--policy")

    validate_cmd = sub.add_parser("validate")
    validate_cmd.add_argument("snapshot")

    args = parser.parse_args()
    if args.command == "create":
        plan = load_plan(args.plan)
        observed_at = args.observed_at or plan.get("as_of")
        if not observed_at:
            raise SystemExit("create requires --observed-at or plan.as_of")
        snapshot = create_snapshot(plan, str(observed_at), args.parent_snapshot_id)
        _write(args.output, snapshot)
        print(json.dumps({"snapshot_id": snapshot["snapshot_id"], "output": args.output}, indent=2))
        return 0
    if args.command == "validate":
        result = validate_snapshot(load_snapshot(args.snapshot))
        print(json.dumps(result, indent=2))
        return 0 if result["valid"] else 1

    result = validate_transition(
        load_snapshot(args.previous),
        load_snapshot(args.current),
        load_policy(args.policy) if args.policy else None,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
