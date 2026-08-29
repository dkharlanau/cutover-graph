# Cutover Graph

**A deterministic cutover control room for dependencies, live readiness, timing, checkpoints, contingency, risk and verified evidence.**

Cutover Graph models a cutover as versionable state rather than a status spreadsheet. It can answer both planning and live-execution questions, preserve trusted snapshots, reject illegal state transitions, and hold execution when required evidence cannot be verified.

## The operating question

During a cutover, the useful question is not just “what is green?” It is:

> **What can run now, what is blocking go-live, which task caused the delay, what changed since the last trusted state, where is operational risk concentrated, and—if forward execution must stop—which contingency is actually justified?**

The control-room layer consolidates those signals into JSON, Markdown or standalone HTML without hiding the deterministic evidence underneath.

## Try it

Requires Python 3.10+.

```bash
python -m pip install .

cutover-graph validate examples/customer-cutover.json
cutover-graph plan examples/customer-cutover.json
```

Render the control room:

```bash
cutover-graph control-room examples/timed-cutover-after.json \
  --observed-at 2026-08-30T22:30:00Z \
  --readiness-policy examples/readiness-policy.json \
  --json-output build/control-room.json \
  --markdown build/control-room.md \
  --html build/control-room.html
```

The installed command is a thin dispatcher over the same deterministic modules used by CI. Existing `python control_room.py ...` and other module-level workflows remain supported.

## Trusted state transition

With a previous trusted snapshot, the same control room validates whether the observed state transition is legal:

```bash
cutover-graph control-room examples/timed-cutover-after.json \
  --previous-snapshot build/previous-snapshot.json \
  --transition-policy examples/transition-policy.json \
  --observed-at 2026-08-30T22:30:00Z \
  --html build/control-room.html
```

The report derives one explicit operational mode:

```text
planned_execution
readiness_hold
contingency_active
complete
invalid_state
```

`invalid_state` is fail-loud: an invalid plan, illegal snapshot transition, invalid timing state, or invalid contingency state cannot be presented as a normal operating view.

## Verified external evidence

A checkpoint may point to evidence owned by another product instead of copying that evidence into the cutover plan. The first implemented binding is Reconciliation as Code.

Build a local verification registry from retained reconciliation evidence, then render a verified control room:

```bash
cutover-graph evidence build build/evidence-registry.json \
  path/to/reconciliation-evidence.json

cutover-graph control-room-verified examples/checkpoint-cutover.json \
  --evidence-registry build/evidence-registry.json \
  --observed-at 2026-08-30T22:30:00Z \
  --html build/verified-control-room.html
```

External evidence is addressed through stable `eac://` references. A task is not treated as verified-complete when its required external evidence is missing, conflicting, or has failed. The registry retains evidence-document SHA-256 fingerprints and does not silently copy another product's semantic ownership into Cutover Graph.

## Current capabilities

### Planning and execution

- validate tasks and dependencies;
- detect missing dependencies and cycles;
- calculate deterministic execution waves and duration-based critical path;
- identify tasks executable **now** from dependency and checkpoint state;
- detect active blockers and checkpoint-aware completion;
- model approvals and evidence as explicit checkpoints;
- enforce readiness/go-no-go policies and owner/evidence requirements.

### Trusted live state

- create immutable execution snapshots with deterministic snapshot IDs and plan fingerprints;
- validate parentage, timestamps and legal task-state transitions;
- protect against checkpoint regression and illegal state rollback;
- compare trusted snapshots without relying on manually maintained status summaries.

### Timing and risk

- calculate timezone-aware baseline and live forecast from ISO-8601 timestamps;
- propagate delay through dependencies and separate originating from inherited delay;
- forecast completion and schedule variance;
- score open task risk using explicit policy;
- expose owner/workstream risk concentration, critical-path exposure and missing-risk buckets.

### Contingency

- model rollback/contingency as explicit alternative execution branches;
- activate a branch only from explicit task-state or signal conditions;
- validate contingency dependencies/cycles separately from the forward plan;
- calculate branch-specific blockers, waves and `executable_now`.

### Evidence and control-room output

- produce consolidated JSON, Markdown and standalone HTML control-room reports;
- combine execution, transition validity, timing, readiness, contingency and risk in one read-only decision surface;
- preserve stable `eac://` artifact references;
- bind Reconciliation-as-Code run evidence through a verified registry;
- retain source-document SHA-256 and external result status before accepting evidence;
- expose machine-readable output suitable for CI, dashboards and agents;
- install one `cutover-graph` command while retaining deterministic module boundaries.

