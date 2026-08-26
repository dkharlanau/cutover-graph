import json
import tempfile
import unittest
from pathlib import Path

from external_evidence import build_registry, reconciliation_entry, verified_execution, verify_checkpoint


BASE = {
    "schema_version": "1.0",
    "spec_version": 1,
    "engine_version": "0.3.0",
    "configuration_sha256": "a" * 64,
    "run": {
        "id": "production-load-01",
        "started_at": "2026-08-26T09:59:00Z",
        "finished_at": "2026-08-26T10:00:00Z",
        "duration_ms": 60000,
        "python_version": "3.12",
        "platform": "linux"
    },
    "reconciliation": "customer-country-post-load",
    "status": "passed",
    "generated_at": "2026-08-26T10:00:01Z",
    "inputs": {
        "source": {"path": "legacy.csv", "sha256": "b" * 64},
        "target": {"path": "s4.csv", "sha256": "c" * 64}
    },
    "summary": {
        "source_records": 100,
        "target_records": 100,
        "matched_records": 100,
        "missing_in_target": 0,
        "unexpected_in_target": 0,
        "checks_total": 1,
        "checks_failed": 0,
        "warnings_failed": 0
    },
    "checks": []
}


class ExternalEvidenceTests(unittest.TestCase):
    def _write(self, directory: Path, name: str, status: str = "passed") -> Path:
        value = json.loads(json.dumps(BASE))
        value["status"] = status
        path = directory / name
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        return path

    def _plan(self, ref: str) -> dict:
        return {
            "tasks": [
                {"id": "load", "status": "done", "depends_on": []},
                {
                    "id": "reconcile",
                    "status": "done",
                    "depends_on": ["load"],
                    "checkpoint": {
                        "required_approvals": ["business"],
                        "approvals": [{"role": "business", "by": "owner"}],
                        "required_evidence": ["reconciliation"],
                        "evidence": [{"type": "reconciliation", "ref": ref}]
                    }
                },
                {"id": "open", "status": "pending", "depends_on": ["reconcile"]}
            ]
        }

    def test_passed_reconciliation_verifies_checkpoint_and_releases_successor(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(Path(tmp), "passed.json")
            registry = build_registry([path])
            ref = registry["entries"][0]["ref"]
            result = verified_execution(self._plan(ref), registry)
            self.assertTrue(result["passed"])
            self.assertIn("reconcile", result["verified_completed_tasks"])
            self.assertEqual(result["verified_executable_now"], ["open"])
            verification = result["checkpoint_verifications"][0]["verifications"][0]
            self.assertEqual(verification["status"], "passed")
            self.assertEqual(len(verification["document_sha256"]), 64)
            self.assertEqual(verification["observed_at"], "2026-08-26T10:00:01Z")

    def test_failed_reconciliation_blocks_successor(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(Path(tmp), "failed.json", status="failed")
            registry = build_registry([path])
            ref = registry["entries"][0]["ref"]
            result = verified_execution(self._plan(ref), registry)
            self.assertFalse(result["passed"])
            self.assertNotIn("reconcile", result["verified_completed_tasks"])
            self.assertEqual(result["verified_executable_now"], [])
            self.assertEqual(result["verified_blockers"], [{"task": "open", "blocked_by": ["reconcile"]}])
            self.assertEqual(result["external_failures"][0]["reason"], "external_evidence_failed")

    def test_missing_registry_entry_blocks(self):
        registry = {"schema_version": "0.1", "entries": [], "diagnostics": {"valid": True, "errors": [], "duplicate_refs": [], "conflicts": []}}
        ref = "eac://dkharlanau/reconciliation-as-code/reconciliation/customer-country-post-load/run/production-load-01"
        result = verified_execution(self._plan(ref), registry)
        self.assertFalse(result["passed"])
        self.assertEqual(result["external_failures"][0]["reason"], "missing_registry_entry")

    def test_checkpoint_without_external_ref_keeps_existing_semantics(self):
        task = {
            "id": "local-check",
            "status": "done",
            "checkpoint": {
                "required_evidence": ["report"],
                "evidence": [{"type": "report", "ref": "local/report.json"}]
            }
        }
        registry = {"schema_version": "0.1", "entries": [], "diagnostics": {"valid": True}}
        result = verify_checkpoint(task, registry)
        self.assertTrue(result["native_checkpoint_passed"])
        self.assertTrue(result["external_evidence_passed"])
        self.assertTrue(result["passed"])
        self.assertFalse(result["external_refs_required"])

    def test_registry_preserves_exact_document_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(Path(tmp), "evidence.json")
            entry = reconciliation_entry(path)
            import hashlib
            self.assertEqual(entry["document_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(entry["source_files"], [str(path)])

    def test_conflicting_duplicate_logical_ref_fails_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            passed = self._write(base, "passed.json", status="passed")
            failed = self._write(base, "failed.json", status="failed")
            registry = build_registry([passed, failed])
            self.assertFalse(registry["diagnostics"]["valid"])
            self.assertEqual(len(registry["diagnostics"]["conflicts"]), 1)
            self.assertEqual(registry["diagnostics"]["conflicts"][0]["ref"], registry["entries"][0]["ref"])

    def test_invalid_schema_is_registry_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            value = json.loads(json.dumps(BASE))
            value["schema_version"] = "2.0"
            path.write_text(json.dumps(value), encoding="utf-8")
            registry = build_registry([path])
            self.assertFalse(registry["diagnostics"]["valid"])
            self.assertIn("unsupported Reconciliation-as-Code evidence schema", registry["diagnostics"]["errors"][0]["error"])


if __name__ == "__main__":
    unittest.main()
