import unittest

from cutover_gate import evaluate


class CutoverGateTests(unittest.TestCase):
    def setUp(self):
        self.plan = {
            "tasks": [
                {"id": "freeze", "owner": "basis", "status": "done", "evidence": ["approved"], "duration_minutes": 10, "depends_on": []},
                {"id": "load", "owner": "data", "status": "running", "duration_minutes": 20, "depends_on": ["freeze"]},
                {"id": "check", "owner": "business", "status": "pending", "duration_minutes": 10, "depends_on": ["load"]}
            ]
        }

    def test_gate_passes(self):
        result = evaluate(self.plan, {
            "require_valid_plan": True,
            "require_owners": True,
            "required_complete": ["freeze"],
            "require_evidence_for_completed": True,
            "max_blocked_tasks": 1,
            "max_critical_path_minutes": 60
        })
        self.assertTrue(result["passed"])

    def test_gate_fails_on_missing_evidence(self):
        plan = {"tasks": [dict(self.plan["tasks"][0], evidence=[])]}
        result = evaluate(plan, {"require_evidence_for_completed": True})
        self.assertFalse(result["passed"])
        self.assertIn("completed_task_evidence", result["failed_checks"])

    def test_gate_fails_on_required_task(self):
        result = evaluate(self.plan, {"required_complete": ["load"]})
        self.assertFalse(result["passed"])
        self.assertIn("required_complete", result["failed_checks"])


if __name__ == "__main__":
    unittest.main()
