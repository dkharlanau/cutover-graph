# Roadmap

## Done — executable MVP

- canonical cutover task/dependency model
- duplicate and missing-dependency validation
- cycle detection
- deterministic execution waves
- duration-based critical path
- live blockers from task state
- machine-readable readiness/go-no-go policy
- owner and completed-task evidence gates
- unit tests and GitHub Actions workflow

## Now — move from plan to execution

1. Add planned/start/end timestamps and actual duration.
2. Calculate delay propagation and forecasted completion.
3. Identify tasks executable **now**, not only theoretical waves.
4. Model rollback/contingency tasks and activation conditions.
5. Add checkpoints with explicit approval/evidence requirements.
6. Persist execution snapshots so a cutover can resume safely.

## Next — control room

- generate a machine-readable go/no-go report
- show blocker concentration by owner/workstream
- show critical-path movement between snapshots
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

> What can run now, what is blocking go-live, what moved the critical path, and what evidence is still missing for a defensible go/no-go decision?
