#!/usr/bin/env python3
"""Compare two cutover snapshots and explain operational movement."""

from __future__ import annotations

import argparse
import json
from typing import Any

from cutover_graph import _task_index, blockers, critical_path, executable_now, load_plan, progress


def _blocker_map(plan: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    return {item["task"]: tuple(sorted(item["blocked_by"])) for item in blockers(plan)}


def compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_tasks, _ = _task_index(before)
    after_tasks, _ = _task_index(after)
    before_ids = set(before_tasks)
    after_ids = set(after_tasks)

    status_changes = []
    for task_id in sorted(before_ids & after_ids):
        old = str(before_tasks[task_id].get("status", "pending")).lower()
        new = str(after_tasks[task_id].get("status", "pending")).lower()
        if old != new:
            status_changes.append({"task": task_id, "from": old, "to": new})

    old_blockers = _blocker_map(before)
    new_blockers = _blocker_map(after)
    newly_blocked = []
    resolved_blockers = []
    changed_blockers = []

    for task_id in sorted(set(old_blockers) | set(new_blockers)):
        old = old_blockers.get(task_id)
        new = new_blockers.get(task_id)
        if old is None and new is not None:
            newly_blocked.append({"task": task_id, "blocked_by": list(new)})
        elif old is not None and new is None:
            resolved_blockers.append({"task": task_id, "was_blocked_by": list(old)})
        elif old != new:
            changed_blockers.append({"task": task_id, "from": list(old or ()), "to": list(new or ())})

    before_cp = critical_path(before)
    after_cp = critical_path(after)
    before_progress = progress(before)
    after_progress = progress(after)

    return {
        "added_tasks": sorted(after_ids - before_ids),
        "removed_tasks": sorted(before_ids - after_ids),
        "status_changes": status_changes,
        "newly_blocked": newly_blocked,
        "resolved_blockers": resolved_blockers,
        "changed_blockers": changed_blockers,
        "executable_now": {
            "before": executable_now(before),
            "after": executable_now(after),
        },
        "completion_ratio": {
            "before": before_progress["completion_ratio"],
            "after": after_progress["completion_ratio"],
            "delta": after_progress["completion_ratio"] - before_progress["completion_ratio"],
        },
        "critical_path": {
            "before": before_cp,
            "after": after_cp,
            "duration_delta_minutes": None
            if before_cp["duration_minutes"] is None or after_cp["duration_minutes"] is None
            else after_cp["duration_minutes"] - before_cp["duration_minutes"],
            "path_changed": before_cp["tasks"] != after_cp["tasks"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two Cutover Graph snapshots")
    parser.add_argument("before")
    parser.add_argument("after")
    args = parser.parse_args()
    print(json.dumps(compare(load_plan(args.before), load_plan(args.after)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
