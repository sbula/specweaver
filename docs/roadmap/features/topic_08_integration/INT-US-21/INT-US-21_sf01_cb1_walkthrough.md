# INT-US-21 SF-01 CB-1 — Walkthrough: Registry Completeness (FR-1)

**Commit boundary:** 1 of 4 (`f1de38f1`) · **Date:** 2026-07-25 · Plan:
[sf01](INT-US-21_sf01_implementation_plan.md) (APPROVED 2026-07-25)

## Delivered

`feature_decomposition.yaml` now runs past steps 1–2. `draft+feature` and `validate+feature` were
valid in `VALID_STEP_COMBINATIONS` (`engine/models.py:115-117`) but unmapped in
`StepHandlerRegistry`, so the runner stopped at step 1 with `No handler registered for draft+feature`.

| File | Change |
|---|---|
| `core/flow/handlers/draft.py` | **+`DraftFeatureHandler`** wrapping `FeatureDrafter` with full `DraftSpecHandler` parity; `_pop_feedback` extracted to module-level `_pop_step_feedback` (delegate retained) |
| `core/flow/handlers/registry.py` | **+2 rows**: `(DRAFT, FEATURE)` → `DraftFeatureHandler`; `(VALIDATE, FEATURE)` → `ValidateSpecHandler` |
| `workflows/drafting/context.yaml` | `exposes:` gains `FeatureDrafter` |
| `docs/architecture/06_lessons_and_future/known_boundary_violations.md` | **+1 row** for the `forbids: specweaver/drafting` breach (AD-3) |
| `docs/architecture/02_bounded_contexts/domain_flow_engine.md` | Registry table corrected — 9 missing handlers added, stale module paths (`flow/_draft.py`) fixed |
| `docs/dev_guides/special_patterns_and_adaptations.md` | **+Pattern 24** — Round-Trip Name Derivation for Self-Naming Writers |
| `tests/unit/core/flow/handlers/test_draft_feature_handler.py` | **NEW** — 41 tests |
| `tests/unit/core/flow/handlers/test_handlers.py` | registry rows resolve |
| `tests/integration/core/flow/engine/test_feature_pipeline.py` | +2 tests; `PIPELINES_DIR` fixed |

- **Path round-trip.** `FeatureDrafter.draft()` takes `(name, output_dir)` and derives its own path
  `output_dir/f"{name}_feature_spec.md"`; every downstream step reads `context.spec_path`.
  `DraftFeatureHandler` derives `name` so the drafter's path IS `context.spec_path`, guards the
  filename shape before spending tokens, and asserts the round trip after the call.
- **`(VALIDATE, FEATURE)` is a registry line only** — `ValidateSpecHandler` already routes
  `kind=feature` to `validation_spec_feature` (`validation.py:155-156`) and the YAML passes the param.
- **No PASSED without a file.** `_execute_drafting` checks existence explicitly after the round-trip
  assertion
  (`test_correct_path_but_no_file_written_errors`): a drafter returning the right path without
  writing no longer passes.
- **`FEATURE_SPEC_SUFFIX`** is a public module constant so SF-03's `_resolve_spec_path` imports it
  (D6).
- **`PIPELINES_DIR`** used `Path(__file__).resolve().parents[4]` (= `tests/`), so both tests in
  `TestFeatureDecompositionPipelineIntegration` had skipped via `if not path.exists(): pytest.skip(...)`
  since written. Now `parents[5]`; integration skips 5 → 3.

## Proof

| Suite | Result |
|---|---|
| Unit | **4884 passed**, 15 skipped |
| Integration | **515 passed**, 3 skipped, 15 deselected |
| E2E | **166 passed**, 1 skipped |
| **Grand total** | **5565 passed, 19 skipped** (baseline 5548 / 21: +17 passed, −2 skipped) |

| Check | Result |
|---|---|
| `ruff check src/ tests/` | All checks passed |
| `mypy src/` | Success — no issues in 304 source files |
| `ruff check src/ --select C901` | All checks passed |
| `scripts/check_file_sizes.py` | 0 errors, 34 warnings (pre-existing; `draft.py` is 445/500) |
| `tach check` | All modules validated |
| `scripts/check_roadmap_sync.py` | Dependency boxes fully in sync |

Red/Blue (Phase 7.5), 2 cycles: 1 HIGH fixed (the missing-file PASSED above), 1 MEDIUM accepted,
1 LOW actioned (the public suffix constant).

## Findings still open

- **MEDIUM, accepted:** `gen_config` construction and `_build_base_prompt` sit outside the `try`, so a
  malformed `context.config` (e.g. `config.llm is None`) is caught by the runner, not the handler.
  Verbatim `DraftSpecHandler` structure; diverging would break FR-1's parity.
- `DraftSpecHandler` has the same missing-file hole; not changed (no FR covers it) — TECH ticket
  candidate.
- Vacuous proofs found so far: INT-US-02's E6/E7 assert only `exit_code == 0`;
  `test_pipeline_yaml_loads_and_parks_at_hitl` overwrites every handler with `_AlwaysPassHandler`;
  the two `PIPELINES_DIR` tests never ran. Read existing coverage before trusting it.
