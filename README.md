# Cutover Graph

Model cutover dependencies, execution waves, blockers, critical paths, controls, and evidence as a versionable graph.

## Problem

Cutovers are typically tracked in large spreadsheets with hidden dependencies and difficult sequencing.

## Core idea

Model cutover tasks and their dependencies as a versionable graph with cycle detection, execution waves, and critical paths.

## Example

```yaml
tasks:
  - id: load-customers
    depends_on:
      - configure-number-ranges
      - load-reference-data

  - id: load-orders
    depends_on:
      - load-customers
      - load-materials
```

## Initial scope

- dependency graph
- cycle detection
- execution waves
- critical paths
- blockers
- owners
- checkpoints
- evidence references
- status overlay

## Long-term direction

A Git-native cutover model that can feed project plans, visual dashboards, evidence packs, and go/no-go reviews.

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

Planning.
