# Cutover Graph

Model and execute cutover dependencies, waves, blockers, critical paths, controls, and evidence as a versionable graph.

## Why this exists

Cutovers are typically coordinated through large spreadsheets, calls, and manually maintained status columns. Dependencies are implicit, blockers become visible late, and the rationale for a go/no-go decision is difficult to reconstruct.

Cutover Graph turns the plan into a machine-readable dependency model that can be validated before execution and evaluated during the cutover window.

## Current MVP

The repository now contains a zero-dependency Python planning engine with:

- task and dependency validation
- missing-dependency detection
- cycle detection
- deterministic execution waves
- duration-based critical path calculation
- runtime blocker detection from task status
- JSON reporting suitable for CI, dashboards, and agents
- GitHub Actions validation

This repo is deliberately becoming the executable cutover core, so a separate `cutover-orchestrator` repository is not required at this stage.

## Quick start

```bash
python cutover_graph.py examples/customer-cutover.json validate
python cutover_graph.py examples/customer-cutover.json plan
python -m unittest discover -s tests -v
```

Example output includes the ordered execution waves, critical path duration, and tasks currently blocked by unfinished dependencies.

## Model

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

## Product direction

The next product layers are:

1. readiness gates and go/no-go policies
2. checkpoints, approvals, and evidence references
3. rollback tasks and contingency branches
4. planned vs actual timestamps and delay propagation
5. resumable execution state
6. command hooks/webhooks for automation
7. HTML/GitHub Pages live cutover view
8. integration with Reconciliation as Code for post-load controls
9. integration with Project Evidence Graph for auditable go-live evidence
10. agent-readable recommendations: next executable task, active blockers, and risk concentration

## Design principles

- versionable
- portable
- machine-readable
- deterministic-first
- visual where useful
- Git-friendly
- vendor-neutral where practical
- interoperable with enterprise tools

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

**MVP / active development.** Validation, dependency analysis, waves, blockers, critical path calculation, examples, tests, and CI are implemented.
