# Immutable Cutover Snapshots

`cutover_snapshot.py` captures a trusted execution state and validates transitions between trusted states.

The snapshot is not a mutable status file. Its identity is derived from its content.

## Create

A snapshot requires an explicit timezone-aware observation timestamp. `plan.as_of` is used when available; otherwise pass `--observed-at`.

```bash
python cutover_snapshot.py create current-plan.json \
  --observed-at 2026-08-30T22:00:00Z \
  --output snapshot-01.json
```

For a chained snapshot:

```bash
python cutover_snapshot.py create next-plan.json \
  --observed-at 2026-08-30T22:20:00Z \
  --parent-snapshot-id snap-... \
  --output snapshot-02.json
```

## Snapshot contents

A v0.1 snapshot records:

- deterministic `snapshot_id`;
- `observed_at` normalized to UTC;
- optional `parent_snapshot_id`;
- SHA-256 of the complete input plan;
- normalized task execution state;
- checkpoint-required/pass/missing state;
- checkpoint-aware task completion;
- dependency IDs;
- owner/workstream/risk/timing fields when present;
- signals;
- active contingency IDs.

The same semantic state, timestamp, and parent generate the same snapshot ID. Any captured state change produces a different ID.

## Validate snapshot integrity

```bash
python cutover_snapshot.py validate snapshot-01.json
```

Validation recalculates the snapshot identity, validates timestamp/timezone, and checks required structural fields.

## Validate a transition

```bash
python cutover_snapshot.py transition snapshot-01.json snapshot-02.json
```

Default task-state rules are conservative:

| From | Allowed next state |
|---|---|
| pending | pending, running, done, failed, cancelled, skipped |
| running | running, done, failed, cancelled |
| failed | failed, running, cancelled |
| done | done |
| cancelled | cancelled |
| skipped | skipped |

`failed -> running` supports an explicit retry. `done -> running` is treated as an illegal regression.

Additional controls:

- current timestamp must be later than previous;
- if a parent ID is supplied, it must equal the previous snapshot ID;
- a previously passed required checkpoint cannot disappear or regress to failed;
- added/removed tasks fail by default;
- changes are reported explicitly.

## Policy overrides

A transition policy can explicitly change these defaults:

```json
{
  "require_parent": true,
  "allow_added_tasks": false,
  "allow_removed_tasks": false,
  "allowed_transitions": {
    "pending": ["pending", "running", "failed"],
    "running": ["running", "done", "failed"],
    "failed": ["failed", "running", "cancelled"],
    "done": ["done"],
    "cancelled": ["cancelled"],
    "skipped": ["skipped"]
  }
}
```

Overrides are explicit. The engine does not infer that a regression is justified because a comment, ticket, or status label changed.

## Resume boundary

A practical control-room loop can persist the latest trusted snapshot ID and compare the newly observed execution state against it before resuming work. This provides a deterministic guard before any future state-changing automation is added.
