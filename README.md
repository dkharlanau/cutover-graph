# Cutover Graph

Model and execute cutover dependencies, live readiness, blockers, critical paths, controls, evidence, and go/no-go policies as a versionable graph.

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
- compare two cutover snapshots: status movement, blocker movement, progress, and critical-path change
- emit JSON suitable for CI, dashboards, and agents

This repository now covers the useful core of the earlier `cutover-orchestrator` idea; a second thin repository is not needed.

## Quick start

```bash
python cutover_graph.py examples/customer-cutover.json validate
python cutover_graph.py examples/customer-cutover.json plan
python cutover_gate.py examples/customer-cutover.json examples/readiness-policy.json
python cutover_diff.py examples/customer-cutover.json examples/customer-cutover-after.json
python -m unittest discover -s tests -v
```

The planner reports `executable_now`, live blockers, progress, theoretical waves, and critical path. The readiness gate evaluates explicit go/no-go criteria. The diff explains what changed between two control-room snapshots.

## Plan model

```json
{
  "tasks": [
    {
      "id": "load-customers",
      "owner": "mdg",
      "duration_minutes": 90,
      "status": "running",
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

1. Planned/start/end timestamps and actual duration.
2. Delay propagation and forecasted completion.
3. Rollback/contingency tasks and activation conditions.
4. Checkpoints with multi-stage approval/evidence requirements.
5. Resumable execution snapshots.
6. Browser control-room view using the shared graph explorer.
7. Reconciliation-as-Code checks as cutover gates.
8. Project Evidence Graph output for auditable go-live evidence.
9. Controlled command hooks behind explicit approval envelopes.

## Design principles

- deterministic planning before automation
- explicit policy rather than hidden go/no-go logic
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

**MVP / active development.** Planning, live execution readiness, policy gates, evidence checks, snapshot comparison, examples, tests, and CI workflow are implemented.
