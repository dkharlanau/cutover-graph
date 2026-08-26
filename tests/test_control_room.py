import unittest

from control_room import build_control_room, render_html, render_markdown
from cutover_snapshot import create_snapshot


class ControlRoomTests(unittest.TestCase):
    def _plan(self):
        return {
            "cutover_start": "2026-08-30T20:00:00Z",
            "as_of": "2026-08-30T22:20:00Z",
            "signals": {"abort": False},
            "tasks": [
                {"id": "load", "status": "done", "risk": "medium", "owner": "data", "workstream": "customer", "duration_minutes": 60, "depends_on": []},
                {"id": "reconcile", "status": "done", "risk": "high", "owner": "data", "workstream": "customer", "duration_minutes": 30, "actual_end": "2026-08-30T21:35:00Z", "depends_on": ["load"]},
                {"id": "open", "status": "running", "risk": "medium", "owner": "integration", "workstream": "integration", "duration_minutes": 20, "actual_start": "2026-08-30T21:40:00Z", "depends_on": ["reconcile"]},
            ],
        }

    def test_normal_in_progress_mode_combines_execution_timing_and_risk(self):
        plan = self._plan()
        previous_plan = {"cutover_start": plan["cutover_start"], "tasks": [
            {"id": "load", "status": "done", "risk": "medium", "owner": "data", "workstream": "customer", "duration_minutes": 60, "depends_on": []},
            {"id": "reconcile", "status": "running", "risk": "high", "owner": "data", "workstream": "customer", "duration_minutes": 30, "depends_on": ["load"]},
            {"id": "open", "status": "pending", "risk": "medium", "owner": "integration", "workstream": "integration", "duration_minutes": 20, "depends_on": ["reconcile"]},
        ]}
        previous = create_snapshot(previous_plan, "2026-08-30T21:20:00Z")
        report = build_control_room(plan, plan["as_of"], previous_snapshot=previous)
        self.assertEqual(report["mode"], "planned_execution")
        self.assertTrue(report["transition"]["valid"])
        self.assertTrue(report["timing"]["timing_valid"])
        self.assertEqual(report["execution"]["progress"]["running"], ["open"])
        self.assertGreater(report["risk"]["total_open_risk_score"], 0)

    def test_illegal_transition_forces_invalid_state(self):
        previous_plan = {"tasks": [{"id": "x", "status": "done", "depends_on": []}]}
        current_plan = {"as_of": "2026-08-30T21:10:00Z", "tasks": [{"id": "x", "status": "running", "depends_on": []}]}
        previous = create_snapshot(previous_plan, "2026-08-30T21:00:00Z")
        report = build_control_room(current_plan, current_plan["as_of"], previous_snapshot=previous)
        self.assertEqual(report["mode"], "invalid_state")
        self.assertIn("illegal_snapshot_transition", report["invalid_reasons"])

    def test_failed_readiness_gate_forces_hold(self):
        plan = self._plan()
        report = build_control_room(
            plan,
            plan["as_of"],
            readiness_policy={"required_complete": ["open"]},
        )
        self.assertEqual(report["mode"], "readiness_hold")
        self.assertFalse(report["readiness"]["passed"])

    def test_active_contingency_changes_mode(self):
        plan = self._plan()
        plan["signals"]["abort"] = True
        plan["contingencies"] = [{
            "id": "rollback",
            "mode": "any",
            "activate_when": [{"signal": "abort", "equals": True}],
            "tasks": [{"id": "restore", "status": "pending", "depends_on": []}],
        }]
        report = build_control_room(plan, plan["as_of"])
        self.assertEqual(report["mode"], "contingency_active")
        self.assertEqual(report["contingencies"]["active_contingencies"], ["rollback"])
        self.assertEqual(report["contingencies"]["contingencies"][0]["execution"]["executable_now"], ["restore"])

    def test_complete_mode(self):
        plan = {"as_of": "2026-08-30T23:00:00Z", "tasks": [
            {"id": "a", "status": "done", "depends_on": []},
            {"id": "b", "status": "done", "depends_on": ["a"]},
        ]}
        report = build_control_room(plan, plan["as_of"])
        self.assertEqual(report["mode"], "complete")

    def test_renderers_include_machine_state(self):
        plan = self._plan()
        report = build_control_room(plan, plan["as_of"])
        markdown = render_markdown(report)
        html = render_html(report)
        self.assertIn("Operational mode", markdown)
        self.assertIn("Operational risk", markdown)
        self.assertIn("Machine report", markdown)
        self.assertIn("<!doctype html>", html)
        self.assertIn("planned_execution", html)


if __name__ == "__main__":
    unittest.main()
