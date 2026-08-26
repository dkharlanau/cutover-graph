import unittest

from cutover_snapshot import create_snapshot, validate_snapshot, validate_transition


class CutoverSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.base_plan = {
            "tasks": [
                {"id": "load", "status": "done", "depends_on": []},
                {"id": "reconcile", "status": "running", "depends_on": ["load"]},
            ],
            "signals": {"abort": False},
        }

    def test_same_state_time_parent_has_same_snapshot_id(self):
        first = create_snapshot(self.base_plan, "2026-08-30T20:00:00Z", "snap-parent")
        second = create_snapshot(self.base_plan, "2026-08-30T20:00:00+00:00", "snap-parent")
        self.assertEqual(first["snapshot_id"], second["snapshot_id"])
        self.assertTrue(validate_snapshot(first)["valid"])

    def test_state_change_changes_snapshot_id(self):
        first = create_snapshot(self.base_plan, "2026-08-30T20:00:00Z")
        changed = {"tasks": [dict(task) for task in self.base_plan["tasks"]], "signals": {"abort": False}}
        changed["tasks"][1]["status"] = "done"
        second = create_snapshot(changed, "2026-08-30T20:00:00Z")
        self.assertNotEqual(first["snapshot_id"], second["snapshot_id"])

    def test_done_to_running_is_illegal(self):
        before_plan = {"tasks": [{"id": "x", "status": "done", "depends_on": []}]}
        after_plan = {"tasks": [{"id": "x", "status": "running", "depends_on": []}]}
        before = create_snapshot(before_plan, "2026-08-30T20:00:00Z")
        after = create_snapshot(after_plan, "2026-08-30T20:05:00Z", before["snapshot_id"])
        result = validate_transition(before, after)
        self.assertFalse(result["valid"])
        finding = next(item for item in result["findings"] if item["type"] == "illegal_task_transition")
        self.assertEqual((finding["from"], finding["to"]), ("done", "running"))

    def test_failed_to_running_retry_is_legal(self):
        before_plan = {"tasks": [{"id": "x", "status": "failed", "depends_on": []}]}
        after_plan = {"tasks": [{"id": "x", "status": "running", "depends_on": []}]}
        before = create_snapshot(before_plan, "2026-08-30T20:00:00Z")
        after = create_snapshot(after_plan, "2026-08-30T20:05:00Z", before["snapshot_id"])
        result = validate_transition(before, after)
        self.assertTrue(result["valid"])
        self.assertEqual(result["state_changes"], [{"task": "x", "from": "failed", "to": "running"}])

    def test_checkpoint_regression_fails(self):
        before_plan = {"tasks": [{
            "id": "x", "status": "done", "depends_on": [],
            "checkpoint": {
                "required_approvals": ["business"],
                "approvals": [{"role": "business"}],
                "required_evidence": ["reconciliation"],
                "evidence": [{"type": "reconciliation", "ref": "eac://example/evidence"}]
            }
        }]}
        after_plan = {"tasks": [{
            "id": "x", "status": "done", "depends_on": [],
            "checkpoint": {
                "required_approvals": ["business"],
                "approvals": [],
                "required_evidence": ["reconciliation"],
                "evidence": [{"type": "reconciliation", "ref": "eac://example/evidence"}]
            }
        }]}
        before = create_snapshot(before_plan, "2026-08-30T20:00:00Z")
        after = create_snapshot(after_plan, "2026-08-30T20:05:00Z", before["snapshot_id"])
        result = validate_transition(before, after)
        self.assertFalse(result["valid"])
        self.assertIn("checkpoint_regression", [item["type"] for item in result["findings"]])

    def test_parent_mismatch_fails(self):
        before = create_snapshot(self.base_plan, "2026-08-30T20:00:00Z")
        after = create_snapshot(self.base_plan, "2026-08-30T20:05:00Z", "snap-wrong")
        result = validate_transition(before, after)
        self.assertFalse(result["valid"])
        self.assertIn("parent_mismatch", [item["type"] for item in result["findings"]])

    def test_non_forward_timestamp_fails(self):
        before = create_snapshot(self.base_plan, "2026-08-30T20:00:00Z")
        after = create_snapshot(self.base_plan, "2026-08-30T19:59:00Z", before["snapshot_id"])
        result = validate_transition(before, after)
        self.assertFalse(result["valid"])
        self.assertIn("non_forward_timestamp", [item["type"] for item in result["findings"]])

    def test_added_task_requires_policy(self):
        before_plan = {"tasks": [{"id": "a", "status": "pending", "depends_on": []}]}
        after_plan = {"tasks": [
            {"id": "a", "status": "pending", "depends_on": []},
            {"id": "b", "status": "pending", "depends_on": []},
        ]}
        before = create_snapshot(before_plan, "2026-08-30T20:00:00Z")
        after = create_snapshot(after_plan, "2026-08-30T20:05:00Z", before["snapshot_id"])
        self.assertFalse(validate_transition(before, after)["valid"])
        self.assertTrue(validate_transition(before, after, {"allow_added_tasks": True})["valid"])

    def test_custom_transition_policy(self):
        before_plan = {"tasks": [{"id": "a", "status": "done", "depends_on": []}]}
        after_plan = {"tasks": [{"id": "a", "status": "running", "depends_on": []}]}
        before = create_snapshot(before_plan, "2026-08-30T20:00:00Z")
        after = create_snapshot(after_plan, "2026-08-30T20:05:00Z", before["snapshot_id"])
        policy = {"allowed_transitions": {"done": ["done", "running"]}}
        self.assertTrue(validate_transition(before, after, policy)["valid"])

    def test_naive_timestamp_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            create_snapshot(self.base_plan, "2026-08-30T20:00:00")


if __name__ == "__main__":
    unittest.main()
