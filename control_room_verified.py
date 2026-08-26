#!/usr/bin/env python3
"""Cutover control-room report with verified external evidence overlays."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from control_room import build_control_room, render_html as render_base_html, render_markdown as render_base_markdown
from cutover_gate import load_policy as load_readiness_policy
from cutover_graph import load_plan
from cutover_risk import load_policy as load_risk_policy
from cutover_snapshot import load_policy as load_transition_policy
from cutover_snapshot import load_snapshot
from external_evidence import load_registry, verified_execution


def build_verified_control_room(
    plan: dict[str, Any],
    observed_at: str,
    registry: dict[str, Any],
    previous_snapshot: dict[str, Any] | None = None,
    transition_policy: dict[str, Any] | None = None,
    readiness_policy: dict[str, Any] | None = None,
    risk_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = build_control_room(
        plan,
        observed_at,
        previous_snapshot,
        transition_policy,
        readiness_policy,
        risk_policy,
    )
    external = verified_execution(plan, registry)
    report["external_evidence"] = external
    report["execution"]["raw_executable_now"] = list(report["execution"].get("executable_now", []))
    report["execution"]["verified_executable_now"] = list(external["verified_executable_now"])

    if report["mode"] != "invalid_state" and not external["passed"]:
        report["mode"] = "readiness_hold"
        report.setdefault("hold_reasons", []).append("external_evidence_unverified")
    else:
        report.setdefault("hold_reasons", [])
    return report


def render_markdown(report: dict[str, Any], title: str = "Cutover Control Room") -> str:
    base = render_base_markdown(report, title)
    external = report["external_evidence"]
    failures = external.get("external_failures", [])
    failure_text = ", ".join(
        f"{item['task']}:{item['reason']}:{item['ref']}"
        for item in failures
    ) or "none"
    section = "\n".join([
        "## External evidence verification",
        "",
        f"- Result: **{'PASS' if external['passed'] else 'FAIL'}**",
        f"- Registry entries: {external['registry_entry_count']}",
        f"- Verified completed tasks: {', '.join(external['verified_completed_tasks']) or 'none'}",
        f"- Verified executable now: {', '.join(external['verified_executable_now']) or 'none'}",
        f"- External failures: {failure_text}",
        "",
    ])
    marker = "## Machine report"
    if marker in base:
        return base.replace(marker, section + marker, 1)
    return base + "\n" + section


def render_html(report: dict[str, Any], title: str = "Cutover Control Room") -> str:
    base = render_base_html(report, title)
    external = report["external_evidence"]
    failures = external.get("external_failures", [])
    failure_text = ", ".join(
        f"{item['task']}:{item['reason']}:{item['ref']}"
        for item in failures
    ) or "none"
    section = (
        "<section><h2>External evidence verification</h2><ul>"
        f"<li>Result: <strong>{'PASS' if external['passed'] else 'FAIL'}</strong></li>"
        f"<li>Registry entries: {external['registry_entry_count']}</li>"
        f"<li>Verified completed tasks: {html.escape(', '.join(external['verified_completed_tasks']) or 'none')}</li>"
        f"<li>Verified executable now: {html.escape(', '.join(external['verified_executable_now']) or 'none')}</li>"
        f"<li>External failures: {html.escape(failure_text)}</li>"
        "</ul></section>"
    )
    marker = "<section><h2>Machine report</h2>"
    if marker in base:
        return base.replace(marker, section + marker, 1)
    return base.replace("</body>", section + "</body>", 1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Cutover Graph control-room report with verified external evidence")
    parser.add_argument("plan")
    parser.add_argument("--evidence-registry", required=True)
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
        raise SystemExit("verified control-room report requires --observed-at or plan.as_of")
    report = build_verified_control_room(
        plan,
        str(observed_at),
        load_registry(args.evidence_registry),
        load_snapshot(args.previous_snapshot) if args.previous_snapshot else None,
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
