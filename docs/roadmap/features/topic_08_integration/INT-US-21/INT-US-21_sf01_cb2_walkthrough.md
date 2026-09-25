# INT-US-21 SF-01 CB-2 — Walkthrough: Plan Hydration Bridge (FR-2)

**Commit boundary:** 2 of 4 (`c4c1a109`; CB-1 `f1de38f1`) · **Date:** 2026-07-25 · Plan:
[sf01](INT-US-21_sf01_implementation_plan.md) (APPROVED 2026-07-25)

## Delivered

One writer for both plan fields. `RunContext.plan` promised "(set by runner hook)" but nothing in
`src/` wrote it, while `OrchestrateComponentsHandler` expected a `DecompositionPlan` JSON string and
the generation handlers an implementation `PlanArtifact` body (design AD-1).

| File | Change |
|---|---|
| `core/flow/engine/hydration.py` | **NEW** — `hydrate_plan_context()`, the single writer for both plan fields |
| `core/flow/handlers/base.py` | **+`RunContext.decomposition`**; `plan`'s comment names the implementation PlanArtifact |
| `core/flow/engine/runner.py` | Calls the hook at the join point; router block extracted out |
| `core/flow/engine/routers.py` | **+`resolve_route_target()`** — router resolution in the router module |
| `core/flow/handlers/decompose.py` | `OrchestrateComponentsHandler` reads `context.decomposition`; error message names the field |
| `core/flow/context.yaml` | Clarified a misleading comment (A2) |
| `docs/architecture/.../domain_flow_engine.md` | New "Plan Context Hydration" section |
| `docs/architecture/.../known_boundary_violations.md` | **+1 row** — `specweaver/commons` unenforceable by tach |
| `docs/roadmap/topics/topic_07_technical_debt.md` | **+`TECH-014`** — fan-out `RunContext` isolation |
| tests | `test_runner_hydration.py` **NEW** (38); `test_decompose.py`, `test_orchestration_integration.py`, `test_planning_integration.py` migrated (16 call sites) |

Behaviour worth knowing:

- **Live and resume serialize the same way.** `StateStore` persists step records with
  `json.dumps(..., default=str)` (`store.py:132-133`); the hook does too. With strict `dumps`, a
  decompose output holding a `Path` or `set` raised live but hydrated after a resume. Pinned by a
  test that hydrates live and via a store round-trip and asserts byte-equality.
- **Never raises on a bad plan file.** `UnicodeDecodeError` (a `ValueError`, not `OSError`) from a
  corrupt/binary artifact is caught — it used to escape *after* the gate had decided to advance.
- **A failed re-run clears the stale plan.** `decompose passes → hydrates → loop_back → decompose
  fails` no longer leaves the superseded plan for orchestrate. Only `FAILED`/`ERROR` clear the field
  the combo owns; `SKIPPED` and `WAITING_FOR_INPUT` produce no new verdict and do not clear (pinned).
- Routing log keeps the step name ("target 'plan_spec' (index 3)"); `resolve_route_target` takes a
  `PipelineDefinition`, not `pipeline: Any`.
- `runner.py` was **598/600** lines; the two extractions bring it to 593, 0 file-size errors.

## Proof

| Suite | Result |
|---|---|
| Unit | **4922 passed**, 15 skipped |
| Integration | **515 passed**, 3 skipped, 15 deselected |
| E2E | **166 passed**, 1 skipped |
| **Grand total** | **5603 passed, 19 skipped** (CB-1: 5565; +38) |

| Check | Result |
|---|---|
| `ruff check src/ tests/` | All checks passed |
| `mypy src/` | Success — no issues in 305 source files |
| `ruff check src/ --select C901` | All checks passed |
| `scripts/check_file_sizes.py` | **0 errors** (was 1) |
| `tach check` | All modules validated |
| `scripts/check_roadmap_sync.py` | In sync |

Pre-commit: architecture A1–A5; the user's Phase-2 challenge (*"unusual flows? edge cases? graceful
failure/tear down?"*) found F1–F4 — F3 → fix fully as `TECH-014`, F4 → option (b), clear the field.
Phase 7.5 Red/Blue: 3 findings, all fixed (over-broad clearing, the routing-log name, the `Any`
type).

## Findings still open

- **Fan-out shared-context race → `TECH-014`.** `decompose.py` hands the same `RunContext` to every
  concurrent sub-runner while the runner writes `run_id`/`step_records`/`pipeline_runner` to it each
  step (`runner.py:404-406`) — lineage and telemetry are mis-attributed in shipped `C-FLOW-03`
  fan-out. FR-2 widened it to the plan fields. A TECH ticket, not the add-on: a defect in delivered
  code, live now; `C-FLOW-12` (unbuilt, behind `C-EXEC-07`) should assume context hygiene.
- Hydration writes the in-memory context and dies with the process (under C-EXEC-06 isolation, a
  shallow copy discarded at teardown) — survived by CB-3's rehydration.
