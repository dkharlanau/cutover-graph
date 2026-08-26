# Roadmap

## Done — executable MVP

- canonical cutover task/dependency model
- duplicate and missing-dependency validation
- cycle detection
- deterministic execution waves
- duration-based critical path
- live blockers from task state
- tasks executable now from checkpoint-complete dependencies
- checkpoint-aware completion/running summary
- approval/evidence checkpoint gates
- duplicate/missing checkpoint diagnostics
- machine-readable readiness/go-no-go policy
- owner and completed-task evidence gates
- timezone-aware baseline and live forecast
- delay propagation with originating vs inherited delay
- forecasted cutover completion and schedule variance
- snapshot diff for status, blockers, progress, critical path, and timing
- explicit rollback/contingency branches with task/signal activation rules
- validation and execution state for active rollback branches
- stable `eac://` refs for main tasks, checkpoints, contingencies, and contingency tasks
- checkpoint evidence refs preserved in a domain-owned artifact index
- artifact-index JSON Schema and consumer-facing contract
- immutable execution snapshots with deterministic `snapshot_id`
- plan fingerprint, signals, active contingencies, task/checkpoint state captured in snapshots
- legal state-transition validation with checkpoint regression protection
- parent/timestamp/add-remove transition controls and optional policy overrides
- unit tests and GitHub Actions workflow

## Now — make execution risk-aware and reviewable

1. Add workstream/owner risk concentration metrics.
2. Generate a concise control-room decision report from current plan + previous trusted snapshot.
3. Compare trusted snapshot state with timing/blocker movement in one operational readout.

## Next — ecosystem execution controls

- consume Reconciliation-as-Code result status directly as a checkpoint control without copying evidence content
- emit cutover evidence fragments for Project Evidence Graph through the artifact index boundary
- feed the shared enterprise graph explorer/control-room view
- add next-action recommendations from deterministic state

## Later — automation boundary

- controlled command hooks for executable tasks
- approval envelope before state-changing actions
- external status adapters for ticketing/monitoring systems
- signed/attested snapshot and evidence-pack manifests

## Product test

During a real cutover the model should answer, from the current state alone:

> What can run now, what gate is still blocking go-live, which task caused the delay, what completion is now forecast, what changed since the previous trusted snapshot, did the state transition remain legal, where is operational risk concentrated, and if forward execution must stop, which rollback branch is justified and what can execute in it now?
