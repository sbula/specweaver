# D-INTL-03 — Explicit Plan Phase: as built

**Design**: [D-INTL-03_design.md](D-INTL-03_design.md)

| File (`src/specweaver/`) | Holds | FRs |
|:---|:---|:---|
| `workflows/pipelines/new_feature.yaml` | `plan_spec` after `review_spec`, gate `on_fail: abort` | FR-1 |
| `core/flow/handlers/generation.py` | `PlanSpecHandler`: the plan, tagged and saved as `<spec>_plan.yaml` | FR-2, FR-3 |
| `core/flow/engine/hydration.py` | the plan read into `RunContext.plan_context` for later steps | FR-2 |
| `workflows/planning/planner.py` · `models.py` · `renderer.py` | `Planner` (JSON, retries), `PlanArtifact`, Markdown rendering | FR-2, FR-3 |
