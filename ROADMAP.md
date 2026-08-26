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
- snapshot diff for status, blockers, progress, and critical path
- unit tests and GitHub Actions workflow

## Now — move from state to time-aware execution

1. Add planned/start/end timestamps and actual duration.
2. Calculate delay propagation and forecasted completion.
3. Model rollback/contingency tasks and activation conditions.
4. Add checkpoints with explicit approval/evidence requirements.
5. Persist execution snapshots so a cutover can resume safely.

## Next — control room

- generate a concise go/no-go report
- show blocker concentration by owner/workstream
- show critical-path movement visually
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

> What can run now, what is blocking go-live, what changed since the last snapshot, and what evidence is still missing for a defensible go/no-go decision?
