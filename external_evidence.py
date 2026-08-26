#!/usr/bin/env python3
"""Bind external eac:// evidence refs to verified local evidence documents."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

from cutover_graph import DONE_STATES, RUNNING_STATES, checkpoint_status, load_plan


REGISTRY_VERSION = "0.1"


def _rac_run_ref(name: str, run_id: str) -> str:
    encoded_name = quote(name, safe="._-:@")
    encoded_run = quote(run_id, safe="._-:@")
    return (
        "eac://dkharlanau/reconciliation-as-code/reconciliation/"
        f"{encoded_name}/run/{encoded_run}"
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return value


def reconciliation_entry(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    evidence = load_json(source)
    if evidence.get("schema_version") != "1.0":
        raise ValueError(f"unsupported Reconciliation-as-Code evidence schema in {source}: expected 1.0")
    if evidence.get("status") not in {"passed", "failed"}:
        raise ValueError(f"invalid reconciliation status in {source}: {evidence.get('status')!r}")
    name = str(evidence.get("reconciliation", "")).strip()
    run = evidence.get("run") if isinstance(evidence.get("run"), dict) else {}
    run_id = str(run.get("id", "")).strip()
    observed_at = str(evidence.get("generated_at", "")).strip()
    configuration_sha = str(evidence.get("configuration_sha256", "")).strip()
    if not name or not run_id or not observed_at:
        raise ValueError(f"reconciliation, run.id and generated_at are required in {source}")
    return {
        "ref": _rac_run_ref(name, run_id),
        "kind": "reconciliation-as-code-run",
        "status": evidence["status"],
        "observed_at": observed_at,
        "document_sha256": _sha256_file(source),
        "configuration_sha256": configuration_sha or None,
        "source_files": [str(source)],
        "summary": evidence.get("summary", {}),
    }


def build_registry(paths: list[str | Path]) -> dict[str, Any]:
    entries: dict[str, dict[str, Any]] = {}
    duplicate_refs: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for raw_path in sorted(str(Path(path)) for path in paths):
        try:
            entry = reconciliation_entry(raw_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append({"file": raw_path, "error": str(exc)})
            continue
        ref = entry["ref"]
        if ref not in entries:
            entries[ref] = entry
            continue
        existing = entries[ref]
        same_binding = all(
            existing.get(field) == entry.get(field)
            for field in ("kind", "status", "observed_at", "document_sha256", "configuration_sha256", "summary")
        )
        if same_binding:
            sources = sorted(set(existing.get("source_files", [])) | set(entry.get("source_files", [])))
            existing["source_files"] = sources
            duplicate_refs.append({"ref": ref, "files": sources})
        else:
            conflicts.append({
                "ref": ref,
                "first": existing,
                "second": entry,
            })

    diagnostics = {
        "errors": errors,
        "duplicate_refs": sorted(duplicate_refs, key=lambda item: item["ref"]),
        "conflicts": sorted(conflicts, key=lambda item: item["ref"]),
    }
    diagnostics["valid"] = not errors and not conflicts
    return {
        "schema_version": REGISTRY_VERSION,
        "entries": [entries[ref] for ref in sorted(entries)],
        "diagnostics": diagnostics,
    }


def load_registry(path: str | Path) -> dict[str, Any]:
    registry = load_json(path)
    if registry.get("schema_version") != REGISTRY_VERSION:
        raise ValueError(f"registry schema_version must be {REGISTRY_VERSION}")
    if not isinstance(registry.get("entries"), list):
        raise ValueError("registry.entries must be an array")
    diagnostics = registry.get("diagnostics") if isinstance(registry.get("diagnostics"), dict) else {}
    if diagnostics.get("valid") is False:
        raise ValueError("registry diagnostics mark the registry invalid")
    return registry


def _registry_index(registry: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    index: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for entry in registry.get("entries", []):
        if not isinstance(entry, dict):
            continue
        ref = str(entry.get("ref", "")).strip()
        if not ref:
            continue
        if ref in index:
            duplicates.append(ref)
        index[ref] = entry
    return index, sorted(set(duplicates))


def _checkpoint_external_refs(task: dict[str, Any]) -> list[dict[str, str]]:
    checkpoint = task.get("checkpoint")
    if not isinstance(checkpoint, dict):
        return []
    refs = []
    for record in checkpoint.get("evidence", []):
        if isinstance(record, str):
            ref = record.strip()
            evidence_type = "evidence"
        elif isinstance(record, dict):
            ref = str(record.get("ref", "")).strip()
            evidence_type = str(record.get("type", "evidence")).strip() or "evidence"
        else:
            continue
        if ref.startswith("eac://"):
            refs.append({"type": evidence_type, "ref": ref})
    refs.sort(key=lambda item: (item["type"], item["ref"]))
    return refs


def verify_checkpoint(task: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    native = checkpoint_status(task)
    registry_index, registry_duplicates = _registry_index(registry)
    external_refs = _checkpoint_external_refs(task)
    verifications = []
    for item in external_refs:
        entry = registry_index.get(item["ref"])
        if entry is None:
            verifications.append({
                **item,
                "verified": False,
                "reason": "missing_registry_entry",
                "status": None,
                "document_sha256": None,
                "observed_at": None,
            })
            continue
        accepted = str(entry.get("status", "")).lower() == "passed"
        verifications.append({
            **item,
            "verified": accepted,
            "reason": "passed" if accepted else "external_evidence_failed",
            "status": entry.get("status"),
            "document_sha256": entry.get("document_sha256"),
            "observed_at": entry.get("observed_at"),
            "kind": entry.get("kind"),
        })
    external_passed = not registry_duplicates and all(item["verified"] for item in verifications)
    return {
        "task": str(task.get("id", "")),
        "native_checkpoint_passed": native["passed"],
        "external_refs_required": bool(external_refs),
        "external_evidence_passed": external_passed,
        "passed": native["passed"] and external_passed,
        "registry_duplicate_refs": registry_duplicates,
        "verifications": verifications,
    }


def verified_task_complete(task: dict[str, Any], registry: dict[str, Any]) -> bool:
    status = str(task.get("status", "pending")).strip().lower()
    if status not in DONE_STATES:
        return False
    return verify_checkpoint(task, registry)["passed"]


def verified_execution(plan: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    tasks = {
        str(task.get("id")): task
        for task in plan.get("tasks", [])
        if str(task.get("id", "")).strip()
    }
    registry_index, registry_duplicates = _registry_index(registry)
    checkpoint_verifications = []
    for task_id in sorted(tasks):
        task = tasks[task_id]
        if isinstance(task.get("checkpoint"), dict):
            checkpoint_verifications.append(verify_checkpoint(task, registry))

    completed = sorted(task_id for task_id, task in tasks.items() if verified_task_complete(task, registry))
    executable = []
    blockers = []
    for task_id in sorted(tasks):
        task = tasks[task_id]
        status = str(task.get("status", "pending")).strip().lower()
        if status in DONE_STATES or status in RUNNING_STATES:
            continue
        dependencies = [str(dep) for dep in task.get("depends_on", [])]
        unresolved = [dep for dep in dependencies if dep not in tasks or not verified_task_complete(tasks[dep], registry)]
        if unresolved:
            blockers.append({"task": task_id, "blocked_by": unresolved})
        else:
            executable.append(task_id)

    external_failures = []
    for result in checkpoint_verifications:
        for verification in result["verifications"]:
            if not verification["verified"]:
                external_failures.append({"task": result["task"], **verification})

    return {
        "passed": not registry_duplicates and not external_failures,
        "registry_entry_count": len(registry_index),
        "registry_duplicate_refs": registry_duplicates,
        "verified_completed_tasks": completed,
        "verified_executable_now": executable,
        "verified_blockers": blockers,
        "checkpoint_verifications": checkpoint_verifications,
        "external_failures": external_failures,
    }


def _write(path: str | Path, value: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and use local external evidence verification registries")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build")
    build.add_argument("output")
    build.add_argument("evidence", nargs="+")

    check = sub.add_parser("check")
    check.add_argument("plan")
    check.add_argument("registry")

    args = parser.parse_args()
    if args.command == "build":
        registry = build_registry(args.evidence)
        _write(args.output, registry)
        print(json.dumps(registry, indent=2))
        return 0 if registry["diagnostics"]["valid"] else 1

    registry = load_registry(args.registry)
    result = verified_execution(load_plan(args.plan), registry)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
