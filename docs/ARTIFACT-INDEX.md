# Cutover Artifact Index

`cutover_artifacts.py` publishes a stable machine-readable identity layer over a Cutover Graph plan.

The index is intended for consumers such as Project Evidence Graph, audit/export tooling, or agent context builders. Consumers do not need to parse the internal raw cutover plan format.

## Generate

```bash
python cutover_artifacts.py examples/checkpoint-cutover.json --output cutover-artifacts.json
```

The contract is described by [`../schema/artifact-index.schema.json`](../schema/artifact-index.schema.json).

## Stable logical refs

Main tasks:

```text
eac://dkharlanau/cutover-graph/task/<task-id>
```

Checkpoints:

```text
eac://dkharlanau/cutover-graph/checkpoint/<task-id>
```

Contingency branches and tasks:

```text
eac://dkharlanau/cutover-graph/contingency/<branch-id>
eac://dkharlanau/cutover-graph/contingency/<branch-id>/task/<task-id>
```

The refs are logical identities. They do not include Git commit SHA or file path.

## Task state

Each main task exports:

- raw status;
- checkpoint-aware `complete` state;
- dependency refs;
- optional owner/workstream/risk/duration/timing fields.

A task with raw `status: done` but an incomplete checkpoint exports `complete: false`.

## Checkpoint state

The checkpoint artifact includes:

- pass/fail state;
- missing required approvals/evidence;
- duplicate approval/evidence diagnostics;
- required approval/evidence types;
- exact evidence refs recorded in the cutover plan.

Evidence refs are not dereferenced. For example:

```text
eac://dkharlanau/reconciliation-as-code/reconciliation/customer-country-post-load/run/production-load-01
```

can point at a Reconciliation-as-Code run that a project-level consumer imports separately.

## Contingencies

Each contingency branch and branch task receives its own stable ref. Activation diagnostics remain part of the index, so a consumer can distinguish an inactive rollback definition from an active rollback branch.

## Validation

The artifact index carries both normal Cutover Graph validation and contingency validation. `valid` is true only if both are valid. Invalid plans do not produce a trustworthy integration index.
