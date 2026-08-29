#!/usr/bin/env python3
"""Unified command dispatcher for the Cutover Graph toolset."""

from __future__ import annotations

import sys
from collections.abc import Callable

import control_room
import control_room_verified
import cutover_artifacts
import cutover_contingency
import cutover_diff
import cutover_gate
import cutover_graph
import cutover_risk
import cutover_snapshot
import cutover_timing
import external_evidence


Main = Callable[[], int]


COMMANDS: dict[str, tuple[Main, str]] = {
    "control-room": (control_room.main, "Render the consolidated read-only control room"),
    "control-room-verified": (
        control_room_verified.main,
        "Render the control room with verified external evidence",
    ),
    "gate": (cutover_gate.main, "Evaluate readiness/go-no-go policy"),
    "timing": (cutover_timing.main, "Calculate baseline, forecast and delay propagation"),
    "diff": (cutover_diff.main, "Compare two cutover states"),
    "contingency": (cutover_contingency.main, "Evaluate contingency/rollback branches"),
    "snapshot": (cutover_snapshot.main, "Create, validate or compare trusted snapshots"),
    "risk": (cutover_risk.main, "Analyze open operational risk concentration"),
    "artifacts": (cutover_artifacts.main, "Build the domain-owned cutover artifact index"),
    "evidence": (external_evidence.main, "Build/check verified external evidence registries"),
}


def _usage() -> str:
    rows = [
        "Cutover Graph — deterministic cutover control room",
        "",
        "Usage:",
        "  cutover-graph validate PLAN",
        "  cutover-graph plan PLAN",
        "  cutover-graph COMMAND [ARGS...]",
        "",
        "Commands:",
        "  validate               Validate a cutover plan",
        "  plan                   Build execution waves, blockers and critical path",
    ]
    width = max(len(name) for name in COMMANDS)
    for name, (_, description) in COMMANDS.items():
        rows.append(f"  {name.ljust(width)}  {description}")
    rows += [
        "",
        "Use `cutover-graph COMMAND --help` for command-specific arguments.",
    ]
    return "\n".join(rows)


def _invoke(main_fn: Main, program: str, args: list[str]) -> int:
    previous = sys.argv
    sys.argv = [program, *args]
    try:
        return int(main_fn())
    finally:
        sys.argv = previous


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print(_usage())
        return 0

    command, rest = args[0], args[1:]

    if command in {"validate", "plan"}:
        if not rest:
            print(f"cutover-graph {command}: PLAN is required", file=sys.stderr)
            return 2
        # The original module keeps backwards-compatible `PLAN COMMAND` ordering.
        return _invoke(
            cutover_graph.main,
            f"cutover-graph {command}",
            [rest[0], command, *rest[1:]],
        )

    target = COMMANDS.get(command)
    if target is None:
        print(f"Unknown command: {command}\n", file=sys.stderr)
        print(_usage(), file=sys.stderr)
        return 2

    main_fn, _ = target
    return _invoke(main_fn, f"cutover-graph {command}", rest)


if __name__ == "__main__":
    raise SystemExit(main())
