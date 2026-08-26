#!/usr/bin/env python3
"""Read-only consolidated Cutover Graph control-room report."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from cutover_contingency import build_report as contingency_report
from cutover_gate import evaluate as evaluate_readiness
from cutover_gate import load_policy as load_readiness_policy
from cutover_graph import build_report as execution_report
from cutover_graph import load_plan
from cutover_risk import analyze as risk_report
from cutover_risk import load_policy as load_risk_policy
from cutover_snapshot import create_snapshot, load_policy as load_transition_policy
from cutover_snapshot import load_snapshot, validate_transition
from cutover_timing import timing_report


def build_control_room(
    plan: dict[str, Any],
    observed_at: str,
    previous_snapshot: dict[str, Any] | None = None,
    transition_policy: dict[str, Any] | None = None,
    readiness_policy: dict[str, Any] | None = None,
    risk_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    execution = execution_report(plan)
    parent_id = previous_snapshot.get("snapshot_id") if previous_snapshot else None
    current_snapshot = create_snapshot(plan, observed_at, parent_id)
    transition = (
        validate_transition(previous_snapshot, current_snapshot, transition_policy)
        if previous_snapshot is not None
        else None
    )
    readiness = evaluate_readiness(plan, readiness_policy) if readiness_policy is not None else None
    timing = timing_report(plan) if plan.get("cutover_start") else None
    contingencies = contingency_report(plan)
    risk = risk_report(plan, risk_policy)

    invalid_reasons = []
    if not execution["validation"]["valid"]:
        invalid_reasons.append("invalid_plan")
    if transition is not None and not transition["valid"]:
        invalid_reasons.append("illegal_snapshot_transition")
    if timing is not None and not timing["timing_valid"]:
        invalid_reasons.append("invalid_timing_state")
    if not contingencies["validation"]["valid"]:
        invalid_reasons.append("invalid_contingency_state")

    if invalid_reasons:
        mode = "invalid_state"
    elif readiness is not None and not readiness["passed"]:
        mode = "readiness_hold"
    elif contingencies["active_contingencies"]:
        mode = "contingency_active"
    elif execution["progress"]["completed_count"] == execution["progress"]["total"]:
        mode = "complete"
    else:
        mode = "planned_execution"

    return {
        "mode": mode,
        "invalid_reasons": invalid_reasons,
        "current_snapshot": {
            "snapshot_id": current_snapshot["snapshot_id"],
            "observed_at": current_snapshot["observed_at"],
            "parent_snapshot_id": current_snapshot.get("parent_snapshot_id"),
            "plan_sha256": current_snapshot["plan_sha256"],
        },
        "transition": transition,
        "execution": execution,
        "timing": timing,
        "readiness": readiness,
        "contingencies": contingencies,
        "risk": risk,
    }


def _list(values: list[Any]) -> str:
    return ", ".join(str(value) for value in values) if values else "none"


def render_markdown(report: dict[str, Any], title: str = "Cutover Control Room") -> str:
    execution = report["execution"]
    progress = execution["progress"]
    risk = report["risk"]
    timing = report.get("timing")
    readiness = report.get("readiness")
    transition = report.get("transition")
    contingencies = report["contingencies"]

    lines = [
        f"# {title}",
        "",
        f"**Operational mode: `{report['mode']}`**",
        "",
        "## Trusted state",
        "",
        f"- Snapshot: `{report['current_snapshot']['snapshot_id']}`",
        f"- Observed at: `{report['current_snapshot']['observed_at']}`",
        f"- Parent: `{report['current_snapshot'].get('parent_snapshot_id') or 'none'}`",
        f"- Plan fingerprint: `{report['current_snapshot']['plan_sha256']}`",
        "",
        "## Execution",
        "",
        f"- Completed: {progress['completed_count']} / {progress['total']}",
        f"- Running: {_list(progress['running'])}",
        f"- Executable now: {_list(execution['executable_now'])}",
        f"- Status-done but checkpoint blocked: {_list(progress.get('status_done_but_checkpoint_blocked', []))}",
        f"- Active blockers: {len(execution['blockers'])}",
        "",
    ]

    if transition is not None:
        state_changes = [
            str(item["task"]) + ":" + str(item["from"]) + "→" + str(item["to"])
            for item in transition["state_changes"]
        ]
        lines += [
            "## Snapshot transition",
            "",
            f"- Valid: {'yes' if transition['valid'] else 'no'}",
            f"- State changes: {_list(state_changes)}",
            f"- Findings: {_list([item['type'] for item in transition['findings']])}",
            "",
        ]

    if timing is not None:
        lines += [
            "## Timing",
            "",
            f"- Timing valid: {'yes' if timing['timing_valid'] else 'no'}",
            f"- Baseline completion: {timing.get('baseline_completion', 'n/a')}",
            f"- Forecast completion: {timing.get('forecast_completion', 'n/a')}",
            f"- Completion variance: {timing.get('completion_variance_minutes', 'n/a')} min",
            f"- Origin delays: {_list([item['task'] for item in timing.get('origin_delays', [])])}",
            "",
        ]

    lines += [
        "## Operational risk",
        "",
        f"- Total open-risk score: {risk['total_open_risk_score']:.2f}",
        f"- Open risk tasks: {risk['open_task_count']}",
        f"- Top owner: {risk['by_owner'][0]['owner'] if risk['by_owner'] else 'none'}",
        f"- Top workstream: {risk['by_workstream'][0]['workstream'] if risk['by_workstream'] else 'none'}",
        "",
        "## Contingencies",
        "",
        f"- Active branches: {_list(contingencies['active_contingencies'])}",
    ]
    for item in contingencies["contingencies"]:
        if item["activation"]["active"] and item["execution"] is not None:
            lines.append(f"- `{item['id']}` executable now: {_list(item['execution']['executable_now'])}")
    lines.append("")

    if readiness is not None:
        lines += [
            "## Readiness policy",
            "",
            f"- Result: **{'PASS' if readiness['passed'] else 'FAIL'}**",
            f"- Failed checks: {_list(readiness['failed_checks'])}",
            "",
        ]

    lines += [
        "## Machine report",
        "",
        "```json",
        json.dumps(report, indent=2, sort_keys=True),
        "```",
        "",
    ]
    return "\n".join(lines)


def render_html(report: dict[str, Any], title: str = "Cutover Control Room") -> str:
    execution = report["execution"]
    progress = execution["progress"]
    risk = report["risk"]
    timing = report.get("timing")
    rows = [
        ("Mode", report["mode"]),
        ("Snapshot", report["current_snapshot"]["snapshot_id"]),
        ("Completed", f"{progress['completed_count']} / {progress['total']}"),
        ("Executable now", _list(execution["executable_now"])),
        ("Blockers", len(execution["blockers"])),
        ("Open risk", f"{risk['total_open_risk_score']:.2f}"),
        ("Active contingencies", _list(report["contingencies"]["active_contingencies"])),
    ]
    if timing is not None:
        rows += [
            ("Forecast completion", timing.get("forecast_completion", "n/a")),
            ("Completion variance", f"{timing.get('completion_variance_minutes', 'n/a')} min"),
        ]
    if report.get("transition") is not None:
        rows.append(("Transition valid", "yes" if report["transition"]["valid"] else "no"))
    if report.get("readiness") is not None:
        rows.append(("Readiness", "PASS" if report["readiness"]["passed"] else "FAIL"))

    body_rows = "".join(
        f"<tr><td>{html.escape(str(label))}</td><td>{html.escape(str(value))}</td></tr>"
        for label, value in rows
    )
    machine = html.escape(json.dumps(report, indent=2, sort_keys=True))
    return f"""<!doctype html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>{html.escape(title)}</title>
