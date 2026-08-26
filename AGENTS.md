# Agent Development Contract

## Product objective

Make cutover execution deterministic, inspectable, and evidence-backed: dependencies, current executable work, blockers, critical path, readiness, rollback, and go/no-go reasoning should be computable from versioned state.

## Work loop

1. Pick the highest-value unfinished item in `ROADMAP.md`.
2. Implement a complete deterministic slice before adding UI.
3. Add a realistic synthetic cutover example or extend the existing one.
4. Add tests for happy path, blocked state, and invalid state.
5. Run tests, planner, and readiness gate.
6. Update documentation only for implemented behavior.

## Commands

```bash
python -m unittest discover -s tests -v
python cutover_graph.py examples/customer-cutover.json validate
python cutover_graph.py examples/customer-cutover.json plan
python cutover_gate.py examples/customer-cutover.json examples/readiness-policy.json
```

## Invariants

- cycles and missing dependencies are hard validation failures
- go/no-go logic is policy data, not hidden code
- state-changing automation must remain separate from deterministic planning
- completed work that is evidence-gated must reference evidence explicitly
- do not infer completion from dependency structure
- examples must remain synthetic and publishable
- identical plan + policy must produce identical decision output

## Definition of done

A feature is complete when model semantics, CLI behavior, tests, example state, and readiness output agree.
