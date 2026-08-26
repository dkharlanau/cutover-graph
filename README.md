# Cutover Graph

Model and execute cutover dependencies, live readiness, blockers, timing, checkpoints, critical paths, controls, evidence, and go/no-go policies as a versionable graph.

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
- attach approval/evidence checkpoints to tasks
- treat a `done` task with an unsatisfied checkpoint as **not dependency-complete**
- report missing and duplicate checkpoint approvals/evidence
- summarize checkpoint-aware completion and running state
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
python cutover_graph.py examples/checkpoint-cutover.json plan
python cutover_gate.py examples/checkpoint-cutover.json examples/checkpoint-policy.json
python cutover_timing.py examples/timed-cutover-before.json
python cutover_diff.py examples/timed-cutover-before.json examples/timed-cutover-after.json
python -m unittest discover -s tests -v
```

The planner reports `executable_now`, live blockers, checkpoint status, progress, theoretical waves, and critical path. The readiness gate evaluates explicit go/no-go criteria. Time-aware planning separates an originating delay from delay inherited through dependencies.

## Checkpoint model

A checkpoint belongs to a task and can require approvals and evidence before the task is considered complete for dependency purposes.

```json
{
  "id": "reconcile-customers",
  "status": "done",
  "depends_on": ["load-customers"],
  "checkpoint": {
    "required_approvals": ["business", "data"],
    "approvals": [
      {"role": "business", "by": "business-owner"},
      {"role": "data", "by": "data-lead"}
    ],
    "required_evidence": ["reconciliation"],
    "evidence": [
      {"type": "reconciliation", "ref": "recon/customer-final.json"}
    ]
  }
}
```

If one required approval or evidence type is missing, downstream tasks remain blocked even when `reconcile-customers.status` is `done`. Duplicate records are reported and do not satisfy distinct requirements.

## Time-aware plan model

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
  "required_complete": ["reconcile-customers"],
  "require_checkpoints_satisfied": true,
  "max_blocked_tasks": 0
}
```

`required_complete` is checkpoint-aware. A raw `done` status does not satisfy the rule when its checkpoint is incomplete.

## Product direction

1. Rollback/contingency tasks and activation conditions.
2. Persisted/resumable execution snapshots.
3. Workstream/owner risk concentration metrics.
4. Browser control-room view using the shared graph explorer.
5. Reconciliation-as-Code checks as cutover gates.
6. Project Evidence Graph output for auditable go-live evidence.
7. Controlled command hooks behind explicit approval envelopes.

## Design principles

- deterministic planning before automation
- explicit policy rather than hidden go/no-go logic
- checkpoint-aware completion
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

**MVP / active development.** Planning, checkpoint-aware execution, live readiness, time-aware forecasting, delay propagation, policy gates, evidence checks, snapshot comparison, examples, tests, and CI workflow are implemented.
