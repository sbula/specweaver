# Walkthrough: INT-US-21 SF-01 CB-2 — Plan Hydration Bridge (FR-2)

- **Design**: `INT-US-21_design.md` (APPROVED 2026-07-25)
- **Plan**: `INT-US-21_sf01_implementation_plan.md` (APPROVED 2026-07-25)
- **Commit boundary**: 2 of 4 (CB-1 committed as `f1de38f1`)
- **Date**: 2026-07-25

---

## What changed and why

`RunContext.plan` promised "(set by runner hook)" but **nothing in `src/` ever wrote it**, while two
incompatible consumers read it: `OrchestrateComponentsHandler` expected a `DecompositionPlan` JSON
string, and the generation handlers expected an implementation `PlanArtifact` body. Two colliding
concepts on one never-written field (design AD-1).

| File | Change |
|---|---|
| `core/flow/engine/hydration.py` | **NEW** — `hydrate_plan_context()`, the single writer for both plan fields |
| `core/flow/handlers/base.py` | **+`RunContext.decomposition`**; `plan`'s comment corrected to name the implementation PlanArtifact |
| `core/flow/engine/runner.py` | Calls the hook at the join point; router block extracted out |
| `core/flow/engine/routers.py` | **+`resolve_route_target()`** — router resolution moved into the router module |
| `core/flow/handlers/decompose.py` | `OrchestrateComponentsHandler` migrated to `context.decomposition`; error message now names the field to fix |
| `core/flow/context.yaml` | Clarified a misleading comment (see A2 below) |
| `docs/architecture/.../domain_flow_engine.md` | New "Plan Context Hydration" section documenting the contract |
| `docs/architecture/.../known_boundary_violations.md` | **+1 row** — `specweaver/commons` unenforceable by tach |
| `docs/roadmap/topics/topic_07_technical_debt.md` | **+`TECH-009`** — fan-out `RunContext` isolation |
| tests | `test_runner_hydration.py` **NEW** (38); `test_decompose.py`, `test_orchestration_integration.py`, `test_planning_integration.py` migrated (16 call sites) |

---

## Test results

| Suite | Result |
|---|---|
| Unit | **4922 passed**, 15 skipped |
| Integration | **515 passed**, 3 skipped, 15 deselected |
| E2E | **166 passed**, 1 skipped |
| **Grand total** | **5603 passed, 19 skipped** |

CB-1 baseline was 5565 passed. Net **+38**.

## Quality gates

| Check | Result |
|---|---|
| `ruff check src/ tests/` | All checks passed |
| `mypy src/` | Success — no issues in 305 source files |
| `ruff check src/ --select C901` | All checks passed |
| `scripts/check_file_sizes.py` | **0 errors** (was 1 — see refactors below) |
| `tach check` | All modules validated |
| `scripts/check_roadmap_sync.py` | In sync |

---

## HITL gate decisions

| Gate | Findings presented | User decision |
|---|---|---|
| **Pre-commit Phase 1+2** | Architecture: A1–A5 (incl. two doc fixes). Coverage matrix + 4 proposed stories | User challenged the analysis: *"unusual flows? edge cases? graceful failure/tear down?"* — see below |
| **Phase 2 follow-up** | 4 new findings surfaced by that challenge (2 live bugs, 2 needing a decision) | **F3 → fix fully, as `TECH-009` (not the add-on). F4 → option (b), clear the field.** |
| **Phase 3** | 4 approved stories + the challenge findings implemented | *presented at this commit gate* |
| **Phase 7.5** | Red/Blue on the diff: 3 findings, all fixed | *presented at this commit gate* |

### The Phase-2 challenge — what it caught

My initial gap analysis was too shallow; the user's push found four things:

1. **Serialization asymmetry, live vs. resume (HIGH — FIXED).** `StateStore` persists step records
   with `json.dumps(..., default=str)` (`store.py:132-133`); the hook used strict `dumps`. Measured:
   a decompose output carrying a `Path` or `set` **raised on the live path** (field left unset) but
   **hydrated cleanly after a resume**, where the store had already stringified it. The same run
   behaved differently depending on whether it was interrupted — precisely the drift a single shared
   function was supposed to prevent. **Sharing the function is only half the guarantee; the
   serialization semantics have to match too.** Pinned by a test that hydrates live and via a store
   round-trip and asserts byte-equality.
2. **`UnicodeDecodeError` escaped the guard (HIGH — FIXED).** It subclasses `ValueError`, not
   `OSError`, so a corrupt/binary plan artifact propagated out of a function documented as
   never-raising — *after* the gate had already decided to advance.
3. **Fan-out shared-context race → `TECH-009`.** `decompose.py` hands the *same* `RunContext` to
   every concurrent sub-runner while the runner writes `run_id`/`step_records`/`pipeline_runner` to
   it every step (`runner.py:404-406`). **Lineage and telemetry are already mis-attributed today**
   in shipped `C-FLOW-03` fan-out; FR-2 widened the blast radius to the plan fields but did not
   create the defect. Filed as a TECH ticket rather than deferred to `C-FLOW-12` because it is a
   defect in delivered code, is live now, and the add-on (unbuilt, sequenced behind `C-EXEC-07`)
   should be able to *assume* context hygiene rather than own the fix.
4. **Stale hydration on a failed re-run (FIXED).** `decompose passes → hydrates → loop_back →
   decompose re-runs and fails` left the **superseded** plan in place for a downstream orchestrate
   step to consume silently. A non-`PASSED` result now clears the field that step owns.

### Phase 7.5 Red/Blue — 3 findings, all fixed

- **Over-broad clearing.** F4's fix initially cleared on *any* non-`PASSED` status, including
  `SKIPPED` and `WAITING_FOR_INPUT` — but those mean the step produced **no new verdict** (bypassed,
  or parked and due to re-run on resume), so there is nothing to supersede and wiping a still-valid
  plan is gratuitous. Restricted to `FAILED`/`ERROR`, with a test pinning that SKIPPED/parked do not clear.
- **Observability regression I introduced.** The router extraction dropped the step *name* from the
  routing log ("target index 3" instead of "target 'plan_spec' (index 3)"). Restored.
- **`pipeline: Any`** in the extracted `resolve_route_target` signature — typed as
  `PipelineDefinition`.

---

## Two refactors forced by the file-size gate

`runner.py` was already **598/600** lines before CB-2 — one line from the RED threshold, so any
addition tripped it. Rather than shave lines, two genuinely separable concerns moved out:

1. `hydrate_plan_context` → **`engine/hydration.py`** (also where CB-3's resume rehydration imports
   it from — the module now has a real reason to exist beyond size).
2. The router-target resolution block → **`engine/routers.py`** as `resolve_route_target()`, putting
   router logic in the router module and shrinking the loop.

`runner.py` is now 593 lines with 0 file-size errors repo-wide.

---

## What CB-2 deliberately does NOT do

- **Does not survive a park.** Hydration writes to the in-memory context, which dies with the
  process; under C-EXEC-06 session isolation it writes to a shallow copy discarded at teardown.
  Cross-session rehydration is **CB-3**, and it will reuse `hydrate_plan_context` so the live and
  resume paths cannot diverge.
- **No seam pins.** FR-9's decompose→orchestrate fan-out proof and hook-driven plan→generate proof
  are **SF-02**. The integration test here stops at "the next handler observes the field".
- No approve-on-resume (CB-4). US-21 remains 🟡; no roadmap checkbox moved.
