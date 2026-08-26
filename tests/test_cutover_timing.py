import unittest

from cutover_timing import timing_report


class CutoverTimingTests(unittest.TestCase):
    def test_running_delay_propagates_downstream(self):
        plan = {
            "cutover_start": "2026-08-30T20:00:00Z",
            "as_of": "2026-08-30T20:25:00Z",
            "tasks": [
                {"id": "a", "duration_minutes": 10, "status": "done", "actual_start": "2026-08-30T20:00:00Z", "actual_end": "2026-08-30T20:10:00Z", "depends_on": []},
                {"id": "b", "duration_minutes": 10, "status": "running", "actual_start": "2026-08-30T20:10:00Z", "depends_on": ["a"]},
                {"id": "c", "duration_minutes": 10, "status": "pending", "depends_on": ["b"]},
            ],
        }
        result = timing_report(plan)
        self.assertTrue(result["timing_valid"])
        self.assertEqual(result["completion_variance_minutes"], 5)
        self.assertEqual(result["origin_delays"], [{"task": "b", "own_delay_minutes": 5}])
        self.assertEqual(result["affected_tasks"], [
            {"task": "b", "variance_minutes": 5},
            {"task": "c", "variance_minutes": 5},
        ])

    def test_actual_overrun_becomes_origin_delay(self):
        plan = {
            "cutover_start": "2026-08-30T20:00:00Z",
            "tasks": [
                {"id": "a", "duration_minutes": 10, "status": "done", "actual_start": "2026-08-30T20:00:00Z", "actual_end": "2026-08-30T20:15:00Z", "depends_on": []},
                {"id": "b", "duration_minutes": 10, "status": "pending", "depends_on": ["a"]},
            ],
        }
        result = timing_report(plan)
        self.assertEqual(result["completion_variance_minutes"], 5)
        self.assertEqual(result["origin_delays"], [{"task": "a", "own_delay_minutes": 5}])
        self.assertEqual(result["tasks"][1]["upstream_delay_minutes"], 5)

    def test_parallel_wave_only_delayed_branch_controls_completion(self):
        plan = {
            "cutover_start": "2026-08-30T20:00:00Z",
            "as_of": "2026-08-30T20:15:00Z",
            "tasks": [
                {"id": "a", "duration_minutes": 10, "status": "done", "actual_end": "2026-08-30T20:10:00Z", "depends_on": []},
                {"id": "b", "duration_minutes": 10, "status": "running", "depends_on": []},
            ],
        }
        result = timing_report(plan)
        self.assertEqual(result["baseline_completion"], "2026-08-30T20:10:00Z")
        self.assertEqual(result["forecast_completion"], "2026-08-30T20:15:00Z")
        self.assertEqual(result["completion_variance_minutes"], 5)

    def test_remaining_minutes_overrides_running_forecast(self):
        plan = {
            "cutover_start": "2026-08-30T20:00:00Z",
            "as_of": "2026-08-30T20:15:00Z",
            "tasks": [
                {"id": "a", "duration_minutes": 10, "status": "running", "remaining_minutes": 7, "depends_on": []}
            ],
        }
        result = timing_report(plan)
        self.assertEqual(result["forecast_completion"], "2026-08-30T20:22:00Z")
        self.assertEqual(result["completion_variance_minutes"], 12)

    def test_missing_anchor_is_invalid(self):
        result = timing_report({"tasks": [{"id": "a", "duration_minutes": 10, "depends_on": []}]})
        self.assertFalse(result["timing_valid"])
        self.assertIn("cutover_start", result["errors"][0])

    def test_timezone_is_required(self):
        result = timing_report({"cutover_start": "2026-08-30T20:00:00", "tasks": []})
        self.assertFalse(result["timing_valid"])
        self.assertIn("timezone", result["errors"][0])


if __name__ == "__main__":
    unittest.main()
