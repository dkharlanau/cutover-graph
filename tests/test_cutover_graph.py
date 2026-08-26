import unittest

from cutover_graph import blockers, build_report, critical_path, execution_waves, validate


class CutoverGraphTests(unittest.TestCase):
    def setUp(self):
        self.plan = {
            "tasks": [
                {"id": "a", "duration_minutes": 10, "status": "done", "depends_on": []},
                {"id": "b", "duration_minutes": 20, "status": "pending", "depends_on": ["a"]},
                {"id": "c", "duration_minutes": 5, "status": "pending", "depends_on": ["a"]},
                {"id": "d", "duration_minutes": 30, "status": "pending", "depends_on": ["b", "c"]},
            ]
        }

    def test_execution_waves(self):
        self.assertEqual(execution_waves(self.plan), [["a"], ["b", "c"], ["d"]])

    def test_critical_path(self):
        result = critical_path(self.plan)
        self.assertEqual(result["tasks"], ["a", "b", "d"])
        self.assertEqual(result["duration_minutes"], 60)

    def test_blockers(self):
        self.assertEqual(blockers(self.plan), [{"task": "d", "blocked_by": ["b", "c"]}])

    def test_missing_dependency_invalidates_plan(self):
        plan = {"tasks": [{"id": "x", "depends_on": ["missing"]}]}
        result = validate(plan)
        self.assertFalse(result["valid"])
        self.assertEqual(result["missing_dependencies"], [{"task": "x", "missing": "missing"}])

    def test_cycle_detection(self):
        plan = {"tasks": [
            {"id": "x", "depends_on": ["y"]},
            {"id": "y", "depends_on": ["x"]},
        ]}
        self.assertFalse(validate(plan)["valid"])
        self.assertEqual(execution_waves(plan), [])

    def test_report(self):
        report = build_report(self.plan)
        self.assertTrue(report["validation"]["valid"])
        self.assertEqual(report["critical_path"]["duration_minutes"], 60)


if __name__ == "__main__":
    unittest.main()
