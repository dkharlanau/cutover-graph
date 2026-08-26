import unittest

from cutover_risk import analyze, execution_state


class CutoverRiskTests(unittest.TestCase):
    def test_failed_high_risk_dominates_pending_low_risk(self):
        plan = {"tasks": [
            {"id": "critical-failure", "status": "failed", "risk": "high", "owner": "data", "workstream": "customer", "depends_on": []},
            {"id": "minor-pending", "status": "pending", "risk": "low", "owner": "basis", "workstream": "technical", "depends_on": []},
        ]}
        result = analyze(plan, {"critical_path_multiplier": 1.0})
        tasks = {item["id"]: item for item in result["tasks"]}
        self.assertGreater(tasks["critical-failure"]["open_risk_score"], tasks["minor-pending"]["open_risk_score"])
        self.assertEqual(tasks["critical-failure"]["open_risk_score"], 10.0)
        self.assertEqual(tasks["minor-pending"]["open_risk_score"], 1.0)

    def test_completed_work_has_zero_open_risk(self):
        plan = {"tasks": [{"id": "done", "status": "done", "risk": "critical", "depends_on": []}]}
        result = analyze(plan)
        self.assertEqual(result["tasks"][0]["execution_state"], "done")
        self.assertEqual(result["tasks"][0]["open_risk_score"], 0.0)
        self.assertEqual(result["total_open_risk_score"], 0.0)

    def test_done_with_unsatisfied_checkpoint_remains_exposed(self):
        task = {
            "id": "gate", "status": "done", "risk": "high", "depends_on": [],
            "checkpoint": {
                "required_approvals": ["business"], "approvals": [],
                "required_evidence": [], "evidence": []
            }
        }
        self.assertEqual(execution_state(task), "checkpoint_blocked")
        result = analyze({"tasks": [task]}, {"critical_path_multiplier": 1.0})
        self.assertEqual(result["tasks"][0]["open_risk_score"], 7.5)

    def test_unresolved_critical_path_multiplier_applies(self):
        plan = {"tasks": [
            {"id": "a", "status": "pending", "risk": "medium", "duration_minutes": 20, "depends_on": []},
            {"id": "b", "status": "pending", "risk": "medium", "duration_minutes": 40, "depends_on": ["a"]},
            {"id": "c", "status": "pending", "risk": "medium", "duration_minutes": 5, "depends_on": []},
        ]}
        result = analyze(plan, {"critical_path_multiplier": 2.0})
        tasks = {item["id"]: item for item in result["tasks"]}
        self.assertTrue(tasks["a"]["on_unresolved_critical_path"])
        self.assertTrue(tasks["b"]["on_unresolved_critical_path"])
        self.assertFalse(tasks["c"]["on_unresolved_critical_path"])
        self.assertEqual(tasks["a"]["open_risk_score"], 4.0)
        self.assertEqual(tasks["c"]["open_risk_score"], 2.0)

    def test_owner_and_workstream_shares_sum_to_one(self):
        plan = {"tasks": [
            {"id": "a", "status": "pending", "risk": "high", "owner": "data", "workstream": "customer", "depends_on": []},
            {"id": "b", "status": "pending", "risk": "low", "owner": "basis", "workstream": "technical", "depends_on": []},
        ]}
        result = analyze(plan, {"critical_path_multiplier": 1.0})
        self.assertAlmostEqual(sum(item["share"] for item in result["by_owner"]), 1.0)
        self.assertAlmostEqual(sum(item["share"] for item in result["by_workstream"]), 1.0)
        self.assertEqual(result["by_owner"][0]["owner"], "data")
        self.assertEqual(result["by_workstream"][0]["workstream"], "customer")

    def test_missing_owner_workstream_and_risk_are_explicit(self):
        plan = {"tasks": [{"id": "x", "status": "pending", "depends_on": []}]}
        result = analyze(plan, {"critical_path_multiplier": 1.0, "default_risk_weight": 3})
        self.assertEqual(result["missing_risk_tasks"], ["x"])
        self.assertEqual(result["by_owner"][0]["owner"], "unassigned_owner")
        self.assertEqual(result["by_workstream"][0]["workstream"], "unassigned_workstream")
        self.assertEqual(result["tasks"][0]["risk_weight"], 3.0)

    def test_custom_risk_and_state_policy(self):
        plan = {"tasks": [{"id": "x", "status": "running", "risk": "tier-x", "depends_on": []}]}
        result = analyze(plan, {
            "risk_weights": {"tier-x": 7},
            "state_factors": {"running": 3},
            "critical_path_multiplier": 1.0,
        })
        self.assertEqual(result["tasks"][0]["open_risk_score"], 21.0)
        self.assertEqual(result["unknown_risks"], [])


if __name__ == "__main__":
    unittest.main()
