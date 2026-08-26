import unittest

from cutover_diff import compare


class CutoverDiffTests(unittest.TestCase):
    def test_status_blocker_progress_and_critical_path_movement(self):
        before = {"tasks": [
            {"id": "a", "status": "done", "duration_minutes": 10, "depends_on": []},
            {"id": "b", "status": "running", "duration_minutes": 20, "depends_on": ["a"]},
            {"id": "c", "status": "pending", "duration_minutes": 30, "depends_on": ["b"]},
        ]}
        after = {"tasks": [
            {"id": "a", "status": "done", "duration_minutes": 10, "depends_on": []},
            {"id": "b", "status": "done", "duration_minutes": 20, "depends_on": ["a"]},
            {"id": "c", "status": "running", "duration_minutes": 40, "depends_on": ["b"]},
        ]}
        result = compare(before, after)
        self.assertEqual(result["status_changes"], [
            {"task": "b", "from": "running", "to": "done"},
            {"task": "c", "from": "pending", "to": "running"},
        ])
        self.assertEqual(result["resolved_blockers"], [{"task": "c", "was_blocked_by": ["b"]}])
        self.assertEqual(result["completion_ratio"]["delta"], 1 / 3)
        self.assertEqual(result["critical_path"]["duration_delta_minutes"], 10)
        self.assertFalse(result["critical_path"]["path_changed"])
        self.assertFalse(result["timing"]["before_valid"])

    def test_added_removed_and_new_blocker(self):
        before = {"tasks": [{"id": "a", "status": "done", "depends_on": []}]}
        after = {"tasks": [
            {"id": "b", "status": "pending", "depends_on": []},
            {"id": "c", "status": "pending", "depends_on": ["b"]},
        ]}
        result = compare(before, after)
        self.assertEqual(result["added_tasks"], ["b", "c"])
        self.assertEqual(result["removed_tasks"], ["a"])
        self.assertEqual(result["newly_blocked"], [{"task": "c", "blocked_by": ["b"]}])

    def test_timing_variance_movement(self):
        before = {
            "cutover_start": "2026-08-30T20:00:00Z",
            "as_of": "2026-08-30T20:15:00Z",
            "tasks": [{"id": "a", "status": "running", "duration_minutes": 10, "depends_on": []}],
        }
        after = {
            "cutover_start": "2026-08-30T20:00:00Z",
            "as_of": "2026-08-30T20:20:00Z",
            "tasks": [{"id": "a", "status": "running", "duration_minutes": 10, "depends_on": []}],
        }
        result = compare(before, after)
        self.assertTrue(result["timing"]["before_valid"])
        self.assertTrue(result["timing"]["after_valid"])
        self.assertEqual(result["timing"]["completion_variance_minutes"], {"before": 5, "after": 10, "delta": 5})
        self.assertEqual(result["timing"]["forecast_completion"], {
            "before": "2026-08-30T20:15:00Z",
            "after": "2026-08-30T20:20:00Z",
        })


if __name__ == "__main__":
    unittest.main()
