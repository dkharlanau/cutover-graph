import unittest

from cutover_gate import evaluate as evaluate_gate
from cutover_graph import blockers, checkpoint_status, executable_now, progress, task_complete


class CutoverCheckpointTests(unittest.TestCase):
    def checkpoint_task(self, approvals=None, evidence=None):
        return {
            "id": "reconcile",
            "status": "done",
            "duration_minutes": 10,
            "depends_on": [],
            "checkpoint": {
                "required_approvals": ["business", "data"],
                "approvals": approvals or [],
                "required_evidence": ["reconciliation"],
                "evidence": evidence or [],
            },
        }

    def test_done_status_does_not_complete_unsatisfied_checkpoint(self):
        task = self.checkpoint_task(
            approvals=[{"role": "business", "by": "alice"}],
            evidence=[{"type": "reconciliation", "ref": "run-1"}],
        )
        self.assertFalse(task_complete(task))
        result = checkpoint_status(task)
        self.assertEqual(result["missing_approvals"], ["data"])

    def test_unsatisfied_checkpoint_blocks_successor(self):
        plan = {
            "tasks": [
                self.checkpoint_task(
                    approvals=[{"role": "business"}],
                    evidence=[{"type": "reconciliation", "ref": "run-1"}],
                ),
                {"id": "open-interfaces", "status": "pending", "depends_on": ["reconcile"]},
            ]
        }
        self.assertEqual(executable_now(plan), [])
        self.assertEqual(blockers(plan), [{"task": "open-interfaces", "blocked_by": ["reconcile"]}])
        self.assertEqual(progress(plan)["status_done_but_checkpoint_blocked"], ["reconcile"])

    def test_satisfied_checkpoint_releases_successor(self):
        plan = {
            "tasks": [
                self.checkpoint_task(
                    approvals=[{"role": "business"}, {"role": "data"}],
                    evidence=[{"type": "reconciliation", "ref": "run-1"}],
                ),
                {"id": "open-interfaces", "status": "pending", "depends_on": ["reconcile"]},
            ]
        }
        self.assertEqual(executable_now(plan), ["open-interfaces"])
        self.assertEqual(blockers(plan), [])
        self.assertEqual(progress(plan)["completed"], ["reconcile"])

    def test_duplicate_records_do_not_fake_distinct_requirements(self):
        task = self.checkpoint_task(
            approvals=[{"role": "business"}, {"role": "business"}],
            evidence=[{"type": "reconciliation"}, {"type": "reconciliation"}],
        )
        result = checkpoint_status(task)
        self.assertFalse(result["passed"])
        self.assertEqual(result["missing_approvals"], ["data"])
        self.assertEqual(result["duplicate_approvals"], ["business"])
        self.assertEqual(result["duplicate_evidence"], ["reconciliation"])

    def test_readiness_required_complete_is_checkpoint_aware(self):
        plan = {"tasks": [self.checkpoint_task(
            approvals=[{"role": "business"}],
            evidence=[{"type": "reconciliation"}],
        )]}
        result = evaluate_gate(plan, {"required_complete": ["reconcile"], "require_checkpoints_satisfied": True})
        self.assertFalse(result["passed"])
        self.assertIn("required_complete", result["failed_checks"])
        self.assertIn("checkpoints_satisfied", result["failed_checks"])

    def test_non_checkpoint_done_task_remains_complete(self):
        self.assertTrue(task_complete({"id": "a", "status": "done", "depends_on": []}))


if __name__ == "__main__":
    unittest.main()