## Command surface

```text
cutover-graph validate
cutover-graph plan
cutover-graph control-room
cutover-graph control-room-verified
cutover-graph gate
cutover-graph timing
cutover-graph diff
cutover-graph contingency
cutover-graph snapshot
cutover-graph risk
cutover-graph artifacts
cutover-graph evidence
```

For module-level development and debugging the original scripts remain available. CI exercises both the installed command and those backwards-compatible paths.

## Checkpoint model

A checkpoint belongs to a task and can require approvals and evidence before the task is considered complete for dependency purposes.

```json
{
  "id": "reconcile-customers",
  "status": "done",
  "depends_on": ["load-customers"],
  "checkpoint": {
    "required_approvals": ["business", "data"],
    "approvals": [
      {"role": "business", "by": "business-owner"},
      {"role": "data", "by": "data-lead"}
    ],
    "required_evidence": ["reconciliation"],
    "evidence": [
      {
        "type": "reconciliation",
        "ref": "eac://dkharlanau/reconciliation-as-code/reconciliation/customer-final/run/RUN-001"
      }
    ]
  }
}
```

A raw `done` status does not release downstream work when a required checkpoint is incomplete or its external evidence cannot be verified.

## Contingency model

Rollback is an explicit alternative branch, not prose attached to a task:

```json
{
  "signals": {"abort_go_live": false},
  "tasks": [
    {"id": "load-customers", "status": "failed"}
  ],
  "contingencies": [
    {
      "id": "rollback-customer-load",
      "mode": "any",
      "activate_when": [
        {"task": "load-customers", "status_in": ["failed"]},
        {"signal": "abort_go_live", "equals": true}
      ],
      "tasks": [
        {"id": "close-inbound", "status": "done", "depends_on": []},
        {"id": "restore-snapshot", "status": "pending", "depends_on": ["close-inbound"]},
        {"id": "reconcile-restored-state", "status": "pending", "depends_on": ["restore-snapshot"]}
      ]
    }
  ]
}
```

A contingency is inactive until its activation rule passes. When active, its branch is evaluated as a separate deterministic DAG with its own executable tasks and blockers.

## Design boundaries

Cutover Graph owns cutover execution state: tasks, dependencies, timing, checkpoints, contingencies, trusted snapshots and readiness decisions.

It does **not** become the semantic owner of the evidence it consumes. Reconciliation controls stay in [Reconciliation as Code](https://github.com/dkharlanau/reconciliation-as-code); project-wide assurance relationships can be projected into [Project Evidence Graph](https://github.com/dkharlanau/project-evidence-graph). Stable references are preferred to copying the same business fact into several repositories.

## Next product steps

- publish a generated control-room reference case as the primary public product proof;
- emit Project Evidence Graph assurance fragments from trusted cutover snapshots and decisions;
- add a stable machine-readable consumer contract for current control-room state;
- add controlled command hooks only behind explicit approval envelopes;
- add ticketing/monitoring status adapters only when their authority and freshness are explicit;
- add signed/attested snapshot and evidence-pack manifests where audit requirements justify them.

## Design principles

- deterministic planning before automation
- explicit policy rather than hidden go/no-go logic
- rollback as an explicit alternative branch
- checkpoint-aware completion
- timezone-aware schedule math
- trusted, versionable state
- evidence-backed completion
- portable machine-readable output
- vendor-neutral core
- synthetic examples safe to publish

## Related projects

- [Reconciliation as Code](https://github.com/dkharlanau/reconciliation-as-code)
- [Project Evidence Graph](https://github.com/dkharlanau/project-evidence-graph)
- [Mapping as Code](https://github.com/dkharlanau/mapping-as-code)
- [Transformation Graph](https://github.com/dkharlanau/transformation-graph)
- [Interface as Code](https://github.com/dkharlanau/interface-as-code)
- [Process as Code](https://github.com/dkharlanau/process-as-code)
- [Enterprise Change Graph](https://github.com/dkharlanau/enterprise-change-graph)

Portfolio map: https://dkharlanau.github.io/products/

## Status

**Executable MVP / active development.** The installed CLI, control room, checkpoint-aware execution, trusted snapshots and transition validation, live timing, risk concentration, readiness policies, explicit contingencies, verified Reconciliation-as-Code evidence bindings, examples, tests and CI are implemented. The main remaining gap is stronger public proof and downstream assurance integration, not distribution or the deterministic execution core.
