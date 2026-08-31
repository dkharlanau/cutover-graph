# Roadmap

## Done — deterministic execution core

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
- deterministic task open-risk scoring
- owner/workstream risk concentration and critical-path exposure
- explicit missing/unknown risk and unassigned owner/workstream buckets
- unit tests and GitHub Actions workflow

## Done — control-room decision surface

- one consolidated read-only control-room report from current plan and optional previous trusted snapshot
- explicit operating modes: `planned_execution`, `readiness_hold`, `contingency_active`, `complete`, `invalid_state`
- legal transition findings, executable-now state, blockers/checkpoints, timing forecast, contingency state and risk concentration in one report
- deterministic JSON, Markdown and standalone HTML renderers
- verified control-room overlay that can hold execution when required external evidence is unresolved
- Reconciliation-as-Code evidence registry with stable `eac://` run references
- external evidence document SHA-256, status and observed timestamp retained in verification output
- tests for control-room modes, renderers and external-evidence verification

## Done — distribution and public reference

- one installable `cutover-graph` CLI with backwards-compatible module workflows
- package version and repository metadata for a known tool release
- generated public control-room HTML, JSON and Markdown built from synthetic trusted-state examples
- GitHub Pages workflow that regenerates the reference case instead of publishing a hand-maintained mock-up

## Now — complete rehearsal and consumer contract

1. Provide one complete synthetic rehearsal path: baseline plan → trusted snapshot → changed live state → verified reconciliation evidence → control-room decision.
2. Emit Project Evidence Graph assurance fragments from trusted cutover snapshots and decisions.
3. Add a stable machine-readable consumer contract for current control-room state.

## Next — ecosystem assurance

- emit Project Evidence Graph assurance fragments from trusted snapshots, checkpoint verification and go/no-go decisions
- expose a stable consumer contract for control-room/current-state output
- add deterministic next-action recommendations that show the rule/evidence behind every recommendation
- strengthen cross-repository contract tests around version compatibility rather than repository-local assumptions

## Later — controlled automation boundary

- controlled command hooks for executable tasks
- approval envelope before any state-changing action
- explicit adapters for ticketing/monitoring systems with authority and freshness metadata
- signed/attested snapshot and evidence-pack manifests

## Product test

During a real cutover the model should answer, from the current trusted state alone:

> What can run now, what gate is still blocking go-live, which task caused the delay, what completion is now forecast, what changed since the previous trusted snapshot, did the state transition remain legal, where is operational risk concentrated, is required external evidence actually verified, and—if forward execution must stop—which rollback branch is justified and what can execute in it now?
