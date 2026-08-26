# Operational Risk Concentration

`cutover_risk.py` quantifies unresolved cutover exposure and shows where it is concentrated by owner and workstream.

The model is intentionally deterministic. It does not ask an LLM to decide whether a task “looks risky”.

## Score model

For each task:

```text
open risk = risk weight × execution-state factor × critical-path multiplier
```

Default risk weights:

| Risk | Weight |
|---|---:|
| R0 | 0.5 |
| R1 / low | 1 |
| R2 / medium | 2 |
| R3 | 4 |
| high | 5 |
| R4 | 8 |
| critical | 10 |

Default execution-state factors:

| State | Factor |
|---|---:|
| pending | 1.0 |
| running | 1.25 |
| failed | 2.0 |
| done but checkpoint blocked | 1.5 |
| checkpoint-complete done | 0 |
| cancelled / skipped | 0 |

An unresolved task on the theoretical critical path receives a default multiplier of `1.5`.

## Why checkpoint-blocked work remains exposed

A task with raw `status: done` is not treated as zero risk if its required checkpoint is incomplete. Its execution state becomes `checkpoint_blocked`, preserving exposure until approvals/evidence are actually satisfied.

## Run

```bash
python cutover_risk.py current-plan.json
```

Optional policy/config:

```json
{
  "risk_weights": {
    "high": 8,
    "critical": 15
  },
  "default_risk_weight": 2,
  "state_factors": {
    "running": 1.5,
    "failed": 2.5,
    "checkpoint_blocked": 2
  },
  "critical_path_multiplier": 2
}
```

```bash
python cutover_risk.py current-plan.json --policy risk-policy.json
```

## Output

The report contains:

- total open risk score;
- open task count;
- task-level score components;
- current critical path;
- unknown/missing task risk labels;
- aggregation by owner;
- aggregation by workstream;
- each group’s share of total open risk.

Missing owners/workstreams are explicit `unassigned_owner` / `unassigned_workstream` buckets rather than disappearing from the report.

## Interpretation

The score is a prioritization/control-room metric, not a universal business-risk truth. Its value comes from being explicit, versionable, and comparable between snapshots. Teams can adjust weights while retaining the same calculation semantics.
