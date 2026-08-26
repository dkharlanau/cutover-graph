# Roadmap

## Done — executable MVP

- canonical cutover task/dependency model
- duplicate and missing-dependency validation
- cycle detection
- deterministic execution waves
- duration-based critical path
- live blockers from task state
- tasks executable now from completed dependencies
- live completion/running summary
- machine-readable readiness/go-no-go policy
- owner and completed-task evidence gates
- timezone-aware baseline and live forecast
- delay propagation with originating vs inherited delay
- forecasted cutover completion and schedule variance
- snapshot diff for status, blockers, progress, critical path, and timing
- unit tests and GitHub Actions workflow

## Now — make execution recoverable and controllable

1. Model rollback/contingency tasks and activation conditions.
2. Add checkpoints with explicit approval/evidence requirements.
3. Persist execution snapshots so a cutover can resume safely.
4. Add workstream/owner risk concentration metrics.

## Next — control room

- generate a concise go/no-go report
- show blocker and delay concentration by owner/workstream
- show critical-path and forecast movement visually
- produce next-action recommendations from deterministic state
- feed the shared enterprise graph explorer
- create post-cutover evidence output for Project Evidence Graph

## Later — automation boundary

- controlled command hooks for executable tasks
- approval envelope before state-changing actions
- external status adapters for ticketing/monitoring systems
- Reconciliation as Code checks as cutover gates
- evidence-pack generation for audit and handover

## Product test

During a real cutover the model should answer, from the current state alone:

> What can run now, what is blocking go-live, which task caused the delay, what completion is now forecast, and what evidence is still missing for a defensible go/no-go decision?
