# Cutover Graph

Model and execute cutover dependencies, live readiness, blockers, timing, critical paths, controls, evidence, and go/no-go policies as a versionable graph.

## Why this exists

Cutovers are typically coordinated through large spreadsheets, calls, and manually maintained status columns. Dependencies are implicit, blockers become visible late, and the rationale for a go/no-go decision is difficult to reconstruct.

Cutover Graph turns the plan into machine-readable state that can answer both planning and live-execution questions.

## Current capabilities

- validate tasks and dependencies
- detect missing dependencies and cycles
- calculate deterministic execution waves
- calculate duration-based critical path
- detect active blockers from current statuses
- identify tasks executable **now** because every dependency is complete
- summarize completion and running state
- enforce readiness/go-no-go policies
- require owners and evidence for completed steps
- calculate a timezone-aware baseline and live forecast from ISO-8601 timestamps
- propagate delays through dependencies and identify originating vs upstream delay
- forecast cutover completion and completion variance
- compare two snapshots: status movement, blocker movement, progress, critical path, and schedule variance
- emit JSON suitable for CI, dashboards, and agents

This repository covers the useful core of the earlier `cutover-orchestrator` idea; a second thin repository is not needed.

## Quick start

```bash
python cutover_graph.py examples/customer-cutover.json validate
python cutover_graph.py examples/customer-cutover.json plan
python cutover_gate.py examples/customer-cutover.json examples/readiness-policy.json
python cutover_diff.py examples/customer-cutover.json examples/customer-cutover-after.json
python cutover_timing.py examples/timed-cutover-before.json
python cutover_diff.py examples/timed-cutover-before.json examples/timed-cutover-after.json
python -m unittest discover -s tests -v
```

The planner reports `executable_now`, live blockers, progress, theoretical waves, and critical path. The readiness gate evaluates explicit go/no-go criteria. Time-aware planning separates an originating delay from delay inherited through dependencies. The diff explains how the control-room state moved between snapshots.

## Plan model

```json
{
  "cutover_start": "2026-08-30T20:00:00Z",
  "as_of": "2026-08-30T22:30:00Z",
  "tasks": [
    {
      "id": "load-customers",
      "owner": "mdg",
      "duration_minutes": 90,
      "status": "running",
      "actual_start": "2026-08-30T20:45:00Z",
      "depends_on": ["load-reference-data"]
    },
    {
      "id": "reconcile-customers",
      "owner": "data",
      "duration_minutes": 45,
      "status": "pending",
      "depends_on": ["load-customers"]
    }
  ]
}
```

For a running task, optional `remaining_minutes` can provide a more explicit forecast. Timestamps must include a timezone. Output is normalized to UTC.

## Readiness policy

```json
{
  "require_valid_plan": true,
  "require_owners": true,
  "required_complete": ["freeze-config", "load-reference-data"],
  "require_evidence_for_completed": true,
  "max_blocked_tasks": 3,
  "max_critical_path_minutes": 240
}
```

Go/no-go criteria become reviewable and versionable instead of existing only in meetings or status spreadsheets.

## Product direction

1. Rollback/contingency tasks and activation conditions.
2. Checkpoints with multi-stage approval/evidence requirements.
3. Persisted/resumable execution snapshots.
4. Browser control-room view using the shared graph explorer.
5. Reconciliation-as-Code checks as cutover gates.
6. Project Evidence Graph output for auditable go-live evidence.
7. Controlled command hooks behind explicit approval envelopes.

## Design principles

- deterministic planning before automation
- explicit policy rather than hidden go/no-go logic
- timezone-aware schedule math
- versionable state
- evidence-backed completion
- portable machine-readable output
- vendor-neutral core
- synthetic examples safe to publish

## Related projects

- [Mapping as Code](https://github.com/dkharlanau/mapping-as-code)
- [Transformation Graph](https://github.com/dkharlanau/transformation-graph)
- [Interface as Code](https://github.com/dkharlanau/interface-as-code)
- [Reconciliation as Code](https://github.com/dkharlanau/reconciliation-as-code)
- [Process as Code](https://github.com/dkharlanau/process-as-code)
- [Enterprise Change Graph](https://github.com/dkharlanau/enterprise-change-graph)
- [Decision Tables as Code](https://github.com/dkharlanau/decision-tables-as-code)
- [Data Relationship Map](https://github.com/dkharlanau/data-relationship-map)
- [Project Evidence Graph](https://github.com/dkharlanau/project-evidence-graph)

## Status

**MVP / active development.** Planning, live execution readiness, time-aware forecasting, delay propagation, policy gates, evidence checks, snapshot comparison, examples, tests, and CI workflow are implemented.
