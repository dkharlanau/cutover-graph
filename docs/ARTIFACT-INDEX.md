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

## Verified Project Evidence Graph handoff

The repository includes a synthetic Reconciliation-as-Code result whose logical reference matches `examples/checkpoint-cutover.json`. This makes the positive handoff reproducible without inventing evidence:

```bash
cutover-graph evidence build build/evidence-registry.json \
  examples/external-evidence/passed-reconciliation.json
cutover-graph artifacts examples/checkpoint-cutover.json \
  --registry build/evidence-registry.json \
  --output build/cutover-artifacts.json
project-evidence-graph import-cutover build/cutover-artifacts.json \
  --output build/project-cutover-fragment.json
project-evidence-graph analyze build/project-cutover-fragment.json
```

The resulting Cutover index has `assurance.passed: true`; the imported project fragment records `assurance_complete: true`. These fields mean the synthetic external checkpoint was verified against the supplied registry. They do not certify a production cutover.

Omitting `--registry` is also a supported, deliberately negative handoff. The external reference remains present for traceability, but the checkpoint is not exported as verified evidence and the Project Evidence import reports an unverified external checkpoint.