<style>
body{{font-family:ui-sans-serif,system-ui,-apple-system,sans-serif;max-width:1000px;margin:40px auto;padding:0 24px;color:#171717;background:#fafafa}}
header{{display:flex;justify-content:space-between;align-items:end;border-bottom:1px solid #ddd;padding-bottom:16px}}h1{{margin:0;font-size:32px}}.mode{{font-weight:700;border:1px solid #aaa;border-radius:999px;padding:8px 14px}}
table{{width:100%;border-collapse:collapse;background:#fff;margin-top:28px}}td{{padding:12px;border-bottom:1px solid #eee}}td:last-child{{text-align:right}}pre{{background:#111;color:#eee;padding:18px;border-radius:8px;white-space:pre-wrap;word-break:break-word;font-size:12px}}section{{margin-top:30px}}
</style>
</head><body>
<header><h1>{html.escape(title)}</h1><div class=\"mode\">{html.escape(report['mode'])}</div></header>
<table>{body_rows}</table>
<section><h2>Machine report</h2><pre>{machine}</pre></section>
</body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate read-only Cutover Graph control-room report")
    parser.add_argument("plan")
    parser.add_argument("--observed-at")
    parser.add_argument("--previous-snapshot")
    parser.add_argument("--transition-policy")
    parser.add_argument("--readiness-policy")
    parser.add_argument("--risk-policy")
    parser.add_argument("--json-output")
    parser.add_argument("--markdown")
    parser.add_argument("--html")
    parser.add_argument("--title", default="Cutover Control Room")
    args = parser.parse_args()

    plan = load_plan(args.plan)
    observed_at = args.observed_at or plan.get("as_of")
    if not observed_at:
        raise SystemExit("control-room report requires --observed-at or plan.as_of")
    previous = load_snapshot(args.previous_snapshot) if args.previous_snapshot else None
    report = build_control_room(
        plan,
        str(observed_at),
        previous,
        load_transition_policy(args.transition_policy) if args.transition_policy else None,
        load_readiness_policy(args.readiness_policy) if args.readiness_policy else None,
        load_risk_policy(args.risk_policy) if args.risk_policy else None,
    )
    if args.json_output:
        Path(args.json_output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.markdown:
        Path(args.markdown).write_text(render_markdown(report, args.title), encoding="utf-8")
    if args.html:
        Path(args.html).write_text(render_html(report, args.title), encoding="utf-8")
    if not any((args.json_output, args.markdown, args.html)):
        print(json.dumps(report, indent=2))
    return 1 if report["mode"] == "invalid_state" else 0


if __name__ == "__main__":
    raise SystemExit(main())
