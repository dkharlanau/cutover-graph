import unittest

from cutover_contingency import branch_active, branch_report, build_report, validate


class CutoverContingencyTests(unittest.TestCase):
    def setUp(self):
        self.plan = {
            "signals": {"abort_go_live": False},
            "tasks": [
                {"id": "load-customers", "status": "failed"},
                {"id": "open-interfaces", "status": "pending"},
            ],
            "contingencies": [
                {
                    "id": "rollback-customer-load",
                    "mode": "any",
                    "activate_when": [
                        {"task": "load-customers", "status_in": ["failed"]},
                        {"signal": "abort_go_live", "equals": True},
                    ],
                    "tasks": [
                        {"id": "close-inbound", "status": "done", "depends_on": []},
                        {"id": "restore-snapshot", "status": "pending", "depends_on": ["close-inbound"]},
                        {"id": "reconcile-restored-state", "status": "pending", "depends_on": ["restore-snapshot"]},
                    ],
                }
            ],
        }

    def test_failed_task_activates_rollback(self):
        report = build_report(self.plan)
        self.assertTrue(report["validation"]["valid"])
        self.assertEqual(report["active_contingencies"], ["rollback-customer-load"])
        execution = report["contingencies"][0]["execution"]
        self.assertEqual(execution["executable_now"], ["restore-snapshot"])
        self.assertEqual(execution["blockers"], [{"task": "reconcile-restored-state", "blocked_by": ["restore-snapshot"]}])

    def test_unrelated_state_does_not_activate_branch(self):
        self.plan["tasks"][0]["status"] = "done"
        result = branch_active(self.plan, self.plan["contingencies"][0])
        self.assertFalse(result["active"])

    def test_signal_can_activate_branch(self):
        self.plan["tasks"][0]["status"] = "done"
        self.plan["signals"]["abort_go_live"] = True
        result = branch_active(self.plan, self.plan["contingencies"][0])
        self.assertTrue(result["active"])

    def test_internal_dependency_gates_execution(self):
        branch = self.plan["contingencies"][0]
        branch["tasks"][0]["status"] = "pending"
        report = branch_report(branch)
        self.assertEqual(report["executable_now"], ["close-inbound"])
        self.assertIn({"task": "restore-snapshot", "blocked_by": ["close-inbound"]}, report["blockers"])

    def test_invalid_branch_dependency_fails_validation(self):
        self.plan["contingencies"][0]["tasks"][1]["depends_on"] = ["missing"]
        result = validate(self.plan)
        self.assertFalse(result["valid"])
        self.assertEqual(result["findings"][0]["error"], "missing branch dependencies")

    def test_branch_cycle_fails_validation(self):
        branch = self.plan["contingencies"][0]
        branch["tasks"][0]["depends_on"] = ["reconcile-restored-state"]
        result = validate(self.plan)
        self.assertFalse(result["valid"])
        self.assertEqual(result["findings"][0]["error"], "branch cycles")


if __name__ == "__main__":
    unittest.main()
