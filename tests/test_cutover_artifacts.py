import unittest

from cutover_artifacts import artifact_ref, build_index


class CutoverArtifactTests(unittest.TestCase):
    def setUp(self):
        self.reconciliation_ref = "eac://dkharlanau/reconciliation-as-code/reconciliation/customer-country/run/run-1"
        self.plan = {
            "tasks": [
                {"id": "load-customers", "status": "done", "owner": "data", "depends_on": []},
                {
                    "id": "reconcile-customers",
                    "status": "done",
                    "owner": "data",
                    "workstream": "customer",
                    "risk": "high",
                    "depends_on": ["load-customers"],
                    "checkpoint": {
                        "required_approvals": ["business"],
                        "approvals": [{"role": "business", "by": "owner"}],
                        "required_evidence": ["reconciliation"],
                        "evidence": [{"type": "reconciliation", "ref": self.reconciliation_ref}]
                    }
                },
                {"id": "open-interfaces", "status": "pending", "depends_on": ["reconcile-customers"]}
            ],
            "signals": {"abort": False},
            "contingencies": [
                {
                    "id": "rollback-customer",
                    "mode": "any",
                    "activate_when": [{"signal": "abort", "equals": True}],
                    "tasks": [
                        {"id": "close-inbound", "status": "pending", "depends_on": []},
                        {"id": "restore", "status": "pending", "depends_on": ["close-inbound"]}
                    ]
                }
            ]
        }

    def _registry(self, status: str = "passed") -> dict:
        return {
            "schema_version": "0.1",
            "entries": [
                {
                    "ref": self.reconciliation_ref,
                    "kind": "reconciliation-as-code-run",
                    "status": status,
                    "observed_at": "2026-08-28T05:00:00Z",
                    "document_sha256": "d" * 64,
                    "configuration_sha256": "c" * 64,
                    "source_files": ["evidence.json"],
                    "summary": {},
                }
            ],
            "diagnostics": {"valid": True, "errors": [], "duplicate_refs": [], "conflicts": []},
        }

    def test_main_task_refs_and_dependencies_are_stable(self):
        index = build_index(self.plan)
        self.assertTrue(index["valid"])
        tasks = {item["id"]: item for item in index["tasks"]}
        self.assertEqual(tasks["load-customers"]["artifact_ref"], "eac://dkharlanau/cutover-graph/task/load-customers")
        self.assertEqual(tasks["reconcile-customers"]["depends_on_refs"], ["eac://dkharlanau/cutover-graph/task/load-customers"])
        self.assertEqual(tasks["open-interfaces"]["depends_on_refs"], ["eac://dkharlanau/cutover-graph/task/reconcile-customers"])

    def test_external_checkpoint_without_registry_fails_closed(self):
        index = build_index(self.plan)
        task = next(item for item in index["tasks"] if item["id"] == "reconcile-customers")
        checkpoint = task["checkpoint"]
        self.assertTrue(checkpoint["native_passed"])
        self.assertFalse(checkpoint["passed"])
        self.assertFalse(task["complete"])
        self.assertEqual(checkpoint["verification_mode"], "unverified_external")
        self.assertFalse(checkpoint["external_evidence_passed"])
        self.assertEqual(checkpoint["verifications"][0]["reason"], "verification_registry_not_supplied")
        self.assertEqual(checkpoint["artifact_ref"], "eac://dkharlanau/cutover-graph/checkpoint/reconcile-customers")
        self.assertEqual(checkpoint["evidence_refs"], [self.reconciliation_ref])
        self.assertFalse(index["assurance"]["passed"])

    def test_passed_registry_promotes_external_checkpoint_to_verified_assurance(self):
        index = build_index(self.plan, self._registry("passed"))
        task = next(item for item in index["tasks"] if item["id"] == "reconcile-customers")
        checkpoint = task["checkpoint"]
        self.assertTrue(checkpoint["native_passed"])
        self.assertTrue(checkpoint["passed"])
        self.assertTrue(task["complete"])
        self.assertEqual(checkpoint["verification_mode"], "external_registry")
        self.assertTrue(checkpoint["external_evidence_passed"])
        verification = checkpoint["verifications"][0]
        self.assertTrue(verification["verified"])
        self.assertEqual(verification["document_sha256"], "d" * 64)
        self.assertEqual(verification["configuration_sha256"], "c" * 64)
        self.assertTrue(index["assurance"]["passed"])
        self.assertEqual(index["assurance"]["external_checkpoints_verified"], 1)

    def test_failed_registry_keeps_native_state_but_blocks_assurance(self):
        index = build_index(self.plan, self._registry("failed"))
        task = next(item for item in index["tasks"] if item["id"] == "reconcile-customers")
        checkpoint = task["checkpoint"]
        self.assertTrue(checkpoint["native_passed"])
        self.assertFalse(checkpoint["passed"])
        self.assertFalse(task["complete"])
        self.assertEqual(checkpoint["verification_mode"], "external_registry")
        self.assertEqual(checkpoint["verifications"][0]["reason"], "external_evidence_failed")
        self.assertFalse(index["assurance"]["passed"])

    def test_local_only_checkpoint_keeps_native_semantics(self):
        checkpoint = self.plan["tasks"][1]["checkpoint"]
        checkpoint["evidence"] = [{"type": "reconciliation", "ref": "local/reconciliation.json"}]
        index = build_index(self.plan)
        task = next(item for item in index["tasks"] if item["id"] == "reconcile-customers")
        self.assertTrue(task["checkpoint"]["passed"])
        self.assertTrue(task["complete"])
        self.assertEqual(task["checkpoint"]["verification_mode"], "local_only")
        self.assertEqual(index["assurance"]["external_checkpoints"], 0)
        self.assertTrue(index["assurance"]["passed"])

    def test_incomplete_checkpoint_makes_task_incomplete(self):
        self.plan["tasks"][1]["checkpoint"]["approvals"] = []
        index = build_index(self.plan, self._registry())
        task = next(item for item in index["tasks"] if item["id"] == "reconcile-customers")
        self.assertFalse(task["complete"])
        self.assertFalse(task["checkpoint"]["passed"])
        self.assertEqual(task["checkpoint"]["missing_approvals"], ["business"])

    def test_contingency_refs_are_unique_and_stable(self):
        index = build_index(self.plan)
        branch = index["contingencies"][0]
        self.assertEqual(branch["artifact_ref"], "eac://dkharlanau/cutover-graph/contingency/rollback-customer")
        self.assertEqual(branch["tasks"][0]["artifact_ref"], "eac://dkharlanau/cutover-graph/contingency/rollback-customer/task/close-inbound")
        restore = next(item for item in branch["tasks"] if item["id"] == "restore")
        self.assertEqual(restore["depends_on_refs"], ["eac://dkharlanau/cutover-graph/contingency/rollback-customer/task/close-inbound"])

    def test_artifact_ref_percent_encodes_spaces(self):
        self.assertEqual(artifact_ref("task", "wave 1/customer"), "eac://dkharlanau/cutover-graph/task/wave%201%2Fcustomer")

    def test_invalid_plan_marks_index_invalid(self):
        self.plan["tasks"][2]["depends_on"] = ["missing"]
        index = build_index(self.plan)
        self.assertFalse(index["valid"])
        self.assertEqual(index["validation"]["plan"]["missing_dependencies"][0]["missing"], "missing")


if __name__ == "__main__":
    unittest.main()
