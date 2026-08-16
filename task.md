# INT-US-16 — CB-1: the US-16 journey, falsified by mutant

> **CB-1 COMPLETE.** 5 integration + 2 e2e tests, all green. M-1 and M-2 both KILLED, and both are
> now durable campaigns in `INT-US-16_mutants.json` with drift hashes, so the nightly session keeps
> asking. `tests.py cb INT-US-16`: integration ok, e2e ok. Full suite 7176 passed. cb 12/1/0,
> doc 10/10.

**FR-1** (e2e) — a real `sw implement` run's LLM cost is visible in `sw usage`.
**FR-3** (integration) — the adapter the `implement` command builds reaches `RunContext.model.llm`
as a `TelemetryCollector`, so `PipelineRunner._flush_telemetry` drains it.

Plan: `docs/roadmap/features/topic_08_integration/INT-US-16/INT-US-16_implementation_plan.md`
(APPROVED 2026-08-16). FR-2 is **CB-2**, not this boundary.

## Why the red is a mutant here, not a failing test

Phase 0 found the machinery complete: the collector is installed, the runner flushes in a
`finally`, `get_usage_summary` reads it back. **Both tests are expected to pass on first run.**
So the boundary's exit condition is that each kills its named mutant — `TECH-017`'s lesson, where a
containment test passed immediately and proved nothing because the function it covered returned
`{}` for every caller.

| Mutant | File | Neutralise | Must kill |
|---|---|---|---|
| M-1 | `core/flow/engine/telemetry.py` | `llm.flush(db)` → `pass` | FR-1 e2e |
| M-2 | `infrastructure/llm/factory.py` | `if telemetry_project:` → `if False:` | FR-1 e2e **and** FR-3 integration |

A green that survives either means the test asserts on something other than the seam.

## Adversarial test matrix (mandated before writing)

| Bucket | Test | Tier |
|---|---|---|
| **Happy path** | active project → `sw implement` → `sw usage` shows the model, an exact token count, a non-zero USD figure | e2e |
| **Happy path** | active project → the command's own `RunContext.model.llm` is a `TelemetryCollector` | integration |
| **Boundary/edge** | **no** active project → it is **not** a `TelemetryCollector` (today's silent no-op, pinned before CB-2 changes anything around it) | integration |
| **Graceful degradation** | a run that ends **non-completed** still records what it spent — the flush is in a `finally` | integration |
| **Hostile input** | a project name carrying SQL metacharacters (`'; DROP TABLE llm_usage_log; --`) round-trips through write and read without executing | integration |

## Found while writing the matrix — NOT this boundary's to fix

`sw usage --since not-a-date` exits 1 with an **unhandled `ValueError`** — a raw traceback rather
than an error message. `infrastructure/llm/interfaces/cli.py:161` calls
`datetime.fromisoformat(since)` with no guard. Probed, confirmed.

It is the read half of this very journey, but it is **outside INT-US-16's three FRs**, and it is a
defect in delivered code — which by the ticket skill's rule becomes its own ticket, not a silent
absorption into an approved plan. Raised for a decision; not fixed here.

**Flush-failure degradation is deliberately NOT re-tested here** (plan Q9):
`TelemetryCollector.flush` documents *"Never raises"* and `tests/unit/infrastructure/llm/test_collector.py`
already covers it at unit tier. Re-proving it here would be duplication, not coverage.

## Tasks

- [x] **T1** — FR-3 + its three siblings.
  `tests/integration/workflows/implementation/test_implement_collector_wiring.py` [NEW].
  Classes: `TestImplementInstallsTelemetryCollector` (happy + no-project boundary),
  `TestImplementRecordsSpendOnFailedRun` (degradation),
  `TestTelemetryProjectNameIsParameterBound` (hostile).
  Spy on `PipelineRunner` to capture the context the command builds — never construct one by hand
  (plan Q5; Red/Blue rejected that phrasing as vacuous once already).
- [x] **T2** — FR-1 token journey e2e DELIVERED in CB-1 after all (see below). ~~originally — FR-1 journey~~ → **moved to CB-2** (boundaries redrawn 2026-08-16).
  FR-1 prices via `sw costs set`, and no command passes `cost_overrides` into
  `create_llm_adapter` — so the e2e goes **red for the right reason**, and belongs in the boundary
  that carries the fix. Kept here for reference only:
  `tests/e2e/interfaces/test_implement_telemetry_journey_e2e.py` [NEW].
  Class `TestImplementSpendIsVisibleInUsage`. `@pytest.mark.e2e`.
  `sw init --path tmp_path` → `sw use` → `sw costs set` → `sw implement` → `sw usage`.
  **DB isolation: the global `tests/e2e/conftest.py::_isolate_env` only.** Do NOT copy
  `test_cli_decentralized_e2e.py`'s `_patch_config_path`, which monkeypatches `_core.get_db` and
  would take DB resolution out of the journey. Probed, not assumed — see the plan's corrected note.
  The `sw costs set` key and the fake's response model must be the **same constant**, or
  `estimated_cost` stays `0.0` and AD-6's non-zero assertion fails for the wrong reason.
  Patch `factory._get_adapter_class` only. **Never `create_llm_adapter`** (AD-2 / plan R-2) and
  **never `scripted_world`**, which patches exactly that and would leave the adapter unwrapped.
  `FakeGeminiAdapter` duplicated locally with a comment naming
  `tests/e2e/capabilities/infrastructure/test_telemetry_e2e.py:52` as the original (plan Q6).
- [x] **T3** — Kill **M-2** (M-1 belongs to CB-2). `SURVIVED` is a T1 defect, not a note.
- [x] **T4** — Durable campaign: `INT-US-16_mutants.json`, one campaign per FR, so the nightly
  session keeps re-asking and reports `STALE` when the code these claims rest on moves.
- [x] **T5** — `python scripts/tests.py cb INT-US-16` (no `--kind`, no `--all` — the
  `INTEGRATION story` profile already runs `integration: all` + `e2e: domain`). **Confirm the e2e
  is actually selected**; `selected NO tests` is a failure, and `e2e: domain` makes file placement
  load-bearing. If it is missed, move the file — do not reach for `--all`, which hides it.
- [x] **T6** — Pre-commit gate, all 7 phases + 7.5 Red/Blue.
- [ ] **T7** — HITL commit stop.

## Assertion hygiene

`sw usage` prints several numeric columns, so a bare substring match can pass on the wrong one.
Give the fake a distinctive, non-round token count that cannot collide with a cost, a duration or a
call count, and assert through `tests/rendering.py::shows()` (NFR-4/NFR-5).
